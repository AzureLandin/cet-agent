# CET Web Agent (CET Writing/Reading/Translation) Design

Date: 2026-05-13

## Summary
Build a basic web agent that wraps three CET skills (writing, reading, translation) into a chat UI, with a pre-auth homepage shown first. The system is a frontend static site (Bootstrap 5, plain HTML/JS) and a Flask API server with MySQL persistence, session auth, and streaming model responses via an OpenAI-compatible API.

## Goals
- Provide a single-page chat UI with module buttons (writing/reading/translation).
- Show a homepage first for unauthenticated users with clear login/register entry buttons.
- Support user registration/login and a simple profile (exam level + exam date).
- Persist users, profiles, sessions, and messages in MySQL.
- Stream assistant responses to the UI.
- Render assistant replies with Markdown.

## Non-goals
- No CET entry/mapping module (no initial 3-question routing).
- No file uploads or OCR.
- No public deployment hardening (rate limiting, admin panel).
- No complex analytics or exports in V1.

## Architecture

Frontend (static)
- Plain HTML/JS + Bootstrap 5 + Markdown renderer (CDN).
- Runs in its own static server process.

Backend (API)
- Flask API server.
- Auth via server-side session id stored in MySQL and cookie.
- Message streaming via HTTP chunked response (text/event-stream).
- Model calls via OpenAI-compatible API.

Data
- MySQL for persistent storage.
- Config file provides DB and model connection.

## User Flow
1. User opens the frontend and first sees a homepage with Login and Register buttons.
2. User clicks Login or Register and completes authentication.
3. User may edit profile (exam level and exam date).
4. User clicks a module button (writing/reading/translation) to create a session.
5. User chats in that session; responses stream in.
6. Sidebar lists past sessions grouped by module; clicking loads history.

## Frontend Design

### Homepage (Pre-auth)
Inspired by AI-native landing pages (e.g., Gemini), the homepage is a dark-themed, centered layout designed to feel like a chat product first, with auth as a lightweight overlay.

**Visual Structure**
- **Background**: dark theme (`#0d0d0d` to `#1a1a2e` gradient), full viewport height.
- **Header bar (top)**: left = app brand name "CET Agent"; right = "登录" and "注册" text buttons (low-key, ghost style).
- **Left edge**: minimal icon-only sidebar (hamburger menu icon, new-chat icon). Collapsed by default; expands on auth.
- **Center stage (vertically centered)**:
  - **Greeting line**: large serif/sans-serif hybrid heading, e.g., "准备好迎接四六级了吗？"
  - **Hero input bar**: a large, pill-shaped or heavily rounded textarea/input (`border-radius: 1.5rem+`, dark surface `#2a2a35`, subtle border). Placeholder: "输入作文题目、阅读材料或翻译句子..."
    - Bottom-left inside bar: "+" attachment icon, "工具" icon (for future features).
    - Bottom-right inside bar: "思考" dropdown, microphone icon (future).
  - **Module pills row**: centered, horizontal scroll if needed. Five rounded chip buttons below the input bar:
    - 📝 写作批改
    - 📖 阅读训练
    - 🔄 翻译练习
    - ✍️ 随便写点什么
    - 📚 帮我制定计划
  - Each pill has a subtle hover lift and border glow.

**Interaction**
- Clicking the hero input bar or any module pill while unauthenticated opens the **Login/Register Modal** (Option A).
- The modal is centered, dark-themed, with tabs for Login / Register, keeping the background visible but dimmed (`backdrop-filter: blur(4px)`).
- After successful auth, the modal closes and the homepage smoothly transitions into the authenticated app layout (input bar becomes active, sidebar expands, pills create sessions).

### Authenticated App Layout
- **Header**: app name, module buttons, profile button, logout.
- **Left sidebar**: session list grouped by module with timestamps.
- **Main panel**: chat history and input box with send button.

### Behavior
- On load, validate auth status; if not authenticated, show homepage first.
- Homepage hero input and module pills open the auth modal when clicked by unauthenticated users.
- After successful login/register, modal closes and the homepage transitions into the authenticated layout.
- New session created when a module button is pressed (either from pills or sidebar).
- One session is bound to one module (no module switching inside a session).
- On load, if already authenticated, skip homepage, fetch session list, and auto-select the most recent.
- Messages render in Markdown; code blocks are supported.
- Streaming: assistant bubble is created and appended as tokens arrive.
- Module pills in authenticated state act as "new session" shortcuts for each module.

### Frontend Dependencies
- Bootstrap 5 (CDN).
- Markdown parser (for example, marked.js via CDN).
- No build step; static files only.

## Backend Design

### API Endpoints
- POST /auth/register
- POST /auth/login
- POST /auth/logout
- GET /profile
- PUT /profile
- POST /sessions
- GET /sessions
- GET /sessions/{id}
- POST /sessions/{id}/messages (streaming)

### Session Auth
- On login, create an auth session record in DB (session_id, user_id, expires_at).
- Set cookie: HttpOnly, SameSite=Lax, Secure in production.
- Each request validates session_id -> user_id.

### Streaming
- /sessions/{id}/messages accepts a user message.
- Server responds with text/event-stream and sends incremental chunks.
- Event types: token, done, error.
- On error, send event: error with a short message, then close.

### Prompting
- Use static prompt templates derived from the three CET skills:
  - writing -> cet-writing system prompt
  - reading -> cet-reading system prompt
  - translation -> cet-translation system prompt
- For each request, construct messages:
  - system: module prompt
  - optional profile info in system or first user message
  - prior session messages
  - new user message

### Validation
- Require auth for all non-auth endpoints.
- Module must be one of: writing, reading, translation.
- Enforce max message length and max history size to protect cost.
- Ensure session ownership on read/write.

## Data Model

### users
- id (pk)
- username (unique)
- password_hash
- created_at

### profiles
- user_id (pk, fk users.id)
- exam_level (CET4/CET6)
- exam_date (nullable)
- updated_at

### sessions
- id (pk)
- user_id (fk users.id)
- module (writing/reading/translation)
- title
- created_at
- updated_at

### messages
- id (pk)
- session_id (fk sessions.id)
- role (user/assistant/system)
- content
- created_at

### auth_sessions
- id (pk)
- user_id (fk users.id)
- session_id (unique)
- expires_at
- created_at

## Configuration

Use a config file (yaml) for backend settings:
- db.host
- db.user
- db.password
- db.name
- model.base_url
- model.api_key
- model.model
- session.secret_key
- cors.allowed_origins

Frontend config:
- API_BASE_URL in a small config.js file next to index.html.

## Error Handling

Non-stream endpoints:
- JSON: {"error_code": "...", "message": "..."}
- HTTP status codes (400, 401, 403, 404, 500)

Streaming endpoint:
- On error, send event: error with a short text payload, then close.
- Frontend shows the error as a system message in the chat.

## Security
- Passwords stored using bcrypt.
- Validate all user inputs.
- CORS only allows the frontend origin with credentials.
- No secrets logged.

## Testing Plan (minimal)
- Auth: register, login, logout, invalid password.
- Profile: get, update, validation.
- Sessions: create, list, fetch, ownership enforcement.
- Streaming: validate token stream and final done event.

## Open Questions
- None for V1. Any additional feature requests should be scoped to V2.
