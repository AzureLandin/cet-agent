import os
from datetime import datetime, timezone
from flask import Flask, g, request, jsonify, make_response
from flask_cors import CORS

from config import load_config
from db import DB
from services.model_client import ModelClient
from auth import auth_bp, get_user_by_session, SESSION_COOKIE_NAME
from profile import profile_bp
from sessions import sessions_bp
from messages import messages_bp


def create_app():
    app = Flask(__name__)
    config = load_config()
    app.config["SECRET_KEY"] = config["session"]["secret_key"]

    # CORS
    origins = config.get("cors", {}).get("allowed_origins", ["http://localhost:8080"])
    CORS(app, origins=origins, supports_credentials=True)

    # DB & Model
    db = DB(config["db"])
    if not db.health_check():
        raise RuntimeError("Database health check failed. Please verify config.yaml settings.")

    required_tables = ["users", "profiles", "sessions", "messages", "auth_sessions"]
    existing_tables = {next(iter(row.values())) for row in db.fetchall("SHOW TABLES")}
    missing = [t for t in required_tables if t not in existing_tables]
    if missing:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        if not os.path.isfile(schema_path):
            raise RuntimeError(f"Missing tables {missing} but schema.sql not found at {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
        for stmt in statements:
            if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
                continue
            db.execute(stmt)
        print(f"Auto-created tables: {', '.join(missing)}")

    model_client = ModelClient(config["model"])
    app.extensions["db"] = db
    app.extensions["model_client"] = model_client

    # Propagate cookie_secure to auth module
    import auth as auth_module
    auth_module.cookie_secure = config.get("session", {}).get("cookie_secure", False)

    @app.before_request
    def before_request():
        # 放行 CORS 预检请求，避免鉴权中间件拦截 OPTIONS 导致跨域失败
        if request.method == "OPTIONS":
            return None

        g.db = db
        g.model_client = model_client
        g.user_id = None

        # Auth middleware
        if request.path.startswith("/auth"):
            return None
        if request.path.startswith("/uploads/"):
            return None
        if request.path == "/health":
            return None

        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id:
            user = get_user_by_session(db, session_id)
            if user:
                g.user_id = user["id"]
                g.username = user["username"]

        if g.user_id is None:
            return jsonify(error_code="UNAUTHORIZED", message="Authentication required."), 401

    @app.after_request
    def after_request(response):
        # Ensure cookie secure flag matches config
        cookie_secure = config.get("session", {}).get("cookie_secure", False)
        if response.headers.get("Set-Cookie"):
            # Flask handles Set-Cookie; we set secure on login/logout explicitly
            pass
        return response

    # Serve uploaded avatars
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(uploads_dir, filename)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(messages_bp)

    @app.route("/health")
    def health():
        return jsonify(status="ok", db=db.health_check())

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
