from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import Blueprint, current_app, g, jsonify, make_response, request

from db import DB

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

SESSION_COOKIE_NAME = "session_id"
SESSION_DURATION_DAYS = 7

# Will be set from app config
cookie_secure = False
admin_usernames: set[str] = set()


def _utc_timestamp(dt: datetime | None = None) -> str:
    target = dt or datetime.now(timezone.utc)
    return target.strftime("%Y-%m-%d %H:%M:%S")


def _get_admin_usernames() -> set[str]:
    configured = set(admin_usernames)
    try:
        ext_admins = current_app.extensions.get("admin_usernames")
        if ext_admins:
            configured.update(ext_admins)
    except RuntimeError:
        pass
    return configured


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session_id() -> str:
    return secrets.token_urlsafe(32)


def create_auth_session(cur, user_id: int) -> str:
    session_id = create_session_id()
    expires_at = _utc_timestamp(datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS))
    cur.execute(
        "INSERT INTO auth_sessions (user_id, session_id, expires_at) VALUES (?, ?, ?)",
        (user_id, session_id, expires_at),
    )
    return session_id


def get_user_by_session(db: DB, session_id: str):
    row = db.fetchone(
        """
        SELECT u.id, u.username, u.role
        FROM auth_sessions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.session_id = ? AND s.expires_at > ?
        """,
        (session_id, _utc_timestamp()),
    )
    return row


def cleanup_expired_auth_sessions(db: DB) -> int:
    return db.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (_utc_timestamp(),))


def delete_auth_session(db: DB, session_id: str):
    db.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))


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
    if db.fetchone("SELECT id FROM users WHERE username = ?", (username,)):
        return jsonify(error_code="USERNAME_TAKEN", message="Username already exists."), 409

    password_hash = hash_password(password)
    configured_admins = _get_admin_usernames()

    try:
        with db.transaction() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM users")
            count_row = cur.fetchone()
            is_first_user = count_row is not None and count_row.get("total", 0) == 0
            role = "admin" if (is_first_user or username in configured_admins) else "student"

            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role),
            )
            user_id = cur.lastrowid
            cur.execute("INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,))
            session_id = create_auth_session(cur, user_id)
    except sqlite3.IntegrityError:
        return jsonify(error_code="USERNAME_TAKEN", message="Username already exists."), 409

    resp = make_response(jsonify(user_id=user_id, username=username, role=role))
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

    user = db.fetchone("SELECT id, password_hash, role FROM users WHERE username = ?", (username,))
    if not user or not check_password(password, user["password_hash"]):
        return jsonify(error_code="INVALID_CREDENTIALS", message="Invalid username or password."), 401

    with db.transaction() as cur:
        session_id = create_auth_session(cur, user["id"])

    role = user.get("role") or "student"
    resp = make_response(jsonify(user_id=user["id"], username=username, role=role))
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
