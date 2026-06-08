import importlib
import os
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


import messages  # noqa: E402
import app as app_module  # noqa: E402
from flask import g, request  # noqa: E402


class FakeDBForBuildMessages:
    def fetchall(self, sql, args=()):
        return [{"role": "user", "content": "hello"}]


class FakeDB:
    def __init__(self, config):
        self.config = config
        self.executed = []

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
        if "FROM sessions WHERE id = %s AND user_id = %s" in sql:
            return {"id": 1, "module": "writing", "title": "Writing", "created_at": None}
        if "FROM profiles" in sql:
            return {
                "username": "alice",
                "exam_level": "CET4",
                "exam_date": None,
                "display_name": "Alice",
                "avatar_color": "#4285f4",
                "avatar_url": None,
            }
        return None

    def execute(self, sql, args=()):
        self.executed.append((sql, args))
        return 1


class FakeModelClient:
    def __init__(self, config):
        self.config = config

    def chat_completion_stream(self, payload):
        yield "A"
        yield "B"


class RegressionTests(unittest.TestCase):
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

    def _create_test_app(self):
        config = {
            "db": {"host": "localhost", "port": 3306, "user": "root", "password": "pw", "name": "cet"},
            "model": {"base_url": "http://example.com", "api_key": "key", "model": "test-model"},
            "session": {"secret_key": "secret", "cookie_secure": False},
            "cors": {"allowed_origins": ["http://localhost:8080"]},
        }

        importlib.reload(app_module)

        with patch.object(app_module, "load_config", return_value=config), \
             patch.object(app_module, "DB", FakeDB), \
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
