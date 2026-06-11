/**
 * 使用本地托管的 marked 渲染 Markdown，并通过 DOMPurify 清洗防止 XSS
 */
function renderMarkdown(text) {
    if (!text) return "";
    const rawHtml = marked.parse(text, {
        breaks: true,
        gfm: true,
    });
    return DOMPurify.sanitize(rawHtml);
}

/**
 * 相对时间格式化
 */
function formatRelativeTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return "刚刚";
    if (diffMin < 60) return `${diffMin}分钟前`;
    if (diffHour < 24) return `${diffHour}小时前`;
    if (diffDay < 7) return `${diffDay}天前`;
    return date.toLocaleDateString("zh-CN");
}

/**
 * DOM 辅助：清空元素
 */
function clearElement(el) {
    while (el.firstChild) {
        el.removeChild(el.firstChild);
    }
}

/**
 * DOM 辅助：创建元素并设置属性
 */
function createEl(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([key, val]) => {
        if (key === "text") {
            el.textContent = val;
        } else if (key === "html") {
            el.innerHTML = val;
        } else {
            el.setAttribute(key, val);
        }
    });
    children.forEach(child => {
        if (typeof child === "string") {
            el.appendChild(document.createTextNode(child));
        } else {
            el.appendChild(child);
        }
    });
    return el;
}

/**
 * 自动调整 textarea 高度
 */
function autoResizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px";
}

/* ===== Loading ===== */

let _loadingOverlay = null;

function getLoadingOverlay() {
    if (!_loadingOverlay) {
        _loadingOverlay = createEl("div", { class: "loading-overlay" }, [
            createEl("div", { class: "loading-box" }, [
                createEl("div", { class: "loading-spinner" }),
                createEl("p", { class: "loading-text", text: "加载中..." }),
            ]),
        ]);
        document.body.appendChild(_loadingOverlay);
    }
    return _loadingOverlay;
}

function showLoading(text = "加载中...") {
    const overlay = getLoadingOverlay();
    const textEl = overlay.querySelector(".loading-text");
    if (textEl) textEl.textContent = text;
    setTimeout(() => overlay.classList.add("active"), 10);
}

function hideLoading() {
    if (_loadingOverlay) {
        _loadingOverlay.classList.remove("active");
    }
}

function renderThinkingIndicator() {
    const dots = createEl("div", { class: "thinking-dots" }, [
        createEl("span"),
        createEl("span"),
        createEl("span"),
    ]);
    const wrapper = createEl("div", { class: "thinking-indicator" }, [
        createEl("span", { text: "正在思考" }),
        dots,
    ]);
    return wrapper;
}

/* ===== Toast & Confirm ===== */

let _toastContainer = null;

function getToastContainer() {
    if (!_toastContainer) {
        _toastContainer = createEl("div", { class: "toast-container" });
        document.body.appendChild(_toastContainer);
    }
    return _toastContainer;
}

function showToast(message, type = "info", duration = 3000) {
    const container = getToastContainer();
    const toast = createEl("div", { class: `toast toast-${type}` }, [
        createEl("span", { text: message }),
    ]);
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("toast-show"));

    if (duration > 0) {
        setTimeout(() => {
            toast.classList.remove("toast-show");
            setTimeout(() => toast.remove(), 400);
        }, duration);
    }

    toast.addEventListener("click", () => {
        toast.classList.remove("toast-show");
        setTimeout(() => toast.remove(), 400);
    });

    return toast;
}

function showConfirm(message, okText = "确定", cancelText = "取消") {
    return new Promise(resolve => {
        const overlay = createEl("div", { class: "confirm-overlay" });
        const box = createEl("div", { class: "confirm-box" }, [
            createEl("p", { class: "confirm-message", text: message }),
            createEl("div", { class: "confirm-actions" }, [
                createEl("button", { class: "confirm-btn confirm-btn-cancel", text: cancelText }),
                createEl("button", { class: "confirm-btn confirm-btn-ok", text: okText }),
            ]),
        ]);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        const close = (result) => {
            overlay.classList.add("confirm-hide");
            setTimeout(() => overlay.remove(), 300);
            resolve(result);
        };

        box.querySelector(".confirm-btn-ok").addEventListener("click", () => close(true));
        box.querySelector(".confirm-btn-cancel").addEventListener("click", () => close(false));
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) close(false);
        });

        requestAnimationFrame(() => overlay.classList.add("confirm-show"));
    });
}
