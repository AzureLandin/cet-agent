import io
import importlib
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import pymysql


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


import auth as auth_module  # noqa: E402
import messages  # noqa: E402
import app as app_module  # noqa: E402
import config as config_module  # noqa: E402
import profile as profile_module  # noqa: E402
from flask import g, request  # noqa: E402


class FakeDBForBuildMessages:
    def fetchall(self, sql, args=()):
        return [{"role": "user", "content": "hello"}]


class FakeCursor:
    """Minimal cursor proxy that records SQL on the parent FakeDB so existing
    assertions on `db.executed` keep working under the new transaction API."""

    def __init__(self, db):
        self._db = db
        self.lastrowid = 1
        self._last_sql = None
        self._last_args = ()

    def execute(self, sql, args=()):
        result = self._db.execute(sql, args)
        self._last_sql = sql
        self._last_args = args
        if sql.startswith("INSERT INTO users"):
            self.lastrowid = 1
        return result

    def fetchone(self):
        return self._db.fetchone(self._last_sql, self._last_args)

    def fetchall(self):
        return self._db.fetchall(self._last_sql, self._last_args)


class FakeDB:
    def __init__(self, config):
        self.config = config
        self.executed = []
        self.events = []
        self.user_exists = config.get("user_exists", True)
        self.profile_exists = config.get("profile_exists", True)
        self.raise_integrity_on_user_insert = config.get("raise_integrity_on_user_insert", False)
        self.password_hash = config.get("password_hash", "stored-hash")
        self.profile_row = self._default_profile_row()

    def _default_profile_row(self):
        return {
            "exam_level": None,
            "exam_date": None,
            "display_name": None,
            "avatar_color": "#4285f4",
            "avatar_url": None,
        }

    def health_check(self):
        return True

    def fetchall(self, sql, args=()):
        if sql == "SHOW TABLES":
            return [
                {"Tables_in_test": "users"},
                {"Tables_in_test": "profiles"},
                {"Tables_in_test": "sessions"},
                {"Tables_in_test": "messages"},
                {"Tables_in_test": "auth_sessions"},
            ]
        if "FROM messages" in sql:
            return []
        return []

    def fetchone(self, sql, args=()):
        if sql == "SELECT id FROM users WHERE username = %s":
            return {"id": 1} if self.user_exists else None
        if sql == "SELECT id, password_hash FROM users WHERE username = %s":
            self.events.append("fetch_login_user")
            if self.user_exists:
                return {"id": 1, "password_hash": self.password_hash}
            return None
        if "FROM sessions WHERE id = %s AND user_id = %s" in sql:
            return {"id": 1, "module": "writing", "title": "Writing", "created_at": None}
        if "FROM profiles" in sql:
            if not self.profile_exists:
                return None
            return dict(self.profile_row)
        return None

    def execute(self, sql, args=()):
        self.executed.append((sql, args))

        if sql.startswith("INSERT INTO users"):
            if self.raise_integrity_on_user_insert:
                raise pymysql.IntegrityError(1062, "Duplicate entry")
            self.user_exists = True
            return 1

        if sql.startswith("INSERT INTO profiles (user_id) VALUES (%s) ON DUPLICATE KEY UPDATE user_id = user_id"):
            self.profile_exists = True
            return 1

        if sql.startswith("INSERT INTO profiles (user_id) VALUES (%s)"):
            self.profile_exists = True
            return 1

        if sql.startswith("UPDATE profiles SET "):
            if not self.profile_exists:
                return 0
            assignments = sql[len("UPDATE profiles SET "):sql.index(" WHERE user_id = %s")].split(", ")
            for assignment, value in zip(assignments, args[:-1]):
                field = assignment.split(" = ")[0]
                self.profile_row[field] = value
            return 1

        if sql.startswith("INSERT INTO auth_sessions"):
            self.events.append("insert_auth_session")
            return 1

        return 1

    @contextmanager
    def transaction(self):
        self.events.append("transaction_enter")
        try:
            yield FakeCursor(self)
        finally:
            self.events.append("transaction_exit")


class FakeModelClient:
    def __init__(self, config):
        self.config = config

    def chat_completion_stream(self, payload):
        yield "A"
        yield "B"


class RegressionTests(unittest.TestCase):
    def test_load_config_reads_backend_settings_from_environment(self):
        with patch.dict(os.environ, {
            "CET_DB_USER": "cet_agent",
            "CET_DB_PASSWORD": "secret",
            "CET_DB_NAME": "cet_web_agent",
            "CET_MODEL_BASE_URL": "https://api.deepseek.com",
            "CET_MODEL_API_KEY": "api-key",
            "CET_MODEL_NAME": "deepseek-chat",
            "CET_SESSION_SECRET_KEY": "session-secret",
        }, clear=True):
            config = config_module.load_config()

        self.assertEqual(config["db"]["host"], "localhost")
        self.assertEqual(config["db"]["port"], 3306)
        self.assertEqual(config["db"]["user"], "cet_agent")
        self.assertEqual(config["db"]["password"], "secret")
        self.assertEqual(config["db"]["name"], "cet_web_agent")
        self.assertEqual(config["model"]["base_url"], "https://api.deepseek.com")
        self.assertEqual(config["model"]["api_key"], "api-key")
        self.assertEqual(config["model"]["model"], "deepseek-chat")
        self.assertEqual(config["session"]["secret_key"], "session-secret")
        self.assertEqual(config["session"]["cookie_secure"], False)
        self.assertEqual(config["cors"]["allowed_origins"], ["http://localhost:8080", "http://127.0.0.1:8080"])

    def test_load_config_rejects_missing_required_environment_variables(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as exc:
                config_module.load_config()

        self.assertIn("CET_DB_USER", str(exc.exception))

    def test_frontend_api_uses_relative_base_path(self):
        api_js = os.path.join(os.path.dirname(BACKEND_DIR), "frontend", "js", "api.js")
        with open(api_js, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn('const API_BASE = "";', contents)
        self.assertNotIn('http://127.0.0.1:5000', contents)

    def test_backend_requirements_include_cryptography_for_mysql8_auth(self):
        requirements = os.path.join(BACKEND_DIR, "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn("cryptography", contents)

    def test_backend_requirements_include_waitress(self):
        requirements = os.path.join(BACKEND_DIR, "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn("waitress", contents)

    def test_backend_dockerfile_uses_waitress(self):
        dockerfile = os.path.join(BACKEND_DIR, "Dockerfile")
        with open(dockerfile, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn('CMD ["waitress-serve"', contents)
        self.assertNotIn('CMD ["python", "app.py"]', contents)

    def test_frontend_uses_font_awesome_icons(self):
        index_html = os.path.join(os.path.dirname(BACKEND_DIR), "frontend", "index.html")
        with open(index_html, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn("fa-solid", contents)
        self.assertNotIn("material-symbols-outlined", contents)

    def test_frontend_uses_local_font_awesome_assets(self):
        index_html = os.path.join(os.path.dirname(BACKEND_DIR), "frontend", "index.html")
        with open(index_html, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn('vendor/fontawesome/css/all.min.css', contents)
        self.assertNotIn('cdnjs.cloudflare.com', contents)

    def test_build_messages_does_not_duplicate_latest_user_message(self):
        result = messages.build_messages(FakeDBForBuildMessages(), 1, "writing", "hello")

        user_messages = [item for item in result if item["role"] == "user"]
        self.assertEqual(user_messages, [{"role": "user", "content": "hello"}])

    def test_health_endpoint_is_public(self):
        app = self._create_test_app()
        client = app.test_client()

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "db": True})

    def test_profile_returns_username_for_authenticated_user(self):
        app = self._create_test_app()
        client = app.test_client()

        response = client.get("/profile", headers={"X-Test-Auth": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["username"], "alice")

    def test_profile_get_self_heals_missing_row(self):
        app = self._create_test_app({"profile_exists": False})
        client = app.test_client()

        response = client.get("/profile", headers={"X-Test-Auth": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(app.extensions["db"].profile_exists)
        self.assertEqual(response.get_json()["avatar_color"], "#4285f4")

    def test_profile_update_self_heals_missing_row(self):
        app = self._create_test_app({"profile_exists": False})
        client = app.test_client()

        response = client.put(
            "/profile",
            json={"display_name": "Alice"},
            headers={"X-Test-Auth": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(app.extensions["db"].profile_exists)
        self.assertEqual(app.extensions["db"].profile_row["display_name"], "Alice")

    def test_avatar_upload_self_heals_missing_row(self):
        app = self._create_test_app({"profile_exists": False})
        client = app.test_client()

        with tempfile.TemporaryDirectory() as uploads_dir, \
             patch.object(profile_module, "_uploads_dir", return_value=uploads_dir):
            response = client.post(
                "/profile/avatar",
                data={"file": (io.BytesIO(b"avatar-bytes"), "avatar.png")},
                headers={"X-Test-Auth": "1"},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(app.extensions["db"].profile_exists)
        self.assertEqual(app.extensions["db"].profile_row["avatar_url"], body["avatar_url"])

    def test_avatar_delete_self_heals_missing_row(self):
        app = self._create_test_app({"profile_exists": False})
        client = app.test_client()

        response = client.delete("/profile/avatar", headers={"X-Test-Auth": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(app.extensions["db"].profile_exists)
        self.assertEqual(response.get_json()["message"], "Avatar deleted.")

    def test_register_duplicate_username_returns_409_without_hashing(self):
        app = self._create_test_app({"user_exists": True})
        client = app.test_client()

        with patch.object(auth_module, "hash_password", side_effect=AssertionError("hash_password should not be called")):
            response = client.post(
                "/auth/register",
                json={"username": "alice", "password": "secret123"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error_code"], "USERNAME_TAKEN")

    def test_register_duplicate_insert_race_maps_integrity_error_to_409(self):
        app = self._create_test_app({"user_exists": False, "raise_integrity_on_user_insert": True})
        client = app.test_client()

        with patch.object(auth_module, "hash_password", return_value="hashed-password"):
            response = client.post(
                "/auth/register",
                json={"username": "alice", "password": "secret123"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error_code"], "USERNAME_TAKEN")

    def test_login_checks_password_before_opening_session_transaction(self):
        app = self._create_test_app()
        client = app.test_client()
        db = app.extensions["db"]

        def fake_check_password(password, password_hash):
            db.events.append("check_password")
            return True

        with patch.object(auth_module, "check_password", side_effect=fake_check_password):
            response = client.post(
                "/auth/login",
                json={"username": "alice", "password": "secret123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLess(db.events.index("fetch_login_user"), db.events.index("check_password"))
        self.assertLess(db.events.index("check_password"), db.events.index("transaction_enter"))
        self.assertLess(db.events.index("transaction_enter"), db.events.index("insert_auth_session"))

    def test_send_message_updates_session_timestamp(self):
        app = self._create_test_app()
        client = app.test_client()

        response = client.post(
            "/sessions/1/messages",
            json={"content": "hello"},
            headers={"X-Test-Auth": "1"},
        )

        body = b"".join(response.response).decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn('"event": "done"', body)

        executed_sql = [sql for sql, _args in app.extensions["db"].executed]
        self.assertIn("UPDATE sessions SET updated_at = NOW() WHERE id = %s", executed_sql)

    def test_create_app_uses_local_profile_module_even_if_profile_is_preloaded(self):
        original_profile = sys.modules.get("profile")
        sys.modules["profile"] = types.SimpleNamespace(__name__="profile")
        try:
            app = self._create_test_app()
        finally:
            if original_profile is None:
                sys.modules.pop("profile", None)
            else:
                sys.modules["profile"] = original_profile

        self.assertIsNotNone(app)
        self.assertTrue(any(bp.name == "profile" for bp in app.blueprints.values()))

    def _create_test_app(self, db_overrides=None, db_class=FakeDB):
        config = {
            "db": {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pw",
                "name": "cet",
            },
            "model": {"base_url": "http://example.com", "api_key": "key", "model": "test-model"},
            "session": {"secret_key": "secret", "cookie_secure": False},
            "cors": {"allowed_origins": ["http://localhost:8080"]},
        }
        if db_overrides:
            config["db"].update(db_overrides)

        importlib.reload(app_module)

        with patch.object(app_module, "load_config", return_value=config), \
             patch.object(app_module, "DB", db_class), \
             patch.object(app_module, "ModelClient", FakeModelClient), \
             patch.object(app_module, "get_user_by_session", return_value={"id": 1, "username": "alice"}):
            app = app_module.create_app()
            app.testing = True
            original_before_request = app.before_request_funcs[None][0]

            def patched_before_request():
                if request.headers.get("X-Test-Auth") == "1":
                    g.db = app.extensions["db"]
                    g.model_client = app.extensions["model_client"]
                    g.user_id = 1
                    g.username = "alice"
                    return None
                return original_before_request()

            app.before_request_funcs[None][0] = patched_before_request
            return app


if __name__ == "__main__":
    unittest.main()
