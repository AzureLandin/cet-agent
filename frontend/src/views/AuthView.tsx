import { FormEvent, useState } from "react";
import { ArrowLeft } from "lucide-react";
import * as api from "../api/client";
import type { AuthResponse } from "../types";

interface AuthViewProps {
  onSuccess: (auth: AuthResponse) => void;
  onBackHome: () => void;
}

export function AuthView({ onSuccess, onBackHome }: AuthViewProps) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (tab === "register" && password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }

    setLoading(true);
    try {
      const auth =
        tab === "login"
          ? await api.login(username.trim(), password)
          : await api.register(username.trim(), password);
      onSuccess(auth);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div style={{ textAlign: "center" }}>
          <h1
            className="home-title"
            style={{ fontSize: 28, margin: "0 0 6px" }}
          >
            CET Agent
          </h1>
          <p
            style={{
              margin: 0,
              fontSize: 13,
              color: "var(--md-sys-color-on-surface-variant)",
            }}
          >
            智能英语四六级学习与真题精练平台
          </p>
        </div>

        <div className="segmented-tabs" style={{ alignSelf: "center" }}>
          <button
            type="button"
            className={`segmented-tab ${tab === "login" ? "active" : ""}`}
            onClick={() => {
              setTab("login");
              setError("");
            }}
          >
            登录
          </button>
          <button
            type="button"
            className={`segmented-tab ${tab === "register" ? "active" : ""}`}
            onClick={() => {
              setTab("register");
              setError("");
            }}
          >
            注册
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <input
            className="m3-input"
            type="text"
            placeholder="用户名（3-50位）"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            required
            minLength={3}
            maxLength={50}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="m3-input"
            type="password"
            placeholder="密码（至少6位）"
            autoComplete={tab === "login" ? "current-password" : "new-password"}
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {tab === "register" && (
            <input
              className="m3-input"
              type="password"
              placeholder="确认密码"
              autoComplete="new-password"
              required
              minLength={6}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          )}

          {error && (
            <div
              style={{
                fontSize: 13,
                padding: "8px 12px",
                borderRadius: 8,
                background: "var(--md-sys-color-error-container)",
                color: "var(--md-sys-color-on-error-container)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="m3-btn-filled"
            disabled={loading}
            style={{ marginTop: 4 }}
          >
            {loading ? "请稍候..." : tab === "login" ? "登录" : "注册并登录"}
          </button>
        </form>

        <button
          type="button"
          className="m3-btn-outlined m3-btn-sm"
          onClick={onBackHome}
          style={{ alignSelf: "center" }}
        >
          <ArrowLeft size={14} />
          <span>返回首页</span>
        </button>
      </div>
    </div>
  );
}
