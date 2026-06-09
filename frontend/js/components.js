/**
 * 渲染侧边栏历史会话列表（按写作/阅读/翻译分组，支持删除）
 */
const MODULE_ICONS = {
    writing: '<i class="fa-solid fa-pen-to-square"></i>',
    reading: '<i class="fa-solid fa-book-open"></i>',
    translation: '<i class="fa-solid fa-language"></i>',
};

const MODULE_LABELS = {
    writing: "写作批改",
    reading: "阅读精读",
    translation: "翻译训练",
};

function renderSidebar() {
    const container = document.getElementById("session-list-container");
    if (!container) return;
    if (!state.sessions) return;
    clearElement(container);

    let hasAny = false;

    ["writing", "reading", "translation"].forEach(module => {
        const sessions = state.sessions[module] || [];
        if (sessions.length === 0) return;
        hasAny = true;

        // 模块分组标题
        const header = createEl("div", { class: "session-group-header" }, [
            createEl("span", { class: "session-group-label", html: `${MODULE_ICONS[module]} ${MODULE_LABELS[module]}` }),
            createEl("span", { class: "session-group-count", text: `${sessions.length}` }),
        ]);
        container.appendChild(header);

        // 该模块下的会话列表
        const list = createEl("ul", { class: "session-list" });
        sessions.forEach(session => {
            const isActive = state.currentSession && state.currentSession.id === session.id;
            const li = createEl("li", {
                class: `session-item${isActive ? " active" : ""}`,
                "data-id": session.id,
            });

            const titleSpan = createEl("span", {
                class: "session-title",
                text: session.title,
            });

            const deleteBtn = createEl("button", {
                class: "session-delete-btn",
                title: "删除会话",
                html: '<i class="fa-solid fa-xmark"></i>',
            });

            deleteBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const ok = await showConfirm("确定要删除这个会话吗？");
                if (!ok) return;
                deleteSession(session.id).then(() => {
                    state.sessions[module] = state.sessions[module].filter(s => s.id !== session.id);
                    if (state.currentSession && state.currentSession.id === session.id) {
                        state.currentSession = null;
                        navigateTo("home");
                    }
                    renderSidebar();
                }).catch(err => {
                    showToast("删除失败: " + err.message, "error");
                });
            });

            li.appendChild(titleSpan);
            li.appendChild(deleteBtn);
            li.addEventListener("click", () => navigateTo("chat", module, session.id));
            list.appendChild(li);
        });
        container.appendChild(list);
    });

    if (!hasAny) {
        container.appendChild(createEl("p", { class: "session-empty" }, ["暂无会话"]));
    }
}

/**
 * 渲染消息气泡
 * @param {object} message - { id, role, content, created_at }
 * @param {boolean} isStreaming - 是否正在流式输出（仅用于 AI 消息）
 * @returns {HTMLElement}
 */
function renderMessageBubble(message, isStreaming = false) {
    const isUser = message.role === "user";
    const wrapper = createEl("div", {
        class: `message-wrapper ${isUser ? "user" : "assistant"}`,
        "data-id": message.id,
    });

    const bubble = createEl("div", { class: "message-bubble" });

    if (isUser) {
        bubble.textContent = message.content;
    } else {
        bubble.innerHTML = renderMarkdown(message.content);
    }

    wrapper.appendChild(bubble);
    return wrapper;
}

/**
 * 更新正在流式输出的 AI 消息内容
 * @param {number} messageId
 * @param {string} content
 */
function updateStreamingMessage(messageId, content) {
    const wrapper = document.querySelector(`.message-wrapper[data-id="${messageId}"]`);
    if (!wrapper) return;
    const bubble = wrapper.querySelector(".message-bubble");
    if (bubble) {
        bubble.innerHTML = renderMarkdown(content);
    }
}

/**
 * 渲染模块快捷卡片
 * @param {HTMLElement} container
 * @param {function} onSelect - (module) => void
 */
function renderModuleCards(container, onSelect) {
    clearElement(container);
    const modules = [
        { key: "writing", label: "写作批改" },
        { key: "reading", label: "阅读精读" },
        { key: "translation", label: "翻译训练" },
    ];

    const ICON_MAP = {
        writing: '<i class="fa-solid fa-pen-to-square"></i>',
        reading: '<i class="fa-solid fa-book-open"></i>',
        translation: '<i class="fa-solid fa-language"></i>',
    };

    modules.forEach(({ key, label }) => {
        const btn = createEl("button", {
            class: "module-card",
            "data-module": key,
        }, [
            createEl("span", { class: "module-icon", html: ICON_MAP[key] }),
            createEl("span", { class: "module-label", text: label }),
        ]);
        btn.addEventListener("click", () => onSelect(key));
        container.appendChild(btn);
    });
}
