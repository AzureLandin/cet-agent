import { useEffect, useRef, useState } from "react";
import { BookOpen, Loader2, MessageSquare } from "lucide-react";
import * as api from "../api/client";
import { ChatPane } from "../components/ChatPane";
import { QuestionCanvas } from "../components/QuestionCanvas";
import { QuestionPickerModal } from "../components/QuestionPickerModal";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type {
  ChatMessage,
  QuestionPublic,
  SessionDetail,
  SubmitQuestionResponse,
} from "../types";

interface WorkspaceViewProps {
  session: SessionDetail;
  pendingPrompt?: string | null;
  onClearPendingPrompt: () => void;
  onSessionUpdated: (updated: SessionDetail) => void;
  onToast: (text: string, type?: "info" | "success" | "error") => void;
}

export function WorkspaceView({
  session,
  pendingPrompt,
  onClearPendingPrompt,
  onSessionUpdated,
  onToast,
}: WorkspaceViewProps) {
  const isMobile = useMediaQuery("(max-width: 960px)");
  const [messages, setMessages] = useState<ChatMessage[]>(session.messages || []);
  const [activeQuestion, setActiveQuestion] = useState<QuestionPublic | null>(
    session.active_question || null
  );
  const [draftAnswer, setDraftAnswer] = useState<unknown>(session.draft_answer ?? null);
  const [isQuestionPaneOpen, setIsQuestionPaneOpen] = useState<boolean>(
    Boolean(session.active_question)
  );
  const [mobileTab, setMobileTab] = useState<"question" | "chat">(() =>
    session.active_question && !pendingPrompt && (session.messages?.length ?? 0) === 0
      ? "question"
      : "chat"
  );
  const [hasUnreadQuestion, setHasUnreadQuestion] = useState(false);
  const [hasUnreadChat, setHasUnreadChat] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [draftSaveStatus, setDraftSaveStatus] = useState<
    "idle" | "saving" | "saved"
  >("idle");

  const abortRef = useRef<AbortController | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const sentPendingRef = useRef<string | null>(null);
  const mobileTabRef = useRef<"question" | "chat">(mobileTab);
  const isMobileRef = useRef<boolean>(isMobile);

  useEffect(() => {
    mobileTabRef.current = mobileTab;
  }, [mobileTab]);

  useEffect(() => {
    isMobileRef.current = isMobile;
  }, [isMobile]);

  // Sync when switching sessions
  useEffect(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setMessages(session.messages || []);
    setActiveQuestion(session.active_question || null);
    setDraftAnswer(session.draft_answer ?? null);
    setIsQuestionPaneOpen(Boolean(session.active_question));
    setMobileTab(
      session.active_question && !pendingPrompt && (session.messages?.length ?? 0) === 0
        ? "question"
        : "chat"
    );
    setHasUnreadQuestion(false);
    setHasUnreadChat(false);
    setDraftSaveStatus("idle");
  }, [session.id]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, []);

  const handleSendMessage = async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || isStreaming) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      toolCalls: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    await api.sendMessageStream(
      session.id,
      trimmed,
      {
        onToolCall: (tc) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = m.toolCalls || [];
              const idx = existing.findIndex((t) => t.name === tc.name && t.status === "running");
              if (idx >= 0) {
                const updated = [...existing];
                updated[idx] = tc;
                return { ...m, toolCalls: updated };
              }
              return { ...m, toolCalls: [...existing, tc] };
            })
          );
        },
        onQuestionLoaded: (question) => {
          setActiveQuestion(question);
          setIsQuestionPaneOpen(true);
          setDraftAnswer(null);
          if (isMobileRef.current && mobileTabRef.current === "chat") {
            setHasUnreadQuestion(true);
          }
          onSessionUpdated({
            ...session,
            active_question_id: question.id,
            active_question: question,
            draft_answer: null,
          });
          onToast(`已加载真题：${question.title}`, "success");
        },
        onToken: (token) => {
          if (isMobileRef.current && mobileTabRef.current === "question") {
            setHasUnreadChat(true);
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + token }
                : m
            )
          );
        },
        onDone: () => {
          setIsStreaming(false);
          if (isMobileRef.current && mobileTabRef.current === "question") {
            setHasUnreadChat(true);
          }
          // Mark any remaining running tool calls as done
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId && m.toolCalls
                ? {
                    ...m,
                    toolCalls: m.toolCalls.map((t) => ({ ...t, status: "done" })),
                  }
                : m
            )
          );
        },
        onError: (err) => {
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    isError: true,
                    content: m.content
                      ? `${m.content}\n\n[错误] ${err.message}`
                      : `[错误] ${err.message}`,
                  }
                : m
            )
          );
          onToast(err.message, "error");
        },
      },
      controller.signal
    );
  };

  // Trigger initial pendingPrompt if navigated from Home quick composer
  useEffect(() => {
    if (pendingPrompt && sentPendingRef.current !== `${session.id}:${pendingPrompt}`) {
      sentPendingRef.current = `${session.id}:${pendingPrompt}`;
      onClearPendingPrompt();
      void handleSendMessage(pendingPrompt);
    }
  }, [pendingPrompt, session.id]);

  const handleDraftChange = (nextDraft: unknown) => {
    setDraftAnswer(nextDraft);
    setDraftSaveStatus("saving");
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(async () => {
      try {
        await api.updateSessionWorkspace(session.id, { draft_answer: nextDraft });
        setDraftSaveStatus("saved");
      } catch {
        setDraftSaveStatus("idle");
      }
    }, 600);
  };

  const handleSelectQuestion = async (question: QuestionPublic) => {
    setPickerOpen(false);
    try {
      const updated = await api.updateSessionWorkspace(session.id, {
        active_question_id: question.id,
        draft_answer: null,
      });
      setActiveQuestion(updated.active_question || question);
      setDraftAnswer(updated.draft_answer ?? null);
      setIsQuestionPaneOpen(true);
      if (isMobile) {
        setMobileTab("question");
        setHasUnreadQuestion(false);
      }
      onSessionUpdated({
        ...session,
        active_question_id: updated.active_question_id,
        active_question: updated.active_question || question,
        draft_answer: updated.draft_answer,
      });
      onToast(`已载入题目：${question.title}`, "success");
    } catch (err) {
      onToast(
        err instanceof Error ? err.message : "载入题目失败",
        "error"
      );
    }
  };

  const handleAskHint = (currentDraft: unknown) => {
    if (!activeQuestion) return;
    if (isMobile) {
      setMobileTab("chat");
      setHasUnreadChat(false);
    }
    const prompt = `我正在做《${activeQuestion.title}》（题号ID: ${activeQuestion.id}）。请先不要直接公布完整答案，给我一些解题提示、定位线索或写作/翻译切入点。我目前的作答进度是：${JSON.stringify(
      currentDraft ?? {}
    )}`;
    void handleSendMessage(prompt);
  };

  const handleSubmitGrading = (
    currentDraft: unknown,
    submitResult: SubmitQuestionResponse | null
  ) => {
    if (!activeQuestion) return;
    if (isMobile) {
      if (activeQuestion.module === "reading" && submitResult?.total) {
        onToast(
          `客观题得分 ${submitResult.score ?? 0}/${submitResult.total}，AI 教练正在精讲`,
          "success"
        );
      }
      setMobileTab("chat");
      setHasUnreadChat(false);
    }
    if (activeQuestion.module === "reading") {
      const scoreSummary = submitResult
        ? `系统客观题判分结果为 ${submitResult.score ?? 0}/${submitResult.total ?? 0}。`
        : "";
      const prompt = `我已完成《${activeQuestion.title}》（题号ID: ${activeQuestion.id}）的作答并提交。${scoreSummary}我的作答是：${JSON.stringify(
        currentDraft ?? {}
      )}。请帮我逐题精讲错题原因、原文定位句以及核心同义替换！`;
      void handleSendMessage(prompt);
    } else {
      const text =
        typeof (currentDraft as { text?: string })?.text === "string"
          ? (currentDraft as { text: string }).text
          : "";
      const prompt = `我已完成《${activeQuestion.title}》（题号ID: ${activeQuestion.id}）的作答并提交批改，请结合评分标准对我的作答进行逐项点评、纠错和升格范文指导：\n\n${
        text || "（我暂时提交了空白草稿，请先给出写作/翻译高分框架指导）"
      }`;
      void handleSendMessage(prompt);
    }
  };

  const switchMobileTab = (tab: "question" | "chat") => {
    setMobileTab(tab);
    if (tab === "question") {
      setHasUnreadQuestion(false);
    } else {
      setHasUnreadChat(false);
    }
  };

  return (
    <div className="workspace-shell">
      {isMobile && activeQuestion && (
        <div
          className="mobile-workspace-tabs"
          role="tablist"
          aria-label="工作区切换"
        >
          <button
            type="button"
            role="tab"
            aria-selected={mobileTab === "question"}
            className={`mobile-workspace-tab ${
              mobileTab === "question" ? "active" : ""
            }`}
            onClick={() => switchMobileTab("question")}
          >
            <BookOpen size={15} />
            <span>真题作答</span>
            {hasUnreadQuestion && <span className="mobile-tab-dot" />}
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={mobileTab === "chat"}
            className={`mobile-workspace-tab ${
              mobileTab === "chat" ? "active" : ""
            }`}
            onClick={() => switchMobileTab("chat")}
          >
            {isStreaming ? (
              <Loader2 size={15} className="spin" />
            ) : (
              <MessageSquare size={15} />
            )}
            <span>AI 教练</span>
            {hasUnreadChat && !isStreaming && <span className="mobile-tab-dot" />}
          </button>
        </div>
      )}

      {activeQuestion && (isMobile || isQuestionPaneOpen) && (
        <QuestionCanvas
          question={activeQuestion}
          draftAnswer={draftAnswer}
          onDraftChange={handleDraftChange}
          draftSaveStatus={draftSaveStatus}
          onChangeQuestion={() => setPickerOpen(true)}
          onCollapsePane={() => setIsQuestionPaneOpen(false)}
          onAskHint={handleAskHint}
          onSubmitGrading={handleSubmitGrading}
          onSubmitToApi={(userAnswers) =>
            api.submitQuestion(activeQuestion.id, userAnswers, session.id)
          }
          isStreaming={isStreaming}
          isMobile={isMobile}
          hiddenOnMobile={isMobile && mobileTab !== "question"}
        />
      )}

      <ChatPane
        module={session.module}
        messages={messages}
        isStreaming={isStreaming}
        hasActiveQuestion={Boolean(activeQuestion)}
        isQuestionPaneOpen={isQuestionPaneOpen}
        onOpenQuestionPane={() => setIsQuestionPaneOpen(true)}
        onOpenQuestionPicker={() => setPickerOpen(true)}
        onSendMessage={handleSendMessage}
        activeQuestion={activeQuestion}
        isMobile={isMobile}
        hiddenOnMobile={isMobile && Boolean(activeQuestion) && mobileTab !== "chat"}
        hasUnreadQuestion={hasUnreadQuestion}
        onSwitchToQuestion={() => switchMobileTab("question")}
      />

      <QuestionPickerModal
        open={pickerOpen}
        defaultModule={session.module}
        onClose={() => setPickerOpen(false)}
        onSelect={handleSelectQuestion}
      />
    </div>
  );
}
