from __future__ import annotations

import json
import os
import uuid
from flask import Blueprint, current_app, g, jsonify, request

from db import DB
from services.mineru_client import MinerUClient, MinerUError, extract_questions_from_markdown

questions_bp = Blueprint("questions", __name__, url_prefix="/questions")
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

VALID_EXAM_LEVELS = {"CET4", "CET6"}
VALID_MODULES = {"writing", "reading", "translation"}
VALID_STATUSES = {"draft", "published"}
ALLOWED_PAPER_EXTENSIONS = {"pdf", "md", "markdown", "txt"}


def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _parse_json(raw, default):
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def serialize_question(row: dict, include_answer: bool = False) -> dict:
    item = {
        "id": row["id"],
        "paper_id": row.get("paper_id"),
        "exam_level": row["exam_level"],
        "module": row["module"],
        "sub_type": row["sub_type"],
        "year": row.get("year"),
        "month": row.get("month"),
        "set_no": row.get("set_no", 1),
        "title": row["title"],
        "topic": row.get("topic"),
        "content": _parse_json(row.get("content_json"), {}),
        "status": row.get("status", "published"),
        "created_at": _to_iso(row.get("created_at")),
    }
    if include_answer:
        item["answer"] = _parse_json(row.get("answer_json"), {})
    return item


def serialize_paper(row: dict) -> dict:
    return {
        "id": row["id"],
        "year": row.get("year"),
        "month": row.get("month"),
        "exam_level": row.get("exam_level"),
        "set_no": row.get("set_no", 1),
        "title": row["title"],
        "pdf_path": row.get("pdf_path"),
        "mineru_task_id": row.get("mineru_task_id"),
        "raw_markdown": row.get("raw_markdown"),
        "status": row.get("status", "draft"),
        "error_message": row.get("error_message"),
        "created_at": _to_iso(row.get("created_at")),
        "updated_at": _to_iso(row.get("updated_at")),
    }


def _papers_upload_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "uploads", "papers")
    os.makedirs(d, exist_ok=True)
    return d


def _get_mineru_client() -> MinerUClient:
    client = getattr(g, "mineru_client", None)
    if client is not None:
        return client
    ext_client = current_app.extensions.get("mineru_client")
    if ext_client is not None:
        return ext_client
    return MinerUClient({})


@questions_bp.get("")
def list_questions():
    db: DB = g.db
    is_admin = getattr(g, "role", "student") == "admin"

    exam_level = request.args.get("exam_level", type=str)
    module = request.args.get("module", type=str)
    sub_type = request.args.get("sub_type", type=str)
    year = request.args.get("year", type=int)
    topic = request.args.get("topic", type=str)
    status_param = (request.args.get("status") or "published").strip().lower()
    include_answer_param = (request.args.get("include_answer") or "").strip().lower()
    include_answer = is_admin and include_answer_param in {"1", "true", "yes"}

    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conditions: list[str] = []
    params: list = []

    if is_admin:
        if status_param != "all":
            if status_param not in VALID_STATUSES:
                status_param = "published"
            conditions.append("status = ?")
            params.append(status_param)
    else:
        conditions.append("status = 'published'")

    if exam_level:
        conditions.append("exam_level = ?")
        params.append(exam_level.upper())
    if module:
        conditions.append("module = ?")
        params.append(module.lower())
    if sub_type:
        conditions.append("sub_type = ?")
        params.append(sub_type.lower())
    if year is not None:
        conditions.append("year = ?")
        params.append(year)
    if topic:
        conditions.append("topic LIKE ?")
        params.append(f"%{topic.strip()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total_row = db.fetchone(
        f"SELECT COUNT(*) AS total FROM questions {where_clause}",
        tuple(params),
    )
    total = total_row["total"] if total_row else 0

    rows = db.fetchall(
        f"""
        SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
               title, topic, content_json, answer_json, status, created_at
        FROM questions
        {where_clause}
        ORDER BY year DESC, month DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [limit, offset]),
    )

    items = [serialize_question(r, include_answer=include_answer) for r in rows]
    return jsonify(items=items, total=total, limit=limit, offset=offset)


@questions_bp.get("/<int:question_id>")
def get_question(question_id: int):
    db: DB = g.db
    is_admin = getattr(g, "role", "student") == "admin"
    include_answer_param = (request.args.get("include_answer") or "").strip().lower()
    include_answer = is_admin and include_answer_param in {"1", "true", "yes"}

    row = db.fetchone(
        """
        SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
               title, topic, content_json, answer_json, status, created_at
        FROM questions
        WHERE id = ?
        """,
        (question_id,),
    )
    if not row or (not is_admin and row["status"] != "published"):
        return jsonify(error_code="NOT_FOUND", message="Question not found."), 404

    return jsonify(serialize_question(row, include_answer=include_answer))


@questions_bp.post("/<int:question_id>/submit")
def submit_question(question_id: int):
    db: DB = g.db
    user_id = g.user_id
    is_admin = getattr(g, "role", "student") == "admin"

    row = db.fetchone(
        """
        SELECT id, module, sub_type, answer_json, status
        FROM questions
        WHERE id = ?
        """,
        (question_id,),
    )
    if not row or (not is_admin and row["status"] != "published"):
        return jsonify(error_code="NOT_FOUND", message="Question not found."), 404

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    user_answers = data.get("user_answers")

    if session_id is not None:
        session_row = db.fetchone(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if not session_row:
            return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    answer = _parse_json(row.get("answer_json"), {})
    correct_answers = answer.get("correct_answers") if isinstance(answer, dict) else None
    explanations = answer.get("explanations") if isinstance(answer, dict) else {}
    if not isinstance(explanations, dict):
        explanations = {}

    score = None
    total = None
    details: list[dict] = []

    if isinstance(correct_answers, dict) and len(correct_answers) > 0:
        user_map = {}
        if isinstance(user_answers, dict):
            user_map = {str(k): str(v).strip().upper() for k, v in user_answers.items() if v is not None}

        total = float(len(correct_answers))
        correct_count = 0
        for q_key, expected_raw in correct_answers.items():
            key_str = str(q_key)
            expected = str(expected_raw).strip().upper()
            actual = user_map.get(key_str, "")
            is_correct = actual == expected
            if is_correct:
                correct_count += 1
            details.append(
                {
                    "number": key_str,
                    "user_answer": actual,
                    "correct_answer": expected,
                    "is_correct": is_correct,
                    "explanation": explanations.get(key_str, ""),
                }
            )
        score = float(correct_count)

    serialized_answers = json.dumps(user_answers, ensure_ascii=False) if user_answers is not None else None
    attempt_id = db.lastrowid(
        """
        INSERT INTO practice_attempts (user_id, question_id, session_id, user_answers_json, score, total, is_completed)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (user_id, question_id, session_id, serialized_answers, score, total),
    )

    return jsonify(
        attempt_id=attempt_id,
        score=score,
        total=total,
        details=details,
        answer=answer,
    )


@admin_bp.before_request
def require_admin():
    if request.method == "OPTIONS":
        return None
    if getattr(g, "role", "student") != "admin":
        return jsonify(error_code="FORBIDDEN", message="Admin access required."), 403


@admin_bp.post("/papers/upload")
def upload_paper():
    db: DB = g.db
    if "file" not in request.files:
        return jsonify(error_code="NO_FILE", message="No file provided."), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error_code="NO_FILE", message="Empty filename."), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_PAPER_EXTENSIONS:
        return jsonify(
            error_code="INVALID_FILE_TYPE",
            message=f"Allowed paper types: {', '.join(sorted(ALLOWED_PAPER_EXTENSIONS))}.",
        ), 400

    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    exam_level = (request.form.get("exam_level") or "").strip().upper() or None
    if exam_level and exam_level not in VALID_EXAM_LEVELS:
        return jsonify(error_code="INVALID_EXAM_LEVEL", message="exam_level must be CET4 or CET6."), 400
    set_no = request.form.get("set_no", default=1, type=int) or 1
    title = (request.form.get("title") or "").strip() or os.path.splitext(file.filename)[0]

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    stored_path = os.path.join(_papers_upload_dir(), stored_name)
    file.save(stored_path)

    mineru_client = _get_mineru_client()
    mineru_task_id = None
    raw_markdown = None
    status = "draft"
    error_message = None

    try:
        task_info = mineru_client.upload_and_create_task(stored_path, filename=file.filename)
        mineru_task_id = task_info.get("task_id")
        if task_info.get("raw_markdown"):
            raw_markdown = task_info["raw_markdown"]
        status = task_info.get("status") or "draft"
        error_message = task_info.get("message")
    except Exception as exc:
        status = "failed"
        error_message = str(exc)

    paper_id = db.lastrowid(
        """
        INSERT INTO exam_papers (
            year, month, exam_level, set_no, title, pdf_path,
            mineru_task_id, raw_markdown, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (year, month, exam_level, set_no, title, stored_path, mineru_task_id, raw_markdown, status, error_message),
    )
    paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    return jsonify(paper=serialize_paper(paper)), 201


@admin_bp.get("/papers")
def list_papers():
    db: DB = g.db
    rows = db.fetchall("SELECT * FROM exam_papers ORDER BY created_at DESC, id DESC")
    return jsonify(items=[serialize_paper(r) for r in rows])


@admin_bp.get("/papers/<int:paper_id>")
def get_paper(paper_id: int):
    db: DB = g.db
    paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    if not paper:
        return jsonify(error_code="NOT_FOUND", message="Exam paper not found."), 404

    q_rows = db.fetchall(
        """
        SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
               title, topic, content_json, answer_json, status, created_at
        FROM questions
        WHERE paper_id = ?
        ORDER BY id ASC
        """,
        (paper_id,),
    )
    return jsonify(
        paper=serialize_paper(paper),
        questions=[serialize_question(q, include_answer=True) for q in q_rows],
    )


@admin_bp.post("/papers/<int:paper_id>/parse")
def parse_paper(paper_id: int):
    db: DB = g.db
    paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    if not paper:
        return jsonify(error_code="NOT_FOUND", message="Exam paper not found."), 404

    data = request.get_json(silent=True) or {}
    raw_markdown = data.get("raw_markdown")
    if raw_markdown is not None:
        raw_markdown = str(raw_markdown)
        db.execute(
            "UPDATE exam_papers SET raw_markdown = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (raw_markdown, paper_id),
        )
    else:
        raw_markdown = paper.get("raw_markdown")

    if (not raw_markdown or not raw_markdown.strip()) and paper.get("mineru_task_id"):
        mineru_client = _get_mineru_client()
        try:
            res = mineru_client.get_task_result(paper["mineru_task_id"])
        except (MinerUError, Exception) as exc:
            db.execute(
                "UPDATE exam_papers SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(exc), paper_id),
            )
            return jsonify(error_code="MINERU_ERROR", message=str(exc)), 502

        if res.get("status") == "parsing":
            updated_paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
            return jsonify(paper=serialize_paper(updated_paper), questions=[]), 200
        if res.get("status") == "failed":
            err = res.get("error_message") or "MinerU parsing failed."
            db.execute(
                "UPDATE exam_papers SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (err, paper_id),
            )
            return jsonify(error_code="MINERU_FAILED", message=err), 400

        raw_markdown = res.get("raw_markdown") or ""
        db.execute(
            "UPDATE exam_papers SET raw_markdown = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (raw_markdown, paper_id),
        )

    if not raw_markdown or not raw_markdown.strip():
        return jsonify(
            error_code="NO_MARKDOWN",
            message="No markdown available to parse. Provide raw_markdown or wait for MinerU.",
        ), 400

    try:
        extracted = extract_questions_from_markdown(
            g.model_client,
            raw_markdown,
            exam_level=paper.get("exam_level") or "CET4",
            year=paper.get("year"),
            month=paper.get("month"),
            set_no=paper.get("set_no") or 1,
        )
    except Exception as exc:
        db.execute(
            "UPDATE exam_papers SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(exc), paper_id),
        )
        return jsonify(error_code="PARSE_FAILED", message=str(exc)), 400

    inserted_ids: list[int] = []
    with db.transaction() as cur:
        cur.execute("DELETE FROM questions WHERE paper_id = ? AND status = 'draft'", (paper_id,))
        for item in extracted:
            cur.execute(
                """
                INSERT INTO questions (
                    paper_id, exam_level, module, sub_type, year, month, set_no,
                    title, topic, content_json, answer_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
                """,
                (
                    paper_id,
                    item["exam_level"],
                    item["module"],
                    item["sub_type"],
                    item.get("year"),
                    item.get("month"),
                    item.get("set_no", 1),
                    item["title"],
                    item.get("topic"),
                    json.dumps(item["content"], ensure_ascii=False),
                    json.dumps(item["answer"], ensure_ascii=False),
                ),
            )
            inserted_ids.append(cur.lastrowid)

        cur.execute(
            "UPDATE exam_papers SET status = 'draft', error_message = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (paper_id,),
        )

    updated_paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    q_rows = db.fetchall(
        """
        SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
               title, topic, content_json, answer_json, status, created_at
        FROM questions
        WHERE paper_id = ?
        ORDER BY id ASC
        """,
        (paper_id,),
    )
    return jsonify(
        paper=serialize_paper(updated_paper),
        questions=[serialize_question(q, include_answer=True) for q in q_rows],
    )


@admin_bp.post("/papers/<int:paper_id>/publish")
def publish_paper(paper_id: int):
    db: DB = g.db
    paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    if not paper:
        return jsonify(error_code="NOT_FOUND", message="Exam paper not found."), 404

    with db.transaction() as cur:
        cur.execute(
            "UPDATE exam_papers SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (paper_id,),
        )
        cur.execute(
            "UPDATE questions SET status = 'published' WHERE paper_id = ?",
            (paper_id,),
        )
        published_count = cur.rowcount

    updated_paper = db.fetchone("SELECT * FROM exam_papers WHERE id = ?", (paper_id,))
    return jsonify(paper=serialize_paper(updated_paper), published_count=published_count)


@admin_bp.post("/questions")
def create_question():
    db: DB = g.db
    data = request.get_json(silent=True) or {}

    exam_level = (data.get("exam_level") or "").strip().upper()
    module = (data.get("module") or "").strip().lower()
    sub_type = (data.get("sub_type") or "").strip().lower()
    title = (data.get("title") or "").strip()
    content = data.get("content")
    answer = data.get("answer")

    if exam_level not in VALID_EXAM_LEVELS:
        return jsonify(error_code="INVALID_EXAM_LEVEL", message="exam_level must be CET4 or CET6."), 400
    if module not in VALID_MODULES:
        return jsonify(error_code="INVALID_MODULE", message="module must be writing, reading, or translation."), 400
    if not sub_type:
        return jsonify(error_code="INVALID_SUB_TYPE", message="sub_type is required."), 400
    if not title:
        return jsonify(error_code="INVALID_TITLE", message="title is required."), 400
    if not isinstance(content, dict):
        return jsonify(error_code="INVALID_CONTENT", message="content must be a JSON object."), 400
    if not isinstance(answer, dict):
        return jsonify(error_code="INVALID_ANSWER", message="answer must be a JSON object."), 400

    status = (data.get("status") or "published").strip().lower()
    if status not in VALID_STATUSES:
        return jsonify(error_code="INVALID_STATUS", message="status must be draft or published."), 400

    question_id = db.lastrowid(
        """
        INSERT INTO questions (
            paper_id, exam_level, module, sub_type, year, month, set_no,
            title, topic, content_json, answer_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("paper_id"),
            exam_level,
            module,
            sub_type,
            data.get("year"),
            data.get("month"),
            data.get("set_no") or 1,
            title,
            (data.get("topic") or "").strip() or None,
            json.dumps(content, ensure_ascii=False),
            json.dumps(answer, ensure_ascii=False),
            status,
        ),
    )
    row = db.fetchone("SELECT * FROM questions WHERE id = ?", (question_id,))
    return jsonify(serialize_question(row, include_answer=True)), 201


@admin_bp.put("/questions/<int:question_id>")
def update_question(question_id: int):
    db: DB = g.db
    existing = db.fetchone("SELECT * FROM questions WHERE id = ?", (question_id,))
    if not existing:
        return jsonify(error_code="NOT_FOUND", message="Question not found."), 404

    data = request.get_json(silent=True) or {}
    updates: list[str] = []
    params: list = []

    if "exam_level" in data:
        level = (data.get("exam_level") or "").strip().upper()
        if level not in VALID_EXAM_LEVELS:
            return jsonify(error_code="INVALID_EXAM_LEVEL", message="exam_level must be CET4 or CET6."), 400
        updates.append("exam_level = ?")
        params.append(level)

    if "module" in data:
        mod = (data.get("module") or "").strip().lower()
        if mod not in VALID_MODULES:
            return jsonify(error_code="INVALID_MODULE", message="module must be writing, reading, or translation."), 400
        updates.append("module = ?")
        params.append(mod)

    if "sub_type" in data:
        st = (data.get("sub_type") or "").strip().lower()
        if not st:
            return jsonify(error_code="INVALID_SUB_TYPE", message="sub_type cannot be empty."), 400
        updates.append("sub_type = ?")
        params.append(st)

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify(error_code="INVALID_TITLE", message="title cannot be empty."), 400
        updates.append("title = ?")
        params.append(title)

    for field in ("year", "month", "set_no", "topic", "paper_id"):
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data.get(field))

    if "content" in data:
        if not isinstance(data.get("content"), dict):
            return jsonify(error_code="INVALID_CONTENT", message="content must be a JSON object."), 400
        updates.append("content_json = ?")
        params.append(json.dumps(data["content"], ensure_ascii=False))

    if "answer" in data:
        if not isinstance(data.get("answer"), dict):
            return jsonify(error_code="INVALID_ANSWER", message="answer must be a JSON object."), 400
        updates.append("answer_json = ?")
        params.append(json.dumps(data["answer"], ensure_ascii=False))

    if "status" in data:
        status = (data.get("status") or "").strip().lower()
        if status not in VALID_STATUSES:
            return jsonify(error_code="INVALID_STATUS", message="status must be draft or published."), 400
        updates.append("status = ?")
        params.append(status)

    if updates:
        params.append(question_id)
        db.execute(f"UPDATE questions SET {', '.join(updates)} WHERE id = ?", tuple(params))

    row = db.fetchone("SELECT * FROM questions WHERE id = ?", (question_id,))
    return jsonify(serialize_question(row, include_answer=True))


@admin_bp.delete("/questions/<int:question_id>")
def delete_question(question_id: int):
    db: DB = g.db
    existing = db.fetchone("SELECT id FROM questions WHERE id = ?", (question_id,))
    if not existing:
        return jsonify(error_code="NOT_FOUND", message="Question not found."), 404
    db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    return jsonify(deleted=True)
