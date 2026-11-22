import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api/client";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { MobileBottomNav } from "./components/MobileBottomNav";
import { Sidebar } from "./components/Sidebar";
import { ToastMessage, ToastStack } from "./components/Toast";
import { TopBar } from "./components/TopBar";
import type {
  AppView,
  AuthResponse,
  GroupedSessions,
  ModuleType,
  QuestionPublic,
  SessionDetail,
  SessionSummary,
  UserProfile,
} from "./types";
import { AdminStudioView } from "./views/AdminStudioView";
import { AuthView } from "./views/AuthView";
import { HomeView } from "./views/HomeView";
import { QuestionBankView } from "./views/QuestionBankView";
import { SettingsView } from "./views/SettingsView";
import { WorkspaceView } from "./views/WorkspaceView";

const EMPTY_SESSIONS: GroupedSessions = {
  writing: [],
  reading: [],
  translation: [],
};

function getInitialTheme(): "light" | "dark" {
  const saved = localStorage.getItem("cet_theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function App() {
  const [theme, setTheme] = useState<"light" | "dark">(getInitialTheme);
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [sessions, setSessions] = useState<GroupedSessions>(EMPTY_SESSIONS);

  const [currentView, setCurrentView] = useState<AppView>("home");
  const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const toastSeq = useRef(1);

  const [confirmTarget, setConfirmTarget] = useState<SessionSummary | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("cet_theme", theme);
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute("content", theme === "dark" ? "#121318" : "#faf9fd");
    }
  }, [theme]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileMenuOpen]);

  const addToast = useCallback(
    (text: string, type: "info" | "success" | "error" = "info") => {
      const id = toastSeq.current++;
      setToasts((prev) => [...prev, { id, text, type }]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3200);
    },
    []
  );

  const loadUserData = useCallback(async () => {
    try {
      const prof = await api.getProfile();
      setProfile(prof);
      try {
        const sess = await api.getSessions();
        setSessions(sess);
      } catch {
        setSessions(EMPTY_SESSIONS);
      }
    } catch {
      setProfile(null);
      setSessions(EMPTY_SESSIONS);
    } finally {
      setAuthChecked(true);
    }
  }, []);

  useEffect(() => {
    void loadUserData();
  }, [loadUserData]);

  // Global shortcut: Ctrl+Shift+O -> New Practice
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        setCurrentView("home");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const refreshSessions = async () => {
    try {
      const sess = await api.getSessions();
      setSessions(sess);
    } catch {
      // ignore
    }
  };

  const handleStartModule = async (module: ModuleType, initialPrompt?: string) => {
    if (!profile) {
      setPendingAction(() => () => {
        void handleStartModule(module, initialPrompt);
      });
      setCurrentView("auth");
      addToast("请先登录以保存练习记录", "info");
      return;
    }

    try {
      const created = await api.createSession(module);
      setActiveSession(created);
      setPendingPrompt(initialPrompt || null);
      setCurrentView("chat");
      void refreshSessions();
    } catch (err) {
      addToast(
        err instanceof Error ? err.message : "创建练习会话失败",
        "error"
      );
    }
  };

  const handleStartQuestion = async (question: QuestionPublic) => {
    if (!profile) {
      setPendingAction(() => () => {
        void handleStartQuestion(question);
      });
      setCurrentView("auth");
      addToast("请先登录以开始真题练习", "info");
      return;
    }

    try {
      const created = await api.createSession(question.module, question.id);
      if (!created.active_question) {
        created.active_question = question;
        created.active_question_id = question.id;
      }
      setActiveSession(created);
      setPendingPrompt(null);
      setCurrentView("chat");
      void refreshSessions();
    } catch (err) {
      addToast(
        err instanceof Error ? err.message : "载入真题会话失败",
        "error"
      );
    }
  };

  const handleSelectSession = async (id: number) => {
    try {
      const detail = await api.getSession(id);
      setActiveSession(detail);
      setPendingPrompt(null);
      setCurrentView("chat");
    } catch (err) {
      addToast(
        err instanceof Error ? err.message : "加载会话失败",
        "error"
      );
    }
  };

  const handleDeleteConfirm = async () => {
    const target = confirmTarget;
    setConfirmTarget(null);
    if (!target) return;
    try {
      await api.deleteSession(target.id);
      if (activeSession?.id === target.id) {
        setActiveSession(null);
        if (currentView === "chat") setCurrentView("home");
      }
      await refreshSessions();
      addToast("会话已删除", "info");
    } catch (err) {
      addToast(
        err instanceof Error ? err.message : "删除会话失败",
        "error"
      );
    }
  };

  const handleAuthSuccess = async (auth: AuthResponse) => {
    addToast(`欢迎回来，${auth.username}`, "success");
    await loadUserData();
    if (pendingAction) {
      const fn = pendingAction;
      setPendingAction(null);
      fn();
    } else {
      setCurrentView("home");
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    setProfile(null);
    setSessions(EMPTY_SESSIONS);
    setActiveSession(null);
    setCurrentView("home");
    addToast("已退出登录", "info");
  };

  const handleNavigate = (view: AppView) => {
    if (view === "admin" && profile?.role !== "admin") {
      addToast("仅管理员可访问真题管理", "error");
      return;
    }
    setCurrentView(view);
  };

  const showMobileBottomNav = currentView !== "chat" && currentView !== "auth";

  return (
    <div className="app-shell">
      <Sidebar
        expanded={sidebarExpanded}
        mobileOpen={mobileMenuOpen}
        onToggleExpand={() => setSidebarExpanded((e) => !e)}
        onCloseMobile={() => setMobileMenuOpen(false)}
        currentView={currentView}
        onNavigate={handleNavigate}
        onNewPractice={() => setCurrentView("home")}
        sessions={sessions}
        activeSessionId={activeSession?.id ?? null}
        onSelectSession={(id) => void handleSelectSession(id)}
        onDeleteSession={(s) => setConfirmTarget(s)}
        profile={profile}
        theme={theme}
        onToggleTheme={() =>
          setTheme((t) => (t === "light" ? "dark" : "light"))
        }
        onLogout={() => void handleLogout()}
      />

      <main className="main-area">
        <TopBar
          currentView={currentView}
          activeModule={activeSession?.module ?? null}
          profile={profile}
          onOpenMobileMenu={() => setMobileMenuOpen((o) => !o)}
          onNavigate={handleNavigate}
          onLogout={() => void handleLogout()}
        />

        <div
          className={`view-body ${
            showMobileBottomNav ? "with-mobile-bottom-nav" : ""
          }`}
        >
          {!authChecked ? (
            <div style={{ padding: 48, textAlign: "center", opacity: 0.7 }}>
              正在初始化 CET Agent 工作台...
            </div>
          ) : currentView === "auth" ? (
            <AuthView
              onSuccess={(auth) => void handleAuthSuccess(auth)}
              onBackHome={() => setCurrentView("home")}
            />
          ) : currentView === "chat" && activeSession ? (
            <WorkspaceView
              session={activeSession}
              pendingPrompt={pendingPrompt}
              onClearPendingPrompt={() => setPendingPrompt(null)}
              onSessionUpdated={(updated) => setActiveSession(updated)}
              onToast={addToast}
            />
          ) : currentView === "bank" ? (
            <QuestionBankView
              defaultExamLevel={profile?.exam_level}
              onStartQuestion={(q) => void handleStartQuestion(q)}
            />
          ) : currentView === "admin" && profile?.role === "admin" ? (
            <AdminStudioView onToast={addToast} />
          ) : currentView === "settings" ? (
            <SettingsView
              profile={profile}
              onProfileUpdated={(p) => setProfile(p)}
              onBackHome={() => setCurrentView("home")}
              onLogout={() => void handleLogout()}
              onRequireLogin={() => setCurrentView("auth")}
              onToast={addToast}
            />
          ) : (
            <HomeView
              profile={profile}
              onStartModule={(m, p) => void handleStartModule(m, p)}
              onStartQuestion={(q) => void handleStartQuestion(q)}
              onOpenBank={() => setCurrentView("bank")}
              onOpenSettings={() => setCurrentView("settings")}
            />
          )}
        </div>

        {showMobileBottomNav && (
          <MobileBottomNav
            currentView={currentView}
            isAdmin={profile?.role === "admin"}
            hasActiveSession={Boolean(activeSession)}
            isLoggedIn={Boolean(profile)}
            onNavigate={handleNavigate}
            onResumeSession={() => {
              if (activeSession) setCurrentView("chat");
            }}
          />
        )}
      </main>

      <ConfirmDialog
        open={Boolean(confirmTarget)}
        title="删除练习会话"
        message={`确定要删除会话「${confirmTarget?.title || "新练习"}」吗？此操作不可撤销。`}
        confirmLabel="删除"
        onConfirm={() => void handleDeleteConfirm()}
        onCancel={() => setConfirmTarget(null)}
      />

      <ToastStack
        toasts={toasts}
        onDismiss={(id) =>
          setToasts((prev) => prev.filter((t) => t.id !== id))
        }
      />
    </div>
  );
}
export default App;
