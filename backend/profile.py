import re
import os
import uuid
from flask import Blueprint, request, jsonify, g
from db import DB

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


@profile_bp.get("")
def get_profile():
    db: DB = g.db
    user_id = g.user_id
    row = db.fetchone(
        "SELECT exam_level, exam_date, display_name, avatar_color, avatar_url FROM profiles WHERE user_id = %s",
        (user_id,),
    )
    if not row:
        return jsonify(error_code="PROFILE_NOT_FOUND", message="Profile not found."), 404
    return jsonify(
        username=getattr(g, "username", None),
        exam_level=row["exam_level"],
        exam_date=row["exam_date"].isoformat() if row["exam_date"] else None,
        display_name=row["display_name"],
        avatar_color=row["avatar_color"] or "#4285f4",
        avatar_url=row["avatar_url"],
    )


@profile_bp.put("")
def update_profile():
    db: DB = g.db
    user_id = g.user_id
    data = request.get_json(silent=True) or {}
    exam_level = data.get("exam_level")
    exam_date = data.get("exam_date")
    display_name = data.get("display_name")
    avatar_color = data.get("avatar_color")

    if exam_level is not None and exam_level not in VALID_EXAM_LEVELS:
        return jsonify(error_code="INVALID_EXAM_LEVEL", message="exam_level must be CET4 or CET6."), 400

    if exam_date is not None and exam_date != "":
        from datetime import date
        try:
            date.fromisoformat(exam_date)
        except ValueError:
            return jsonify(error_code="INVALID_DATE", message="exam_date must be a valid ISO date (YYYY-MM-DD)."), 400
    else:
        exam_date = None

    if display_name is not None:
        display_name = display_name.strip()
        if len(display_name) > 30:
            return jsonify(error_code="INVALID_DISPLAY_NAME", message="display_name must be at most 30 characters."), 400

    if avatar_color is not None and not AVATAR_COLOR_RE.match(avatar_color):
        return jsonify(error_code="INVALID_COLOR", message="avatar_color must be a hex color like #4285f4."), 400

    db.execute(
        """
        INSERT INTO profiles (user_id, exam_level, exam_date, display_name, avatar_color, avatar_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            exam_level = VALUES(exam_level),
            exam_date = VALUES(exam_date),
            display_name = VALUES(display_name),
            avatar_color = VALUES(avatar_color),
            avatar_url = VALUES(avatar_url)
        """,
        (user_id, exam_level, exam_date, display_name, avatar_color, None),
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

    if request.content_length and request.content_length > MAX_AVATAR_SIZE:
        return jsonify(error_code="FILE_TOO_LARGE", message="Max file size is 2 MB."), 400

    # Delete old avatar file if exists
    old = db.fetchone("SELECT avatar_url FROM profiles WHERE user_id = %s", (user_id,))
    if old and old["avatar_url"]:
        old_path = os.path.join(_uploads_dir(), os.path.basename(old["avatar_url"]))
        if os.path.isfile(old_path):
            os.remove(old_path)

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(_uploads_dir(), filename)
    file.save(filepath)

    url = f"/uploads/avatars/{filename}"
    db.execute("UPDATE profiles SET avatar_url = %s WHERE user_id = %s", (url, user_id))

    return jsonify(avatar_url=url)
