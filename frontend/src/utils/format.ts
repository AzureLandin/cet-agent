import type { ModuleType, QuestionPublic, SubType } from "../types";

export const AVATAR_COLORS = [
  "#4285f4",
  "#ea4335",
  "#fbbc04",
  "#34a853",
  "#8e24aa",
  "#00acc1",
  "#ef6c00",
  "#c62828",
  "#2e7d32",
  "#1565c0",
];

export const MODULE_LABELS: Record<ModuleType, string> = {
  writing: "写作批改",
  reading: "阅读精读",
  translation: "翻译训练",
};

export const SUBTYPE_LABELS: Record<string, string> = {
  essay: "短文写作",
  careful_reading: "仔细阅读",
  banked_cloze: "选词填空",
  matching: "长篇匹配",
  paragraph_translation: "段落翻译",
};

export function getSubTypeLabel(subType: SubType): string {
  return SUBTYPE_LABELS[subType] || subType;
}

export function formatQuestionTag(q: QuestionPublic): string {
  const parts: string[] = [];
  if (q.year) {
    parts.push(q.month ? `${q.year}年${q.month}月` : `${q.year}年`);
  }
  if (q.exam_level) {
    parts.push(q.exam_level);
  }
  if (q.set_no && q.set_no > 1) {
    parts.push(`第${q.set_no}套`);
  }
  parts.push(getSubTypeLabel(q.sub_type));
  return parts.join(" · ");
}

export function formatRelativeTime(isoString?: string): string {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  if (diffHour < 24) return `${diffHour}小时前`;
  if (diffDay < 7) return `${diffDay}天前`;
  return date.toLocaleDateString("zh-CN");
}

export function getDaysUntilExam(examDateStr: string | null): number | null {
  if (!examDateStr) return null;
  const target = new Date(`${examDateStr}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  // Count English words + CJK characters if mixed
  const enWords = trimmed.match(/[A-Za-z0-9'-]+/g)?.length ?? 0;
  const cjkChars = trimmed.match(/[\u4e00-\u9fff]/g)?.length ?? 0;
  return enWords + cjkChars;
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function getToolLabel(name: string, status: "running" | "done"): string {
  const runningMap: Record<string, string> = {
    search_questions: "正在从题库检索真题...",
    start_question_practice: "正在将真题加载至左侧工作台...",
    get_answer_key: "正在核对标准答案与解析...",
    record_practice_result: "正在记录本次练习成绩...",
  };
  const doneMap: Record<string, string> = {
    search_questions: "已检索真题库",
    start_question_practice: "真题已加载至工作台",
    get_answer_key: "已核对标准答案",
    record_practice_result: "已记录练习成绩",
  };
  if (status === "running") {
    return runningMap[name] || `正在执行 ${name}...`;
  }
  return doneMap[name] || `已完成 ${name}`;
}
