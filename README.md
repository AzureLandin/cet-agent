# CET Agent

CET Agent 是一个面向大学英语四、六级备考的 Web 学习助手。它提供写作批改、阅读精读、翻译训练三个模块，前端以聊天界面承载学习过程，后端调用 OpenAI 兼容模型接口，并通过 SSE 将模型回复流式返回给浏览器。

这个 README 面向准备运行、调试或继续协作开发本项目的人，优先说明如何启动、如何测试、代码如何组织，以及当前最值得推进的改进方向。

## 功能概览

- 用户注册、登录、登出。
- 基于 Cookie 的 7 天服务端认证会话。
- 用户档案管理：考试级别、考试日期、昵称、头像底色、头像图片。
- 写作批改、阅读精读、翻译训练三个学习模块。
- 学习会话列表、历史消息查看、会话删除。
- 模型回复通过 `fetch` + `ReadableStream` 流式展示。
- Docker Compose 提供 MySQL、Flask 后端、nginx 前端三容器部署。

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

## 快速开始

推荐优先使用 Docker Compose，这条路径最接近项目当前部署模型。

### 1. 准备环境变量

在项目根目录复制环境变量示例：

```powershell
Copy-Item .env.docker.example .env
```

编辑 `.env`，至少填写这些值：

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

### 2. 启动服务

```powershell
docker compose up -d --build
```

启动后访问：

```text
http://localhost:8080
```

Docker Compose 会启动三个服务：

- `mysql`：MySQL 8.0 数据库。
- `backend`：Flask 应用，使用 Waitress 监听 `5000`。
- `frontend`：nginx 静态站点，监听宿主机 `8080`，并反向代理后端 API。

### 3. 查看健康状态

```powershell
curl http://localhost:8080/health
```

期望返回类似：

```json
{"status":"ok","db":true}
```

## 本地开发

### 后端本地运行

本地运行后端时，需要自行准备 MySQL，并确保 `backend/.env` 中数据库配置、模型配置和会话密钥完整可用。

```powershell
Copy-Item backend\.env.example backend\.env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

默认后端地址：

```text
http://localhost:5000
```

### 前端本地运行

前端没有构建步骤，核心文件位于 `frontend/`。在 Docker Compose 路径下，nginx 会托管静态资源并反代后端。

如果绕过 nginx 直接打开静态文件，需要额外处理 API 地址、Cookie 和跨域问题。因此协作开发时建议优先通过 `docker compose up -d --build` 查看完整应用。

## 测试

后端测试位于 `backend/tests/`。推荐在虚拟环境中安装依赖后运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m unittest discover -s backend\tests
```

如果直接使用未安装依赖的全局 Python，测试会在导入阶段失败，例如：

```text
ModuleNotFoundError: No module named 'pymysql'
```

这表示测试环境未准备好，不代表项目测试本身已经执行失败。

## 项目结构

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

## 架构说明

### 后端

`backend/app.py` 是应用装配入口。启动时会读取环境变量配置，初始化数据库连接池，执行数据库健康检查，并在缺表时根据 `schema.sql` 自动创建表。

鉴权逻辑集中在 `before_request`：除 `/auth`、`/health`、`/uploads` 和 CORS 预检外，其余接口都要求浏览器携带有效的 `session_id` Cookie。

`backend/auth.py` 负责注册、登录和登出。密码使用 bcrypt 哈希，登录态使用随机 session id，服务端保存在 `auth_sessions` 表中，默认 7 天过期。

`backend/messages.py` 负责聊天主链路：先保存用户消息，再构建模型上下文，调用 OpenAI 兼容接口，边接收 token 边通过 SSE 返回前端，最后保存完整助手回复。

### 前端

前端是无构建工具的静态 SPA。`frontend/index.html` 直接加载多个 JavaScript 文件，`frontend/js/router.js` 使用 hash 路由，`frontend/js/app.js` 维护全局状态，`frontend/js/views.js` 渲染登录、首页、设置、聊天等页面。

`frontend/js/api.js` 中的 `API_BASE = ""` 表示前端默认按同源路径请求 API。因此 Docker 部署依赖 nginx 反向代理，而不是让浏览器直接跨域访问 `localhost:5000`。

### 部署

`frontend/nginx.conf` 将 `/auth`、`/profile`、`/sessions`、`/health`、`/uploads` 代理到后端容器。其中 `/sessions` 关闭了代理缓冲，这是 SSE 流式输出能及时到达浏览器的关键配置。

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

详细请求和响应格式见 `backend/API.md`。当前该文档与代码存在部分漂移，建议在后续文档整理中同步更新。

## 协作建议

### 提交前检查

建议每次修改后至少执行：

```powershell
python -m unittest discover -s backend\tests
```

如果改动涉及 Docker、nginx、环境变量或静态资源，建议额外执行：

```powershell
docker compose up -d --build
curl http://localhost:8080/health
```

### 不建议提交的内容

- `.env`、`backend/.env` 等真实环境变量文件。
- 虚拟环境目录，例如 `.venv/`。
- 本地调试生成的 Cookie 文件或会话文件。
- 本地分析笔记、临时计划和 IDE 缓存。

## 当前已知问题

### API 文档与代码存在漂移

`backend/API.md` 中仍有 `config.yaml` 的旧描述，但实际运行配置已经改为 `.env` 和环境变量。代码中也已经实现头像上传、头像删除、昵称、头像底色、删除会话等能力，但 API 文档没有完整覆盖。

### 消息历史窗口可能取错方向

`backend/messages.py` 构建模型上下文时目前使用：

```sql
ORDER BY created_at ASC
LIMIT 50
```

这会取最早的 50 条消息，而不是最近的 50 条。长会话中，模型可能看不到最新上下文。

### Markdown 渲染需要安全审查

前端通过 `marked.parse()` 渲染模型回复，并写入 `innerHTML`。如果模型输出包含原始 HTML，存在 XSS 风险。建议引入 DOMPurify 或配置 marked 禁用/过滤 HTML。

### 测试环境需要固定

项目已有回归测试，但缺少更明确的一键测试脚本。建议增加 `scripts/test-backend.ps1` 或类似入口，避免协作者直接使用未安装依赖的全局 Python 运行测试。

### `cookies.txt` 不适合长期跟踪

当前 `cookies.txt` 只是 curl 生成的空 Cookie 文件，没有敏感值。但这类文件容易在调试时写入会话数据，建议删除或加入 `.gitignore`。

## 期望改进方向

### 第一阶段：文档和可运行性

- 同步更新 `backend/API.md`，移除 `config.yaml` 旧描述。
- 补齐头像、昵称、删除会话等实际接口文档。
- 增加 `.env` 字段说明，标明必填项、默认值和生产环境注意事项。
- 增加一键测试脚本和 Windows PowerShell 示例。

### 第二阶段：明确行为修复

- 修复最近 50 条消息上下文窗口。
- 将 `app.py` 中过时的错误提示从 `config.yaml` 改为环境变量或 `.env`。
- 清理 `cookies.txt`。
- 为删除会话、头像接口、消息窗口增加回归测试。

### 第三阶段：安全与稳定性

- 给 Markdown 渲染加 HTML 清洗。
- 上传头像时补充 MIME 检查，不只依赖扩展名。
- 增加登录失败限流或简单防暴力破解策略。
- 定期清理过期 `auth_sessions`。
- 为模型调用增加超时、重试和更友好的错误映射。

### 第四阶段：工程化增强

- 引入格式化和静态检查，例如 Ruff。
- 给前端拆分更明确的状态管理与渲染边界。
- 为核心 API 增加集成测试或 Flask test client 端到端接口测试。
- 根据生产部署补充 HTTPS、`CET_COOKIE_SECURE=true`、反向代理真实域名配置说明。

## 维护备注

这个项目已经具备完整雏形：认证、用户档案、会话管理、SSE 流式聊天和 Docker 部署链路都已建立。后续优先把文档、测试、消息上下文和 Markdown 安全这几处补稳，就能明显提升项目对外协作和继续迭代的体验。
