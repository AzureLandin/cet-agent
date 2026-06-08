# CET Web Agent 后端接口文档

> 框架：Flask 3.0 | 数据库：MySQL | 认证：Cookie Session | 流式：SSE

---

## 1. 接口总览

| # | 方法 | 路径 | 需要认证 | 模块文件 | 说明 |
|---|------|------|---------|---------|------|
| 1 | `GET` | `/health` | 否 | `app.py:70` | 健康检查 |
| 2 | `POST` | `/auth/register` | 否 | `auth.py:55` | 注册 |
| 3 | `POST` | `/auth/login` | 否 | `auth.py:92` | 登录 |
| 4 | `POST` | `/auth/logout` | 否 | `auth.py:119` | 登出 |
| 5 | `GET` | `/profile` | 是 | `profile.py:9` | 获取用户档案 |
| 6 | `PUT` | `/profile` | 是 | `profile.py:25` | 更新用户档案 |
| 7 | `POST` | `/sessions` | 是 | `sessions.py:10` | 创建学习会话 |
| 8 | `GET` | `/sessions` | 是 | `sessions.py:28` | 会话列表（按模块分组） |
| 9 | `GET` | `/sessions/{id}` | 是 | `sessions.py:53` | 会话详情 + 历史消息 |
| 10 | `POST` | `/sessions/{id}/messages` | 是 | `messages.py:54` | 发送消息（SSE 流式） |

---

## 2. 基础约定

### 2.1 服务器地址

```
http://localhost:5000
```

### 2.2 认证机制

基于 **Cookie + Session** 认证，无需手动携带 Token。

- 注册/登录成功后，后端通过 `Set-Cookie` 写入 `session_id`（HttpOnly, SameSite=Lax, Max-Age=7天）
- 浏览器会自动在后续请求中携带该 Cookie
- 前端无需在 Header 中写 Authorization（fetch 需设置 `credentials: "include"`）

**前端 fetch 示例：**

```javascript
fetch("http://localhost:5000/profile", {
  credentials: "include",  // 关键：允许跨域携带 Cookie
});
```

**超时/无效 Session：** 任何需要认证的接口返回 `401`：

```json
{
  "error_code": "UNAUTHORIZED",
  "message": "Authentication required."
}
```

### 2.3 统一错误格式

所有错误响应格式一致：

```json
{
  "error_code": "ERROR_CODE_SNAKE_CASE",
  "message": "Human readable message."
}
```

HTTP 状态码用于表示类别：`400` 参数错误、`401` 未认证、`404` 不存在、`409` 冲突。

### 2.4 Content-Type

- 请求：`application/json`
- 响应（非流式）：`application/json`
- 响应（流式，仅第10号接口）：`text/event-stream`

---

## 3. 接口详细设计

### 3.1 健康检查

```
GET /health
```

| 项目 | 内容 |
|------|------|
| **认证** | 否 |
| **请求参数** | 无 |
| **成功响应 (200)** | `{ "status": "ok", "db": true }` |
| **说明** | 可用于前端启动时检查后端是否就绪。`db` 为 `false` 表示数据库连接异常。 |

---

### 3.2 注册

```
POST /auth/register
```

| 项目 | 内容 |
|------|------|
| **认证** | 否 |
| **请求体** | `{ "username": "string", "password": "string" }` |
| **成功响应 (201)** | `{ "user_id": 1, "username": "alice" }` + `Set-Cookie` |
| **错误响应** | 见下表 |

**校验规则：**

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `INVALID_USERNAME` | 400 | 用户名长度 < 3 或 > 50 |
| `INVALID_PASSWORD` | 400 | 密码长度 < 6 |
| `USERNAME_TAKEN` | 409 | 用户名已存在 |

**示例请求：**

```json
{
  "username": "alice",
  "password": "pass1234"
}
```

**成功后** Cookie `session_id` 已写入，可立即调用其他接口。

---

### 3.3 登录

```
POST /auth/login
```

| 项目 | 内容 |
|------|------|
| **认证** | 否 |
| **请求体** | `{ "username": "string", "password": "string" }` |
| **成功响应 (200)** | `{ "user_id": 1, "username": "alice" }` + `Set-Cookie` |
| **错误响应** | |

**校验规则：**

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `MISSING_CREDENTIALS` | 400 | 用户名或密码为空 |
| `INVALID_CREDENTIALS` | 401 | 用户名或密码错误 |

---

### 3.4 登出

```
POST /auth/logout
```

| 项目 | 内容 |
|------|------|
| **认证** | 否（读取 Cookie） |
| **请求体** | 无 |
| **成功响应 (200)** | `{ "message": "Logged out." }` + 清除 `session_id` Cookie |
| **说明** | 即使没有有效 Session 也返回 200。前端需同步清除本地 Session 状态。 |

---

### 3.5 获取用户档案

```
GET /profile
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **请求参数** | 无 |
| **成功响应 (200)** | `{ "exam_level": "CET4", "exam_date": "2026-06-20" }` |

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `exam_level` | `"CET4"` \| `"CET6"` \| `null` | 考试级别；未设置时为 `null` |
| `exam_date` | `"YYYY-MM-DD"` \| `null` | 考试日期；未设置时为 `null` |

**错误响应：**

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `PROFILE_NOT_FOUND` | 404 | 数据库异常，极少发生 |
| `UNAUTHORIZED` | 401 | 未登录 |

---

### 3.6 更新用户档案

```
PUT /profile
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **请求体** | `{ "exam_level": "CET6", "exam_date": "2026-06-20" }` |
| **成功响应 (200)** | `{ "message": "Profile updated." }` |

**参数说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `exam_level` | 否 | `"CET4"` 或 `"CET6"`。传 `null` 可清空。 |
| `exam_date` | 否 | ISO 日期 `"YYYY-MM-DD"`。传 `""` 或 `null` 可清空。 |

**校验规则：**

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `INVALID_EXAM_LEVEL` | 400 | 不是 `"CET4"` 或 `"CET6"` |
| `INVALID_DATE` | 400 | 日期格式不符 |

**注意：** `PUT` 是部分更新。可以只传其中一个字段。

---

### 3.7 创建会话

```
POST /sessions
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **请求体** | `{ "module": "writing" }` |
| **成功响应 (201)** | `{ "id": 42, "module": "writing", "title": "Writing — 2026-05-14 12:34" }` |

**`module` 取值：**

`"writing"` | `"reading"` | `"translation"`

**`title` 格式：** 由后端自动生成，格式为 `"{Module} — {YYYY-MM-DD HH:MM}"`。

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `INVALID_MODULE` | 400 | module 不合法 |

**说明：** 创建会话后，前端路由到对应训练页面，然后调用「发送消息」接口开始对话。

---

### 3.8 会话列表

```
GET /sessions
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **请求参数** | 无 |
| **成功响应 (200)** | 见下方示例 |

**响应结构：**

```json
{
  "writing": [
    { "id": 42, "title": "Writing — 2026-05-14 12:34", "created_at": "2026-05-14T04:34:00" }
  ],
  "reading": [
    { "id": 43, "title": "Reading — 2026-05-14 13:00", "created_at": "2026-05-14T05:00:00" }
  ],
  "translation": []
}
```

**说明：**
- 按模块分组返回，每个模块内按 `updated_at` 降序排列
- `created_at` 为 ISO 8601 时间戳
- 未创建会话的模块返回空数组

---

### 3.9 会话详情

```
GET /sessions/{session_id}
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **路径参数** | `session_id` (int) |
| **成功响应 (200)** | 见下方示例 |

**响应结构：**

```json
{
  "id": 42,
  "module": "writing",
  "title": "Writing — 2026-05-14 12:34",
  "created_at": "2026-05-14T04:34:00",
  "messages": [
    {
      "id": 1,
      "role": "system",
      "content": "You are a CET writing coach...",
      "created_at": "2026-05-14T04:34:01"
    },
    {
      "id": 2,
      "role": "user",
      "content": "帮我批改这篇作文...",
      "created_at": "2026-05-14T04:34:30"
    },
    {
      "id": 3,
      "role": "assistant",
      "content": "我来分析你的作文...",
      "created_at": "2026-05-14T04:35:00"
    }
  ]
}
```

**`role` 取值：** `"system"` | `"user"` | `"assistant"`

**`messages` 排序：** 按 `created_at` 升序（时间从早到晚）

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `NOT_FOUND` | 404 | 会话不存在或不属于当前用户 |
| `UNAUTHORIZED` | 401 | 未登录 |

**用法：** 前端进入某个历史会话时调用此接口，渲染对话历史。

---

### 3.10 发送消息（SSE 流式）

```
POST /sessions/{session_id}/messages
```

| 项目 | 内容 |
|------|------|
| **认证** | 是 |
| **路径参数** | `session_id` (int) |
| **请求体** | `{ "content": "string" }` |
| **请求头** | `Content-Type: application/json` |
| **响应类型** | `text/event-stream`（Server-Sent Events） |
| **成功响应 (200)** | SSE 事件流 |

**请求校验：**

| 错误码 | HTTP | 条件 |
|--------|------|------|
| `EMPTY_MESSAGE` | 400 | content 为空 |
| `MESSAGE_TOO_LONG` | 400 | content 长度超过 4000 字符 |
| `NOT_FOUND` | 404 | 会话不存在或不属于当前用户 |

**SSE 事件格式：**

每个事件一行 data，格式为：

```
data: {"event":"token","data":"这是"}
data: {"event":"token","data":"AI"}
data: {"event":"token","data":"返回"}
data: {"event":"token","data":"的"}
data: {"event":"token","data":"文本"}
...
data: {"event":"done","data":""}
```

**事件类型：**

| event | data | 说明 |
|-------|------|------|
| `token` | 文本片段 | AI 逐字输出的文本 token，前端需累积拼接显示 |
| `done` | `""` | 流结束。此时 AI 的回话已完整存入数据库 |
| `error` | 错误消息 | 流中断，错误描述在 data 中 |

**前端接收代码示例：**

```javascript
async function sendMessage(sessionId, content) {
  const response = await fetch(
    `http://localhost:5000/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ content }),
    }
  );

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const payload = JSON.parse(line.slice(6));
        if (payload.event === "token") {
          // 逐字追加到 UI
          appendText(payload.data);
        } else if (payload.event === "done") {
          // 流结束
          onStreamEnd();
        } else if (payload.event === "error") {
          console.error(payload.data);
        }
      }
    }
  }
}
```

**注意事项：**
1. SSE 是**单向流**，浏览器通过 `EventSource` 或 `fetch + ReadableStream` 接收
2. `EventSource` 原生不支持 `POST` + `credentials`，推荐用 `fetch` + `ReadableStream` 方式
3. 收到 `done` 事件后，如需刷新历史消息列表，可调用「会话详情」接口

---

## 4. 前端对接要点

### 4.1 CORS

后端允许的跨域来源（配置于 `config.yaml`）：

```yaml
cors:
  allowed_origins:
    - http://localhost:8080
    - http://127.0.0.1:8080
```

前端开发时需确保请求 Origin 在白名单内。生产环境需修改 `config.yaml` 添加实际域名。

### 4.2 Cookie 认证流程

```
注册/登录 → 后端 Set-Cookie: session_id
          → 浏览器自动携带
          → 后续请求 fetch({ credentials: "include" })
          → 登出 → 后端清除 Cookie
```

**前端需处理的状态：**
- 收到 401 → 跳转到登录页
- 登录/注册成功后 → 跳转到主页（此时 Cookie 已就绪）

### 4.3 典型页面流程

| 页面 | 调用接口 | 说明 |
|------|---------|------|
| 登录页 | `POST /auth/login` | |
| 注册页 | `POST /auth/register` | |
| 首页/模块选择 | `GET /sessions` → `GET /profile` | 并行加载历史会话和用户档案 |
| 写作/阅读/翻译训练 | `POST /sessions` → 创建 → `POST /sessions/{id}/messages` | SSE 流式对话 |
| 历史记录 | `GET /sessions/{id}` | 加载完整对话历史 |
| 设置页 | `GET /profile` → `PUT /profile` | 读取并更新考试信息 |

### 4.4 Session 生命周期

- Session (auth_sessions 表) 有效期 **7 天**
- 到期后自动失效，后端返回 401
- Session Cookie 设置为 `HttpOnly` + `SameSite=Lax`
  - `HttpOnly`：JS 无法读取（防 XSS）
  - `SameSite=Lax`：跨站 GET 导航可携带，POST/PUT 需同站

### 4.5 消息长度限制

- 单条消息最大 **4000 字符**
- 历史消息窗口 **最近 50 条**（用于构建 AI context）

---

## 5. 数据库表结构（参考）

| 表名 | 用途 |
|------|------|
| `users` | 用户账号：id, username, password_hash, created_at |
| `profiles` | 用户档案：user_id, exam_level, exam_date, updated_at |
| `auth_sessions` | 认证会话：user_id, session_id, expires_at, created_at |
| `sessions` | 学习会话：user_id, module, title, created_at, updated_at |
| `messages` | 对话消息：session_id, role, content, created_at |
