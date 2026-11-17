import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { listQuestions } from "../api/client";
import type { ModuleType, QuestionPublic } from "../types";
import { formatQuestionTag, MODULE_LABELS } from "../utils/format";

interface QuestionPickerModalProps {
  open: boolean;
  defaultModule?: ModuleType;
  onClose: () => void;
  onSelect: (question: QuestionPublic) => void;
}

export function QuestionPickerModal({
  open,
  defaultModule,
  onClose,
  onSelect,
}: QuestionPickerModalProps) {
  const [module, setModule] = useState<string>(defaultModule || "");
  const [examLevel, setExamLevel] = useState<string>("");
  const [topic, setTopic] = useState<string>("");
  const [items, setItems] = useState<QuestionPublic[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setModule(defaultModule || "");
    }
  }, [open, defaultModule]);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    listQuestions({
      module: module || undefined,
      exam_level: examLevel || undefined,
      topic: topic.trim() || undefined,
      limit: 24,
      offset: 0,
    })
      .then((res) => {
        if (active) setItems(res.items || []);
      })
      .catch(() => {
        if (active) setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open, module, examLevel, topic]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong style={{ fontSize: 16 }}>从真题库抽题</strong>
          <button type="button" className="m3-icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select
              className="m3-select"
              style={{ width: 130 }}
              value={examLevel}
              onChange={(e) => setExamLevel(e.target.value)}
            >
              <option value="">全部级别</option>
              <option value="CET4">CET4</option>
              <option value="CET6">CET6</option>
            </select>

            <select
              className="m3-select"
              style={{ width: 140 }}
              value={module}
              onChange={(e) => setModule(e.target.value)}
            >
              <option value="">全部题型</option>
              <option value="writing">写作</option>
              <option value="reading">阅读</option>
              <option value="translation">翻译</option>
            </select>

            <div style={{ flex: 1, minWidth: 180, position: "relative" }}>
              <Search
                size={15}
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  opacity: 0.6,
                }}
              />
              <input
                className="m3-input"
                style={{ paddingLeft: 34 }}
                placeholder="按主题关键词搜索..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div style={{ padding: 24, textAlign: "center", opacity: 0.7 }}>
              正在加载真题...
            </div>
          ) : items.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", opacity: 0.7 }}>
              没有找到匹配的真题
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {items.map((q) => (
                <div
                  key={q.id}
                  className="question-mini-card"
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                      <span className="m3-pill-badge primary">{formatQuestionTag(q)}</span>
                      <span className="m3-pill-badge">{MODULE_LABELS[q.module]}</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{q.title}</div>
                    {q.topic && (
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--md-sys-color-on-surface-variant)",
                        }}
                      >
                        主题：{q.topic}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    className="m3-btn-tonal m3-btn-sm"
                    onClick={() => onSelect(q)}
                  >
                    载入练习
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
