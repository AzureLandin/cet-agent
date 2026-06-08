# CET Web Agent — Homepage Implementation Plan

Date: 2026-05-13

## Overview

Implement the pre-auth homepage as a dark-themed, centered AI-native landing page (inspired by Gemini). Unauthenticated users see the homepage; clicking the hero input or module pills opens a login/register modal. After auth, the page transitions into the authenticated chat app without a full reload.

## Changeset

### 1. `index.html` — Structure

#### New Homepage Section (`#home-view`)
Add a new top-level container for the unauthenticated state:

```html
<div id="home-view" class="home-view d-flex flex-column vh-100">
  <!-- Top bar -->
  <header class="home-header d-flex justify-content-between align-items-center px-4 py-3">
    <div class="brand">CET Agent</div>
    <div class="auth-buttons">
      <button id="btn-login" class="btn btn-link text-light">登录</button>
      <button id="btn-register" class="btn btn-outline-light btn-sm">注册</button>
    </div>
  </header>

  <!-- Left mini sidebar (icons only) -->
  <aside class="home-sidebar-mini">
    <button class="icon-btn" title="菜单"><i class="bi bi-list"></i></button>
    <button class="icon-btn" title="新对话"><i class="bi bi-pencil-square"></i></button>
  </aside>

  <!-- Center stage -->
  <main class="home-center flex-grow-1 d-flex flex-column justify-content-center align-items-center px-3">
    <h1 class="home-greeting">准备好迎接四六级了吗？</h1>

    <!-- Hero input bar -->
    <div class="hero-input-bar">
      <textarea id="hero-input" class="hero-textarea" rows="1" placeholder="输入作文题目、阅读材料或翻译句子..."></textarea>
      <div class="hero-input-tools">
        <div class="tools-left">
          <button class="icon-btn" title="附件"><i class="bi bi-plus-lg"></i></button>
          <button class="icon-btn" title="工具"><i class="bi bi-tools"></i></button>
        </div>
        <div class="tools-right">
          <button class="icon-btn" title="思考模式"><i class="bi bi-lightning"></i></button>
          <button class="icon-btn" title="语音输入"><i class="bi bi-mic"></i></button>
        </div>
      </div>
    </div>

    <!-- Module pills -->
    <div class="module-pills">
      <button class="pill" data-module="writing"><span class="pill-icon">📝</span> 写作批改</button>
      <button class="pill" data-module="reading"><span class="pill-icon">📖</span> 阅读训练</button>
      <button class="pill" data-module="translation"><span class="pill-icon">🔄</span> 翻译练习</button>
      <button class="pill" data-module="free"><span class="pill-icon">✍️</span> 随便写点什么</button>
      <button class="pill" data-module="plan"><span class="pill-icon">📚</span> 帮我制定计划</button>
    </div>
  </main>
</div>
```

#### Auth Modal (`#auth-modal`)
Add a Bootstrap modal for login/register, placed at the end of `<body>`:

```html
<div class="modal fade" id="auth-modal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-dark text-light border-secondary">
      <div class="modal-header border-secondary">
        <ul class="nav nav-pills" id="auth-tab" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="tab-login" data-bs-toggle="pill" data-bs-target="#pane-login">登录</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-register" data-bs-toggle="pill" data-bs-target="#pane-register">注册</button>
          </li>
        </ul>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="tab-content">
          <div class="tab-pane fade show active" id="pane-login">
            <form id="form-login">
              <div class="mb-3">
                <label class="form-label">用户名</label>
                <input type="text" class="form-control bg-dark text-light border-secondary" id="login-username" required>
              </div>
              <div class="mb-3">
                <label class="form-label">密码</label>
                <input type="password" class="form-control bg-dark text-light border-secondary" id="login-password" required>
              </div>
              <button type="submit" class="btn btn-primary w-100">登录</button>
            </form>
          </div>
          <div class="tab-pane fade" id="pane-register">
            <form id="form-register">
              <div class="mb-3">
                <label class="form-label">用户名</label>
                <input type="text" class="form-control bg-dark text-light border-secondary" id="reg-username" required>
              </div>
              <div class="mb-3">
                <label class="form-label">密码</label>
                <input type="password" class="form-control bg-dark text-light border-secondary" id="reg-password" required>
              </div>
              <div class="mb-3">
                <label class="form-label">确认密码</label>
                <input type="password" class="form-control bg-dark text-light border-secondary" id="reg-password2" required>
              </div>
              <button type="submit" class="btn btn-primary w-100">注册</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

#### Existing App View (`#app-view`)
Wrap the existing authenticated app UI in a container that starts hidden:

```html
<div id="app-view" class="d-none">
  <!-- existing header, sidebar, main panel -->
</div>
```

### 2. `css/homepage.css` — Styles (new file)

```css
/* ===== Base Dark Theme ===== */
.home-view {
  background: linear-gradient(160deg, #0d0d0d 0%, #1a1a2e 100%);
  color: #e8e8e8;
  font-family: 'Segoe UI', system-ui, sans-serif;
}

/* ===== Header ===== */
.home-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}
.brand {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.auth-buttons .btn-link {
  text-decoration: none;
  opacity: 0.8;
}
.auth-buttons .btn-link:hover { opacity: 1; }
.auth-buttons .btn-outline-light {
  border-radius: 999px;
  padding: 0.35rem 1rem;
}

/* ===== Mini Sidebar ===== */
.home-sidebar-mini {
  position: fixed;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
}
.icon-btn {
  background: transparent;
  border: none;
  color: #a0a0a0;
  font-size: 1.25rem;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}
.icon-btn:hover {
  background: rgba(255,255,255,0.08);
  color: #fff;
}

/* ===== Center Stage ===== */
.home-center {
  max-width: 768px;
  margin: 0 auto;
  width: 100%;
  padding-bottom: 10vh;
}
.home-greeting {
  font-size: 2.25rem;
  font-weight: 500;
  margin-bottom: 2rem;
  text-align: center;
  color: #fff;
}

/* ===== Hero Input Bar ===== */
.hero-input-bar {
  width: 100%;
  background: #2a2a35;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 1.75rem;
  padding: 1rem 1.25rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.hero-input-bar:hover,
.hero-input-bar:focus-within {
  border-color: rgba(255,255,255,0.18);
  box-shadow: 0 0 0 3px rgba(66,133,244,0.15);
}
.hero-textarea {
  width: 100%;
  background: transparent;
  border: none;
  color: #fff;
  font-size: 1rem;
  resize: none;
  outline: none;
  min-height: 1.5rem;
  max-height: 8rem;
}
.hero-textarea::placeholder { color: #888; }
.hero-input-tools {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.75rem;
}
.tools-left, .tools-right { display: flex; gap: 0.25rem; }

/* ===== Module Pills ===== */
.module-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.6rem;
  margin-top: 1.25rem;
}
.pill {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  color: #d0d0d0;
  border-radius: 999px;
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s, border-color 0.2s;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.pill:hover {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.2);
  transform: translateY(-1px);
}
.pill-icon { font-size: 1rem; }

/* ===== Auth Modal Overrides ===== */
#auth-modal .modal-content {
  border-radius: 1rem;
}
#auth-modal .nav-pills .nav-link {
  color: #aaa;
  background: transparent;
  border-radius: 999px;
}
#auth-modal .nav-pills .nav-link.active {
  background: rgba(66,133,244,0.2);
  color: #8ab4f8;
}
#auth-modal .form-control:focus {
  background: #1a1a2e;
  color: #fff;
  border-color: #4285f4;
  box-shadow: 0 0 0 0.2rem rgba(66,133,244,0.25);
}

/* ===== View Transitions ===== */
#home-view, #app-view {
  transition: opacity 0.3s ease;
}
.d-none { display: none !important; }
```

### 3. `js/homepage.js` — Logic (new file)

```javascript
// ===== State =====
let isAuthenticated = false;

// ===== DOM References =====
const homeView   = document.getElementById('home-view');
const appView    = document.getElementById('app-view');
const authModalEl= document.getElementById('auth-modal');
const authModal  = new bootstrap.Modal(authModalEl);
const heroInput  = document.getElementById('hero-input');
const pills      = document.querySelectorAll('.pill');
const btnLogin   = document.getElementById('btn-login');
const btnRegister= document.getElementById('btn-register');

// ===== Init =====
document.addEventListener('DOMContentLoaded', async () => {
  isAuthenticated = await checkAuth();
  if (isAuthenticated) {
    showApp();
  } else {
    showHome();
  }
});

// ===== Auth Check =====
async function checkAuth() {
  try {
    const res = await fetch(`${API_BASE_URL}/profile`, { credentials: 'include' });
    return res.ok;
  } catch { return false; }
}

// ===== View Switching =====
function showHome() {
  homeView.classList.remove('d-none');
  appView.classList.add('d-none');
}
function showApp() {
  homeView.classList.add('d-none');
  appView.classList.remove('d-none');
  // existing init logic: load sessions, etc.
  initApp();
}

// ===== Auth Modal Triggers =====
function openAuthModal(activeTab = 'login') {
  const tab = document.getElementById(activeTab === 'register' ? 'tab-register' : 'tab-login');
  const bsTab = new bootstrap.Tab(tab);
  bsTab.show();
  authModal.show();
}

btnLogin.addEventListener('click', () => openAuthModal('login'));
btnRegister.addEventListener('click', () => openAuthModal('register'));

// Hero input & pills trigger auth modal when unauthenticated
heroInput.addEventListener('focus', () => {
  if (!isAuthenticated) {
    heroInput.blur();
    openAuthModal('login');
  }
});
pills.forEach(pill => {
  pill.addEventListener('click', () => {
    if (!isAuthenticated) {
      openAuthModal('login');
      return;
    }
    const module = pill.dataset.module;
    // authenticated: create session and navigate
    createSession(module);
  });
});

// ===== Form Handling =====
document.getElementById('form-login').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('login-username').value;
  const password = document.getElementById('login-password').value;
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password })
  });
  if (res.ok) {
    isAuthenticated = true;
    authModal.hide();
    showApp();
  } else {
    const data = await res.json();
    alert(data.message || '登录失败');
  }
});

document.getElementById('form-register').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username  = document.getElementById('reg-username').value;
  const password  = document.getElementById('reg-password').value;
  const password2 = document.getElementById('reg-password2').value;
  if (password !== password2) { alert('两次密码不一致'); return; }
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password })
  });
  if (res.ok) {
    // auto-login after register, or switch to login tab
    isAuthenticated = true;
    authModal.hide();
    showApp();
  } else {
    const data = await res.json();
    alert(data.message || '注册失败');
  }
});
```

### 4. Integration into existing `index.html`

1. Add Bootstrap Icons CDN in `<head>`:
   ```html
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
   ```
2. Link new stylesheet after existing CSS:
   ```html
   <link rel="stylesheet" href="css/homepage.css">
   ```
3. Include `js/homepage.js` before the existing app JS:
   ```html
   <script src="js/config.js"></script>
   <script src="js/homepage.js"></script>
   <script src="js/app.js"></script>
   ```
4. Wrap existing authenticated UI in `<div id="app-view" class="d-none">`.

## Rollout Steps

1. Create `css/homepage.css` and `js/homepage.js`.
2. Update `index.html` with homepage markup, modal, and integration hooks.
3. Test unauthenticated flow: load page → click input/pills → modal opens → login/register → transitions to app.
4. Test authenticated flow: refresh while logged in → skips homepage → app loads directly.
5. Verify mobile responsiveness (pills wrap, input bar adapts).

## Open Items

- Hero input "thinking" dropdown and microphone are UI placeholders for V2.
- Attachment icon is a UI placeholder for V2 (no file uploads in V1).
- "帮我制定计划" pill maps to `writing` module for now or can create a generic session.
