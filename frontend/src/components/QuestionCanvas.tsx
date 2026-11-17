import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Lightbulb,
  PanelLeftClose,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  XCircle,
} from "lucide-react";
import type { QuestionPublic, SubmitQuestionResponse } from "../types";
import { countWords, formatDuration, formatQuestionTag } from "../utils/format";

interface QuestionCanvasProps {
  question: QuestionPublic;
  draftAnswer: unknown;
  onDraftChange: (nextDraft: unknown) => void;
  draftSaveStatus: "idle" | "saving" | "saved";
  onChangeQuestion: () => void;
  onCollapsePane: () => void;
  onAskHint: (currentDraft: unknown) => void;
  onSubmitGrading: (
    currentDraft: unknown,
    submitResult: SubmitQuestionResponse | null
  ) => void;
  onSubmitToApi: (userAnswers: unknown) => Promise<SubmitQuestionResponse>;
  isStreaming: boolean;
}

function normalizeAnswersMap(draft: unknown): Record<string, string> {
  if (draft && typeof draft === "object" && !Array.isArray(draft)) {
    const obj = draft as Record<string, unknown>;
    if (obj.answers && typeof obj.answers === "object") {
      const inner = obj.answers as Record<string, unknown>;
      return Object.fromEntries(
        Object.entries(inner).map(([k, v]) => [k, String(v ?? "")])
      );
    }
    return Object.fromEntries(
      Object.entries(obj)
        .filter(([k]) => k !== "text")
        .map(([k, v]) => [k, String(v ?? "")])
    );
  }
  return {};
}

function normalizeTextDraft(draft: unknown): string {
  if (typeof draft === "string") return draft;
  if (draft && typeof draft === "object" && !Array.isArray(draft)) {
    const obj = draft as Record<string, unknown>;
    if (typeof obj.text === "string") return obj.text;
  }
  return "";
}

export function QuestionCanvas({
  question,
  draftAnswer,
  onDraftChange,
  draftSaveStatus,
  onChangeQuestion,
  onCollapsePane,
  onAskHint,
  onSubmitGrading,
  onSubmitToApi,
  isStreaming,
}: QuestionCanvasProps) {
  const [seconds, setSeconds] = useState(0);
  const [timerRunning, setTimerRunning] = useState(true);
  const [highlightedParas, setHighlightedParas] = useState<Record<number, boolean>>({});
  const [activeBlankKey, setActiveBlankKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitQuestionResponse | null>(null);

  const prevQuestionIdRef = useRef<number>(question.id);
  useEffect(() => {
    if (prevQuestionIdRef.current !== question.id) {
      prevQuestionIdRef.current = question.id;
      setSeconds(0);
      setTimerRunning(true);
      setHighlightedParas({});
      setActiveBlankKey(null);
      setSubmitResult(null);
    }
  }, [question.id]);

  useEffect(() => {
    if (!timerRunning) return;
    const id = window.setInterval(() => {
      setSeconds((s) => s + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [timerRunning]);

  const toggleParaHighlight = (idx: number) => {
    setHighlightedParas((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const answersMap = useMemo(() => normalizeAnswersMap(draftAnswer), [draftAnswer]);
  const textDraft = useMemo(() => normalizeTextDraft(draftAnswer), [draftAnswer]);

  const setAnswerKey = (key: string, val: string) => {
    const next = { ...answersMap, [key]: val };
    onDraftChange(next);
  };

  const handleTextChange = (val: string) => {
    onDraftChange({ text: val });
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload =
        question.module === "reading" ? answersMap : { text: textDraft };
      const res = await onSubmitToApi(payload);
      setSubmitResult(res);
      onSubmitGrading(payload, res);
    } catch {
      // Fallback: still notify parent if needed
      onSubmitGrading(
        question.module === "reading" ? answersMap : { text: textDraft },
        null
      );
    } finally {
      setSubmitting(false);
    }
  };

  const c = question.content || {};

  // Normalized paragraphs for careful reading
  const carefulParagraphs = useMemo(() => {
    if (Array.isArray(c.paragraphs)) {
      return c.paragraphs.map((p) =>
        typeof p === "string" ? p : `${p.label ? `[${p.label}] ` : ""}${p.text}`
      );
    }
    if (typeof c.passage === "string") {
      return c.passage
        .split(/\n{2,}/)
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  }, [c.paragraphs, c.passage]);

  // Normalized word bank for banked_cloze
  const wordBankEntries = useMemo(() => {
    const wb = c.word_bank;
    if (!wb) return [] as Array<{ letter: string; word: string }>;
    if (Array.isArray(wb)) {
      return wb.map((item, idx) => {
        const defaultLetter = String.fromCharCode(65 + idx);
        if (typeof item === "string") {
          const m = item.match(/^([A-O])[.):\s]+(.+)$/i);
          if (m) return { letter: m[1].toUpperCase(), word: m[2].trim() };
          return { letter: defaultLetter, word: item };
        }
        return {
          letter: (item.letter || item.label || defaultLetter).toUpperCase(),
          word: item.word,
        };
      });
    }
    if (typeof wb === "object") {
      return Object.entries(wb).map(([k, v]) => ({
        letter: k.toUpperCase(),
        word: String(v),
      }));
    }
    return [];
  }, [c.word_bank]);

  const bankedClozeBlanks = useMemo(() => {
    const rawList = Array.isArray(c.blank_numbers) && c.blank_numbers.length > 0
      ? c.blank_numbers
      : Array.isArray(c.blanks) && c.blanks.length > 0
      ? c.blanks
      : null;
    if (rawList) {
      return rawList.map((b) => String(b));
    }
    // Extract blank numbers from passage markers like [26], (26), __26__, {{26}}
    const found = new Set<string>();
    const passageStr = typeof c.passage === "string" ? c.passage : "";
    const regex = /(?:\[(\d+)\]|\((\d+)\)|_{2,}(\d+)_{2,}|\{\{(\d+)\}\}|_{2,}\s*(\d+)\s*_{2,})/g;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(passageStr)) !== null) {
      const num = m[1] || m[2] || m[3] || m[4] || m[5];
      if (num) found.add(num);
    }
    if (found.size > 0) return Array.from(found);
    return Array.from({ length: 10 }, (_, i) => String(26 + i));
  }, [c.blank_numbers, c.blanks, c.passage]);

  // Normalized matching paragraphs
  const matchingParagraphs = useMemo(() => {
    const p = c.paragraphs;
    if (Array.isArray(p)) {
      return p.map((item, idx) => {
        if (typeof item === "string") {
          const m = item.match(/^\[?([A-O])\]?[.)\s:]+([\s\S]+)$/);
          if (m) return { label: m[1], text: m[2].trim() };
          return { label: String.fromCharCode(65 + idx), text: item };
        }
        return {
          label: item.label || String.fromCharCode(65 + idx),
          text: item.text,
        };
      });
    }
    if (p && typeof p === "object") {
      return Object.entries(p).map(([label, text]) => ({
        label,
        text: String(text),
      }));
    }
    return [];
  }, [c.paragraphs]);

  const usedLetters = useMemo(
    () => new Set(Object.values(answersMap).filter(Boolean)),
    [answersMap]
  );

  const renderBankedPassage = () => {
    const passageStr = typeof c.passage === "string" ? c.passage : "";
    if (!passageStr) return null;

    const tokenRegex =
      /(\[\d+\]\s*_{2,}|\(\d+\)\s*_{2,}|\[\d+\]|\(\d+\)|_{2,}\s*\d+\s*_{2,}|\{\{\d+\}\})/g;
    const parts = passageStr.split(tokenRegex);

    const hasInlineBlanks = parts.length > 1;

    return (
      <div className="passage-box">
        <div style={{ whiteSpace: "pre-wrap" }}>
          {hasInlineBlanks ? (
            parts.map((part, idx) => {
              const numMatch = part.match(/(\d+)/);
              const isBlank =
                /^(\[\d+\]\s*_{2,}|\(\d+\)\s*_{2,}|\[\d+\]|\(\d+\)|_{2,}\s*\d+\s*_{2,}|\{\{\d+\}\})$/.test(
                  part
                );

              if (isBlank && numMatch) {
                const key = numMatch[1];
                const chosenLetter = answersMap[key] || "";
                const chosenWord = wordBankEntries.find(
                  (w) => w.letter === chosenLetter
                )?.word;
                const isActive = activeBlankKey === key;
                const correctAns = submitResult?.answer?.correct_answers?.[key];
                const isRight =
                  correctAns && chosenLetter
                    ? chosenLetter.toUpperCase() === correctAns.toUpperCase()
                    : null;

                return (
                  <button
                    key={idx}
                    type="button"
                    className={`blank-pill ${isActive ? "active" : ""}`}
                    style={
                      submitResult && correctAns
                        ? {
                            borderColor: isRight
                              ? "var(--md-sys-color-success)"
                              : "var(--md-sys-color-error)",
                            background: isRight
                              ? "var(--md-sys-color-success-container)"
                              : "var(--md-sys-color-error-container)",
                            color: isRight
                              ? "var(--md-sys-color-on-success-container)"
                              : "var(--md-sys-color-on-error-container)",
                          }
                        : undefined
                    }
                    onClick={() => setActiveBlankKey(isActive ? null : key)}
                    title={
                      chosenLetter
                        ? `第${key}题：${chosenLetter} (${chosenWord || ""})，点击选择或替换`
                        : `点击选择第${key}题`
                    }
                  >
                    <span>({key})</span>
                    <span>
                      {chosenLetter
                        ? `${chosenLetter}${chosenWord ? ` ${chosenWord}` : ""}`
                        : "____"}
                    </span>
                    {submitResult && correctAns && !isRight && (
                      <span style={{ fontSize: 11 }}>→ {correctAns}</span>
                    )}
                  </button>
                );
              }
              return <Fragment key={idx}>{part}</Fragment>;
            })
          ) : (
            <div>{passageStr}</div>
          )}
        </div>
      </div>
    );
  };

  return (
    <section className="workspace-left" aria-label="题目工作区">
      <header className="pane-header">
        <div className="pane-header-left">
          <span className="m3-pill-badge primary">{formatQuestionTag(question)}</span>
          {draftSaveStatus !== "idle" && (
            <span
              style={{
                fontSize: 12,
                color: "var(--md-sys-color-on-surface-variant)",
              }}
            >
              {draftSaveStatus === "saving" ? "保存草稿中..." : "已自动保存"}
            </span>
          )}
        </div>

        <div className="pane-header-right">
          <div className="timer-pill" title="练习计时器">
            <Clock size={13} />
            <span>{formatDuration(seconds)}</span>
            <button
              type="button"
              style={{
                border: "none",
                background: "transparent",
                padding: 0,
                display: "inline-flex",
              }}
              onClick={() => setTimerRunning((r) => !r)}
              title={timerRunning ? "暂停计时" : "继续计时"}
            >
              {timerRunning ? <Pause size={12} /> : <Play size={12} />}
            </button>
            <button
              type="button"
              style={{
                border: "none",
                background: "transparent",
                padding: 0,
                display: "inline-flex",
              }}
              onClick={() => setSeconds(0)}
              title="重置计时"
            >
              <RotateCcw size={12} />
            </button>
          </div>

          <button
            type="button"
            className="m3-btn-tonal m3-btn-sm"
            onClick={onChangeQuestion}
            title="更换题目"
          >
            <RefreshCw size={13} />
            <span>更换题目</span>
          </button>

          <button
            type="button"
            className="m3-icon-btn"
            onClick={onCollapsePane}
            title="收起题板"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
      </header>

      <div className="question-scroll">
        <div>
          <h2 style={{ margin: "0 0 6px", fontSize: 18, fontWeight: 700 }}>
            {question.title}
          </h2>
          {question.topic && (
            <span className="m3-pill-badge">主题：{question.topic}</span>
          )}
        </div>

        {c.directions && (
          <div className="question-directions">
            <strong>Directions: </strong>
            {c.directions}
          </div>
        )}

        {/* Instant Submit Score Banner */}
        {submitResult && (
          <div
            className="m3-card"
            style={{
              padding: "14px 16px",
              background: "var(--md-sys-color-primary-container)",
              color: "var(--md-sys-color-on-primary-container)",
              border: "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                <Sparkles size={18} />
                {submitResult.total ? (
                  <span>
                    客观题得分：{submitResult.score ?? 0} / {submitResult.total}
                  </span>
                ) : (
                  <span>已提交作答，右侧 AI 教练正在为你批改点评</span>
                )}
              </div>
              <span style={{ fontSize: 12, opacity: 0.85 }}>
                Attempt #{submitResult.attempt_id}
              </span>
            </div>
            {submitResult.answer?.analysis && (
              <p style={{ margin: "8px 0 0", fontSize: 13 }}>{submitResult.answer.analysis}</p>
            )}
          </div>
        )}

        {/* ===== Careful Reading ===== */}
        {question.module === "reading" &&
          question.sub_type === "careful_reading" && (
            <>
              <div className="passage-box">
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--md-sys-color-on-surface-variant)",
                    marginBottom: 4,
                  }}
                >
                  提示：点击任意段落可高亮标记重点句
                </div>
                {carefulParagraphs.map((para, idx) => (
                  <p
                    key={idx}
                    className={`passage-para ${highlightedParas[idx] ? "highlighted" : ""}`}
                    onClick={() => toggleParaHighlight(idx)}
                  >
                    <span className="para-index">[{idx + 1}]</span>
                    {para}
                  </p>
                ))}
              </div>

              <div className="mcq-list">
                {(c.questions || []).map((item, idx) => {
                  const qKey = String(item.number ?? item.id ?? idx + 1);
                  const selected = answersMap[qKey] || "";
                  const correctAns = submitResult?.answer?.correct_answers?.[qKey];
                  const explanation = submitResult?.answer?.explanations?.[qKey];

                  const optionEntries: Array<[string, string]> = Array.isArray(item.options)
                    ? item.options.map((opt, oIdx) => {
                        const letter = String.fromCharCode(65 + oIdx);
                        const cleaned = String(opt).replace(/^[A-D][.):\s]+/i, "");
                        return [letter, cleaned];
                      })
                    : Object.entries(item.options || {});

                  return (
                    <div key={qKey} className="mcq-card">
                      <div className="mcq-stem">
                        {qKey}. {item.stem || item.question}
                      </div>
                      <div className="mcq-options">
                        {optionEntries.map(([letter, text]) => {
                          const isSelected =
                            selected.toUpperCase() === letter.toUpperCase();
                          const isCorrectOption =
                            correctAns &&
                            correctAns.toUpperCase() === letter.toUpperCase();
                          const isWrongSelected =
                            submitResult && isSelected && correctAns && !isCorrectOption;

                          return (
                            <button
                              key={letter}
                              type="button"
                              className={`mcq-option ${isSelected ? "selected" : ""} ${
                                submitResult && isCorrectOption ? "correct" : ""
                              } ${isWrongSelected ? "wrong" : ""}`}
                              onClick={() => setAnswerKey(qKey, letter)}
                            >
                              <strong>{letter}.</strong>
                              <span style={{ flex: 1 }}>{text}</span>
                              {submitResult && isCorrectOption && (
                                <CheckCircle2 size={16} />
                              )}
                              {isWrongSelected && <XCircle size={16} />}
                            </button>
                          );
                        })}
                      </div>
                      {submitResult && explanation && (
                        <div
                          style={{
                            fontSize: 13,
                            padding: "8px 10px",
                            borderRadius: 8,
                            background: "var(--md-sys-color-surface-container)",
                          }}
                        >
                          <strong>解析：</strong>
                          {explanation}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}

        {/* ===== Banked Cloze ===== */}
        {question.module === "reading" && question.sub_type === "banked_cloze" && (
          <>
            {renderBankedPassage()}

            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 8,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span>
                  备选词库（15选10）
                  {activeBlankKey
                    ? ` · 当前选中第 (${activeBlankKey}) 空，点击下方词汇填入`
                    : " · 先点击上方空位，再点击词库词汇"}
                </span>
                {activeBlankKey && answersMap[activeBlankKey] && (
                  <button
                    type="button"
                    className="m3-chip-sm"
                    onClick={() => setAnswerKey(activeBlankKey, "")}
                  >
                    清空 ({activeBlankKey})
                  </button>
                )}
              </div>
              <div className="word-bank-grid">
                {wordBankEntries.map(({ letter, word }) => {
                  const isUsed = usedLetters.has(letter);
                  return (
                    <button
                      key={letter}
                      type="button"
                      className={`word-chip ${isUsed ? "used" : ""}`}
                      onClick={() => {
                        const target =
                          activeBlankKey ||
                          bankedClozeBlanks.find((b) => !answersMap[b]) ||
                          bankedClozeBlanks[0];
                        if (target) {
                          setAnswerKey(target, letter);
                          // Advance to next empty blank
                          const nextEmpty = bankedClozeBlanks.find(
                            (b) => b !== target && !answersMap[b]
                          );
                          setActiveBlankKey(nextEmpty || null);
                        }
                      }}
                    >
                      <strong>{letter})</strong>
                      <span>{word}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Compact blank grid for quick review/selection */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
                gap: 8,
              }}
            >
              {bankedClozeBlanks.map((b) => (
                <div
                  key={b}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 13,
                  }}
                >
                  <span style={{ fontWeight: 600, minWidth: 28 }}>({b})</span>
                  <select
                    className="m3-select"
                    style={{ padding: "5px 8px", fontSize: 13 }}
                    value={answersMap[b] || ""}
                    onChange={(e) => setAnswerKey(b, e.target.value)}
                  >
                    <option value="">--</option>
                    {wordBankEntries.map((w) => (
                      <option key={w.letter} value={w.letter}>
                        {w.letter} {w.word}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ===== Matching ===== */}
        {question.module === "reading" && question.sub_type === "matching" && (
          <>
            <div className="passage-box">
              {c.title && (
                <h3 style={{ margin: "0 0 6px", fontSize: 16 }}>{String(c.title)}</h3>
              )}
              {matchingParagraphs.map((para) => (
                <div key={para.label} style={{ fontSize: 14 }}>
                  <span className="para-index">[{para.label}]</span>
                  <span>{para.text}</span>
                </div>
              ))}
            </div>

            <div className="mcq-list">
              {(c.statements || []).map((st, idx) => {
                const key = String(st.number ?? st.id ?? idx + 1);
                const selected = answersMap[key] || "";
                const correctAns = submitResult?.answer?.correct_answers?.[key];
                const isRight =
                  submitResult &&
                  correctAns &&
                  selected.toUpperCase() === correctAns.toUpperCase();

                return (
                  <div
                    key={key}
                    className="mcq-card"
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <div style={{ flex: 1, fontSize: 14 }}>
                      <strong>{key}. </strong>
                      {st.text}
                      {submitResult && correctAns && (
                        <div
                          style={{
                            marginTop: 4,
                            fontSize: 12,
                            fontWeight: 600,
                            color: isRight
                              ? "var(--md-sys-color-success)"
                              : "var(--md-sys-color-error)",
                          }}
                        >
                          {isRight ? "回答正确" : `正确答案：${correctAns}`}
                        </div>
                      )}
                    </div>
                    <select
                      className="m3-select"
                      style={{ width: 96 }}
                      value={selected}
                      onChange={(e) => setAnswerKey(key, e.target.value)}
                    >
                      <option value="">段落</option>
                      {matchingParagraphs.map((p) => (
                        <option key={p.label} value={p.label}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* ===== Writing & Translation ===== */}
        {(question.module === "writing" || question.module === "translation") && (
          <>
            <div className="passage-box">
              {c.prompt && <div style={{ whiteSpace: "pre-wrap" }}>{c.prompt}</div>}
              {(c.source_text || c.chinese_text) && (
                <div style={{ whiteSpace: "pre-wrap", fontSize: 15 }}>
                  {c.source_text || c.chinese_text}
                </div>
              )}
              {c.requirements && (
                <div
                  style={{
                    fontSize: 13,
                    color: "var(--md-sys-color-on-surface-variant)",
                  }}
                >
                  {c.requirements}
                </div>
              )}
              {c.word_limit && (
                <div style={{ fontSize: 12 }}>
                  <span className="m3-pill-badge">字数要求：{c.word_limit}</span>
                </div>
              )}
              {Array.isArray(c.hints) && c.hints.length > 0 && (
                <div
                  style={{
                    fontSize: 13,
                    padding: "10px 12px",
                    borderRadius: 10,
                    background: "var(--md-sys-color-surface-container)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}
                >
                  <strong>参考词汇提示：</strong>
                  {c.hints.map((h, i) => (
                    <span key={i}>• {h}</span>
                  ))}
                </div>
              )}
              {c.image_url && (
                <img
                  src={c.image_url}
                  alt="写作题目配图"
                  style={{
                    maxWidth: "100%",
                    borderRadius: 12,
                    border: "1px solid var(--md-sys-color-outline-variant)",
                  }}
                />
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: 13,
                }}
              >
                <span style={{ fontWeight: 600 }}>
                  {question.module === "writing" ? "作文草稿区" : "译文作答区"}
                </span>
                <span className="m3-pill-badge">
                  词数统计：{countWords(textDraft)} words
                </span>
              </div>
              <textarea
                className="m3-textarea"
                rows={12}
                placeholder={
                  question.module === "writing"
                    ? "在这里撰写你的英语作文，系统会自动保存草稿..."
                    : "在这里输入你的英文翻译，系统会自动保存草稿..."
                }
                value={textDraft}
                onChange={(e) => handleTextChange(e.target.value)}
                style={{ minHeight: 240, lineHeight: 1.7, resize: "vertical" }}
              />
            </div>
          </>
        )}
      </div>

      <footer className="pane-footer">
        <button
          type="button"
          className="m3-btn-outlined"
          disabled={isStreaming}
          onClick={() =>
            onAskHint(question.module === "reading" ? answersMap : { text: textDraft })
          }
        >
          <Lightbulb size={16} />
          <span>向教练求提示</span>
        </button>

        <button
          type="button"
          className="m3-btn-filled"
          disabled={submitting || isStreaming}
          onClick={handleSubmit}
        >
          <Send size={16} />
          <span>{submitting ? "提交中..." : "提交批改"}</span>
        </button>
      </footer>
    </section>
  );
}
