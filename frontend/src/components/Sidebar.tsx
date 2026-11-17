import {
  BookOpen,
  FileSpreadsheet,
  Home,
  Languages,
  Menu,
  MessageSquare,
  Moon,
  PenTool,
  Plus,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
} from "lucide-react";
import type {
  AppView,
  GroupedSessions,
  ModuleType,
  SessionSummary,
  UserProfile,
} from "../types";
import { useState } from "react";

interface SidebarProps {
  expanded: boolean;
  mobileOpen: boolean;
  onToggleExpand: () => void;
  onCloseMobile: () => void;
  currentView: AppView;
  onNavigate: (view: AppView) => void;
  onNewPractice: () => void;
  sessions: GroupedSessions;
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onDeleteSession: (session: SessionSummary) => void;
  profile: UserProfile | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const MODULE_ICON: Record<ModuleType, JSX.Element> = {
  writing: <PenTool size={15} />,
  reading: <BookOpen size={15} />,
  translation: <Languages size={15} />,
};

export function Sidebar({
  expanded,
  mobileOpen,
  onToggleExpand,
  onCloseMobile,
  currentView,
  onNavigate,
  onNewPractice,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  profile,
  theme,
  onToggleTheme,
}: SidebarProps) {
  const [moduleFilter, setModuleFilter] = useState<"all" | ModuleType>("all");

  const allSessions: Array<SessionSummary & { module: ModuleType }> = [
    ...(moduleFilter === "all" || moduleFilter === "writing"
      ? sessions.writing.map((s) => ({ ...s, module: "writing" as ModuleType }))
      : []),
    ...(moduleFilter === "all" || moduleFilter === "reading"
      ? sessions.reading.map((s) => ({ ...s, module: "reading" as ModuleType }))
      : []),
    ...(moduleFilter === "all" || moduleFilter === "translation"
      ? sessions.translation.map((s) => ({ ...s, module: "translation" as ModuleType }))
      : []),
  ].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const isAdmin = profile?.role === "admin";

  return (
    <aside
      className={`nav-rail ${expanded ? "expanded" : ""} ${
        mobileOpen ? "mobile-open" : ""
      }`}
    >
      <div className="nav-rail-header">
        <button
          type="button"
          className="m3-icon-btn"
          title={expanded ? "收起菜单" : "展开菜单"}
          onClick={onToggleExpand}
        >
          <Menu size={20} />
        </button>
        {expanded && (
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.01em" }}>
            CET Agent
          </span>
        )}
      </div>

      <button
        type="button"
        className="m3-fab"
        title="发起新练习 (Ctrl+Shift+O)"
        onClick={() => {
          onNewPractice();
          onCloseMobile();
        }}
      >
        <Plus size={18} />
        {(expanded || mobileOpen) && <span>发起新练习</span>}
      </button>

      <nav className="nav-destinations" aria-label="主导航">
        <button
          type="button"
          className={`nav-item ${currentView === "home" ? "active" : ""}`}
          title="首页"
          onClick={() => {
            onNavigate("home");
            onCloseMobile();
          }}
        >
          <Home size={18} />
          {(expanded || mobileOpen) && <span>首页工作台</span>}
        </button>

        <button
          type="button"
          className={`nav-item ${currentView === "bank" ? "active" : ""}`}
          title="真题题库"
          onClick={() => {
            onNavigate("bank");
            onCloseMobile();
          }}
        >
          <FileSpreadsheet size={18} />
          {(expanded || mobileOpen) && <span>真题题库</span>}
        </button>

        {isAdmin && (
          <button
            type="button"
            className={`nav-item ${currentView === "admin" ? "active" : ""}`}
            title="真题管理"
            onClick={() => {
              onNavigate("admin");
              onCloseMobile();
            }}
          >
            <ShieldCheck size={18} />
            {(expanded || mobileOpen) && (
              <>
                <span>真题管理</span>
                <span className="nav-badge">Admin</span>
              </>
            )}
          </button>
        )}
      </nav>

      {(expanded || mobileOpen) && (
        <>
          <div className="nav-divider" />
          <div className="nav-sessions-section">
            <div className="nav-filter-chips">
              {(
                [
                  ["all", "全部"],
                  ["writing", "写作"],
                  ["reading", "阅读"],
                  ["translation", "翻译"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={`m3-chip-sm ${moduleFilter === key ? "active" : ""}`}
                  onClick={() => setModuleFilter(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="session-list">
              {allSessions.length === 0 ? (
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--md-sys-color-on-surface-variant)",
                    padding: "12px 8px",
                  }}
                >
                  {profile ? "暂无练习记录" : "登录后查看历史练习"}
                </div>
              ) : (
                allSessions.map((s) => (
                  <div
                    key={s.id}
                    className={`session-item ${
                      currentView === "chat" && activeSessionId === s.id
                        ? "active"
                        : ""
                    }`}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      onSelectSession(s.id);
                      onCloseMobile();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        onSelectSession(s.id);
                        onCloseMobile();
                      }
                    }}
                  >
                    {MODULE_ICON[s.module] ?? <MessageSquare size={15} />}
                    <span className="session-title" title={s.title}>
                      {s.title || "新练习"}
                    </span>
                    <button
                      type="button"
                      className="session-delete-btn"
                      title="删除会话"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(s);
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      <div className="nav-footer" style={{ marginTop: expanded || mobileOpen ? 0 : "auto" }}>
        <button
          type="button"
          className="nav-item"
          title={theme === "light" ? "切换深色模式" : "切换浅色模式"}
          onClick={onToggleTheme}
        >
          {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          {(expanded || mobileOpen) && (
            <span>{theme === "light" ? "深色主题" : "浅色主题"}</span>
          )}
        </button>

        <button
          type="button"
          className={`nav-item ${currentView === "settings" ? "active" : ""}`}
          title="设置"
          onClick={() => {
            onNavigate("settings");
            onCloseMobile();
          }}
        >
          <Settings size={18} />
          {(expanded || mobileOpen) && <span>设置与账户</span>}
        </button>
      </div>
    </aside>
  );
}
