// ===== Global State =====
const state = {
    user: null,
    profile: null,
    sessions: {
        writing: [],
        reading: [],
        translation: [],
    },
    currentSession: null,
    sidebarOpen: false,
    isStreaming: false,
};

// ===== Initialization =====

async function initApp() {
    // 立即绑定事件并启动路由（不等待网络请求）
    bindGlobalEvents();
    initRouter();

    // 后台异步检查登录状态（通过已有 Cookie）
    try {
        const [profile, sessionsOrNull] = await Promise.all([
            getProfile(),
            getSessions().catch((dataErr) => {
                console.error("加载会话列表失败:", dataErr);
                return null;
            }),
        ]);
        state.profile = profile;
        state.user = { username: profile.username || profile.display_name || "用户" };
        if (sessionsOrNull) state.sessions = sessionsOrNull;

        renderSidebar();
        updateAvatar();
        updateHomeNickname();
        document.getElementById("sidebar").classList.remove("collapsed");
        state.sidebarOpen = true;
    } catch (err) {
        // 任何错误视为未登录，保持首页状态即可
        console.warn("未登录或后端不可达:", err.message || err);
    }
}

function updateHomeNickname() {
    const nicknameEl = document.querySelector(".welcome-subtitle");
    if (!nicknameEl) return;
    const name = (state.profile && state.profile.display_name)
        || (state.user && state.user.username)
        || "同学";
    nicknameEl.textContent = name + "，你好";
}

function updateAvatar() {
    const avatar = document.getElementById("user-avatar");
    if (state.profile && state.profile.avatar_url) {
        avatar.textContent = "";
        avatar.style.backgroundImage = `url(${API_BASE}${state.profile.avatar_url})`;
        avatar.style.backgroundSize = "cover";
        avatar.style.backgroundPosition = "center";
    } else {
        avatar.style.backgroundImage = "";
        const name = (state.profile && state.profile.display_name) || (state.user && state.user.username);
        if (name) {
            avatar.textContent = name.charAt(0).toUpperCase();
            const color = (state.profile && state.profile.avatar_color) || "#4285f4";
            avatar.style.background = color;
        } else {
            avatar.textContent = "?";
            avatar.style.background = "";
        }
    }
}

function bindGlobalEvents() {
    // 菜单切换
    const menuToggle = document.getElementById("menu-toggle");
    const sidebar = document.getElementById("sidebar");
    menuToggle.addEventListener("click", () => {
        sidebar.classList.toggle("collapsed");
        state.sidebarOpen = !sidebar.classList.contains("collapsed");
    });

    // 新对话按钮
    const newChatBtn = document.getElementById("new-chat-btn");
    newChatBtn.addEventListener("click", () => {
        state.currentSession = null;
        navigateTo("home");
    });

    // 设置按钮
    const settingsBtn = document.getElementById("settings-btn");
    settingsBtn.addEventListener("click", () => navigateTo("settings"));

    // 快捷键：Ctrl+Shift+O 新对话
    document.addEventListener("keydown", (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === "O") {
            e.preventDefault();
            state.currentSession = null;
            navigateTo("home");
        }
    });

    // 头像点击：未登录跳转登录页，已登录确认后登出
    const avatar = document.getElementById("user-avatar");
    avatar.addEventListener("click", async () => {
        if (!state.user) {
            navigateTo("login");
            return;
        }
        const ok = await showConfirm("确定要退出登录吗？");
        if (!ok) return;
        handleLogout();
    });
}

async function handleLogout() {
    try {
        await logout();
    } catch (err) {
        console.error("登出失败:", err);
    }
    state.user = null;
    state.profile = null;
    state.sessions = { writing: [], reading: [], translation: [] };
    state.currentSession = null;
    navigateTo("login");
}

// 启动
initApp();
