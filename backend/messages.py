from flask import Blueprint, request, jsonify, g, Response, stream_with_context
from db import DB
from services.model_client import ModelClient
import json

messages_bp = Blueprint("messages", __name__)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 50


def load_module_prompt(module: str) -> str:
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(base_dir, "prompts", f"cet-{module}.txt")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"You are a CET {module} coach."


def build_messages(db: DB, session_id: int, module: str, user_content: str, profile: dict = None):
    system_prompt = load_module_prompt(module)
    if profile:
        level = profile.get("exam_level") or "CET"
        parts = [system_prompt]
        parts.append(f"The user is preparing for {level}.")
        exam_date = profile.get("exam_date")
        if exam_date:
            parts.append(f"Their exam date is {exam_date}.")
        system_prompt = "\n".join(parts)

    messages = [{"role": "system", "content": system_prompt}]

    history = db.fetchall(
        """
        SELECT role, content
        FROM messages
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (session_id, MAX_HISTORY_MESSAGES),
    )
    for row in history:
        if row["role"] in ("user", "assistant"):
            messages.append({"role": row["role"], "content": row["content"]})

    if not history or history[-1]["role"] != "user" or history[-1]["content"] != user_content:
        messages.append({"role": "user", "content": user_content})
    return messages


@messages_bp.post("/sessions/<int:session_id>/messages")
def send_message(session_id: int):
    db: DB = g.db
    user_id = g.user_id

    # Verify session ownership
    session_row = db.fetchone(
        "SELECT id, module FROM sessions WHERE id = %s AND user_id = %s",
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

    # Store user message
    db.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
        (session_id, "user", user_content),
    )
    db.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s", (session_id,))

    # Fetch profile
    profile = db.fetchone(
        "SELECT exam_level, exam_date FROM profiles WHERE user_id = %s",
        (user_id,),
    )

    messages = build_messages(db, session_id, session_row["module"], user_content, profile)

    client: ModelClient = g.model_client

    def generate():
        assistant_chunks = []
        try:
            for chunk in client.chat_completion_stream(messages):
                assistant_chunks.append(chunk)
                payload = json.dumps({"event": "token", "data": chunk})
                yield f"data: {payload}\n\n"

            full_response = "".join(assistant_chunks)
            db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, "assistant", full_response),
            )
            db.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
            payload = json.dumps({"event": "done", "data": ""})
            yield f"data: {payload}\n\n"
        except Exception as e:
            payload = json.dumps({"event": "error", "data": str(e)})
            yield f"data: {payload}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
