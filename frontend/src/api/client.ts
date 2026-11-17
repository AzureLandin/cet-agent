import type {
  AdminQuestionPayload,
  AuthResponse,
  ExamPaper,
  GroupedSessions,
  ModuleType,
  PaperDetailResponse,
  ProfileUpdatePayload,
  QuestionListResponse,
  QuestionPublic,
  SessionDetail,
  SubmitQuestionResponse,
  ToolCallEvent,
  UserProfile,
  WorkspaceUpdateResponse,
} from "../types";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: {
      ...headers,
      ...(options.headers as Record<string, string> | undefined),
    },
  });

  if (response.status === 401) {
    const errBody = await response.json().catch(() => ({}));
    throw new ApiError(
      errBody.message || "请先登录后再继续。",
      errBody.error_code || "UNAUTHORIZED",
      401
    );
  }

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    throw new ApiError(
      errBody.message || `HTTP ${response.status}`,
      errBody.error_code || `HTTP_${response.status}`,
      response.status
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/* ===== Auth ===== */

export function register(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function login(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout(): Promise<{ message: string }> {
  return request<{ message: string }>("/auth/logout", { method: "POST" });
}

/* ===== Profile ===== */

export function getProfile(): Promise<UserProfile> {
  return request<UserProfile>("/profile", { method: "GET" });
}

export function updateProfile(data: ProfileUpdatePayload): Promise<{ message: string }> {
  return request<{ message: string }>("/profile", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function uploadAvatar(file: File): Promise<{ avatar_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  return request<{ avatar_url: string }>("/profile/avatar", {
    method: "POST",
    body: formData,
  });
}

export function deleteAvatar(): Promise<{ message: string }> {
  return request<{ message: string }>("/profile/avatar", { method: "DELETE" });
}

/* ===== Sessions & Workspace ===== */

export function createSession(
  module: ModuleType,
  questionId?: number
): Promise<SessionDetail> {
  const body: { module: ModuleType; question_id?: number } = { module };
  if (questionId !== undefined) {
    body.question_id = questionId;
  }
  return request<SessionDetail>("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSessions(): Promise<GroupedSessions> {
  return request<GroupedSessions>("/sessions", { method: "GET" });
}

export function getSession(id: number): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${id}`, { method: "GET" });
}

export function updateSessionWorkspace(
  id: number,
  payload: { active_question_id?: number | null; draft_answer?: unknown }
): Promise<WorkspaceUpdateResponse> {
  return request<WorkspaceUpdateResponse>(`/sessions/${id}/workspace`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteSession(id: number): Promise<{ message?: string } | void> {
  return request(`/sessions/${id}`, { method: "DELETE" });
}

/* ===== SSE Messages ===== */

export interface StreamCallbacks {
  onToolCall?: (event: ToolCallEvent) => void;
  onQuestionLoaded?: (question: QuestionPublic) => void;
  onToken?: (token: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

const STREAM_IDLE_TIMEOUT_MS = 120_000;

export async function sendMessageStream(
  sessionId: number,
  content: string,
  callbacks: StreamCallbacks,
  externalSignal?: AbortSignal
): Promise<void> {
  const { onToolCall, onQuestionLoaded, onToken, onDone, onError } = callbacks;

  const controller = new AbortController();
  let timedOut = false;

  let timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, STREAM_IDLE_TIMEOUT_MS);

  const resetTimeout = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, STREAM_IDLE_TIMEOUT_MS);
  };

  const handleExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) {
      window.clearTimeout(timeoutId);
      return;
    }
    externalSignal.addEventListener("abort", handleExternalAbort);
  }

  let finishedNormally = false;

  try {
    const response = await fetch(`/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ content }),
      signal: controller.signal,
    });

    if (response.status === 401) {
      const err = new ApiError("Authentication required.", "UNAUTHORIZED", 401);
      onError?.(err);
      return;
    }

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const err = new ApiError(
        errBody.message || `HTTP ${response.status}`,
        errBody.error_code || `HTTP_${response.status}`,
        response.status
      );
      onError?.(err);
      return;
    }

    if (!response.body) {
      onError?.(new Error("Empty response stream"));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          if (!jsonStr) continue;

          let payload: { event?: string; data?: unknown };
          try {
            payload = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          resetTimeout();

          switch (payload.event) {
            case "tool_call":
              if (payload.data && typeof payload.data === "object") {
                onToolCall?.(payload.data as ToolCallEvent);
              }
              break;
            case "question_loaded":
              if (payload.data && typeof payload.data === "object") {
                onQuestionLoaded?.(payload.data as QuestionPublic);
              }
              break;
            case "token":
              if (typeof payload.data === "string") {
                onToken?.(payload.data);
              }
              break;
            case "done":
              finishedNormally = true;
              onDone?.();
              break;
            case "error":
              finishedNormally = true;
              onError?.(
                new Error(
                  typeof payload.data === "string"
                    ? payload.data
                    : "AI 回复过程中发生错误"
                )
              );
              break;
          }
        }
      }

      if (!finishedNormally) {
        onDone?.();
      }
    } finally {
      reader.releaseLock();
    }
  } catch (err) {
    if (timedOut) {
      onError?.(new ApiError("响应超时，请重试", "TIMEOUT", 408));
      return;
    }
    if (externalSignal?.aborted) {
      return;
    }
    onError?.(err instanceof Error ? err : new Error("网络请求失败"));
  } finally {
    window.clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", handleExternalAbort);
  }
}

/* ===== Question Bank ===== */

export interface QuestionQueryParams {
  exam_level?: string;
  module?: string;
  sub_type?: string;
  year?: string | number;
  topic?: string;
  status?: string;
  include_answer?: boolean;
  limit?: number;
  offset?: number;
}

export function listQuestions(
  params: QuestionQueryParams = {}
): Promise<QuestionListResponse> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") {
      if (key === "include_answer") {
        if (val) qs.set(key, "1");
      } else {
        qs.set(key, String(val));
      }
    }
  });
  const query = qs.toString();
  return request<QuestionListResponse>(`/questions${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export function getQuestion(
  id: number,
  includeAnswer = false
): Promise<QuestionPublic> {
  const suffix = includeAnswer ? "?include_answer=1" : "";
  return request<QuestionPublic>(`/questions/${id}${suffix}`, { method: "GET" });
}

export function submitQuestion(
  id: number,
  userAnswers: unknown,
  sessionId?: number
): Promise<SubmitQuestionResponse> {
  const body: { user_answers: unknown; session_id?: number } = {
    user_answers: userAnswers,
  };
  if (sessionId !== undefined) {
    body.session_id = sessionId;
  }
  return request<SubmitQuestionResponse>(`/questions/${id}/submit`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/* ===== Admin Studio ===== */

export function uploadPaper(params: {
  file: File;
  year?: number | string;
  month?: number | string;
  exam_level?: string;
  set_no?: number | string;
  title: string;
}): Promise<{ paper: ExamPaper }> {
  const formData = new FormData();
  formData.append("file", params.file);
  formData.append("title", params.title);
  if (params.year) formData.append("year", String(params.year));
  if (params.month) formData.append("month", String(params.month));
  if (params.exam_level) formData.append("exam_level", params.exam_level);
  if (params.set_no) formData.append("set_no", String(params.set_no));

  return request<{ paper: ExamPaper }>("/admin/papers/upload", {
    method: "POST",
    body: formData,
  });
}

export function listPapers(): Promise<{ items: ExamPaper[] }> {
  return request<{ items: ExamPaper[] }>("/admin/papers", { method: "GET" });
}

export function getPaper(id: number): Promise<PaperDetailResponse> {
  return request<PaperDetailResponse>(`/admin/papers/${id}`, { method: "GET" });
}

export function parsePaper(
  id: number,
  rawMarkdown?: string
): Promise<PaperDetailResponse> {
  const body =
    rawMarkdown !== undefined ? { raw_markdown: rawMarkdown } : {};
  return request<PaperDetailResponse>(`/admin/papers/${id}/parse`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function publishPaper(
  id: number
): Promise<{ paper: ExamPaper; published_count: number }> {
  return request<{ paper: ExamPaper; published_count: number }>(
    `/admin/papers/${id}/publish`,
    { method: "POST" }
  );
}

export function createAdminQuestion(
  payload: AdminQuestionPayload
): Promise<QuestionPublic> {
  return request<QuestionPublic>("/admin/questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAdminQuestion(
  id: number,
  payload: Partial<AdminQuestionPayload>
): Promise<QuestionPublic> {
  return request<QuestionPublic>(`/admin/questions/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminQuestion(id: number): Promise<{ message?: string }> {
  return request<{ message?: string }>(`/admin/questions/${id}`, {
    method: "DELETE",
  });
}

export function healthCheck(): Promise<{ status: string; db: boolean }> {
  return request<{ status: string; db: boolean }>("/health", { method: "GET" });
}
