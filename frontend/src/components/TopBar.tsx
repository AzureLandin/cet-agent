import { LogIn, LogOut, Menu, Settings } from "lucide-react";
import type { AppView, UserProfile } from "../types";

interface TopBarProps {
  currentView: AppView;
  profile: UserProfile | null;
  onOpenMobileMenu: () => void;
  onNavigate: (view: AppView) => void;
  onLogout: () => void;
}

const VIEW_TITLES: Record<AppView, string> = {
  home: "学习首页",
  chat: "左题右聊练习工作台",
  bank: "真题题库",
  admin: "真题管理 · MinerU Studio",
  settings: "偏好设置",
  auth: "账户登录",
};

export function TopBar({
  currentView,
  profile,
  onOpenMobileMenu,
  onNavigate,
  onLogout,
}: TopBarProps) {
  const displayName = profile?.display_name || profile?.username || "未登录";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <button
          type="button"
          className="m3-icon-btn mobile-menu-btn"
          onClick={onOpenMobileMenu}
          title="打开菜单"
        >
          <Menu size={20} />
        </button>
        <div className="brand-title">
          <span>CET Agent</span>
          <span className="brand-pill">{VIEW_TITLES[currentView]}</span>
        </div>
      </div>

      <div className="top-bar-right">
        {profile ? (
          <>
            {profile.exam_level && (
              <span className="m3-pill-badge primary">{profile.exam_level}</span>
            )}
            <button
              type="button"
              className="avatar-btn"
              onClick={() => onNavigate("settings")}
              title="个人资料与设置"
            >
              <span
                className="avatar-circle"
                style={
                  profile.avatar_url
                    ? { backgroundImage: `url(${profile.avatar_url})` }
                    : { backgroundColor: profile.avatar_color || "#4285f4" }
                }
              >
                {!profile.avatar_url ? initial : null}
              </span>
              <span>{displayName}</span>
              <Settings size={14} style={{ opacity: 0.7 }} />
            </button>
            <button
              type="button"
              className="m3-icon-btn"
              title="退出登录"
              onClick={onLogout}
            >
              <LogOut size={18} />
            </button>
          </>
        ) : (
          <button
            type="button"
            className="m3-btn-tonal m3-btn-sm"
            onClick={() => onNavigate("auth")}
          >
            <LogIn size={15} />
            <span>登录 / 注册</span>
          </button>
        )}
      </div>
    </header>
  );
}
