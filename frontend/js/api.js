const API_BASE = "";

/**
 * 基础请求封装
 */
async function request(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const defaults = {
        credentials: "include",
        headers: { "Content-Type": "application/json" },
    };

    const response = await fetch(url, { ...defaults, ...options });

    if (response.status === 401) {
        const err = new Error("Authentication required.");
        err.code = "UNAUTHORIZED";
        err.status = 401;
        throw err;
    }

    if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const err = new Error(errBody.message || `HTTP ${response.status}`);
        err.code = errBody.error_code || `HTTP_${response.status}`;
        err.status = response.status;
        throw err;
    }

    // 204 No Content
    if (response.status === 204) {
        return null;
    }

    return response.json();
}

/* ===== Auth ===== */

function register(username, password) {
    return request("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
    });
}

function login(username, password) {
    return request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
    });
}

function logout() {
    return request("/auth/logout", { method: "POST" });
}

/* ===== Profile ===== */

function getProfile() {
    return request("/profile", { method: "GET" });
}

function updateProfile(data) {
    return request("/profile", {
        method: "PUT",
        body: JSON.stringify(data),
    });
}

async function uploadAvatar(file) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/profile/avatar`, {
        method: "POST",
        credentials: "include",
        body: formData,
    });
    if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const err = new Error(errBody.message || `HTTP ${response.status}`);
        err.code = errBody.error_code || `HTTP_${response.status}`;
        err.status = response.status;
        throw err;
    }
    return response.json();
}

function deleteAvatar() {
    return request("/profile/avatar", { method: "DELETE" });
}

/* ===== Sessions ===== */

function createSession(module) {
    return request("/sessions", {
        method: "POST",
        body: JSON.stringify({ module }),
    });
}

function getSessions() {
    return request("/sessions", { method: "GET" });
}

function getSession(id) {
    return request(`/sessions/${id}`, { method: "GET" });
}

function deleteSession(id) {
    return request(`/sessions/${id}`, { method: "DELETE" });
}

/* ===== Messages (SSE) ===== */

/**
 * 发送消息，通过 SSE 流式接收回复
 * @param {number} sessionId
 * @param {string} content
 * @param {object} callbacks - { onToken(token), onDone(), onError(error) }
 * @returns {Promise<void>}
 */
const STREAM_IDLE_TIMEOUT_MS = 120_000;

async function sendMessage(sessionId, content, callbacks = {}) {
    const { onToken, onDone, onError } = callbacks;

    const controller = new AbortController();
    let timeoutId = setTimeout(() => controller.abort(), STREAM_IDLE_TIMEOUT_MS);
    const resetTimeout = () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => controller.abort(), STREAM_IDLE_TIMEOUT_MS);
    };

    try {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ content }),
            signal: controller.signal,
        });

        if (response.status === 401) {
            const err = new Error("Authentication required.");
            err.code = "UNAUTHORIZED";
            if (onError) { onError(err); return; }
            throw err;
        }

        if (!response.ok) {
            const errBody = await response.json().catch(() => ({}));
            const err = new Error(errBody.message || `HTTP ${response.status}`);
            err.code = errBody.error_code || `HTTP_${response.status}`;
            if (onError) { onError(err); return; }
            throw err;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop(); // 保留未完整的一行

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;

                    let payload;
                    try {
                        payload = JSON.parse(line.slice(6));
                    } catch (e) {
                        continue; // 忽略解析失败的行
                    }

                    if (payload.event === "token" && onToken) {
                        resetTimeout();
                        onToken(payload.data);
                    } else if (payload.event === "done" && onDone) {
                        onDone();
                    } else if (payload.event === "error" && onError) {
                        onError(new Error(payload.data || "Stream error"));
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    } catch (err) {
        if (err.name === "AbortError" || controller.signal.aborted) {
            const timeoutErr = new Error("响应超时，请重试");
            timeoutErr.code = "TIMEOUT";
            if (onError) { onError(timeoutErr); return; }
            throw timeoutErr;
        }
        throw err;
    } finally {
        clearTimeout(timeoutId);
    }
}

/* ===== Health ===== */

function healthCheck() {
    return request("/health", { method: "GET" });
}
