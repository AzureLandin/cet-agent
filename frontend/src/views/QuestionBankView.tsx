import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Play, Search } from "lucide-react";
import { listQuestions } from "../api/client";
import type { QuestionPublic } from "../types";
import {
  formatQuestionTag,
  getSubTypeLabel,
  MODULE_LABELS,
} from "../utils/format";

interface QuestionBankViewProps {
  defaultExamLevel?: string | null;
  onStartQuestion: (question: QuestionPublic) => void;
}

const PAGE_SIZE = 12;

export function QuestionBankView({
  defaultExamLevel,
  onStartQuestion,
}: QuestionBankViewProps) {
  const [examLevel, setExamLevel] = useState<string>(defaultExamLevel || "");
  const [module, setModule] = useState<string>("");
  const [subType, setSubType] = useState<string>("");
  const [year, setYear] = useState<string>("");
  const [topic, setTopic] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);

  const [items, setItems] = useState<QuestionPublic[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listQuestions({
      exam_level: examLevel || undefined,
      module: module || undefined,
      sub_type: subType || undefined,
      year: year.trim() || undefined,
      topic: topic.trim() || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((res) => {
        if (!active) return;
        setItems(res.items || []);
        setTotal(res.total || 0);
      })
      .catch(() => {
        if (!active) return;
        setItems([]);
        setTotal(0);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [examLevel, module, subType, year, topic, offset]);

  const getSnippet = (q: QuestionPublic): string => {
    const c = q.content || {};
    const raw =
      c.passage ||
      c.prompt ||
      c.source_text ||
      c.chinese_text ||
      c.directions ||
      "";
    const s = String(raw).trim();
    return s.length > 110 ? `${s.slice(0, 110)}...` : s;
  };

  return (
    <div className="page-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: "0 0 4px", fontSize: 24 }}>真题题库</h1>
          <p style={{ margin: 0, fontSize: 14, color: "var(--md-sys-color-on-surface-variant)" }}>
            筛选四六级历年真题，点击「开始练习」即可在左题右聊分栏工作台开练
          </p>
        </div>
        <span className="m3-pill-badge primary">共 {total} 道已发布真题</span>
      </div>

      {/* M3 Filter Bar */}
      <div className="filter-bar">
        <div style={{ display: "flex", gap: 6 }}>
          {[
            ["", "全部级别"],
            ["CET4", "CET4"],
            ["CET6", "CET6"],
          ].map(([val, label]) => (
            <button
              key={val}
              type="button"
              className={`module-pill ${examLevel === val ? "active" : ""}`}
              onClick={() => {
                setExamLevel(val);
                setOffset(0);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 6 }}>
          {[
            ["", "全部模块"],
            ["writing", "写作"],
            ["reading", "阅读"],
            ["translation", "翻译"],
          ].map(([val, label]) => (
            <button
              key={val}
              type="button"
              className={`module-pill ${module === val ? "active" : ""}`}
              onClick={() => {
                setModule(val);
                setOffset(0);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <select
          className="m3-select"
          style={{ width: 150 }}
          value={subType}
          onChange={(e) => {
            setSubType(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">全部子题型</option>
          <option value="essay">短文写作</option>
          <option value="careful_reading">仔细阅读</option>
          <option value="banked_cloze">选词填空</option>
          <option value="matching">长篇匹配</option>
          <option value="paragraph_translation">段落翻译</option>
        </select>

        <input
          className="m3-input"
          style={{ width: 110 }}
          type="number"
          placeholder="年份"
          value={year}
          onChange={(e) => {
            setYear(e.target.value);
            setOffset(0);
          }}
        />

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
            placeholder="搜索主题 / 关键词..."
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value);
              setOffset(0);
            }}
          />
        </div>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="m3-card" style={{ textAlign: "center", padding: 40 }}>
          正在加载真题题库...
        </div>
      ) : items.length === 0 ? (
        <div className="m3-card" style={{ textAlign: "center", padding: 40 }}>
          暂无符合条件的真题，请尝试调整筛选条件。
        </div>
      ) : (
        <div className="question-cards-grid">
          {items.map((q) => (
            <article key={q.id} className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className="m3-pill-badge primary">{formatQuestionTag(q)}</span>
                <span className="m3-pill-badge">{MODULE_LABELS[q.module]}</span>
                <span className="m3-pill-badge">{getSubTypeLabel(q.sub_type)}</span>
              </div>

              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{q.title}</h3>

              {q.topic && (
                <div style={{ fontSize: 12, color: "var(--md-sys-color-primary)", fontWeight: 600 }}>
                  主题：{q.topic}
                </div>
              )}

              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  color: "var(--md-sys-color-on-surface-variant)",
                  lineHeight: 1.55,
                  flex: 1,
                }}
              >
                {getSnippet(q) || "点击开始练习查看完整题目内容"}
              </p>

              <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 6 }}>
                <button
                  type="button"
                  className="m3-btn-tonal m3-btn-sm"
                  onClick={() => onStartQuestion(q)}
                >
                  <Play size={14} />
                  <span>开始练习</span>
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            className="m3-btn-outlined m3-btn-sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            <ChevronLeft size={15} />
            <span>上一页</span>
          </button>
          <span style={{ fontSize: 13 }}>
            第 {Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(total / PAGE_SIZE)} 页
          </span>
          <button
            type="button"
            className="m3-btn-outlined m3-btn-sm"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            <span>下一页</span>
            <ChevronRight size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
