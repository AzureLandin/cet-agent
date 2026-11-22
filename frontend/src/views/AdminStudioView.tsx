import { FormEvent, useEffect, useState } from "react";
import {
  CheckCircle2,
  Edit3,
  FileText,
  FileUp,
  Loader2,
  Plus,
  RefreshCw,
  Rocket,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import * as api from "../api/client";
import type {
  AdminQuestionPayload,
  ExamPaper,
  ModuleType,
  QuestionAnswer,
  QuestionContent,
  QuestionPublic,
} from "../types";
import { formatQuestionTag, getSubTypeLabel, MODULE_LABELS } from "../utils/format";

interface AdminStudioViewProps {
  onToast: (text: string, type?: "info" | "success" | "error") => void;
}

interface QuestionEditorModalProps {
  open: boolean;
  initialQuestion: QuestionPublic | null;
  defaultPaperId?: number | null;
  onClose: () => void;
  onSaved: (saved: QuestionPublic) => void;
  onToast: (text: string, type?: "info" | "success" | "error") => void;
}

function QuestionEditorModal({
  open,
  initialQuestion,
  defaultPaperId,
  onClose,
  onSaved,
  onToast,
}: QuestionEditorModalProps) {
  const [examLevel, setExamLevel] = useState("CET4");
  const [module, setModule] = useState<ModuleType>("reading");
  const [subType, setSubType] = useState("careful_reading");
  const [year, setYear] = useState("2025");
  const [month, setMonth] = useState("6");
  const [setNo, setSetNo] = useState("1");
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState("published");

  // Structured common fields
  const [directions, setDirections] = useState("");
  const [passageOrPrompt, setPassageOrPrompt] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [referenceText, setReferenceText] = useState("");
  const [jsonMode, setJsonMode] = useState(false);
  const [contentJsonStr, setContentJsonStr] = useState("{}");
  const [answerJsonStr, setAnswerJsonStr] = useState("{}");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (initialQuestion) {
      setExamLevel(initialQuestion.exam_level || "CET4");
      setModule(initialQuestion.module || "reading");
      setSubType(initialQuestion.sub_type || "careful_reading");
      setYear(initialQuestion.year ? String(initialQuestion.year) : "");
      setMonth(initialQuestion.month ? String(initialQuestion.month) : "6");
      setSetNo(initialQuestion.set_no ? String(initialQuestion.set_no) : "1");
      setTitle(initialQuestion.title || "");
      setTopic(initialQuestion.topic || "");
      setStatus(initialQuestion.status || "published");

      const c = initialQuestion.content || {};
      const a = initialQuestion.answer || {};
      setDirections(String(c.directions || ""));
      setPassageOrPrompt(
        String(c.passage || c.prompt || c.source_text || c.chinese_text || "")
      );
      setImageUrl(String(c.image_url || ""));
      setAnalysis(String(a.analysis || ""));
      setReferenceText(
        String(a.reference_essay || a.reference_translation || "")
      );
      setContentJsonStr(JSON.stringify(c, null, 2));
      setAnswerJsonStr(JSON.stringify(a, null, 2));
      setJsonMode(initialQuestion.module === "reading");
    } else {
      setExamLevel("CET4");
      setModule("writing");
      setSubType("essay");
      setYear(String(new Date().getFullYear()));
      setMonth("6");
      setSetNo("1");
      setTitle("");
      setTopic("");
      setStatus("draft");
      setDirections("");
      setPassageOrPrompt("");
      setImageUrl("");
      setAnalysis("");
      setReferenceText("");
      setContentJsonStr(
        JSON.stringify(
          { directions: "", prompt: "", word_limit: "120-180 words" },
          null,
          2
        )
      );
      setAnswerJsonStr(
        JSON.stringify({ reference_essay: "", analysis: "", key_points: [] }, null, 2)
      );
      setJsonMode(false);
    }
  }, [open, initialQuestion]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    let contentObj: QuestionContent;
    let answerObj: QuestionAnswer;

    if (jsonMode) {
      try {
        contentObj = JSON.parse(contentJsonStr) as QuestionContent;
        answerObj = JSON.parse(answerJsonStr) as QuestionAnswer;
      } catch {
        onToast("JSON 格式有误，请检查 content/answer JSON 语法", "error");
        return;
      }
    } else {
      const baseContent: QuestionContent = initialQuestion?.content
        ? { ...initialQuestion.content }
        : {};
      baseContent.directions = directions || undefined;
      if (module === "writing") {
        baseContent.prompt = passageOrPrompt;
        if (imageUrl.trim()) baseContent.image_url = imageUrl.trim();
      } else if (module === "translation") {
        baseContent.source_text = passageOrPrompt;
      } else {
        baseContent.passage = passageOrPrompt;
      }

      const baseAnswer: QuestionAnswer = initialQuestion?.answer
        ? { ...initialQuestion.answer }
        : {};
      if (analysis.trim()) baseAnswer.analysis = analysis.trim();
      if (module === "writing" && referenceText.trim()) {
        baseAnswer.reference_essay = referenceText.trim();
      } else if (module === "translation" && referenceText.trim()) {
        baseAnswer.reference_translation = referenceText.trim();
      }

      contentObj = baseContent;
      answerObj = baseAnswer;
    }

    const payload: AdminQuestionPayload = {
      paper_id: initialQuestion?.paper_id ?? defaultPaperId ?? null,
      exam_level: examLevel,
      module,
      sub_type: subType,
      year: year ? Number(year) : null,
      month: month ? Number(month) : null,
      set_no: setNo ? Number(setNo) : 1,
      title: title.trim(),
      topic: topic.trim() || null,
      content: contentObj,
      answer: answerObj,
      status,
    };

    setSaving(true);
    try {
      const saved = initialQuestion
        ? await api.updateAdminQuestion(initialQuestion.id, payload)
        : await api.createAdminQuestion(payload);
      onToast(initialQuestion ? "题目已更新" : "题目已创建", "success");
      onSaved(saved);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "保存题目失败", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card modal-sheet"
        style={{ maxWidth: 820 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header editor-modal-header">
          <strong style={{ fontSize: 16 }}>
            {initialQuestion ? `编辑题目 #${initialQuestion.id}` : "新增单题"}
          </strong>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              className="m3-chip-sm active"
              onClick={() => setJsonMode((m) => !m)}
            >
              {jsonMode ? "切换表单视图" : "切换 JSON 高级编辑"}
            </button>
            <button
              type="button"
              className="m3-icon-btn"
              onClick={onClose}
              aria-label="关闭弹窗"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <form onSubmit={handleSave} className="modal-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 10,
            }}
          >
            <label style={{ fontSize: 12 }}>
              级别
              <select
                className="m3-select"
                value={examLevel}
                onChange={(e) => setExamLevel(e.target.value)}
              >
                <option value="CET4">CET4</option>
                <option value="CET6">CET6</option>
              </select>
            </label>

            <label style={{ fontSize: 12 }}>
              模块
              <select
                className="m3-select"
                value={module}
                onChange={(e) => {
                  const next = e.target.value as ModuleType;
                  setModule(next);
                  if (next === "writing") setSubType("essay");
                  if (next === "translation") setSubType("paragraph_translation");
                  if (next === "reading") setSubType("careful_reading");
                }}
              >
                <option value="writing">writing（写作）</option>
                <option value="reading">reading（阅读）</option>
                <option value="translation">translation（翻译）</option>
              </select>
            </label>

            <label style={{ fontSize: 12 }}>
              子题型
              <select
                className="m3-select"
                value={subType}
                onChange={(e) => setSubType(e.target.value)}
              >
                <option value="essay">essay（短文写作）</option>
                <option value="careful_reading">careful_reading（仔细阅读）</option>
                <option value="banked_cloze">banked_cloze（选词填空）</option>
                <option value="matching">matching（长篇匹配）</option>
                <option value="paragraph_translation">paragraph_translation（段落翻译）</option>
              </select>
            </label>

            <label style={{ fontSize: 12 }}>
              状态
              <select
                className="m3-select"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="published">published（已发布）</option>
                <option value="draft">draft（草稿）</option>
              </select>
            </label>
          </div>

          <div className="editor-title-meta-grid">
            <label className="editor-title-field" style={{ fontSize: 12 }}>
              题目标题 *
              <input
                className="m3-input"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例如：2025年6月四级仔细阅读 Passage 1"
              />
            </label>
            <label style={{ fontSize: 12 }}>
              年份
              <input
                className="m3-input"
                type="number"
                inputMode="numeric"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              月份
              <select
                className="m3-select"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
              >
                <option value="6">6月</option>
                <option value="12">12月</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              套数
              <input
                className="m3-input"
                type="number"
                inputMode="numeric"
                min={1}
                value={setNo}
                onChange={(e) => setSetNo(e.target.value)}
              />
            </label>
          </div>

          <label style={{ fontSize: 12 }}>
            主题标签（Topic）
            <input
              className="m3-input"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：人工智能、传统文化、环境保护"
            />
          </label>

          {jsonMode ? (
            <div className="editor-json-grid">
              <label style={{ fontSize: 12 }}>
                content (JSON)
                <textarea
                  className="m3-textarea"
                  rows={14}
                  style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
                  value={contentJsonStr}
                  onChange={(e) => setContentJsonStr(e.target.value)}
                />
              </label>
              <label style={{ fontSize: 12 }}>
                answer (JSON)
                <textarea
                  className="m3-textarea"
                  rows={14}
                  style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
                  value={answerJsonStr}
                  onChange={(e) => setAnswerJsonStr(e.target.value)}
                />
              </label>
            </div>
          ) : (
            <>
              <label style={{ fontSize: 12 }}>
                Directions / 题目要求
                <textarea
                  className="m3-textarea"
                  rows={2}
                  value={directions}
                  onChange={(e) => setDirections(e.target.value)}
                />
              </label>

              <label style={{ fontSize: 12 }}>
                {module === "writing"
                  ? "写作题干 (prompt)"
                  : module === "translation"
                  ? "中文原文 (source_text)"
                  : "阅读文章 (passage)"}
                <textarea
                  className="m3-textarea"
                  rows={6}
                  value={passageOrPrompt}
                  onChange={(e) => setPassageOrPrompt(e.target.value)}
                />
              </label>

              {module === "writing" && (
                <label style={{ fontSize: 12 }}>
                  配图 URL（可选）
                  <input
                    className="m3-input"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    placeholder="/uploads/..."
                  />
                </label>
              )}

              {(module === "writing" || module === "translation") && (
                <label style={{ fontSize: 12 }}>
                  {module === "writing" ? "参考范文" : "参考译文"}
                  <textarea
                    className="m3-textarea"
                    rows={4}
                    value={referenceText}
                    onChange={(e) => setReferenceText(e.target.value)}
                  />
                </label>
              )}

              <label style={{ fontSize: 12 }}>
                解析说明 (analysis)
                <textarea
                  className="m3-textarea"
                  rows={3}
                  value={analysis}
                  onChange={(e) => setAnalysis(e.target.value)}
                />
              </label>
            </>
          )}

          <div className="modal-footer" style={{ padding: "12px 0 0" }}>
            <button
              type="button"
              className="m3-btn-outlined m3-btn-sm"
              onClick={onClose}
            >
              取消
            </button>
            <button
              type="submit"
              className="m3-btn-filled m3-btn-sm"
              disabled={saving}
            >
              {saving ? "保存中..." : "保存题目"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AdminStudioView({ onToast }: AdminStudioViewProps) {
  const [activeTab, setActiveTab] = useState<"papers" | "questions">("papers");

  // Papers state
  const [papers, setPapers] = useState<ExamPaper[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<ExamPaper | null>(null);
  const [paperQuestions, setPaperQuestions] = useState<QuestionPublic[]>([]);
  const [rawMarkdownDraft, setRawMarkdownDraft] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [publishing, setPublishing] = useState(false);

  // Upload form
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [paperTitle, setPaperTitle] = useState("");
  const [paperYear, setPaperYear] = useState(String(new Date().getFullYear()));
  const [paperMonth, setPaperMonth] = useState("6");
  const [paperLevel, setPaperLevel] = useState("CET4");
  const [paperSetNo, setPaperSetNo] = useState("1");

  // Single question management state
  const [allQuestions, setAllQuestions] = useState<QuestionPublic[]>([]);
  const [loadingAllQuestions, setLoadingAllQuestions] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<QuestionPublic | null>(null);

  const loadPapers = async () => {
    try {
      const res = await api.listPapers();
      setPapers(res.items || []);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "加载试卷列表失败", "error");
    }
  };

  const loadPaperDetail = async (id: number) => {
    try {
      const detail = await api.getPaper(id);
      setSelectedPaper(detail.paper);
      setPaperQuestions(detail.questions || []);
      setRawMarkdownDraft(detail.paper.raw_markdown || "");
    } catch (err) {
      onToast(err instanceof Error ? err.message : "加载试卷详情失败", "error");
    }
  };

  const loadAllQuestions = async () => {
    setLoadingAllQuestions(true);
    try {
      const res = await api.listQuestions({
        status: "all",
        include_answer: true,
        limit: 100,
        offset: 0,
      });
      setAllQuestions(res.items || []);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "加载题目列表失败", "error");
    } finally {
      setLoadingAllQuestions(false);
    }
  };

  useEffect(() => {
    void loadPapers();
  }, []);

  useEffect(() => {
    if (activeTab === "questions") {
      void loadAllQuestions();
    }
  }, [activeTab]);

  const handleUploadPaper = async (e: FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      onToast("请先选择 PDF 或 Markdown 真题文件", "error");
      return;
    }
    setUploading(true);
    try {
      const res = await api.uploadPaper({
        file: uploadFile,
        title: paperTitle.trim() || uploadFile.name.replace(/\.[^.]+$/, ""),
        year: paperYear,
        month: paperMonth,
        exam_level: paperLevel,
        set_no: paperSetNo,
      });
      onToast("真题文件已上传，准备 MinerU 解析", "success");
      setUploadFile(null);
      setPaperTitle("");
      await loadPapers();
      await loadPaperDetail(res.paper.id);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "上传失败", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleParsePaper = async () => {
    if (!selectedPaper) return;
    setParsing(true);
    try {
      const res = await api.parsePaper(
        selectedPaper.id,
        rawMarkdownDraft.trim() ? rawMarkdownDraft : undefined
      );
      setSelectedPaper(res.paper);
      setPaperQuestions(res.questions || []);
      setRawMarkdownDraft(res.paper.raw_markdown || rawMarkdownDraft);
      onToast(`AI 智能拆题完成，共提取 ${res.questions.length} 道题目`, "success");
      await loadPapers();
    } catch (err) {
      onToast(err instanceof Error ? err.message : "解析或拆题失败", "error");
    } finally {
      setParsing(false);
    }
  };

  const handlePublishPaper = async () => {
    if (!selectedPaper) return;
    setPublishing(true);
    try {
      const res = await api.publishPaper(selectedPaper.id);
      setSelectedPaper(res.paper);
      onToast(`成功发布 ${res.published_count} 道真题入库！`, "success");
      await loadPapers();
      await loadPaperDetail(selectedPaper.id);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "发布失败", "error");
    } finally {
      setPublishing(false);
    }
  };

  const handleDeleteQuestion = async (q: QuestionPublic) => {
    try {
      await api.deleteAdminQuestion(q.id);
      onToast(`已删除题目 #${q.id}`, "info");
      if (selectedPaper) {
        await loadPaperDetail(selectedPaper.id);
      }
      if (activeTab === "questions") {
        await loadAllQuestions();
      }
    } catch (err) {
      onToast(err instanceof Error ? err.message : "删除失败", "error");
    }
  };

  return (
    <div className="page-container">
      <div className="page-header-row admin-header-row">
        <div>
          <h1 style={{ margin: "0 0 4px", fontSize: 24 }}>真题管理与 MinerU 解析台</h1>
          <p style={{ margin: 0, fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}>
            上传 PDF 真题试卷，调用 MinerU 云端解析与 AI 智能拆题，核验后一键发布至真题库
          </p>
        </div>

        <div className="segmented-tabs">
          <button
            type="button"
            className={`segmented-tab ${activeTab === "papers" ? "active" : ""}`}
            onClick={() => setActiveTab("papers")}
          >
            PDF 上传与 MinerU 解析
          </button>
          <button
            type="button"
            className={`segmented-tab ${activeTab === "questions" ? "active" : ""}`}
            onClick={() => setActiveTab("questions")}
          >
            单题管理与录入
          </button>
        </div>
      </div>

      {activeTab === "papers" ? (
        <div className="admin-split">
          {/* Left column: Upload form & Paper list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <form
              onSubmit={handleUploadPaper}
              className="m3-card"
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              <div style={{ fontWeight: 700, fontSize: 15, display: "flex", alignItems: "center", gap: 8 }}>
                <FileUp size={18} color="var(--md-sys-color-primary)" />
                <span>上传真题试卷 (PDF / MD)</span>
              </div>

              <label
                style={{
                  border: "1.5px dashed var(--md-sys-color-outline)",
                  borderRadius: 14,
                  padding: "16px 12px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: "var(--md-sys-color-surface-container)",
                  fontSize: 13,
                }}
              >
                <input
                  type="file"
                  accept=".pdf,.md,.markdown,.txt"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setUploadFile(f);
                    if (f && !paperTitle) {
                      setPaperTitle(f.name.replace(/\.[^.]+$/, ""));
                    }
                  }}
                />
                {uploadFile ? (
                  <strong>{uploadFile.name}</strong>
                ) : (
                  <span>点击选择 PDF 或 Markdown 文件</span>
                )}
              </label>

              <input
                className="m3-input"
                placeholder="试卷标题（如：2025年6月 CET-4 真题卷一）"
                value={paperTitle}
                onChange={(e) => setPaperTitle(e.target.value)}
                required
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input
                  className="m3-input"
                  type="number"
                  inputMode="numeric"
                  placeholder="年份"
                  value={paperYear}
                  onChange={(e) => setPaperYear(e.target.value)}
                />
                <select
                  className="m3-select"
                  value={paperMonth}
                  onChange={(e) => setPaperMonth(e.target.value)}
                >
                  <option value="6">6 月</option>
                  <option value="12">12 月</option>
                </select>
                <select
                  className="m3-select"
                  value={paperLevel}
                  onChange={(e) => setPaperLevel(e.target.value)}
                >
                  <option value="CET4">CET4</option>
                  <option value="CET6">CET6</option>
                </select>
                <input
                  className="m3-input"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  placeholder="第几套"
                  value={paperSetNo}
                  onChange={(e) => setPaperSetNo(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="m3-btn-filled"
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    <span>上传并提交任务...</span>
                  </>
                ) : (
                  <>
                    <FileUp size={16} />
                    <span>上传试卷</span>
                  </>
                )}
              </button>
            </form>

            <div className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: 15 }}>已上传试卷</strong>
                <button
                  type="button"
                  className="m3-icon-btn"
                  onClick={() => void loadPapers()}
                  title="刷新"
                >
                  <RefreshCw size={15} />
                </button>
              </div>

              {papers.length === 0 ? (
                <div style={{ fontSize: 13, opacity: 0.7 }}>暂无上传记录</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {papers.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => void loadPaperDetail(p.id)}
                      style={{
                        textAlign: "left",
                        padding: "10px 12px",
                        borderRadius: 12,
                        border:
                          selectedPaper?.id === p.id
                            ? "1.5px solid var(--md-sys-color-primary)"
                            : "1px solid var(--md-sys-color-outline-variant)",
                        background:
                          selectedPaper?.id === p.id
                            ? "var(--md-sys-color-primary-container)"
                            : "var(--md-sys-color-surface-container-lowest)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{p.title}</div>
                      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                        <span className="m3-pill-badge">{p.exam_level || "CET"}</span>
                        <span
                          className={`m3-pill-badge ${
                            p.status === "published"
                              ? "success"
                              : p.status === "error" || p.status === "failed"
                              ? "error"
                              : "warning"
                          }`}
                        >
                          {p.status}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right column: Selected Paper MinerU Markdown & Extracted Questions */}
          <div className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {!selectedPaper ? (
              <div style={{ textAlign: "center", padding: "48px 20px", opacity: 0.7 }}>
                <FileText size={32} style={{ marginBottom: 8 }} />
                <div>请在左侧上传或选择一份试卷进行 MinerU 解析与 AI 拆题</div>
              </div>
            ) : (
              <>
                <div className="admin-paper-header">
                  <div>
                    <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>{selectedPaper.title}</h2>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
                      <span className="m3-pill-badge">状态：{selectedPaper.status}</span>
                      {selectedPaper.mineru_task_id && (
                        <span className="m3-pill-badge task-id-badge">
                          MinerU Task: {selectedPaper.mineru_task_id}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="admin-paper-actions">
                    <button
                      type="button"
                      className="m3-btn-tonal m3-btn-sm"
                      disabled={parsing}
                      onClick={handleParsePaper}
                    >
                      {parsing ? (
                        <>
                          <Loader2 size={14} className="spin" />
                          <span>解析拆题中...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} />
                          <span>AI 智能拆题</span>
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      className="m3-btn-filled m3-btn-sm"
                      disabled={publishing || paperQuestions.length === 0}
                      onClick={handlePublishPaper}
                    >
                      {publishing ? (
                        <>
                          <Loader2 size={14} className="spin" />
                          <span>发布中...</span>
                        </>
                      ) : (
                        <>
                          <Rocket size={14} />
                          <span>一键发布入库 ({paperQuestions.length})</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {selectedPaper.error_message && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 12,
                      background: "var(--md-sys-color-error-container)",
                      color: "var(--md-sys-color-on-error-container)",
                      fontSize: 13,
                    }}
                  >
                    解析提示：{selectedPaper.error_message}
                  </div>
                )}

                <div className="admin-review-grid">
                  {/* Left: Raw Markdown Editor */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <strong style={{ fontSize: 13 }}>
                      原始 Markdown（支持直接粘贴或修改 MinerU 解析结果）
                    </strong>
                    <textarea
                      className="m3-textarea"
                      rows={20}
                      style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.5 }}
                      placeholder="MinerU 解析后的 Markdown 将显示在此处，也可手动粘贴真题 Markdown 后点击「AI 智能拆题」..."
                      value={rawMarkdownDraft}
                      onChange={(e) => setRawMarkdownDraft(e.target.value)}
                    />
                  </div>

                  {/* Right: Extracted Questions Preview */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ fontSize: 13 }}>
                        拆题结果预览 ({paperQuestions.length})
                      </strong>
                      <button
                        type="button"
                        className="m3-btn-outlined m3-btn-sm"
                        onClick={() => {
                          setEditingQuestion(null);
                          setEditorOpen(true);
                        }}
                      >
                        <Plus size={14} />
                        <span>手动加题</span>
                      </button>
                    </div>

                    {paperQuestions.length === 0 ? (
                      <div
                        style={{
                          padding: 24,
                          borderRadius: 12,
                          border: "1px dashed var(--md-sys-color-outline-variant)",
                          textAlign: "center",
                          fontSize: 13,
                          opacity: 0.75,
                        }}
                      >
                        尚未拆出题目。请点击上方「AI 智能拆题」自动提取，或手动加题。
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 480, overflowY: "auto" }}>
                        {paperQuestions.map((q) => (
                          <div
                            key={q.id}
                            style={{
                              padding: 12,
                              borderRadius: 12,
                              border: "1px solid var(--md-sys-color-outline-variant)",
                              background: "var(--md-sys-color-surface-container-lowest)",
                              display: "flex",
                              flexDirection: "column",
                              gap: 6,
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                <span className="m3-pill-badge primary">
                                  {MODULE_LABELS[q.module]} · {getSubTypeLabel(q.sub_type)}
                                </span>
                                <span
                                  className={`m3-pill-badge ${
                                    q.status === "published" ? "success" : "warning"
                                  }`}
                                >
                                  {q.status === "published" ? (
                                    <>
                                      <CheckCircle2 size={11} /> 已发布
                                    </>
                                  ) : (
                                    "草稿"
                                  )}
                                </span>
                              </div>
                              <div style={{ display: "flex", gap: 4 }}>
                                <button
                                  type="button"
                                  className="m3-icon-btn"
                                  style={{ width: 30, height: 30 }}
                                  title="编辑"
                                  onClick={() => {
                                    setEditingQuestion(q);
                                    setEditorOpen(true);
                                  }}
                                >
                                  <Edit3 size={14} />
                                </button>
                                <button
                                  type="button"
                                  className="m3-icon-btn"
                                  style={{ width: 30, height: 30 }}
                                  title="删除"
                                  onClick={() => void handleDeleteQuestion(q)}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{q.title}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        /* Tab 2: Single Question CRUD */
        <div className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="admin-questions-header">
            <strong style={{ fontSize: 16 }}>全部真题管理（含草稿与已发布）</strong>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="m3-btn-outlined m3-btn-sm"
                onClick={() => void loadAllQuestions()}
              >
                <RefreshCw size={14} />
                <span>刷新</span>
              </button>
              <button
                type="button"
                className="m3-btn-filled m3-btn-sm"
                onClick={() => {
                  setEditingQuestion(null);
                  setEditorOpen(true);
                }}
              >
                <Plus size={14} />
                <span>新建题目</span>
              </button>
            </div>
          </div>

          {loadingAllQuestions ? (
            <div style={{ padding: 24, textAlign: "center" }}>加载中...</div>
          ) : allQuestions.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", opacity: 0.7 }}>暂无题目</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {allQuestions.map((q) => (
                <div
                  key={q.id}
                  className="admin-question-row"
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                      <span className="m3-pill-badge">#{q.id}</span>
                      <span className="m3-pill-badge primary">{formatQuestionTag(q)}</span>
                      <span
                        className={`m3-pill-badge ${
                          q.status === "published" ? "success" : "warning"
                        }`}
                      >
                        {q.status}
                      </span>
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{q.title}</div>
                  </div>
                  <div className="admin-question-actions">
                    <button
                      type="button"
                      className="m3-btn-tonal m3-btn-sm"
                      onClick={() => {
                        setEditingQuestion(q);
                        setEditorOpen(true);
                      }}
                    >
                      <Edit3 size={14} />
                      <span>编辑</span>
                    </button>
                    <button
                      type="button"
                      className="m3-btn-outlined m3-btn-sm"
                      onClick={() => void handleDeleteQuestion(q)}
                    >
                      <Trash2 size={14} />
                      <span>删除</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <QuestionEditorModal
        open={editorOpen}
        initialQuestion={editingQuestion}
        defaultPaperId={activeTab === "papers" ? selectedPaper?.id : null}
        onClose={() => setEditorOpen(false)}
        onSaved={async () => {
          setEditorOpen(false);
          if (selectedPaper && activeTab === "papers") {
            await loadPaperDetail(selectedPaper.id);
          }
          if (activeTab === "questions") {
            await loadAllQuestions();
          }
        }}
        onToast={onToast}
      />
    </div>
  );
}
