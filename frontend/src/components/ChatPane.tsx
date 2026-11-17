import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  FilePlus2,
  Loader2,
  PanelLeftOpen,
  Send,
  Sparkles,
} from "lucide-react";
import type { ChatMessage, ModuleType, QuestionPublic } from "../types";
import { getToolLabel, MODULE_LABELS } from "../utils/format";
import { renderSanitizedMarkdown, stripToolMarkup } from "../utils/markdown";

interface ChatPaneProps {
  module: ModuleType;
  messages: ChatMessage[];
  isStreaming: boolean;
  hasActiveQuestion: boolean;
  isQuestionPaneOpen: boolean;
  onOpenQuestionPane: () => void;
  onOpenQuestionPicker: () => void;
  onSendMessage: (content: string) => void;
  activeQuestion: QuestionPublic | null;
}

const QUICK_CHIPS_BY_MODULE: Record<ModuleType, string[]> = {
  writing: ["给我出一道真题", "进入审题模式", "分析高分句型与结构", "帮我润色当前草稿"],
  reading: ["给我出一道真题", "总结同义替换", "分析长难句", "给出解题定位思路"],
  translation: ["给我出一道真题", "拆解核心词汇与句型", "提示主干翻译结构", "逐句精批我的译文"],
};

export function ChatPane({
  module,
  messages,
  isStreaming,
  hasActiveQuestion,
  isQuestionPaneOpen,
  onOpenQuestionPane,
  onOpenQuestionPicker,
  onSendMessage,
  activeQuestion,
}: ChatPaneProps) {
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isStreaming]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    onSendMessage(trimmed);
  };

  const quickChips = QUICK_CHIPS_BY_MODULE[module] || QUICK_CHIPS_BY_MODULE.reading;

  return (
    <section
      className={`workspace-right ${!hasActiveQuestion || !isQuestionPaneOpen ? "centered" : ""}`}
      aria-label="AI 教练对话区"
    >
      <header className="pane-header">
        <div className="pane-header-left">
          <span className="m3-pill-badge primary">
            <Sparkles size={13} />
            <span>{MODULE_LABELS[module]} · AI 教练</span>
          </span>
          {activeQuestion && !isQuestionPaneOpen && (
            <span
              style={{
                fontSize: 12,
                color: "var(--md-sys-color-on-surface-variant)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              当前题目：{activeQuestion.title}
            </span>
          )}
        </div>

        <div className="pane-header-right">
          <button
            type="button"
            className="m3-btn-tonal m3-btn-sm"
            onClick={onOpenQuestionPicker}
          >
            <FilePlus2 size={14} />
            <span>抽题</span>
          </button>

          {hasActiveQuestion && !isQuestionPaneOpen && (
            <button
              type="button"
              className="m3-btn-outlined m3-btn-sm"
              onClick={onOpenQuestionPane}
            >
              <PanelLeftOpen size={14} />
              <span>展开题板</span>
            </button>
          )}
        </div>
      </header>

      <div className="chat-messages" ref={listRef}>
        {messages.length === 0 ? (
          <div
            className="m3-card"
            style={{
              margin: "auto 0",
              textAlign: "center",
              padding: "32px 24px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Sparkles size={28} color="var(--md-sys-color-primary)" />
            <div style={{ fontWeight: 700, fontSize: 16 }}>
              准备好开始 {MODULE_LABELS[module]} 了吗？
            </div>
            <div
              style={{
                fontSize: 13,
                color: "var(--md-sys-color-on-surface-variant)",
                maxWidth: 460,
              }}
            >
              {hasActiveQuestion
                ? "左侧已为你载入真题。你可以直接做题提交，或者随时向我提问获取思路提示！"
                : "你可以点击右上角「抽题」从真题库选题，或直接告诉我“给我出一道真题”。"}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={msg.id ?? idx} className={`chat-row ${msg.role}`}>
              {msg.role === "assistant" &&
                msg.toolCalls &&
                msg.toolCalls.length > 0 && (
                  <div className="tool-status-list">
                    {msg.toolCalls.map((tc, tIdx) => (
                      <span
                        key={`${tc.name}-${tIdx}`}
                        className={`tool-status-chip ${tc.status}`}
                      >
                        {tc.status === "running" ? (
                          <Loader2 size={13} className="spin" />
                        ) : (
                          <CheckCircle2 size={13} />
                        )}
                        <span>{getToolLabel(tc.name, tc.status)}</span>
                      </span>
                    ))}
                  </div>
                )}

              {msg.role === "user" ? (
                <div className="chat-bubble user">{msg.content}</div>
              ) : (() => {
                const cleanedContent = stripToolMarkup(msg.content);
                const showLoading = isStreaming && idx === messages.length - 1;
                if (!cleanedContent && !showLoading) {
                  return null;
                }
                return (
                  <div
                    className="chat-bubble assistant"
                    style={
                      msg.isError
                        ? {
                            borderColor: "var(--md-sys-color-error)",
                            background: "var(--md-sys-color-error-container)",
                            color: "var(--md-sys-color-on-error-container)",
                          }
                        : undefined
                    }
                  >
                    {cleanedContent ? (
                      <div
                        dangerouslySetInnerHTML={{
                          __html: renderSanitizedMarkdown(cleanedContent),
                        }}
                      />
                    ) : (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 8,
                          fontSize: 13,
                          color: "var(--md-sys-color-on-surface-variant)",
                        }}
                      >
                        <Loader2 size={14} className="spin" />
                        <span>正在思考与组织回复...</span>
                      </span>
                    )}
                  </div>
                );
              })()}
            </div>
          ))
        )}
      </div>

      <div className="chat-composer-wrap">
        <div className="quick-chips-row">
          {quickChips.map((chip) => (
            <button
              key={chip}
              type="button"
              className="quick-chip"
              disabled={isStreaming}
              onClick={() => onSendMessage(chip)}
            >
              {chip}
            </button>
          ))}
        </div>

        <div className="chat-composer">
          <textarea
            rows={1}
            placeholder="输入你的问题、句子或思路（Enter 发送，Shift+Enter 换行）"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <button
            type="button"
            className="m3-btn-filled m3-btn-sm"
            disabled={!input.trim() || isStreaming}
            onClick={handleSubmit}
            title="发送"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </section>
  );
}
