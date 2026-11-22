import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CalendarClock,
  Languages,
  PenTool,
  Send,
  Sparkles,
} from "lucide-react";
import { listQuestions } from "../api/client";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { ModuleType, QuestionPublic, UserProfile } from "../types";
import {
  formatQuestionTag,
  getDaysUntilExam,
  MODULE_LABELS,
} from "../utils/format";

interface HomeViewProps {
  profile: UserProfile | null;
  onStartModule: (module: ModuleType, initialPrompt?: string) => void;
  onStartQuestion: (question: QuestionPublic) => void;
  onOpenBank: () => void;
  onOpenSettings: () => void;
}

export function HomeView({
  profile,
  onStartModule,
  onStartQuestion,
  onOpenBank,
  onOpenSettings,
}: HomeViewProps) {
  const isCoarsePointer = useMediaQuery("(pointer: coarse)");
  const [prompt, setPrompt] = useState("");
  const [selectedModule, setSelectedModule] = useState<ModuleType>("reading");
  const [sampleQuestions, setSampleQuestions] = useState<QuestionPublic[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  useEffect(() => {
    let active = true;
    setLoadingQuestions(true);
    listQuestions({
      exam_level: profile?.exam_level || undefined,
      limit: 6,
      offset: 0,
    })
      .then((res) => {
        if (active) setSampleQuestions(res.items || []);
      })
      .catch(() => {
        if (active) setSampleQuestions([]);
      })
      .finally(() => {
        if (active) setLoadingQuestions(false);
      });
    return () => {
      active = false;
    };
  }, [profile?.exam_level]);

  const displayName = profile?.display_name || profile?.username || "同学";
  const daysLeft = getDaysUntilExam(profile?.exam_date ?? null);

  const handleQuickSend = () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setPrompt("");
    onStartModule(selectedModule, trimmed);
  };

  return (
    <div className="home-container">
      <div className="home-hero">
        <div className="home-greeting-row">
          <span className="home-greeting">{displayName}，你好</span>

          {profile?.exam_date && daysLeft !== null ? (
            <button
              type="button"
              className="countdown-chip"
              onClick={onOpenSettings}
              title="点击修改考试日期"
            >
              <CalendarClock size={14} />
              <span>
                {profile.exam_level ? `${profile.exam_level} ` : "CET "}
                {daysLeft > 0
                  ? `距考试还有 ${daysLeft} 天`
                  : daysLeft === 0
                  ? "就是今天，加油！"
                  : `考试日 ${profile.exam_date}`}
              </span>
            </button>
          ) : (
            <button
              type="button"
              className="countdown-chip"
              onClick={onOpenSettings}
            >
              <CalendarClock size={14} />
              <span>
                {profile?.exam_level ? `${profile.exam_level} · ` : ""}
                设置考试倒计时
              </span>
            </button>
          )}
        </div>

        <h1 className="home-title">今天想专攻哪项真题训练？</h1>
      </div>

      {/* Quick Prompt Composer */}
      <div className="home-composer">
        <textarea
          placeholder="问问 CET Agent（例如：给我出一道六级仔细阅读真题 / 帮我批改这篇四级作文）..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            if (!isCoarsePointer && e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleQuickSend();
            }
          }}
        />
        <div className="home-composer-footer">
          <div className="module-pills">
            {(["writing", "reading", "translation"] as ModuleType[]).map((m) => (
              <button
                key={m}
                type="button"
                className={`module-pill ${selectedModule === m ? "active" : ""}`}
                onClick={() => setSelectedModule(m)}
              >
                {MODULE_LABELS[m]}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="m3-btn-filled m3-btn-sm home-composer-send"
            disabled={!prompt.trim()}
            onClick={handleQuickSend}
          >
            <Send size={14} />
            <span>开始对话</span>
          </button>
        </div>
      </div>

      {/* 3 M3 Module Cards */}
      <div className="module-grid">
        <button
          type="button"
          className="module-card"
          onClick={() => onStartModule("writing")}
        >
          <span className="module-card-icon">
            <PenTool size={22} />
          </span>
          <div className="module-card-body">
            <span className="module-card-title">写作批改</span>
            <span className="module-card-desc">
              审题立意、结构框架搭建、高级句式润色与考官级评分反馈
            </span>
          </div>
        </button>

        <button
          type="button"
          className="module-card"
          onClick={() => onStartModule("reading")}
        >
          <span className="module-card-icon">
            <BookOpen size={22} />
          </span>
          <div className="module-card-body">
            <span className="module-card-title">阅读精读</span>
            <span className="module-card-desc">
              仔细阅读、选词填空与长篇匹配，左题右聊同义替换与长难句精讲
            </span>
          </div>
        </button>

        <button
          type="button"
          className="module-card"
          onClick={() => onStartModule("translation")}
        >
          <span className="module-card-icon">
            <Languages size={22} />
          </span>
          <div className="module-card-body">
            <span className="module-card-title">翻译训练</span>
            <span className="module-card-desc">
              中国文化与社会热点段落汉译英，主干切分与地道表达对比提升
            </span>
          </div>
        </button>
      </div>

      {/* Quick Start from Question Bank */}
      <section style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="section-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} color="var(--md-sys-color-primary)" />
            <h2>从真题库抽题练习</h2>
          </div>
          <button
            type="button"
            className="m3-btn-outlined m3-btn-sm"
            onClick={onOpenBank}
          >
            <span>浏览全部真题</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {loadingQuestions ? (
          <div style={{ fontSize: 13, opacity: 0.7 }}>正在加载真题推荐...</div>
        ) : sampleQuestions.length === 0 ? (
          <div className="m3-card" style={{ fontSize: 13, opacity: 0.8 }}>
            暂无已发布的真题，你可以直接点击上方模块卡片与 AI 教练开始对话练习。
          </div>
        ) : (
          <div className="quick-question-grid">
            {sampleQuestions.map((q) => (
              <div key={q.id} className="question-mini-card">
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span className="m3-pill-badge primary">
                    {formatQuestionTag(q)}
                  </span>
                </div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{q.title}</div>
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
                <button
                  type="button"
                  className="m3-btn-tonal m3-btn-sm"
                  style={{ marginTop: "auto", alignSelf: "flex-start" }}
                  onClick={() => onStartQuestion(q)}
                >
                  开始练习
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
