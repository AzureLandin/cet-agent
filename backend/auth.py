import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, make_response, g
from db import DB

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

SESSION_COOKIE_NAME = "session_id"
SESSION_DURATION_DAYS = 7

# Will be set from app config
cookie_secure = False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session_id() -> str:
    return secrets.token_urlsafe(32)


def create_auth_session(db: DB, user_id: int) -> str:
    session_id = create_session_id()
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)
    db.execute(
        "INSERT INTO auth_sessions (user_id, session_id, expires_at) VALUES (%s, %s, %s)",
        (user_id, session_id, expires_at),
    )
    return session_id


def get_user_by_session(db: DB, session_id: str):
    row = db.fetchone(
        """
        SELECT u.id, u.username
        FROM auth_sessions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.session_id = %s AND s.expires_at > %s
        """,
        (session_id, datetime.now(timezone.utc)),
    )
    return row


def delete_auth_session(db: DB, session_id: str):
    db.execute("DELETE FROM auth_sessions WHERE session_id = %s", (session_id,))


@auth_bp.post("/register")
def register():
    db: DB = g.db
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or len(username) < 3 or len(username) > 50:
        return jsonify(error_code="INVALID_USERNAME", message="Username must be 3-50 characters."), 400
    if not password or len(password) < 6:
        return jsonify(error_code="INVALID_PASSWORD", message="Password must be at least 6 characters."), 400

    existing = db.fetchone("SELECT id FROM users WHERE username = %s", (username,))
    if existing:
        return jsonify(error_code="USERNAME_TAKEN", message="Username already exists."), 409

    password_hash = hash_password(password)
    user_id = db.lastrowid(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (username, password_hash),
    )
    # create empty profile row
    db.execute("INSERT INTO profiles (user_id) VALUES (%s)", (user_id,))

    session_id = create_auth_session(db, user_id)
    resp = make_response(jsonify(user_id=user_id, username=username))
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="Lax",
        secure=cookie_secure,
        max_age=SESSION_DURATION_DAYS * 86400,
    )
    return resp, 201


@auth_bp.post("/login")
def login():
    db: DB = g.db
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify(error_code="MISSING_CREDENTIALS", message="Username and password are required."), 400

    user = db.fetchone("SELECT id, password_hash FROM users WHERE username = %s", (username,))
    if not user or not check_password(password, user["password_hash"]):
        return jsonify(error_code="INVALID_CREDENTIALS", message="Invalid username or password."), 401

    session_id = create_auth_session(db, user["id"])
    resp = make_response(jsonify(user_id=user["id"], username=username))
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="Lax",
        secure=cookie_secure,
        max_age=SESSION_DURATION_DAYS * 86400,
    )
    return resp


@auth_bp.post("/logout")
def logout():
    db: DB = g.db
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_auth_session(db, session_id)
    resp = make_response(jsonify(message="Logged out."))
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp
