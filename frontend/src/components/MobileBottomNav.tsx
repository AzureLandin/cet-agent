import {
  FileSpreadsheet,
  Home,
  LogIn,
  MessageSquare,
  Settings,
  ShieldCheck,
} from "lucide-react";
import type { AppView } from "../types";

interface MobileBottomNavProps {
  currentView: AppView;
  isAdmin: boolean;
  hasActiveSession: boolean;
  isLoggedIn: boolean;
  onNavigate: (view: AppView) => void;
  onResumeSession: () => void;
}

export function MobileBottomNav({
  currentView,
  isAdmin,
  hasActiveSession,
  isLoggedIn,
  onNavigate,
  onResumeSession,
}: MobileBottomNavProps) {
  return (
    <nav className="mobile-bottom-nav" aria-label="移动端主导航">
      <button
        type="button"
        className={`mobile-bottom-nav-item ${currentView === "home" ? "active" : ""}`}
        onClick={() => onNavigate("home")}
      >
        <span className="mobile-bottom-nav-pill">
          <Home size={20} />
        </span>
        <span>首页</span>
      </button>

      <button
        type="button"
        className={`mobile-bottom-nav-item ${currentView === "bank" ? "active" : ""}`}
        onClick={() => onNavigate("bank")}
      >
        <span className="mobile-bottom-nav-pill">
          <FileSpreadsheet size={20} />
        </span>
        <span>题库</span>
      </button>

      {hasActiveSession && (
        <button
          type="button"
          className={`mobile-bottom-nav-item ${currentView === "chat" ? "active" : ""}`}
          onClick={onResumeSession}
        >
          <span className="mobile-bottom-nav-pill">
            <MessageSquare size={20} />
            <span className="mobile-bottom-nav-dot" aria-hidden="true" />
          </span>
          <span>练习中</span>
        </button>
      )}

      {isAdmin && (
        <button
          type="button"
          className={`mobile-bottom-nav-item ${currentView === "admin" ? "active" : ""}`}
          onClick={() => onNavigate("admin")}
        >
          <span className="mobile-bottom-nav-pill">
            <ShieldCheck size={20} />
          </span>
          <span>管理</span>
        </button>
      )}

      {isLoggedIn ? (
        <button
          type="button"
          className={`mobile-bottom-nav-item ${currentView === "settings" ? "active" : ""}`}
          onClick={() => onNavigate("settings")}
        >
          <span className="mobile-bottom-nav-pill">
            <Settings size={20} />
          </span>
          <span>我的</span>
        </button>
      ) : (
        <button
          type="button"
          className={`mobile-bottom-nav-item ${currentView === "auth" ? "active" : ""}`}
          onClick={() => onNavigate("auth")}
        >
          <span className="mobile-bottom-nav-pill">
            <LogIn size={20} />
          </span>
          <span>登录</span>
        </button>
      )}
    </nav>
  );
}
