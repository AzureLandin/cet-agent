from __future__ import annotations

import importlib.util
import os
import random
from flask import Flask, abort, g, jsonify, request, send_from_directory
from flask_cors import CORS

from auth import SESSION_COOKIE_NAME, auth_bp, cleanup_expired_auth_sessions, get_user_by_session
from config import load_config
from db import DB
from messages import messages_bp
from questions import admin_bp, questions_bp
from seed_questions import seed_sample_questions
from services.mineru_client import MinerUClient
from services.model_client import ModelClient
from sessions import sessions_bp


def _load_profile_blueprint():
    module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.py")
    spec = importlib.util.spec_from_file_location("cet_agent_profile", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.profile_bp


profile_bp = _load_profile_blueprint()


def _ensure_column(db: DB, table_name: str, column_name: str, column_def: str):
    cols = db.fetchall(f"PRAGMA table_info({table_name})")
    if not cols:
        return
    existing = {c.get("name") for c in cols if isinstance(c, dict)}
    if column_name not in existing:
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def create_app():
    app = Flask(__name__)
    config = load_config()
    app.config["SECRET_KEY"] = config["session"]["secret_key"]
    server_cfg = config.get("server", {})
    app.config["SERVER_HOST"] = server_cfg.get("host", "0.0.0.0")
    app.config["SERVER_PORT"] = server_cfg.get("port", 5100)

    # CORS
    origins = config.get("cors", {}).get("allowed_origins", ["http://localhost:8080"])
    CORS(app, origins=origins, supports_credentials=True)

    # DB & Clients
    db = DB(config["db"])
    if not db.health_check():
        raise RuntimeError("Database health check failed. Please verify CET_DB_PATH settings.")

    required_tables = [
        "users",
        "profiles",
        "exam_papers",
        "questions",
        "sessions",
        "messages",
        "auth_sessions",
        "practice_attempts",
    ]
    existing_tables = {
        next(iter(row.values()))
        for row in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        if row
    }
    missing = [t for t in required_tables if t not in existing_tables]

    if missing:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        if not os.path.isfile(schema_path):
            raise RuntimeError(f"Missing tables {missing} but schema.sql not found at {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()

        statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
        for stmt in statements:
            db.execute(stmt)

        print(f"Auto-created tables: {', '.join(missing)}")

    # Incremental column safety for existing SQLite DBs
    _ensure_column(db, "users", "role", "TEXT NOT NULL DEFAULT 'student'")
    _ensure_column(db, "sessions", "active_question_id", "INTEGER REFERENCES questions(id) ON DELETE SET NULL")
    _ensure_column(db, "sessions", "draft_answer_json", "TEXT")

    seed_sample_questions(db)

    model_client = ModelClient(config["model"])
    mineru_client = MinerUClient(config.get("mineru", {}))
    admin_usernames = set(config.get("auth", {}).get("admin_usernames", []))

    app.extensions["db"] = db
    app.extensions["model_client"] = model_client
    app.extensions["mineru_client"] = mineru_client
    app.extensions["admin_usernames"] = admin_usernames
    auth_session_cleanup_probability = config.get("session", {}).get("auth_session_cleanup_probability", 0.01)

    import auth as auth_module

    auth_module.cookie_secure = config.get("session", {}).get("cookie_secure", False)
    auth_module.admin_usernames = admin_usernames

    @app.before_request
    def before_request():
        if request.method == "OPTIONS":
            return None

        g.db = db
        g.model_client = model_client
        g.mineru_client = mineru_client
        g.user_id = None
        g.role = None

        if request.path.startswith("/auth"):
            return None
        if request.path.startswith("/uploads/"):
            return None
        if request.path == "/health":
            return None

        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id:
            if random.random() < auth_session_cleanup_probability:
                try:
                    cleanup_expired_auth_sessions(db)
                except Exception:
                    pass
            user = get_user_by_session(db, session_id)
            if user:
                g.user_id = user["id"]
                g.username = user["username"]
                g.role = user.get("role") or "student"

        if g.user_id is None:
            return jsonify(error_code="UNAUTHORIZED", message="Authentication required."), 401

    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        if not filename.startswith("avatars/"):
            abort(403)
        return send_from_directory(uploads_dir, filename)

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(admin_bp)

    @app.route("/health")
    def health():
        return jsonify(status="ok", db=db.health_check())

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["SERVER_HOST"],
        port=app.config["SERVER_PORT"],
        debug=False,
    )
