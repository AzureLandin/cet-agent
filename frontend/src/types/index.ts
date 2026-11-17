export type UserRole = "student" | "admin";
export type ModuleType = "writing" | "reading" | "translation";
export type ExamLevel = "CET4" | "CET6";
export type SubType =
  | "essay"
  | "careful_reading"
  | "banked_cloze"
  | "matching"
  | "paragraph_translation"
  | string;

export interface AuthResponse {
  user_id: number;
  username: string;
  role: UserRole;
}

export interface UserProfile {
  username: string;
  role: UserRole;
  exam_level: ExamLevel | null;
  exam_date: string | null;
  display_name: string | null;
  avatar_color: string;
  avatar_url: string | null;
}

export interface ProfileUpdatePayload {
  exam_level?: ExamLevel | null;
  exam_date?: string | null;
  display_name?: string | null;
  avatar_color?: string | null;
}

export interface ReadingQuestionItem {
  number?: number;
  id?: number | string;
  stem?: string;
  question?: string;
  options: Record<string, string> | string[];
}

export interface BankedClozeWordItem {
  letter?: string;
  label?: string;
  word: string;
}

export interface MatchingParagraph {
  label: string;
  text: string;
}

export interface MatchingStatement {
  number?: number;
  id?: number | string;
  text: string;
}

export interface QuestionContent {
  directions?: string;
  prompt?: string;
  topic?: string;
  title?: string;
  word_limit?: string;
  image_url?: string;
  requirements?: string;
  source_text?: string;
  chinese_text?: string;
  hints?: string[];
  passage?: string;
  paragraphs?: string[] | MatchingParagraph[] | Record<string, string>;
  questions?: ReadingQuestionItem[];
  word_bank?: BankedClozeWordItem[] | string[] | Record<string, string>;
  blanks?: Array<number | string>;
  blank_numbers?: Array<number | string>;
  statements?: MatchingStatement[];
  [key: string]: unknown;
}

export interface QuestionAnswer {
  correct_answers?: Record<string, string>;
  explanations?: Record<string, string>;
  analysis?: string;
  reference_essay?: string;
  reference_translation?: string;
  key_points?: string[];
  vocabulary?: string[];
  synonyms?: string[];
  [key: string]: unknown;
}

export interface QuestionPublic {
  id: number;
  paper_id?: number | null;
  exam_level: ExamLevel | string;
  module: ModuleType;
  sub_type: SubType;
  year?: number | null;
  month?: number | null;
  set_no?: number | null;
  title: string;
  topic?: string | null;
  content: QuestionContent;
  answer?: QuestionAnswer;
  status: string;
  created_at?: string;
}

export interface QuestionListResponse {
  items: QuestionPublic[];
  total: number;
  limit: number;
  offset: number;
}

export interface SubmitQuestionDetail {
  user_answer?: string;
  correct_answer?: string;
  is_correct?: boolean;
  explanation?: string;
}

export interface SubmitQuestionResponse {
  attempt_id: number;
  score: number | null;
  total: number | null;
  details: Record<string, SubmitQuestionDetail | boolean | unknown>;
  answer: QuestionAnswer;
}

export interface ToolCallEvent {
  name: string;
  status: "running" | "done";
}

export interface ChatMessage {
  id?: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  toolCalls?: ToolCallEvent[];
  isError?: boolean;
}

export interface SessionSummary {
  id: number;
  module: ModuleType;
  title: string;
  created_at: string;
  active_question_id?: number | null;
}

export interface GroupedSessions {
  writing: SessionSummary[];
  reading: SessionSummary[];
  translation: SessionSummary[];
}

export interface SessionDetail {
  id: number;
  module: ModuleType;
  title: string;
  created_at: string;
  active_question_id: number | null;
  active_question: QuestionPublic | null;
  draft_answer: unknown;
  messages: ChatMessage[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface WorkspaceUpdateResponse {
  id: number;
  active_question_id: number | null;
  active_question: QuestionPublic | null;
  draft_answer: unknown;
}

export interface ExamPaper {
  id: number;
  year?: number | null;
  month?: number | null;
  exam_level?: string | null;
  set_no?: number | null;
  title: string;
  pdf_path?: string | null;
  mineru_task_id?: string | null;
  raw_markdown?: string | null;
  status: string;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PaperDetailResponse {
  paper: ExamPaper;
  questions: QuestionPublic[];
}

export interface AdminQuestionPayload {
  paper_id?: number | null;
  exam_level: string;
  module: ModuleType;
  sub_type: string;
  year?: number | null;
  month?: number | null;
  set_no?: number | null;
  title: string;
  topic?: string | null;
  content: QuestionContent;
  answer: QuestionAnswer;
  status?: string;
}

export type AppView = "home" | "chat" | "bank" | "admin" | "settings" | "auth";
