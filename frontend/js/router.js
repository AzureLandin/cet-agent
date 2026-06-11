const routes = {
    login: () => showLoginView(),
    home: () => showHomeView(),
    chat: (module, sessionId) => showChatView(module, parseInt(sessionId, 10)),
    settings: () => showSettingsView(),
};

let currentRoute = "";

function initRouter() {
    window.addEventListener("hashchange", handleRoute);
    // 初始加载
    handleRoute();
}

function handleRoute() {
    const hash = window.location.hash || "#/";
    const path = hash.replace("#", "").replace(/^\//, "");
    const segments = path.split("/").filter(Boolean);

    // 重置流式状态（防止导航后卡住）
    state.isStreaming = false;

    // 隐藏所有视图
    document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));

    let routeName = segments[0] || "home";

    // 未登录时：只允许访问首页和登录页
    if (!state.user && routeName !== "login" && routeName !== "home") {
        navigateTo("login");
        return;
    }

    const handler = routes[routeName];
    if (!handler) {
        navigateTo("home");
        return;
    }

    currentRoute = routeName;

    if (routeName === "chat" && segments.length >= 3) {
        handler(segments[1], segments[2]);
    } else {
        handler();
    }
}

function navigateTo(route, ...params) {
    if (route === "home") {
        window.location.hash = "#/";
    } else if (route === "login") {
        window.location.hash = "#/login";
    } else if (route === "settings") {
        window.location.hash = "#/settings";
    } else if (route === "chat" && params.length >= 2) {
        window.location.hash = `#/chat/${params[0]}/${params[1]}`;
    } else {
        window.location.hash = `#/${route}`;
    }
}
