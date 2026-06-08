# CET Web Agent Implementation Plan

**Goal:** Build a basic web agent that wraps CET writing/reading/translation into a single-page chat UI with Flask API, MySQL persistence, and streaming responses.

**Architecture:** Frontend static site (Bootstrap 5, plain HTML/JS) served by a static server; backend Flask API with session auth, SSE streaming, and MySQL storage. OpenAI-compatible API for model calls.

**Tech Stack:** Python 3.10+, Flask, flask-cors, bcrypt, PyMySQL (or mysql-connector), PyYAML, openai (compatible client), Bootstrap 5 (CDN), marked.js (Markdown rendering).

---

## File Structure

| File | Responsibility |
| --- | --- |
| `cet-web-agent/backend/app.py` | Flask app entry, route registration, SSE streaming |
| `cet-web-agent/backend/config.yaml.example` | Config template (DB, model, CORS, session) |
| `cet-web-agent/backend/config.py` | Config loader (YAML -> dict) |
| `cet-web-agent/backend/db.py` | DB connection helpers |
| `cet-web-agent/backend/schema.sql` | MySQL schema for users, profiles, sessions, messages, auth_sessions |
| `cet-web-agent/backend/auth.py` | Register/login/logout, session cookie management |
| `cet-web-agent/backend/profile.py` | Profile GET/PUT endpoints |
| `cet-web-agent/backend/sessions.py` | Session list/create/detail endpoints |
| `cet-web-agent/backend/messages.py` | Message create + SSE stream endpoint |
| `cet-web-agent/backend/prompts/cet-writing.txt` | System prompt for writing module |
| `cet-web-agent/backend/prompts/cet-reading.txt` | System prompt for reading module |
| `cet-web-agent/backend/prompts/cet-translation.txt` | System prompt for translation module |
| `cet-web-agent/backend/services/model_client.py` | OpenAI-compatible client wrapper |
| `cet-web-agent/backend/requirements.txt` | Backend dependencies |
| `cet-web-agent/frontend/index.html` | Single-page UI with login + chat views |
| `cet-web-agent/frontend/app.js` | UI logic, API calls, SSE handling |
| `cet-web-agent/frontend/config.js` | API base URL config |
| `cet-web-agent/frontend/styles.css` | Custom styles |
| `cet-web-agent/README.md` | Run instructions for backend + frontend |

---

## Task 1: Project Skeleton and Config

- [ ] **Step 1: Create directories**
  - `cet-web-agent/backend`
  - `cet-web-agent/backend/prompts`
  - `cet-web-agent/backend/services`
  - `cet-web-agent/frontend`

- [ ] **Step 2: Add backend requirements**
  - Create `cet-web-agent/backend/requirements.txt` with Flask, flask-cors, bcrypt, PyYAML, PyMySQL (or mysql-connector), openai.

- [ ] **Step 3: Add config template + loader**
  - Create `cet-web-agent/backend/config.yaml.example` with db/model/session/cors fields.
  - Implement `cet-web-agent/backend/config.py` to load YAML and validate required keys.

---

## Task 2: Database Schema and Connection Helpers

- [ ] **Step 1: Create schema.sql**
  - Tables: users, profiles, sessions, messages, auth_sessions.
  - Include indexes on user_id, session_id, module, created_at.

- [ ] **Step 2: DB helper layer**
  - Implement `db.py` with connection pooling and simple query helpers.
  - Add a health check query for startup validation.

---

## Task 3: Auth and Session Management

- [ ] **Step 1: Register/login/logout endpoints**
  - `/auth/register`: validate username/password, bcrypt hash, insert user.
  - `/auth/login`: verify, create session row, set cookie.
  - `/auth/logout`: delete session row, clear cookie.

- [ ] **Step 2: Auth middleware**
  - Resolve session cookie -> user_id for protected routes.
  - Return 401 for unauthenticated requests.

---

## Task 4: Profile Endpoints

- [ ] **Step 1: GET /profile**
  - Return exam_level and exam_date (nullable).

- [ ] **Step 2: PUT /profile**
  - Validate exam_level (CET4/CET6).
  - Store exam_date as nullable date.

---

## Task 5: Session and Message Storage

- [ ] **Step 1: POST /sessions**
  - Create session for module (writing/reading/translation).
  - Generate a short title (module + timestamp).

- [ ] **Step 2: GET /sessions and /sessions/{id}**
  - List sessions grouped by module.
  - Return message history for selected session.

- [ ] **Step 3: POST /sessions/{id}/messages**
  - Store user message before calling model.
  - After model stream completes, store assistant message.

---

## Task 6: Model Client and SSE Streaming

- [ ] **Step 1: Model client wrapper**
  - Build `services/model_client.py` using OpenAI-compatible API.
  - Support base_url, api_key, model from config.

- [ ] **Step 2: SSE streaming**
  - Use `text/event-stream` response and `stream_with_context` generator.
  - Event types: `token`, `done`, `error`.
  - Convert model stream tokens into SSE chunks.

---

## Task 7: Frontend Layout

- [ ] **Step 1: index.html structure**
  - Header with module buttons, profile button, logout.
  - Sidebar for session history grouped by module.
  - Main chat panel with messages + input.

- [ ] **Step 2: Styles**
  - Add minimal custom CSS for layout, chat bubbles, and sidebar.

---

## Task 8: Frontend Logic

- [ ] **Step 1: Auth flow**
  - Register/login forms embedded in the single page.
  - Store auth state and toggle UI panels.

- [ ] **Step 2: Session management**
  - Create session via module buttons.
  - Load and render session history.

- [ ] **Step 3: Streaming chat**
  - Send user message to `/sessions/{id}/messages`.
  - Read SSE stream, append tokens to assistant bubble.
  - Render Markdown with marked.js.

- [ ] **Step 4: Profile UI**
  - Modal form for exam level and exam date.
  - Save via GET/PUT /profile.

---

## Task 9: Run Docs and Manual Tests

- [ ] **Step 1: README**
  - Backend: install deps, copy config, run Flask.
  - Frontend: set API_BASE_URL, run static server.

- [ ] **Step 2: Manual test checklist**
  - Register/login/logout.
  - Profile update.
  - Create sessions for each module.
  - Streaming response success and error handling.
  - Session history loads and renders Markdown.
