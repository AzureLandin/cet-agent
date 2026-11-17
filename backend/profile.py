from __future__ import annotations

import os
import re
import uuid
from flask import Blueprint, g, jsonify, request

from db import DB

# MIME type magic bytes for image validation
MAGIC_BYTES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WebP starts with RIFF
}

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

VALID_EXAM_LEVELS = {"CET4", "CET6"}
AVATAR_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


def _uploads_dir():
    base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "uploads", "avatars")
    os.makedirs(d, exist_ok=True)
    return d


def _check_mime_type(file_bytes: bytes) -> str:
    """Check MIME type from file magic bytes. Returns MIME type or empty string."""
    for magic, mime in MAGIC_BYTES.items():
        if file_bytes.startswith(magic):
            return mime
    if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _to_date_str(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def ensure_profile_row(target, user_id):
    target.execute(
        "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
        (user_id,),
    )


@profile_bp.get("")
def get_profile():
    db: DB = g.db
    user_id = g.user_id
    row = db.fetchone(
        "SELECT exam_level, exam_date, display_name, avatar_color, avatar_url FROM profiles WHERE user_id = ?",
        (user_id,),
    )
    if not row:
        # Auto-heal: create profile row if missing
        ensure_profile_row(db, user_id)
        row = db.fetchone(
            "SELECT exam_level, exam_date, display_name, avatar_color, avatar_url FROM profiles WHERE user_id = ?",
            (user_id,),
        )
    if not row:
        return jsonify(error_code="PROFILE_NOT_FOUND", message="Profile not found."), 404
    return jsonify(
        username=getattr(g, "username", None),
        role=getattr(g, "role", "student") or "student",
        exam_level=row["exam_level"],
        exam_date=_to_date_str(row["exam_date"]),
        display_name=row["display_name"],
        avatar_color=row["avatar_color"] or "#4285f4",
        avatar_url=row["avatar_url"],
    )


@profile_bp.put("")
def update_profile():
    db: DB = g.db
    user_id = g.user_id
    data = request.get_json(silent=True) or {}

    updates: list[str] = []
    params: list = []

    if "exam_level" in data:
        exam_level = data.get("exam_level")
        if exam_level is not None and exam_level not in VALID_EXAM_LEVELS:
            return jsonify(error_code="INVALID_EXAM_LEVEL", message="exam_level must be CET4 or CET6."), 400
        updates.append("exam_level = ?")
        params.append(exam_level)

    if "exam_date" in data:
        exam_date = data.get("exam_date")
        if exam_date is not None and exam_date != "":
            from datetime import date

            try:
                date.fromisoformat(exam_date)
            except ValueError:
                return jsonify(error_code="INVALID_DATE", message="exam_date must be a valid ISO date (YYYY-MM-DD)."), 400
        else:
            exam_date = None
        updates.append("exam_date = ?")
        params.append(exam_date)

    if "display_name" in data:
        display_name = data.get("display_name")
        if display_name is not None:
            display_name = display_name.strip()
            if len(display_name) > 30:
                return jsonify(error_code="INVALID_DISPLAY_NAME", message="display_name must be at most 30 characters."), 400
        updates.append("display_name = ?")
        params.append(display_name)

    if "avatar_color" in data:
        avatar_color = data.get("avatar_color")
        if avatar_color is not None and not AVATAR_COLOR_RE.match(avatar_color):
            return jsonify(error_code="INVALID_COLOR", message="avatar_color must be a hex color like #4285f4."), 400
        updates.append("avatar_color = ?")
        params.append(avatar_color)

    ensure_profile_row(db, user_id)
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        db.execute(
            f"UPDATE profiles SET {', '.join(updates)} WHERE user_id = ?",
            tuple(params),
        )
    return jsonify(message="Profile updated.")


@profile_bp.post("/avatar")
def upload_avatar():
    db: DB = g.db
    user_id = g.user_id

    if "file" not in request.files:
        return jsonify(error_code="NO_FILE", message="No file provided."), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error_code="NO_FILE", message="Empty filename."), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify(error_code="INVALID_FILE_TYPE", message=f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}."), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_AVATAR_SIZE:
        return jsonify(error_code="FILE_TOO_LARGE", message="Max file size is 2 MB."), 400

    mime_type = _check_mime_type(file_bytes)
    allowed_mimes = {"image/png", "image/jpeg", "image/gif", "image/webp"}
    if mime_type not in allowed_mimes:
        return jsonify(error_code="INVALID_FILE_TYPE", message="File content does not match an allowed image type."), 400

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(_uploads_dir(), filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    url = f"/uploads/avatars/{filename}"

    try:
        with db.transaction() as cur:
            ensure_profile_row(cur, user_id)
            cur.execute("SELECT avatar_url FROM profiles WHERE user_id = ?", (user_id,))
            old = cur.fetchone()
            cur.execute("UPDATE profiles SET avatar_url = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (url, user_id))
    except Exception:
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        raise

    if old and old["avatar_url"]:
        old_path = os.path.join(_uploads_dir(), os.path.basename(old["avatar_url"]))
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    return jsonify(avatar_url=url)


@profile_bp.delete("/avatar")
def delete_avatar():
    db: DB = g.db
    user_id = g.user_id

    with db.transaction() as cur:
        ensure_profile_row(cur, user_id)
        cur.execute("SELECT avatar_url FROM profiles WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row["avatar_url"]:
            return jsonify(message="Avatar deleted.")
        cur.execute("UPDATE profiles SET avatar_url = NULL, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))

    old_path = os.path.join(_uploads_dir(), os.path.basename(row["avatar_url"]))
    if os.path.isfile(old_path):
        try:
            os.remove(old_path)
        except OSError:
            pass

    return jsonify(message="Avatar deleted.")
