# CET Agent

CET Agent 是一个面向大学英语四、六级（CET-4 / CET-6）备考的 Web 学习助手。应用提供写作批改、阅读精读、翻译训练三大模块，支持内置真题题库、MinerU 云端 PDF 真题解析、左题右聊分栏工作台，以及具备 Tool Calling 能力的 AI 教练。

## 功能概览

- 用户注册、登录、登出，基于 Cookie 的 7 天服务端认证会话（支持 `student` 与 `admin` 角色：首位注册用户或 `CET_ADMIN_USERNAMES` 名单内用户自动授予 `admin`）。
- 用户档案管理：考试级别（CET4/CET6）、考试日期、昵称、头像底色、头像图片上传与删除。
- **真题题库（Question Bank）**：按考试级别、模块（写作/阅读/翻译）、子题型、年份、主题筛选，内置 4 道精选真题样例，支持客观题自动判分与练习记录保存。
- **左题右聊分栏工作台**：支持选题绑定到会话、草稿自动保存、SSE 流式对话与 `tool_call` / `question_loaded` 实时联动。
- **Agent Tool Calling**：模型可通过 `search_questions`、`start_question_practice`、`get_answer_key`、`record_practice_result` 主动抽题、核对答案并记录练习成绩。
- **Admin Studio 与 MinerU 云端解析**：管理员可上传 PDF 或 Markdown 真题试卷，调用 MinerU Cloud API v4 提取 Markdown，并通过 LLM 智能拆分为结构化题目草稿，审校后一键发布入库。
- 零外部数据库依赖：采用 Python 内置 `sqlite3`（WAL 模式），开箱即用。

## 技术栈

| 层级 | 技术 | 说明 |
|---|---|---|
| 后端 | Flask 3.0 + Waitress | REST API、Cookie Session、SSE 流式响应与 Tool Calling |
| 数据库 | SQLite 3 (`sqlite3`) | 用户、档案、真题题库、练习记录、学习会话与消息记录 |
| 文档解析 | MinerU Cloud API v4 (`httpx`) | PDF 上传、任务轮询、Markdown 下载与 LLM 拆题 |
| 模型接口 | OpenAI Python SDK | 支持 OpenAI 兼容的 `base_url`、`api_key`、`model` 配置 |
| 前端 | React 18 + TypeScript + Vite | Material Design 3 界面、左题右聊工作台与 Admin Studio |
| 部署 | Docker Compose + nginx + Waitress | 后端 + 前端双容器部署，数据卷持久化 |

## 快速开始

### 1. 准备环境变量

在项目根目录复制环境变量示例：

```bash
cp .env.docker.example .env
```

编辑 `.env`，至少配置模型接口与会话密钥：

```env
CET_DB_PATH=/app/data/cet_agent.db
CET_ADMIN_USERNAMES=
CET_MINERU_API_KEY=
CET_MINERU_BASE_URL=https://mineru.net/api/v4

CET_MODEL_BASE_URL=https://api.openai.com/v1
CET_MODEL_API_KEY=your_api_key_here
CET_MODEL_NAME=gpt-4o-mini

CET_SESSION_SECRET_KEY=change_this_session_secret
CET_COOKIE_SECURE=false
CET_AUTH_SESSION_CLEANUP_PROBABILITY=0.01
CET_CORS_ALLOWED_ORIGINS=http://localhost:8080
```

### 2. 启动服务

```bash
docker compose up -d --build
```

启动后访问：

```text
http://localhost:8080
```

Docker Compose 会启动两个服务：

- `backend`：Flask 应用，使用 Waitress 监听 `5000`，通过命名卷挂载 `/app/data`（SQLite 数据库）与 `/app/uploads`（头像与试卷文件）。
- `frontend`：nginx 静态站点，监听宿主机 `8080`，并反向代理后端 API。

### 3. 查看健康状态

```bash
curl http://localhost:8080/health
```

期望返回：

```json
{"status":"ok","db":true}
```

## 本地开发

### 后端本地运行

SQLite 无需安装额外数据库服务，复制 `backend/.env.example` 为 `backend/.env` 后即可直接启动：

```bash
cp backend/.env.example backend/.env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/app.py
```

默认后端地址：`http://localhost:5000`。

### 前端本地运行

```bash
cd frontend
npm install
npm run dev
```

## 测试

后端单元测试位于 `backend/tests/`：

```bash
python3 -m unittest discover -s backend/tests
```

## 项目结构

```text
cet-agent/
├── backend/
│   ├── app.py                      # Flask 应用入口、SQLite 初始化、蓝图注册
│   ├── auth.py                     # 注册、登录、登出、角色判定与 Cookie Session
│   ├── config.py                   # 环境变量配置读取
│   ├── db.py                       # SQLite 连接管理（支持文件与 :memory:）
│   ├── messages.py                 # 消息存储、Agent Tool Calling、SSE 流式输出
│   ├── profile.py                  # 用户档案、昵称、头像颜色、头像上传/删除
│   ├── questions.py                # 题库查询/交卷与管理员试卷/题目管理 API
│   ├── seed_questions.py           # 内置 4 道四六级精选真题样例
│   ├── sessions.py                 # 学习会话与左侧做题面板工作区绑定
│   ├── schema.sql                  # SQLite 表结构
│   ├── services/
│   │   ├── mineru_client.py        # MinerU Cloud API v4 客户端与 LLM 拆题器
│   │   └── model_client.py         # OpenAI 兼容模型客户端（含流式 Tool Calling）
│   ├── prompts/                    # 写作、阅读、翻译模块提示词
│   └── tests/                      # 单元与回归测试
├── frontend/                       # React 18 + TypeScript + Vite + M3 前端应用
├── docker-compose.yml              # backend + frontend 容器编排
├── .env.docker.example             # Docker Compose 环境变量示例
└── backend/.env.example            # 后端本地运行环境变量示例
```

## API 概览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/health` | 否 | 健康检查 |
| `POST` | `/auth/register` | 否 | 注册（返回 `user_id`, `username`, `role`） |
| `POST` | `/auth/login` | 否 | 登录（返回 `user_id`, `username`, `role`） |
| `POST` | `/auth/logout` | 否 | 登出并清除 Cookie |
| `GET` | `/profile` | 是 | 获取用户档案（含 `role`） |
| `PUT` | `/profile` | 是 | 更新考试信息、昵称、头像底色 |
| `POST` | `/profile/avatar` | 是 | 上传头像 |
| `DELETE` | `/profile/avatar` | 是 | 删除头像 |
| `GET` | `/questions` | 是 | 按条件筛选真题列表 |
| `GET` | `/questions/{id}` | 是 | 获取题目详情 |
| `POST` | `/questions/{id}/submit` | 是 | 提交答案并自动判分/记录练习 |
| `POST` | `/sessions` | 是 | 创建会话（可选 `question_id` 绑定真题） |
| `GET` | `/sessions` | 是 | 获取按模块分组的会话列表 |
| `GET` | `/sessions/{id}` | 是 | 获取会话详情、绑定题目与历史消息 |
| `PUT` | `/sessions/{id}/workspace` | 是 | 更新会话绑定题目与草稿答案 |
| `DELETE` | `/sessions/{id}` | 是 | 删除会话 |
| `POST` | `/sessions/{id}/messages` | 是 | 发送消息并流式返回 SSE（`token`/`tool_call`/`question_loaded`/`done`/`error`） |
| `POST` | `/admin/papers/upload` | 管理员 | 上传 PDF 或 Markdown 真题试卷 |
| `GET` | `/admin/papers` | 管理员 | 查看试卷列表 |
| `GET` | `/admin/papers/{id}` | 管理员 | 查看试卷详情与拆出的题目 |
| `POST` | `/admin/papers/{id}/parse` | 管理员 | 轮询 MinerU 结果并调用 LLM 智能拆题 |
| `POST` | `/admin/papers/{id}/publish` | 管理员 | 一键发布试卷及关联题目 |
| `POST/PUT/DELETE` | `/admin/questions` | 管理员 | 单题增删改 |
