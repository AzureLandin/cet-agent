/* ===== 登录页 ===== */

let loginListenersBound = false;

function showLoginView() {
    const view = document.getElementById("view-login");
    view.classList.remove("hidden");

    // 隐藏侧边栏和标题栏（登录页全屏）
    document.getElementById("sidebar").classList.add("collapsed");
    document.querySelector(".top-bar").style.display = "none";

    // 返回首页链接（已登录用户从此返回）
    const backLink = document.getElementById("auth-back-link");
    backLink.onclick = (e) => {
        e.preventDefault();
        document.getElementById("sidebar").classList.remove("collapsed");
        document.querySelector(".top-bar").style.display = "flex";
        navigateTo("home");
    };

    if (!loginListenersBound) {
        setupLoginListeners();
        loginListenersBound = true;
    }
}

function setupLoginListeners() {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const tabs = document.querySelectorAll(".auth-tab");
    const errorEl = document.getElementById("auth-error");

    // Tab 切换 — 使用 onclick 避免重复绑定
    tabs.forEach(tab => {
        tab.onclick = () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            const target = tab.dataset.tab;
            if (target === "login") {
                loginForm.classList.remove("hidden");
                registerForm.classList.add("hidden");
            } else {
                loginForm.classList.add("hidden");
                registerForm.classList.remove("hidden");
            }
            errorEl.textContent = "";
        };
    });

    // 登录提交
    loginForm.onsubmit = async (e) => {
        e.preventDefault();
        errorEl.textContent = "";
        const username = loginForm.username.value.trim();
        const password = loginForm.password.value;

        showLoading("正在登录...");
        try {
            const user = await login(username, password);
            state.user = user;
            state.profile = await getProfile();
            hideLoading();
            navigateTo("home");
            getSessions().then(sessions => {
                state.sessions = sessions;
                renderSidebar();
                updateAvatar();
            }).catch(e => console.error("加载会话失败:", e));
        } catch (err) {
            hideLoading();
            errorEl.textContent = err.message || "登录失败";
        }
    };

    // 注册提交
    registerForm.onsubmit = async (e) => {
        e.preventDefault();
        errorEl.textContent = "";
        const username = registerForm.username.value.trim();
        const password = registerForm.password.value;
        const confirm = registerForm.confirm.value;

        if (password !== confirm) {
            errorEl.textContent = "两次输入的密码不一致";
            return;
        }

        showLoading("正在注册...");
        try {
            const user = await register(username, password);
            state.user = user;
            state.profile = await getProfile();
            hideLoading();
            navigateTo("home");
            getSessions().then(sessions => {
                state.sessions = sessions;
                renderSidebar();
                updateAvatar();
            }).catch(e => console.error("加载会话失败:", e));
        } catch (err) {
            hideLoading();
            errorEl.textContent = err.message || "注册失败";
        }
    };
}

/* ===== 首页 ===== */

function showHomeView() {
    const view = document.getElementById("view-home");
    view.classList.remove("hidden");

    const sidebar = document.getElementById("sidebar");
    const topBar = document.querySelector(".top-bar");

    if (state.user) {
        // 已登录：显示侧边栏和顶部栏
        sidebar.classList.remove("collapsed");
        topBar.style.display = "flex";
    } else {
        // 未登录：隐藏侧边栏，但显示顶部栏（只显示Logo）
        sidebar.classList.add("collapsed");
        topBar.style.display = "flex";
    }

    // 更新昵称
    const nicknameEl = document.querySelector(".welcome-subtitle");
    const name = state.user ? state.user.username : "同学";
    nicknameEl.textContent = name + "，你好";

    // 绑定模块卡片点击
    const cardsContainer = view.querySelector(".module-cards");
    renderModuleCards(cardsContainer, async (module) => {
        if (!state.user) {
            navigateTo("login");
            return;
        }
        try {
            showLoading("正在创建会话...");
            const session = await createSession(module);
            if (!state.sessions[module]) state.sessions[module] = [];
            state.sessions[module].unshift(session);
            renderSidebar();
            state._pendingSession = session;
            state._pendingGreeting = true;
            navigateTo("chat", module, session.id);
        } catch (err) {
            hideLoading();
            console.error("创建会话失败:", err);
            showToast("创建会话失败: " + err.message, "error");
        }
    });

    // 绑定首页输入框发送
    const input = document.getElementById("home-input");
    const sendBtn = document.getElementById("home-send");

    const doSend = async () => {
        const content = input.value.trim();
        if (!content) return;

        if (!state.user) {
            navigateTo("login");
            return;
        }

        input.value = "";
        autoResizeTextarea(input);

        try {
            showLoading("正在创建会话...");
            const session = await createSession("writing");
            if (!state.sessions.writing) state.sessions.writing = [];
            state.sessions.writing.unshift(session);
            renderSidebar();
            state._pendingSession = session;
            state._pendingGreeting = false;
            navigateTo("chat", "writing", session.id);
            setTimeout(() => sendChatMessage(session.id, content), 200);
        } catch (err) {
            hideLoading();
            showToast("创建会话失败: " + err.message, "error");
        }
    };

    sendBtn.onclick = doSend;
    input.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            doSend();
        }
    };
    input.oninput = () => autoResizeTextarea(input);
}

/* ===== 设置页 ===== */

function showSettingsView() {
    const view = document.getElementById("view-settings");
    view.classList.remove("hidden");

    document.getElementById("sidebar").classList.remove("collapsed");
    document.querySelector(".top-bar").style.display = "flex";

    const saveBtn = document.getElementById("save-settings");
    const backBtn = document.getElementById("back-home");
    const msgEl = document.getElementById("settings-message");
    const nameInput = document.getElementById("display-name");
    const avatarPreview = document.getElementById("avatar-preview");
    const colorContainer = document.getElementById("avatar-colors");
    const fileInput = document.getElementById("avatar-file-input");
    const resetBtn = document.getElementById("avatar-reset-btn");

    const AVATAR_COLORS = [
        "#4285f4", "#ea4335", "#fbbc04", "#34a853",
        "#8e24aa", "#00acc1", "#ef6c00", "#c62828",
        "#2e7d32", "#1565c0",
    ];

    let selectedColor = "#4285f4";
    let pendingAvatarUrl = null;
    let avatarReset = false;

    colorContainer.innerHTML = "";
    AVATAR_COLORS.forEach(color => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "avatar-color-dot";
        dot.style.background = color;
        dot.addEventListener("click", () => {
            colorContainer.querySelectorAll(".avatar-color-dot").forEach(d => d.classList.remove("selected"));
            dot.classList.add("selected");
            selectedColor = color;
            updateAvatarPreview();
        });
        colorContainer.appendChild(dot);
    });

    function updateAvatarPreview() {
        if (pendingAvatarUrl) {
            avatarPreview.style.backgroundImage = `url(${API_BASE}${pendingAvatarUrl})`;
            avatarPreview.style.backgroundSize = "cover";
            avatarPreview.textContent = "";
            avatarPreview.style.background = `url(${API_BASE}${pendingAvatarUrl}) center/cover no-repeat`;
        } else if (avatarReset) {
            avatarPreview.style.backgroundImage = "";
            avatarPreview.style.background = selectedColor;
            const name = nameInput.value.trim() || state.user.username;
            avatarPreview.textContent = name.charAt(0).toUpperCase();
        } else {
            avatarPreview.style.backgroundImage = "";
            avatarPreview.style.background = selectedColor;
            const name = nameInput.value.trim() || state.user.username;
            avatarPreview.textContent = name.charAt(0).toUpperCase();
        }
    }

    if (state.profile) {
        const levelInputs = document.querySelectorAll('input[name="exam_level"]');
        levelInputs.forEach(input => {
            input.checked = input.value === state.profile.exam_level;
        });
        const dateInput = document.getElementById("exam-date");
        if (state.profile.exam_date) {
            dateInput.value = state.profile.exam_date;
        }
        if (state.profile.display_name) {
            nameInput.value = state.profile.display_name;
        }
        if (state.profile.avatar_color) {
            selectedColor = state.profile.avatar_color;
            const match = colorContainer.querySelector(`.avatar-color-dot[style*="${selectedColor}"]`);
            if (match) match.classList.add("selected");
        } else {
            colorContainer.querySelector(".avatar-color-dot").classList.add("selected");
        }
        if (state.profile.avatar_url) {
            pendingAvatarUrl = state.profile.avatar_url;
        }
        updateAvatarPreview();
    }

    nameInput.addEventListener("input", updateAvatarPreview);

    fileInput.addEventListener("change", async () => {
        msgEl.textContent = "";
        const file = fileInput.files[0];
        if (!file) return;
        try {
            const result = await uploadAvatar(file);
            pendingAvatarUrl = result.avatar_url;
            avatarReset = false;
            updateAvatarPreview();
        } catch (err) {
            msgEl.textContent = "上传失败: " + err.message;
        }
        fileInput.value = "";
    });

    resetBtn.addEventListener("click", () => {
        pendingAvatarUrl = null;
        avatarReset = true;
        updateAvatarPreview();
    });

    saveBtn.onclick = async () => {
        msgEl.textContent = "";
        const levelInput = document.querySelector('input[name="exam_level"]:checked');
        const dateInput = document.getElementById("exam-date");

        const data = {};
        if (levelInput) data.exam_level = levelInput.value;
        if (dateInput.value) data.exam_date = dateInput.value;
        data.display_name = nameInput.value.trim() || null;
        data.avatar_color = selectedColor;

        try {
            await updateProfile(data);
            state.profile = { ...state.profile, ...data, avatar_url: pendingAvatarUrl || (avatarReset ? null : state.profile.avatar_url) };
            updateAvatar();
            msgEl.textContent = "保存成功";
        } catch (err) {
            msgEl.textContent = "保存失败: " + err.message;
        }
    };

    backBtn.onclick = () => navigateTo("home");
}

/* ===== 对话页 ===== */

let streamingMessageId = null;
let streamingContent = "";

function showChatView(module, sessionId) {
    const view = document.getElementById("view-chat");
    view.classList.remove("hidden");

    // 恢复侧边栏和顶部栏
    document.getElementById("sidebar").classList.remove("collapsed");
    document.querySelector(".top-bar").style.display = "flex";

    const input = document.getElementById("chat-input");
    const sendBtn = document.getElementById("chat-send");

    if (state._pendingSession && state._pendingSession.id === sessionId) {
        state.currentSession = state._pendingSession;
        delete state._pendingSession;
        const messagesList = document.getElementById("messages-list");
        clearElement(messagesList);
        const visibleMessages = state.currentSession.messages.filter(m => m.role !== "system");
        visibleMessages.forEach(msg => {
            messagesList.appendChild(renderMessageBubble(msg));
        });
        scrollToBottom(messagesList);
        hideLoading();
        if (state._pendingGreeting) {
            delete state._pendingGreeting;
            setTimeout(() => sendChatMessage(sessionId, "开始"), 100);
        }
    } else {
        loadSession(sessionId);
    }

    // 绑定发送
    const doSend = () => {
        const content = input.value.trim();
        if (!content || state.isStreaming) return;
        input.value = "";
        autoResizeTextarea(input);
        sendChatMessage(sessionId, content);
    };

    sendBtn.onclick = doSend;
    input.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            doSend();
        }
    };
    input.oninput = () => autoResizeTextarea(input);
}

async function loadSession(sessionId) {
    const messagesList = document.getElementById("messages-list");
    clearElement(messagesList);
    showLoading("正在加载会话...");

    try {
        const session = await getSession(sessionId);
        state.currentSession = session;
        renderSidebar();

        const visibleMessages = session.messages.filter(m => m.role !== "system");
        visibleMessages.forEach(msg => {
            messagesList.appendChild(renderMessageBubble(msg));
        });
        scrollToBottom(messagesList);
    } catch (err) {
        console.error("加载会话失败:", err);
        messagesList.appendChild(createEl("p", { class: "error-text" }, ["加载会话失败: " + err.message]));
    } finally {
        hideLoading();
    }
}

async function sendChatMessage(sessionId, content) {
    const messagesList = document.getElementById("messages-list");

    // 1. 添加用户消息到 UI
    const userMsg = {
        id: Date.now(),
        role: "user",
        content: content,
        created_at: new Date().toISOString(),
    };
    messagesList.appendChild(renderMessageBubble(userMsg));
    scrollToBottom(messagesList);

    // 2. 创建 AI 消息占位符（含思考中指示器）
    streamingContent = "";
    streamingMessageId = Date.now() + 1;
    let isFirstToken = true;
    const aiMsg = {
        id: streamingMessageId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
    };
    const aiBubble = renderMessageBubble(aiMsg, true);
    aiBubble.classList.add("streaming");
    const bubbleEl = aiBubble.querySelector(".message-bubble");
    if (bubbleEl) {
        bubbleEl.textContent = "";
        bubbleEl.appendChild(renderThinkingIndicator());
    }
    messagesList.appendChild(aiBubble);
    scrollToBottom(messagesList);

    state.isStreaming = true;

    // 3. 发送 SSE 请求
    try {
        await sendMessage(sessionId, content, {
            onToken: (token) => {
                if (isFirstToken) {
                    const b = document.querySelector(`.message-wrapper[data-id="${streamingMessageId}"] .message-bubble`);
                    if (b) b.innerHTML = "";
                    isFirstToken = false;
                }
                streamingContent += token;
                updateStreamingMessage(streamingMessageId, streamingContent);
                scrollToBottom(messagesList);
            },
            onDone: () => {
                state.isStreaming = false;
                const wrapper = document.querySelector(`.message-wrapper[data-id="${streamingMessageId}"]`);
                if (wrapper) wrapper.classList.remove("streaming");
                streamingMessageId = null;
                streamingContent = "";
            },
            onError: (err) => {
                state.isStreaming = false;
                const wrapper = document.querySelector(`.message-wrapper[data-id="${streamingMessageId}"]`);
                if (wrapper) {
                    wrapper.classList.remove("streaming");
                    const bubble = wrapper.querySelector(".message-bubble");
                    if (bubble) bubble.innerHTML += `<br><span style="color:#f28b82">[错误] ${err.message}</span>`;
                }
                streamingMessageId = null;
                streamingContent = "";
            },
        });
    } catch (err) {
        state.isStreaming = false;
        console.error("发送消息失败:", err);
        const wrapper = document.querySelector(`.message-wrapper[data-id="${streamingMessageId}"]`);
        if (wrapper) {
            wrapper.classList.remove("streaming");
            const bubble = wrapper.querySelector(".message-bubble");
            if (bubble) bubble.innerHTML += `<br><span style="color:#f28b82">[错误] ${err.message}</span>`;
        }
        streamingMessageId = null;
        streamingContent = "";
    }
}

function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}
