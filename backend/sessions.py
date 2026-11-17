from __future__ import annotations

import json
from datetime import datetime
from flask import Blueprint, g, jsonify, request

from db import DB
from questions import serialize_question

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")

VALID_MODULES = {"writing", "reading", "translation"}


def _to_iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _parse_json(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _load_public_question(db: DB, question_id: int | None, is_admin: bool = False):
    if question_id is None:
        return None
    row = db.fetchone(
        """
        SELECT id, paper_id, exam_level, module, sub_type, year, month, set_no,
               title, topic, content_json, answer_json, status, created_at
        FROM questions
        WHERE id = ?
        """,
        (question_id,),
    )
    if not row:
        return None
    if not is_admin and row.get("status") != "published":
        return None
    return serialize_question(row, include_answer=False)


@sessions_bp.post("")
def create_session():
    db: DB = g.db
    user_id = g.user_id
    is_admin = getattr(g, "role", "student") == "admin"
    data = request.get_json(silent=True) or {}
    module = data.get("module")
    question_id = data.get("question_id")

    active_question = None
    if question_id is not None:
        active_question = _load_public_question(db, question_id, is_admin=is_admin)
        if not active_question:
            return jsonify(error_code="NOT_FOUND", message="Question not found."), 404
        if not module:
            module = active_question["module"]

    if module not in VALID_MODULES:
        return jsonify(error_code="INVALID_MODULE", message="module must be writing, reading, or translation."), 400

    title = active_question["title"] if active_question else f"{module.capitalize()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    session_id = db.lastrowid(
        """
        INSERT INTO sessions (user_id, module, title, active_question_id, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (user_id, module, title, question_id),
    )

    session = db.fetchone(
        "SELECT id, module, title, active_question_id, draft_answer_json, created_at FROM sessions WHERE id = ?",
        (session_id,),
    )

    return jsonify(
        id=session["id"],
        module=session["module"],
        title=session["title"],
        created_at=_to_iso(session["created_at"]),
        active_question_id=session.get("active_question_id"),
        active_question=active_question,
        draft_answer=_parse_json(session.get("draft_answer_json")),
        messages=[],
    ), 201


@sessions_bp.get("")
def list_sessions():
    db: DB = g.db
    user_id = g.user_id
    rows = db.fetchall(
        """
        SELECT id, module, title, active_question_id, created_at
        FROM sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (user_id,),
    )
    grouped = {"writing": [], "reading": [], "translation": []}
    for row in rows:
        grouped[row["module"]].append(
            {
                "id": row["id"],
                "title": row["title"],
                "active_question_id": row.get("active_question_id"),
                "created_at": _to_iso(row["created_at"]),
            }
        )
    return jsonify(grouped)


@sessions_bp.get("/<int:session_id>")
def get_session(session_id: int):
    db: DB = g.db
    user_id = g.user_id
    is_admin = getattr(g, "role", "student") == "admin"

    session_row = db.fetchone(
        """
        SELECT id, module, title, active_question_id, draft_answer_json, created_at
        FROM sessions
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    limit = request.args.get("limit", 200, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = min(limit, 500)

    messages = db.fetchall(
        """
        SELECT id, role, content, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC, id ASC
        LIMIT ? OFFSET ?
        """,
        (session_id, limit, offset),
    )

    total_row = db.fetchone(
        "SELECT COUNT(*) as total FROM messages WHERE session_id = ?",
        (session_id,),
    )
    total = total_row["total"] if total_row else 0

    active_question_id = session_row.get("active_question_id")
    active_question = _load_public_question(db, active_question_id, is_admin=is_admin)

    return jsonify(
        id=session_row["id"],
        module=session_row["module"],
        title=session_row["title"],
        created_at=_to_iso(session_row["created_at"]),
        active_question_id=active_question_id,
        active_question=active_question,
        draft_answer=_parse_json(session_row.get("draft_answer_json")),
        messages=[
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": _to_iso(m["created_at"]),
            }
            for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@sessions_bp.put("/<int:session_id>/workspace")
def update_workspace(session_id: int):
    db: DB = g.db
    user_id = g.user_id
    is_admin = getattr(g, "role", "student") == "admin"

    session_row = db.fetchone(
        "SELECT id, active_question_id, draft_answer_json FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    data = request.get_json(silent=True) or {}
    updates: list[str] = []
    params: list = []

    if "active_question_id" in data:
        new_qid = data.get("active_question_id")
        if new_qid is not None:
            question = _load_public_question(db, new_qid, is_admin=is_admin)
            if not question:
                return jsonify(error_code="NOT_FOUND", message="Question not found."), 404
        updates.append("active_question_id = ?")
        params.append(new_qid)
        if new_qid != session_row.get("active_question_id") and "draft_answer" not in data:
            updates.append("draft_answer_json = NULL")

    if "draft_answer" in data:
        draft_val = data.get("draft_answer")
        serialized = json.dumps(draft_val, ensure_ascii=False) if draft_val is not None else None
        updates.append("draft_answer_json = ?")
        params.append(serialized)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(session_id)
        db.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )

    updated = db.fetchone(
        "SELECT id, active_question_id, draft_answer_json FROM sessions WHERE id = ?",
        (session_id,),
    )
    active_qid = updated.get("active_question_id")
    return jsonify(
        id=updated["id"],
        active_question_id=active_qid,
        active_question=_load_public_question(db, active_qid, is_admin=is_admin),
        draft_answer=_parse_json(updated.get("draft_answer_json")),
    )


@sessions_bp.delete("/<int:session_id>")
def delete_session(session_id: int):
    db: DB = g.db
    user_id = g.user_id
    session_row = db.fetchone(
        "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return jsonify(deleted=True), 200
