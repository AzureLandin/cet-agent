# CET Agent

CET Agent 是一个面向大学英语四、六级备考的 Web 学习助手。项目提供写作批改、阅读精读、翻译训练三个学习模块，前端通过聊天式界面与后端交互，后端调用 OpenAI 兼容模型接口并以 SSE 流式返回回答。

当前代码形态适合个人项目、课程项目或小规模内部部署继续迭代：后端职责拆分清楚，前端无需构建工具即可部署，Docker Compose 已提供 MySQL、后端、前端 nginx 三容器运行方式。

## 技术栈

| 层级 | 技术 | 说明 |
|---|---|---|
| 后端 | Flask 3.0 | REST API、Cookie Session、SSE 流式响应 |
| 数据库 | MySQL 8.0 | 用户、档案、认证会话、学习会话、消息记录 |
| 数据库访问 | PyMySQL + DBUtils | 参数化 SQL 与连接池 |
| 模型接口 | OpenAI Python SDK | 支持 OpenAI 兼容的 `base_url`、`api_key`、`model` 配置 |
| 前端 | 原生 HTML/CSS/JavaScript | 无构建流程，hash 路由，fetch 请求 |
| Markdown | marked | 渲染模型返回内容 |
| 部署 | Docker Compose + nginx + Waitress | 前端 nginx 同源反代后端 API |

## 目录结构

```text
cet-agent/
├── backend/
│   ├── app.py                    # Flask 应用入口、鉴权中间件、蓝图注册
│   ├── auth.py                   # 注册、登录、登出、Cookie Session
│   ├── config.py                 # 从环境变量读取运行配置
│   ├── db.py                     # MySQL 连接池与基础查询封装
│   ├── messages.py               # 消息存储、模型调用、SSE 流式输出
│   ├── profile.py                # 用户档案、昵称、头像颜色、头像上传/删除
│   ├── sessions.py               # 学习会话创建、列表、详情、删除
│   ├── schema.sql                # MySQL 表结构
│   ├── services/model_client.py  # OpenAI 兼容模型客户端
│   ├── prompts/                  # 写作、阅读、翻译模块提示词
│   └── tests/                    # 回归测试
├── frontend/
│   ├── index.html                # 静态 SPA 入口
│   ├── css/styles.css            # 页面样式
│   ├── js/api.js                 # API 请求封装与 SSE 接收
│   ├── js/app.js                 # 全局状态与初始化
│   ├── js/components.js          # 侧边栏、消息气泡、模块卡片等组件
│   ├── js/router.js              # hash 路由
│   ├── js/utils.js               # DOM、Loading、Toast、Confirm 等工具
│   └── nginx.conf                # 静态资源服务与 API 反向代理
├── docker-compose.yml            # MySQL、backend、frontend 三容器部署
├── .env.docker.example           # Docker Compose 环境变量示例
└── backend/.env.example          # 后端本地运行环境变量示例
```

## 核心功能

- 用户注册、登录、登出。
- 基于 Cookie 的 7 天认证会话。
- 用户档案管理：考试级别、考试日期、昵称、头像底色、头像图片。
- 写作批改、阅读精读、翻译训练三个模块。
- 学习会话列表、历史消息查看、会话删除。
- 模型回答通过 `fetch` + `ReadableStream` 方式流式展示。
- Docker Compose 一键启动数据库、后端和前端。

## 运行方式

### Docker Compose 部署

复制环境变量示例：

```powershell
Copy-Item .env.docker.example .env
```

编辑 `.env`，至少填写以下配置：

```env
MYSQL_ROOT_PASSWORD=change_this_root_password
CET_DB_USER=cet_agent
CET_DB_PASSWORD=change_this_db_password
CET_DB_NAME=cet_web_agent

CET_MODEL_BASE_URL=https://api.openai.com/v1
CET_MODEL_API_KEY=your_api_key_here
CET_MODEL_NAME=gpt-4o-mini

CET_SESSION_SECRET_KEY=change_this_session_secret
CET_COOKIE_SECURE=false
CET_CORS_ALLOWED_ORIGINS=http://localhost:8080
```

启动：

```powershell
docker compose up -d --build
```

访问：

```text
http://localhost:8080
```

该部署方式下，前端由 nginx 提供静态资源，并把 `/auth`、`/profile`、`/sessions`、`/health`、`/uploads` 反向代理到后端容器。

### 后端本地运行

复制后端环境变量示例：

```powershell
Copy-Item backend\.env.example backend\.env
```

安装依赖并启动后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

默认后端地址：

```text
http://localhost:5000
```

本地运行后端时需要自行准备 MySQL，并确保 `backend/.env` 中的数据库配置、模型配置和会话密钥完整可用。

## API 概览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/health` | 否 | 健康检查 |
| `POST` | `/auth/register` | 否 | 注册并写入 Cookie Session |
| `POST` | `/auth/login` | 否 | 登录并写入 Cookie Session |
| `POST` | `/auth/logout` | 否 | 登出并清除 Cookie |
| `GET` | `/profile` | 是 | 获取用户档案 |
| `PUT` | `/profile` | 是 | 更新考试信息、昵称、头像底色 |
| `POST` | `/profile/avatar` | 是 | 上传头像 |
| `DELETE` | `/profile/avatar` | 是 | 删除头像 |
| `POST` | `/sessions` | 是 | 创建学习会话 |
| `GET` | `/sessions` | 是 | 获取按模块分组的会话列表 |
| `GET` | `/sessions/{id}` | 是 | 获取会话详情和历史消息 |
| `DELETE` | `/sessions/{id}` | 是 | 删除会话 |
| `POST` | `/sessions/{id}/messages` | 是 | 发送消息并以 SSE 流式返回模型回答 |

更细的请求与响应格式见 `backend/API.md`。需要注意的是，当前 `backend/API.md` 与代码存在部分漂移，见下方“已知问题”。

## 当前架构分析

### 后端

`backend/app.py` 是应用装配入口。启动时会读取环境变量配置，初始化数据库连接池，执行数据库健康检查，并在缺表时根据 `schema.sql` 自动创建表。鉴权逻辑集中在 `before_request`，除 `/auth`、`/health`、`/uploads` 和 CORS 预检外，其余接口都需要有效的 `session_id` Cookie。

认证由 `backend/auth.py` 负责。密码使用 bcrypt 哈希，登录态使用随机 opaque session id，服务端保存在 `auth_sessions` 表中，默认 7 天过期。

消息链路由 `backend/messages.py` 负责。用户消息先写入数据库，再构建模型上下文，随后调用 OpenAI 兼容接口，边接收 token 边通过 SSE 返回给前端。模型回复完整结束后，再把助手消息写入数据库。

### 前端

前端是无构建工具的静态 SPA。`frontend/index.html` 直接加载多个 JavaScript 文件，`frontend/js/router.js` 使用 hash 路由，`frontend/js/app.js` 维护全局状态，`frontend/js/views.js` 渲染登录、首页、设置、聊天等页面。

API 请求集中在 `frontend/js/api.js`。其中 `API_BASE = ""` 表示前端默认按同源路径请求 API，因此生产或 Docker 部署依赖 nginx 反向代理，而不是直接跨域请求后端。

聊天流式输出使用 `fetch` + `ReadableStream`，这比原生 `EventSource` 更适合当前接口，因为接口需要 `POST` 请求体和 Cookie 凭据。

### 部署

`docker-compose.yml` 定义三个服务：

- `mysql`：MySQL 8.0，持久化数据卷 `mysql_data`。
- `backend`：Python 3.11 slim 镜像，Waitress 监听 `0.0.0.0:5000`。
- `frontend`：nginx alpine 镜像，监听宿主机 `8080`，提供静态资源并反代后端。

`frontend/nginx.conf` 对 `/sessions` 设置了 `proxy_buffering off`，这是 SSE 流式输出能及时到达前端的关键配置。

## 已知问题

### 1. API 文档与代码存在漂移

`backend/API.md` 中仍有 `config.yaml` 的旧描述，但实际运行配置已经改为 `.env` 和环境变量。代码中也已经实现了头像上传、头像删除、昵称、头像底色、删除会话等能力，但 API 文档没有完整覆盖。

建议：同步更新 `backend/API.md`，并把 README 作为面向使用者的入口文档，`backend/API.md` 作为详细接口契约文档。

### 2. 消息历史窗口可能取错方向

`backend/messages.py` 中构建模型上下文时使用：

```sql
ORDER BY created_at ASC
LIMIT 50
```

这会取最早的 50 条消息，而不是最近的 50 条。长会话中，模型可能看不到最新上下文。

建议：先按 `created_at DESC LIMIT 50` 取最近消息，再在 Python 中反转为正序传给模型，并增加回归测试。

### 3. Markdown 渲染需要安全审查

前端通过 `marked.parse()` 渲染模型回复，并写入 `innerHTML`。如果模型输出包含原始 HTML，存在 XSS 风险。

建议：引入 DOMPurify 或配置 marked 禁用/过滤 HTML，再补充包含 `<script>`、事件属性、危险链接的前端安全测试或手工验证用例。

### 4. 本地测试环境缺少一键说明

当前有 `backend/tests/test_regressions.py`，但仓库缺少明确的测试环境搭建说明。分析时使用全局 Python 直接运行：

```powershell
python -m unittest discover -s "D:\Projects\cet-agent\backend\tests"
```

会因为未安装依赖而在导入阶段失败：

```text
ModuleNotFoundError: No module named 'pymysql'
```

建议：在 README 或脚本中固定测试流程，例如先创建 `.venv` 并安装 `backend/requirements.txt`，再运行 unittest。

### 5. `cookies.txt` 不建议长期纳入仓库

当前 `cookies.txt` 只是 curl 生成的空 Cookie 文件，没有敏感内容。但 Cookie 文件容易在后续调试中写入会话数据。

建议：删除该文件或加入 `.gitignore`。

## 修改方向建议

### 第一阶段：文档和可运行性

- 完善 `README.md` 的本地运行、Docker 运行、测试命令和架构说明。
- 更新 `backend/API.md`，移除 `config.yaml` 旧描述，补齐头像、昵称、删除会话接口。
- 增加 `.env` 字段说明，标明哪些变量必填、哪些变量有默认值。
- 增加一条推荐测试命令和 Windows PowerShell 示例。

### 第二阶段：修复明确行为问题

- 修复最近 50 条消息上下文窗口。
- 将 `app.py` 中过时的错误提示从 `config.yaml` 改为环境变量或 `.env`。
- 清理 `cookies.txt`。
- 为删除会话、头像接口、消息窗口增加回归测试。

### 第三阶段：安全和稳定性

- 给 Markdown 渲染加 HTML 清洗。
- 增加上传头像的 MIME 校验，而不只检查扩展名。
- 增加登录失败限流或简单防暴力破解策略。
- 定期清理过期 `auth_sessions`。
- 为模型调用增加超时、重试和更友好的错误映射。

### 第四阶段：工程化增强

- 增加统一的开发脚本，例如 `scripts/dev-backend.ps1`、`scripts/test-backend.ps1`。
- 引入格式化和静态检查，例如 Ruff。
- 给前端拆分更明确的状态管理与渲染边界。
- 为核心 API 增加集成测试或基于 Flask test client 的端到端接口测试。
- 根据部署环境补充 HTTPS、`CET_COOKIE_SECURE=true`、反向代理真实域名配置说明。

## 测试

后端测试入口：

```powershell
python -m unittest discover -s backend\tests
```

如果使用干净环境，先执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m unittest discover -s backend\tests
```

## 当前分析结论

项目主体已经具备可运行的学习助手雏形：认证、用户档案、会话管理、SSE 流式聊天和 Docker 部署链路都已建立。后续最值得优先投入的是文档同步、测试环境固定、消息上下文窗口修复和 Markdown 安全处理。这些改动范围不大，但能显著提升项目的可维护性、可部署性和安全边界。
