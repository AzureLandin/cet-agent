from datetime import datetime
from flask import Blueprint, request, jsonify, g
from db import DB

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")

VALID_MODULES = {"writing", "reading", "translation"}


@sessions_bp.post("")
def create_session():
    db: DB = g.db
    user_id = g.user_id
    data = request.get_json(silent=True) or {}
    module = data.get("module")

    if module not in VALID_MODULES:
        return jsonify(error_code="INVALID_MODULE", message="module must be writing, reading, or translation."), 400

    title = f"{module.capitalize()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    session_id = db.lastrowid(
        "INSERT INTO sessions (user_id, module, title, updated_at) VALUES (%s, %s, %s, NOW())",
        (user_id, module, title),
    )

    session = db.fetchone(
        "SELECT id, module, title, created_at FROM sessions WHERE id = %s",
        (session_id,),
    )

    return jsonify(
        id=session["id"],
        module=session["module"],
        title=session["title"],
        created_at=session["created_at"].isoformat() if session["created_at"] else None,
        messages=[],
    ), 201


@sessions_bp.get("")
def list_sessions():
    db: DB = g.db
    user_id = g.user_id
    rows = db.fetchall(
        """
        SELECT id, module, title, created_at
        FROM sessions
        WHERE user_id = %s
        ORDER BY updated_at DESC
        """,
        (user_id,),
    )
    grouped = {"writing": [], "reading": [], "translation": []}
    for row in rows:
        grouped[row["module"]].append(
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return jsonify(grouped)


@sessions_bp.get("/<int:session_id>")
def get_session(session_id: int):
    db: DB = g.db
    user_id = g.user_id
    session_row = db.fetchone(
        "SELECT id, module, title, created_at FROM sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    # Pagination support
    limit = request.args.get("limit", 200, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = min(limit, 500)  # Cap at 500

    messages = db.fetchall(
        """
        SELECT id, role, content, created_at
        FROM messages
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s OFFSET %s
        """,
        (session_id, limit, offset),
    )

    # Get total count for pagination
    total_row = db.fetchone(
        "SELECT COUNT(*) as total FROM messages WHERE session_id = %s",
        (session_id,),
    )
    total = total_row["total"] if total_row else 0

    return jsonify(
        id=session_row["id"],
        module=session_row["module"],
        title=session_row["title"],
        created_at=session_row["created_at"].isoformat() if session_row["created_at"] else None,
        messages=[
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@sessions_bp.delete("/<int:session_id>")
def delete_session(session_id: int):
    db: DB = g.db
    user_id = g.user_id
    session_row = db.fetchone(
        "SELECT id FROM sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session_row:
        return jsonify(error_code="NOT_FOUND", message="Session not found."), 404

    db.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    return jsonify(deleted=True), 200
