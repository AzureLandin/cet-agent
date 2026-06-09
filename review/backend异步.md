异步代码审查报告

  🔴 严重问题

1. [backend/messages.py:92-110] SSE 流中数据库操作未做事务保护 / 回滚缺失
   
   问题： generate() 生成器在 SSE 流式响应中执行 db.execute() 插入助手消息和更新 updated_at。每个 db.execute()
   调用独立获取连接并自动提交（cursor() 上下文管理器逐条 commit）。如果第一条 INSERT 成功但第二条 UPDATE sessions
   失败，数据不一致；若流中途断开（客户端断连），生成器被 GC 终止时不会执行 INSERT，导致用户看到回复但历史中丢失。
   
   影响： 消息丢失或数据不一致；流中断时无法恢复。
   
   修复方案： 将两条写操作合并到同一个 cursor() 上下文中，或引入 DB.run_in_transaction() 方法执行批量操作：
   
   def generate():
    assistant_chunks = []
    try:
   
        for chunk in client.chat_completion_stream(messages):
            assistant_chunks.append(chunk)
            payload = json.dumps({"event": "token", "data": chunk})
            yield f"data: {payload}\n\n"
       
        full_response = "".join(assistant_chunks)
        with db.cursor() as cur:          # 单事务
            cur.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, "assistant", full_response),
            )
            cur.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
        payload = json.dumps({"event": "done", "data": ""})
        yield f"data: {payload}\n\n"
   
    except Exception as e:
   
        payload = json.dumps({"event": "error", "data": str(e)})
        yield f"data: {payload}\n\n"

  ---

2. [backend/auth.py:56-89] 注册操作多表写入缺少事务 — 用户创建与 profile/session 插入非原子
   
   问题： register() 依次执行 INSERT users → INSERT profiles → INSERT auth_sessions，每次 db.execute()
   独立获取连接并自动提交。若 INSERT profiles 失败，用户行已提交无法回滚，产生无 profile 的僵尸用户。
   
   影响： 部分写入导致数据不一致（用户存在但无 profile）。
   
   修复方案： 用单一 cursor() 上下文包裹全部写操作：
   
   with db.cursor() as cur:
    cur.execute("INSERT INTO users ...", (...))
    user_id = cur.lastrowid
    cur.execute("INSERT INTO profiles (user_id) VALUES (%s)", (user_id,))
    cur.execute("INSERT INTO auth_sessions ...", (...))
    session_id = ...

  ---

3. [backend/profile.py:96-129] 头像上传：文件写入与数据库更新非原子
   
   问题： upload_avatar() 先 file.save(filepath) 写磁盘，再 db.execute() 更新 DB。若 DB
   更新失败，磁盘上留下孤立文件；若磁盘写入失败但已删除旧头像，旧头像丢失且 DB 未更新。
   
   影响： 文件泄漏或头像丢失。
   
   修复方案： 先写 DB 成功后再提交文件，或用事务 + 补偿逻辑：
   
   # 先写 DB
   
   db.execute("UPDATE profiles SET avatar_url = %s WHERE user_id = %s", (url, user_id))
   
   # DB 成功后再写文件（若文件写入失败，回滚 DB）
   
   try:
    file.save(filepath)
   except Exception:
    db.execute("UPDATE profiles SET avatar_url = %s WHERE user_id = %s", (old_url, user_id))
    raise

  ---

  🟠 中等问题

4. [frontend/js/views.js:341-342] 流式消息全局变量导致竞态条件
   
   问题： streamingMessageId 和 streamingContent 是模块级全局变量。若用户快速连续发送两条消息（虽然 state.isStreaming
   守卫，但 isStreaming 在 onDone/onError 回调中才设为 false，存在微任务间隙），第二次发送可能覆盖第一次的
   streamingMessageId，导致第一条流的 token 写入第二条消息气泡。
   
   影响： 快速操作时消息内容错乱。
   
   修复方案： 用闭包或请求 ID 绑定状态，而非全局变量：
   
   async function sendChatMessage(sessionId, content) {
    const myStreamId = Date.now() + 1;  // 闭包内唯一
    // ... 所有回调用 myStreamId 代替 streamingMessageId
   }

  ---

5. [frontend/js/views.js:180] setTimeout 竞态 — 首页发送消息依赖导航后 DOM 就绪
   
   问题： setTimeout(() => sendChatMessage(session.id, content), 200) 用固定延时等待页面导航完成。若导航渲染超过
   200ms（慢设备），sendChatMessage 找不到 DOM 元素；若太快则 DOM 尚未准备好。
   
   影响： 消息发送失败或 UI 异常。
   
   修复方案： 改用回调/事件机制确认视图已就绪后再发送：
   
   state._pendingMessage = content;  // 在 showChatView 中检查并发送

  ---

6. [frontend/js/views.js:65-69, 96-100] 登录/注册后 getSessions() 是火后不管的 Promise
   
   问题： getSessions().then(...).catch(...) 没有 await，登录流程立即 navigateTo("home")。若 getSessions()
   先于页面渲染返回，renderSidebar() 操作的 DOM 可能尚未就绪；若失败，侧边栏为空但用户无感知。
   
   影响： 侧边栏偶尔为空，用户困惑。
   
   修复方案： await getSessions() 或在 navigateTo 之后用路由回调刷新：
   
   const sessions = await getSessions();
   state.sessions = sessions;
   renderSidebar();

  ---

7. [backend/db.py:28-39] 每个 execute()/fetchone()/fetchall() 独立获取连接并自动提交
   
   问题： DB.cursor() 上下文管理器每次调用获取新连接 → 执行 → 提交 → 关闭。同一请求中多个 db.execute()
   调用实际在不同连接/事务中执行。这意味着：
- 读后写不是原子的（auth.py:67-78 先查再插，可被并发插入超越）

- 逻辑上应是一体的多步操作无法整体回滚
  
  影响： 并发请求下 TOCTOU（Time-of-check to time-of-use）竞态，如重复注册、重复创建会话。
  
  修复方案： 在请求级别复用连接（Flask g.db_conn），before_request 获取连接，teardown_appcontext 关闭：
  
  @app.before_request
  def before_request():
    g.db_conn = db._connect()
  
  @app.teardown_appcontext
  def teardown_db(exception):
    conn = g.pop('db_conn', None)
    if conn:
  
        if exception:
            conn.rollback()
        else:
            conn.commit()
        conn.close()

  ---

8. [backend/services/model_client.py:17-19] OpenAI 流式响应未处理 choices[0] 为空或 finish_reason
   
   问题： chunk.choices[0].delta.content 未检查 choices 是否为空列表。OpenAI SDK 在流开始/结束时会发送 choices=[] 或
   delta.content=None 的 chunk，直接访问 [0] 会 IndexError。
   
   影响： LLM 流式响应中途崩溃，用户看到错误。
   
   修复方案：
   
   for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
   
        yield chunk.choices[0].delta.content

  ---

  🟡 轻微问题

9. [frontend/js/api.js:148-182] sendMessage 中 reader.read() 无超时
   
   问题： while (true) 循环中 await reader.read() 无超时保护。若服务端挂起不关闭连接，前端永远等待，isStreaming 永远为
   true，用户无法再发消息。
   
   影响： 极端情况下 UI 卡死。
   
   修复方案： 用 AbortController 设置超时：
   
   const controller = new AbortController();
   const timeoutId = setTimeout(() => controller.abort(), 120_000); // 2 min
   const response = await fetch(url, { ..., signal: controller.signal });

  ---

10. [frontend/js/api.js:123-183] sendMessage 同时调用 onError 回调并 throw err
    
    问题： HTTP 错误时先 if (onError) onError(err) 再 throw err。调用方 sendChatMessage 的 catch
    块也会处理同一错误，导致错误显示两次（一次在 onError 回调写入气泡，一次在 catch 写入气泡）。
    
    影响： 错误信息重复显示。
    
    修复方案： 二选一：回调模式不 throw，或 throw 模式不调回调：
    
    if (onError) {
    onError(err);
    return; // 不再 throw，由回调处理
    }
    throw err;

  ---

11. [frontend/js/app.js:23-42] initApp 中 getProfile() 和 getSessions() 串行执行
    
    问题： await getProfile() 完成后才 await getSessions()。两者无依赖关系，可以并行。
    
    影响： 初始化多等待一个网络往返时间。
    
    修复方案：
    
    const [profile, sessions] = await Promise.all([
    getProfile(),
    getSessions().catch(e => { console.error("加载会话列表失败:", e); return null; })
    ]);

  ---

12. [backend/messages.py:76-80] 用户消息插入与 updated_at 更新分属不同事务
    
    问题： db.execute(INSERT messages) 和 db.execute(UPDATE sessions) 各自独立提交。若第二个失败，消息已入库但 session 的
    updated_at 未更新，列表排序错误。
    
    影响： 会话排序不正确。
    
    修复方案： 同问题 #1，合并到单一事务。

  ---

  📋 汇总

  ┌─────┬───────────────────────┬────────┬────────────┬───────────────────────────────────────────────┐
  │  #  │       文件:行号       │ 严重度 │    类别    │                     问题                      │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 1   │ messages.py:92-110    │ 🔴     │ 事务回滚   │ SSE 流中 DB 写入非原子，流中断丢消息          │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 2   │ auth.py:56-89         │ 🔴     │ 事务回滚   │ 注册多表插入非原子，产生僵尸用户              │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 3   │ profile.py:96-129     │ 🔴     │ 事务回滚   │ 文件写入与 DB 更新非原子，文件泄漏            │
  问题： db.execute(INSERT messages) 和 db.execute(UPDATE sessions) 各自独立提交。若第二个失败，消息已入库但 session 的 updated_at 未更新，列表排序错误。

  影响： 会话排序不正确。

  修复方案： 同问题 #1，合并到单一事务。

  ---

  📋 汇总

  ┌─────┬───────────────────────┬────────┬────────────┬───────────────────────────────────────────────┐
  │  #  │       文件:行号       │ 严重度 │    类别    │                     问题                      │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 1   │ messages.py:92-110    │ 🔴     │ 事务回滚   │ SSE 流中 DB 写入非原子，流中断丢消息          │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 2   │ auth.py:56-89         │ 🔴     │ 事务回滚   │ 注册多表插入非原子，产生僵尸用户              │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 3   │ profile.py:96-129     │ 🔴     │ 事务回滚   │ 文件写入与 DB 更新非原子，文件泄漏            │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 4   │ views.js:341-342      │ 🟠     │ 竞态条件   │ 全局流式状态变量可被并发覆盖                  │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 5   │ views.js:180          │ 🟠     │ 竞态条件   │ setTimeout 硬编码延时依赖 DOM 就绪            │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 6   │ views.js:65-69        │ 🟠     │ 未 await   │ 火后不管的 getSessions 导致侧边栏空           │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 7   │ db.py:28-39           │ 🟠     │ 事务/竞态  │ 每次操作独立连接，无请求级事务                │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 8   │ model_client.py:17-19 │ 🟠     │ 未处理异常 │ choices 数组未做空检查                        │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 9   │ api.js:148-182        │ 🟡     │ 无超时     │ SSE 流读取无超时，可永久挂起                  │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 10  │ api.js:133-145        │ 🟡     │ 双重处理   │ onError 回调 + throw 导致错误显示两次         │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 11  │ app.js:23-42          │ 🟡     │ 串行 await │ getProfile/getSessions 可 Promise.all 并行    │
  ├─────┼───────────────────────┼────────┼────────────┼───────────────────────────────────────────────┤
  │ 12  │ messages.py:76-80     │ 🟡     │ 事务       │ INSERT message 与 UPDATE session 分属不同事务 │
  └─────┴───────────────────────┴────────┴────────────┴───────────────────────────────────────────────┘

  核心问题： 后端 DB 类的设计（每次操作独立连接+自动提交）是 #1/#2/#3/#7/#12 的根因。建议优先引入请求级事务（before_request 获取连接，teardown 提交/回滚），可一次性解决 5 个问题。
