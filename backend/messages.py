from __future__ import annotations

import json
import os
import re
from typing import Literal

from flask import Blueprint, Response, g, jsonify, request, stream_with_context
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
)
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from db import DB
from questions import serialize_question
from services.model_client import extract_message_text, to_langchain_messages

messages_bp = Blueprint("messages", __name__)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 50
MAX_TOOL_ROUNDS = 5

_TOOL_MARKUP_RE = re.compile(
    r"<tool_call\b[\s\S]*?(?:</tool_call>|$)"
    r"|<function=[\s\S]*?(?:</function>|$)"
    r"|<\|tool_call\|>[\s\S]*?(?:<\|/tool_call\|>|$)"
    r"|<\|tool_calls_section_begin\|>[\s\S]*?(?:<\|tool_calls_section_end\|>|$)",
    re.IGNORECASE,
)


def _strip_tool_markup(text: str) -> str:
    if not text:
        return ""
    return _TOOL_MARKUP_RE.sub("", text).strip()


class _ToolMarkupStreamFilter:
    """Suppress inline <tool_call> / <function=...> markup from streamed text."""

    _OPENERS = (
        ("<tool_call", "</tool_call>"),
        ("<function=", "</function>"),
        ("<|tool_call|>", "<|/tool_call|>"),
        ("<|tool_calls_section_begin|>", "<|tool_calls_section_end|>"),
    )

    def __init__(self) -> None:
        self._buf = ""
        self._close_tag: str | None = None

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buf += chunk
        out: list[str] = []

        while self._buf:
            if self._close_tag is not None:
                end_idx = self._buf.find(self._close_tag)
                if end_idx == -1:
                    keep = len(self._close_tag) - 1
                    if len(self._buf) > keep:
                        self._buf = self._buf[-keep:]
                    break
                self._buf = self._buf[end_idx + len(self._close_tag) :]
                self._close_tag = None
                continue

            lt_idx = self._buf.find("<")
            if lt_idx == -1:
                out.append(self._buf)
                self._buf = ""
                break

            if lt_idx > 0:
                out.append(self._buf[:lt_idx])
                self._buf = self._buf[lt_idx:]

            matched_opener = False
            could_be_prefix = False
            lower_buf = self._buf.lower()
            for opener, closer in self._OPENERS:
                if lower_buf.startswith(opener):
                    self._buf = self._buf[len(opener) :]
                    self._close_tag = closer
                    matched_opener = True
                    break
                if opener.startswith(lower_buf):
                    could_be_prefix = True

            if matched_opener:
                continue
            if could_be_prefix:
                break

            out.append("<")
            self._buf = self._buf[1:]

        return "".join(out)

    def flush(self) -> str:
        if self._close_tag is not None:
            self._buf = ""
            self._close_tag = None
            return ""
        rem = self._buf
        self._buf = ""
        return rem

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_questions",
            "description": "Search published CET-4/CET-6 questions from the question bank.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exam_level": {
                        "type": "string",
                        "enum": ["CET4", "CET6"],
                        "description": "Filter by exam level (CET4 or CET6).",
                    },
                    "module": {
                        "type": "string",
                        "enum": ["writing", "reading", "translation"],
                        "description": "Filter by module.",
                    },
                    "sub_type": {
                        "type": "string",
                        "description": "Optional sub-type, e.g. essay, careful_reading, banked_cloze, matching, paragraph_translation.",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional exam year, e.g. 2024.",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic keyword.",
                    },
                    "unpracticed_only": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to prioritize questions the student has not practiced yet.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_question_practice",
            "description": "Bind a specific question to the current practice session and load it into the student's left workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "integer",
                        "description": "The ID of the question to load into the workspace.",
                    },
                },
                "required": ["question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_answer_key",
            "description": "Retrieve the official answer key, explanations, reference essay/translation, and synonyms for a question so you can give accurate hints or grade submissions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "integer",
                        "description": "The ID of the question.",
                    },
                },
                "required": ["question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_practice_result",
            "description": "Record a graded practice attempt score and feedback summary for a student's question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "integer",
                        "description": "The ID of the question practiced.",
                    },
                    "score": {
                        "type": "number",
                        "description": "Score awarded.",
                    },
                    "total": {
                        "type": "number",
                        "description": "Maximum possible score.",
                    },
                    "feedback_summary": {
                        "type": "string",
                        "description": "Short summary of grading feedback.",
                    },
                },
                "required": ["question_id", "score", "total"],
            },
        },
    },
]


def load_module_prompt(module: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(base_dir, "prompts", f"cet-{module}.txt")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"You are a CET {module} coach."


def build_messages(
    db: DB,
    session_id: int,
    module: str,
    user_content: str,
    profile: dict = None,
    active_question: dict = None,
):
    system_prompt = load_module_prompt(module)
    parts = [system_prompt]
    if profile:
        level = profile.get("exam_level") or "CET"
        parts.append(f"The user is preparing for {level}.")
        exam_date = profile.get("exam_date")
        if exam_date:
            parts.append(f"Their exam date is {exam_date}.")

    parts.append(
        "\n## 题库工具使用说明\n"
        "- 当学生希望从题库出题/抽题练习时，先调用 `search_questions` 查找合适题目，再调用 `start_question_practice(question_id)` 将题目加载到左侧做题面板。\n"
        "- 当学生针对当前题目求提示或提交答案请求批改时，可调用一次 `get_answer_key(question_id)` 核对标准答案、参考范文/译文与同义替换（已获取过的题目无需重复调用），但不要在学生未请求公布答案前直接剧透完整答案。\n"
        "- 对主观题（写作/翻译）完成批改打分后，调用一次 `record_practice_result` 记录本次练习成绩，随后必须立即向学生输出完整的批改报告。\n"
        "- 不要在回复正文中输出 `<tool_call>`、`<function=...>` 等原始工具调用标签。"
    )

    if active_question:
        question_context = {
            "id": active_question.get("id"),
            "exam_level": active_question.get("exam_level"),
            "module": active_question.get("module"),
            "sub_type": active_question.get("sub_type"),
            "year": active_question.get("year"),
            "month": active_question.get("month"),
            "title": active_question.get("title"),
            "content": active_question.get("content"),
        }
        parts.append(
            "\n## 当前左侧练习面板已加载题目\n"
            f"```json\n{json.dumps(question_context, ensure_ascii=False)}\n```"
        )

    messages = [{"role": "system", "content": "\n".join(parts)}]

    history = db.fetchall(
        """
        SELECT role, content FROM (
            SELECT id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        ) sub
        ORDER BY created_at ASC, id ASC
        """,
        (session_id, MAX_HISTORY_MESSAGES),
    )
    for row in history:
        if row["role"] == "user":
            messages.append({"role": "user", "content": row["content"]})
        elif row["role"] == "assistant":
            clean_hist = _strip_tool_markup(row["content"])
            if clean_hist:
                messages.append({"role": "assistant", "content": clean_hist})

    if not history or history[-1]["role"] != "user" or history[-1]["content"] != user_content:
        messages.append({"role": "user", "content": user_content})
    return messages


def _coerce_int_id(raw_value) -> int | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(raw_value)
    except (ValueError, TypeError):
        return None


def _execute_tool(
    db: DB,
    user_id: int,
    session_id: int,
    tool_name: str,
    arguments: dict,
    active_question_id: int | None = None,
) -> tuple[dict, dict | None]:
    """Execute one agent tool. Returns (result_for_llm, optional_loaded_question)."""
    if tool_name == "search_questions":
        conditions = ["status = 'published'"]
        params: list = []

        if arguments.get("exam_level"):
            conditions.append("exam_level = ?")
            params.append(str(arguments["exam_level"]).upper())
        if arguments.get("module"):
            conditions.append("module = ?")
            params.append(str(arguments["module"]).lower())
        if arguments.get("sub_type"):
            conditions.append("sub_type = ?")
            params.append(str(arguments["sub_type"]).lower())
        if arguments.get("year") is not None:
            conditions.append("year = ?")
            params.append(int(arguments["year"]))
        if arguments.get("topic"):
            conditions.append("topic LIKE ?")
            params.append(f"%{str(arguments['topic']).strip()}%")

        unpracticed_only = arguments.get("unpracticed_only", True)
        if unpracticed_only:
            conditions.append(
                "id NOT IN (SELECT question_id FROM practice_attempts WHERE user_id = ?)"
            )
            params.append(user_id)

        where_clause = f"WHERE {' AND '.join(conditions)}"
        rows = db.fetchall(
            f"""
            SELECT id, exam_level, module, sub_type, year, month, set_no, title, topic
            FROM questions
            {where_clause}
            ORDER BY year DESC, month DESC, id DESC
            LIMIT 10
            """,
            tuple(params),
        )
        # Fallback to practiced questions if unpracticed filter yielded empty
        if not rows and unpracticed_only:
            base_conditions = [c for c in conditions if "practice_attempts" not in c]
            base_params = params[:-1]
            rows = db.fetchall(
                f"""
                SELECT id, exam_level, module, sub_type, year, month, set_no, title, topic
                FROM questions
                WHERE {' AND '.join(base_conditions)}
                ORDER BY year DESC, month DESC, id DESC
                LIMIT 10
                """,
                tuple(base_params),
            )
        return {"questions": rows, "count": len(rows)}, None

    if tool_name == "start_question_practice":
        question_id = _coerce_int_id(arguments.get("question_id") or arguments.get("id"))
        if question_id is None:
            return {"error": "question_id is required."}, None
        row = db.fetchone(
            """
            SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
                   title, topic, content_json, answer_json, status, created_at
            FROM questions
            WHERE id = ? AND status = 'published'
            """,
            (question_id,),
        )
        if not row:
            return {"error": f"Published question {question_id} not found."}, None

        db.execute(
            """
            UPDATE sessions
            SET active_question_id = ?, draft_answer_json = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (question_id, session_id, user_id),
        )
        public_question = serialize_question(row, include_answer=False)
        return {"loaded": True, "question": public_question}, public_question

    if tool_name == "get_answer_key":
        question_id = _coerce_int_id(
            arguments.get("question_id") or arguments.get("id") or active_question_id
        )
        if question_id is None:
            return {"error": "question_id is required."}, None
        row = db.fetchone(
            "SELECT id, title, module, sub_type, answer_json FROM questions WHERE id = ? AND status = 'published'",
            (question_id,),
        )
        if not row:
            return {"error": f"Question {question_id} not found."}, None
        try:
            answer = json.loads(row["answer_json"])
        except (ValueError, TypeError):
            answer = {}
        return {
            "question_id": row["id"],
            "title": row["title"],
            "module": row["module"],
            "sub_type": row["sub_type"],
            "answer": answer,
        }, None

    if tool_name == "record_practice_result":
        question_id = _coerce_int_id(
            arguments.get("question_id") or arguments.get("id") or active_question_id
        )
        score = arguments.get("score")
        total = arguments.get("total")
        feedback_summary = arguments.get("feedback_summary")
        if question_id is None:
            return {"error": "question_id is required."}, None
        row = db.fetchone("SELECT id FROM questions WHERE id = ?", (question_id,))
        if not row:
            return {"error": f"Question {question_id} not found."}, None

        user_answers_json = (
            json.dumps({"feedback_summary": feedback_summary}, ensure_ascii=False)
            if feedback_summary
            else None
        )
        attempt_id = db.lastrowid(
            """
            INSERT INTO practice_attempts (user_id, question_id, session_id, user_answers_json, score, total, is_completed)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, question_id, session_id, user_answers_json, score, total),
        )
        return {"recorded": True, "attempt_id": attempt_id}, None

    return {"error": f"Unknown tool: {tool_name}"}, None


class _SearchQuestionsInput(BaseModel):
    exam_level: Literal["CET4", "CET6"] | None = Field(
        default=None,
        description="Filter by exam level (CET4 or CET6).",
    )
    module: Literal["writing", "reading", "translation"] | None = Field(
        default=None,
        description="Filter by module.",
    )
    sub_type: str | None = Field(
        default=None,
        description="Optional sub-type, e.g. essay, careful_reading, banked_cloze, matching, paragraph_translation.",
    )
    year: int | None = Field(default=None, description="Optional exam year, e.g. 2024.")
    topic: str | None = Field(default=None, description="Optional topic keyword.")
    unpracticed_only: bool = Field(
        default=True,
        description="Whether to prioritize questions the student has not practiced yet.",
    )


class _QuestionIdInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question_id: int | None = Field(default=None, description="The ID of the question.")

    @model_validator(mode="before")
    @classmethod
    def _accept_id_alias(cls, data):
        if isinstance(data, dict) and data.get("question_id") is None and data.get("id") is not None:
            return {**data, "question_id": data["id"]}
        return data


class _RecordPracticeResultInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question_id: int | None = Field(default=None, description="The ID of the question practiced.")
    score: float = Field(..., description="Score awarded.")
    total: float = Field(..., description="Maximum possible score.")
    feedback_summary: str | None = Field(default=None, description="Short summary of grading feedback.")

    @model_validator(mode="before")
    @classmethod
    def _accept_id_alias(cls, data):
        if isinstance(data, dict) and data.get("question_id") is None and data.get("id") is not None:
            return {**data, "question_id": data["id"]}
        return data


class _ForceSynthesisAfterToolRoundsMiddleware(AgentMiddleware):
    """Disable tools after `max_tool_rounds` so the model must emit a final user-facing response."""

    def __init__(self, max_tool_rounds: int = MAX_TOOL_ROUNDS) -> None:
        super().__init__()
        self.max_tool_rounds = max_tool_rounds

    def wrap_model_call(self, request: ModelRequest, handler):
        ai_turns_in_run = 0
        for msg in reversed(request.messages):
            if isinstance(msg, HumanMessage):
                break
            if isinstance(msg, AIMessage):
                ai_turns_in_run += 1

        if ai_turns_in_run >= self.max_tool_rounds and request.tools:
            request = request.override(tools=[], tool_choice=None)
        return handler(request)


def _on_tool_error(exc: Exception, request: ToolCallRequest) -> str:
    tool_name = request.tool_call.get("name", "unknown")
    return json.dumps(
        {"error": f"Tool '{tool_name}' failed: {type(exc).__name__}: {exc}"},
        ensure_ascii=False,
    )


def _build_langchain_tools(db: DB, user_id: int, session_id: int, state_tracker: dict):
    @tool("search_questions", args_schema=_SearchQuestionsInput)
    def search_questions(
        exam_level: str | None = None,
        module: str | None = None,
        sub_type: str | None = None,
        year: int | None = None,
        topic: str | None = None,
        unpracticed_only: bool = True,
    ) -> str:
        """Search published CET-4/CET-6 questions from the question bank."""
        args = {
            "exam_level": exam_level,
            "module": module,
            "sub_type": sub_type,
            "year": year,
            "topic": topic,
            "unpracticed_only": unpracticed_only,
        }
        result_obj, _ = _execute_tool(
            db,
            user_id,
            session_id,
            "search_questions",
            {k: v for k, v in args.items() if v is not None},
            active_question_id=state_tracker.get("active_question_id"),
        )
        return json.dumps(result_obj, ensure_ascii=False)

    @tool("start_question_practice", args_schema=_QuestionIdInput)
    def start_question_practice(question_id: int | None = None) -> str:
        """Bind a specific question to the current practice session and load it into the student's left workspace."""
        result_obj, loaded_question = _execute_tool(
            db,
            user_id,
            session_id,
            "start_question_practice",
            {"question_id": question_id},
            active_question_id=state_tracker.get("active_question_id"),
        )
        if loaded_question is not None:
            state_tracker["active_question_id"] = loaded_question["id"]
            state_tracker["loaded_questions"].append(loaded_question)
        return json.dumps(result_obj, ensure_ascii=False)

    @tool("get_answer_key", args_schema=_QuestionIdInput)
    def get_answer_key(question_id: int | None = None) -> str:
        """Retrieve the official answer key, explanations, reference essay/translation, and synonyms for a question so you can give accurate hints or grade submissions."""
        result_obj, _ = _execute_tool(
            db,
            user_id,
            session_id,
            "get_answer_key",
            {"question_id": question_id},
            active_question_id=state_tracker.get("active_question_id"),
        )
        return json.dumps(result_obj, ensure_ascii=False)

    @tool("record_practice_result", args_schema=_RecordPracticeResultInput)
    def record_practice_result(
        score: float,
        total: float,
        question_id: int | None = None,
        feedback_summary: str | None = None,
    ) -> str:
        """Record a graded practice attempt score and feedback summary for a student's question."""
        result_obj, _ = _execute_tool(
            db,
            user_id,
            session_id,
            "record_practice_result",
            {
                "question_id": question_id,
                "score": score,
                "total": total,
                "feedback_summary": feedback_summary,
            },
            active_question_id=state_tracker.get("active_question_id"),
        )
        return json.dumps(result_obj, ensure_ascii=False)

    return [search_questions, start_question_practice, get_answer_key, record_practice_result]


def _stream_langchain_agent(
    chat_model,
    messages: list[dict],
    db: DB,
    user_id: int,
    session_id: int,
    active_qid: int | None,
    assistant_chunks: list[str],
):
    system_prompt = ""
    conv_dicts = messages
    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0].get("content") or ""
        conv_dicts = messages[1:]

    lc_messages = to_langchain_messages(conv_dicts)
    state_tracker = {"active_question_id": active_qid, "loaded_questions": []}
    lc_tools = _build_langchain_tools(db, user_id, session_id, state_tracker)

    agent = create_agent(
        model=chat_model,
        tools=lc_tools,
        system_prompt=system_prompt,
        middleware=[
            _ForceSynthesisAfterToolRoundsMiddleware(max_tool_rounds=MAX_TOOL_ROUNDS),
            ToolCallLimitMiddleware(tool_name="get_answer_key", run_limit=2, exit_behavior="continue"),
            ToolCallLimitMiddleware(run_limit=8, exit_behavior="continue"),
            ToolErrorMiddleware(on_error=_on_tool_error),
        ],
    )

    markup_filter = _ToolMarkupStreamFilter()
    emitted_indices_this_round: set[int] = set()
    running_emitted_this_round = 0

    for mode, data in agent.stream(
        {"messages": lc_messages},
        stream_mode=["messages", "updates"],
        config={"recursion_limit": 30},
    ):
        if mode == "messages":
            msg_chunk, metadata = data
            node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None
            if node not in (None, "model"):
                continue
            if not isinstance(msg_chunk, (AIMessageChunk, AIMessage)):
                continue

            raw_text = extract_message_text(msg_chunk.content)
            if raw_text:
                visible = markup_filter.feed(raw_text)
                if visible:
                    assistant_chunks.append(visible)
                    payload = json.dumps({"event": "token", "data": visible}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

            for tcc in getattr(msg_chunk, "tool_call_chunks", None) or []:
                tc_name = tcc.get("name")
                tc_idx = tcc.get("index")
                if tc_name:
                    key_idx = tc_idx if isinstance(tc_idx, int) else running_emitted_this_round
                    if key_idx not in emitted_indices_this_round:
                        emitted_indices_this_round.add(key_idx)
                        running_emitted_this_round += 1
                        running_evt = json.dumps(
                            {"event": "tool_call", "data": {"name": tc_name, "status": "running"}},
                            ensure_ascii=False,
                        )
                        yield f"data: {running_evt}\n\n"

        elif mode == "updates" and isinstance(data, dict):
            if "model" in data:
                tail = markup_filter.flush()
                if tail:
                    assistant_chunks.append(tail)
                    payload = json.dumps({"event": "token", "data": tail}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                markup_filter = _ToolMarkupStreamFilter()

                model_msgs = (data["model"] or {}).get("messages") or []
                for m in model_msgs:
                    if isinstance(m, AIMessage) and m.tool_calls:
                        for tc in m.tool_calls[running_emitted_this_round:]:
                            tc_name = tc.get("name") or ""
                            if tc_name:
                                running_evt = json.dumps(
                                    {"event": "tool_call", "data": {"name": tc_name, "status": "running"}},
                                    ensure_ascii=False,
                                )
                                yield f"data: {running_evt}\n\n"

                emitted_indices_this_round.clear()
                running_emitted_this_round = 0

            if "tools" in data:
                while state_tracker["loaded_questions"]:
                    loaded_q = state_tracker["loaded_questions"].pop(0)
                    q_evt = json.dumps(
                        {"event": "question_loaded", "data": loaded_q},
                        ensure_ascii=False,
                    )
                    yield f"data: {q_evt}\n\n"

                tool_msgs = (data["tools"] or {}).get("messages") or []
                for tm in tool_msgs:
                    if isinstance(tm, ToolMessage) and tm.name:
                        done_evt = json.dumps(
                            {"event": "tool_call", "data": {"name": tm.name, "status": "done"}},
                            ensure_ascii=False,
                        )
                        yield f"data: {done_evt}\n\n"

    tail = markup_filter.flush()
    if tail:
        assistant_chunks.append(tail)
        payload = json.dumps({"event": "token", "data": tail}, ensure_ascii=False)
        yield f"data: {payload}\n\n"


@messages_bp.post("/sessions/<int:session_id>/messages")
def send_message(session_id: int):
    db: DB = g.db
    user_id = g.user_id

    # Verify session ownership
    session_row = db.fetchone(
        "SELECT id, module, active_question_id FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    data = request.get_json(silent=True) or {}
    user_content = (data.get("content") or "").strip()
    if not user_content:
        return jsonify(error_code="EMPTY_MESSAGE", message="Message content is required."), 400
    if len(user_content) > MAX_MESSAGE_LENGTH:
        return jsonify(error_code="MESSAGE_TOO_LONG", message=f"Max message length is {MAX_MESSAGE_LENGTH}."), 400

    # Store user message + bump session timestamp atomically
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "user", user_content),
        )
        cur.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))

    # Fetch profile
    profile = db.fetchone(
        "SELECT exam_level, exam_date FROM profiles WHERE user_id = ?",
        (user_id,),
    )

    active_question = None
    active_qid = session_row.get("active_question_id")
    if active_qid is not None:
        q_row = db.fetchone(
            """
            SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
                   title, topic, content_json, answer_json, status, created_at
            FROM questions
            WHERE id = ?
            """,
            (active_qid,),
        )
        if q_row:
            active_question = serialize_question(q_row, include_answer=False)

    messages = build_messages(
        db,
        session_id,
        session_row["module"],
        user_content,
        profile,
        active_question=active_question,
    )

    client = g.model_client

    def generate():
        assistant_chunks: list[str] = []
        current_active_qid = active_qid

        def stream_round(conversation: list[dict], tools: list[dict] | None):
            markup_filter = _ToolMarkupStreamFilter()
            pending_tool_calls = None
            round_text: list[str] = []

            for evt in client.chat_completion_stream_events(conversation, tools=tools):
                if evt["type"] == "token":
                    visible = markup_filter.feed(evt["content"])
                    if visible:
                        round_text.append(visible)
                        assistant_chunks.append(visible)
                        payload = json.dumps({"event": "token", "data": visible}, ensure_ascii=False)
                        yield "sse", f"data: {payload}\n\n"
                elif evt["type"] == "tool_calls":
                    pending_tool_calls = evt["tool_calls"]

            tail = markup_filter.flush()
            if tail:
                round_text.append(tail)
                assistant_chunks.append(tail)
                payload = json.dumps({"event": "token", "data": tail}, ensure_ascii=False)
                yield "sse", f"data: {payload}\n\n"

            yield "result", ("".join(round_text), pending_tool_calls)

        try:
            if hasattr(client, "get_chat_model"):
                yield from _stream_langchain_agent(
                    client.get_chat_model(),
                    messages,
                    db,
                    user_id,
                    session_id,
                    active_qid,
                    assistant_chunks,
                )
            elif hasattr(client, "chat_completion_stream_events"):
                conversation = list(messages)
                any_tool_executed = False
                hit_tool_limit = True

                for _round in range(MAX_TOOL_ROUNDS):
                    round_text_str = ""
                    pending_tool_calls = None
                    for kind, val in stream_round(conversation, tools=AGENT_TOOLS):
                        if kind == "sse":
                            yield val
                        else:
                            round_text_str, pending_tool_calls = val

                    if not pending_tool_calls:
                        hit_tool_limit = False
                        break

                    any_tool_executed = True
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": round_text_str or None,
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc["arguments"] or "{}",
                                    },
                                }
                                for tc in pending_tool_calls
                            ],
                        }
                    )

                    for tc in pending_tool_calls:
                        tool_name = tc["name"]
                        running_evt = json.dumps(
                            {"event": "tool_call", "data": {"name": tool_name, "status": "running"}},
                            ensure_ascii=False,
                        )
                        yield f"data: {running_evt}\n\n"

                        try:
                            args = json.loads(tc["arguments"]) if tc.get("arguments") else {}
                            if not isinstance(args, dict):
                                args = {}
                        except (ValueError, TypeError):
                            args = {}

                        result_obj, loaded_question = _execute_tool(
                            db,
                            user_id,
                            session_id,
                            tool_name,
                            args,
                            active_question_id=current_active_qid,
                        )
                        if loaded_question is not None:
                            current_active_qid = loaded_question["id"]
                            q_evt = json.dumps(
                                {"event": "question_loaded", "data": loaded_question},
                                ensure_ascii=False,
                            )
                            yield f"data: {q_evt}\n\n"

                        done_evt = json.dumps(
                            {"event": "tool_call", "data": {"name": tool_name, "status": "done"}},
                            ensure_ascii=False,
                        )
                        yield f"data: {done_evt}\n\n"

                        conversation.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(result_obj, ensure_ascii=False),
                            }
                        )

                # Ensure a final user-facing response is generated if tool rounds hit the limit
                # or if the model ended without emitting visible text after executing tools.
                if hit_tool_limit or (any_tool_executed and not "".join(assistant_chunks).strip()):
                    for kind, val in stream_round(conversation, tools=None):
                        if kind == "sse":
                            yield val
            else:
                markup_filter = _ToolMarkupStreamFilter()
                for chunk in client.chat_completion_stream(messages):
                    visible = markup_filter.feed(chunk)
                    if visible:
                        assistant_chunks.append(visible)
                        payload = json.dumps({"event": "token", "data": visible}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                tail = markup_filter.flush()
                if tail:
                    assistant_chunks.append(tail)
                    payload = json.dumps({"event": "token", "data": tail}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

            full_response = _strip_tool_markup("".join(assistant_chunks))
            with db.transaction() as cur:
                cur.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", full_response),
                )
                cur.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
            payload = json.dumps({"event": "done", "data": ""})
            yield f"data: {payload}\n\n"
        except Exception as e:
            payload = json.dumps({"event": "error", "data": str(e)})
            yield f"data: {payload}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
