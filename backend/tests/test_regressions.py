from __future__ import annotations

import importlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as app_module  # noqa: E402
import auth as auth_module  # noqa: E402
import config as config_module  # noqa: E402
import db as db_module  # noqa: E402
import messages  # noqa: E402
import profile as profile_module  # noqa: E402
from services.mineru_client import MinerUClient, extract_questions_from_markdown  # noqa: E402
from flask import g, request  # noqa: E402


class FakeDBForBuildMessages:
    def fetchall(self, sql, args=()):
        return [{"role": "user", "content": "hello"}]


class FakeDBForBuildMessagesWithHistory:
    """Simulates a session with 60 messages to test history window ordering."""

    def __init__(self):
        self._messages = []
        for i in range(60):
            role = "user" if i % 2 == 0 else "assistant"
            self._messages.append({"role": role, "content": f"message-{i}"})

    def fetchall(self, sql, args=()):
        return self._messages[10:]


class FakeCursor:
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
        if "sqlite_master" in sql:
            return [
                {"name": "users"},
                {"name": "profiles"},
                {"name": "exam_papers"},
                {"name": "questions"},
                {"name": "sessions"},
                {"name": "messages"},
                {"name": "auth_sessions"},
                {"name": "practice_attempts"},
            ]
        if "PRAGMA table_info" in sql:
            return []
        if "FROM messages" in sql:
            return []
        return []

    def fetchone(self, sql, args=()):
        if "SELECT COUNT(*) AS total FROM questions" in sql:
            return {"total": 4}
        if "SELECT COUNT(*) AS total FROM users" in sql:
            return {"total": 1}
        if "SELECT id FROM users WHERE username" in sql:
            return {"id": 1} if self.user_exists else None
        if "SELECT id, password_hash" in sql and "FROM users WHERE username" in sql:
            self.events.append("fetch_login_user")
            if self.user_exists:
                return {"id": 1, "password_hash": self.password_hash, "role": "student"}
            return None
        if "FROM sessions WHERE id =" in sql and "user_id =" in sql:
            return {"id": 1, "module": "writing", "title": "Writing", "active_question_id": None, "created_at": None}
        if "FROM auth_sessions AS s" in sql:
            return {"id": 1, "username": "alice", "role": "student"}
        if "FROM profiles" in sql:
            if not self.profile_exists:
                return None
            return dict(self.profile_row)
        return None

    def execute(self, sql, args=()):
        self.executed.append((sql, args))

        if sql.startswith("INSERT INTO users"):
            if self.raise_integrity_on_user_insert:
                raise sqlite3.IntegrityError("UNIQUE constraint failed: users.username")
            self.user_exists = True
            return 1

        if sql.startswith("INSERT OR IGNORE INTO profiles"):
            self.profile_exists = True
            return 1

        if sql.startswith("UPDATE profiles SET "):
            if not self.profile_exists:
                return 0
            assignments = sql[len("UPDATE profiles SET "):sql.index(" WHERE user_id =")].split(", ")
            for assignment, value in zip(assignments, args):
                field = assignment.split(" = ")[0]
                if "= CURRENT_TIMESTAMP" not in assignment:
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


class FakeToolModelClient:
    """Fake model client supporting streaming tool calls across rounds."""

    def __init__(self, config):
        self.config = config
        self.calls = 0

    def chat_completion(self, messages, response_format=None):
        return json.dumps(
            {
                "questions": [
                    {
                        "exam_level": "CET6",
                        "module": "reading",
                        "sub_type": "careful_reading",
                        "title": "2025年6月 CET-6 仔细阅读：AI与教育",
                        "topic": "ai_education",
                        "content": {
                            "directions": "Read the passage carefully.",
                            "passage": "AI tools are transforming university classrooms.",
                            "questions": [
                                {
                                    "number": 46,
                                    "stem": "What is transforming classrooms?",
                                    "options": {"A": "Books", "B": "AI tools", "C": "Exams", "D": "Sports"},
                                }
                            ],
                        },
                        "answer": {
                            "correct_answers": {"46": "B"},
                            "explanations": {"46": "First sentence mentions AI tools."},
                        },
                    }
                ]
            },
            ensure_ascii=False,
        )

    def chat_completion_stream_events(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "search_questions",
                        "arguments": json.dumps({"module": "reading"}),
                    }
                ],
            }
        elif self.calls == 2:
            # Extract first question id returned by search_questions
            last_tool = json.loads(messages[-1]["content"])
            qid = last_tool["questions"][0]["id"]
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "name": "start_question_practice",
                        "arguments": json.dumps({"question_id": qid}),
                    }
                ],
            }
        else:
            yield {"type": "token", "content": "题目已加载到左侧工作台，请开始阅读。"}


class RegressionTests(unittest.TestCase):
    def test_load_config_reads_sqlite_and_mineru_settings_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "CET_HOST": "127.0.0.1",
                "CET_PORT": "5050",
                "CET_DB_PATH": ":memory:",
                "CET_ADMIN_USERNAMES": "rootadmin, teacher1",
                "CET_MINERU_API_KEY": "mineru-secret",
                "CET_MINERU_BASE_URL": "https://mineru.example/api/v4",
                "CET_MODEL_BASE_URL": "https://api.deepseek.com",
                "CET_MODEL_API_KEY": "api-key",
                "CET_MODEL_NAME": "deepseek-chat",
                "CET_SESSION_SECRET_KEY": "session-secret",
                "CET_AUTH_SESSION_CLEANUP_PROBABILITY": "0.25",
            },
            clear=True,
        ):
            config = config_module.load_config()

        self.assertEqual(config["server"]["host"], "127.0.0.1")
        self.assertEqual(config["server"]["port"], 5050)
        self.assertEqual(config["db"]["path"], ":memory:")
        self.assertEqual(config["auth"]["admin_usernames"], ["rootadmin", "teacher1"])
        self.assertEqual(config["mineru"]["api_key"], "mineru-secret")
        self.assertEqual(config["mineru"]["base_url"], "https://mineru.example/api/v4")
        self.assertEqual(config["model"]["base_url"], "https://api.deepseek.com")
        self.assertEqual(config["model"]["api_key"], "api-key")
        self.assertEqual(config["model"]["model"], "deepseek-chat")
        self.assertEqual(config["session"]["secret_key"], "session-secret")
        self.assertEqual(config["session"]["cookie_secure"], False)
        self.assertEqual(config["session"]["auth_session_cleanup_probability"], 0.25)
        self.assertEqual(config["cors"]["allowed_origins"], ["http://localhost:8080", "http://127.0.0.1:8080"])

    def test_load_config_defaults_sqlite_path_and_mineru(self):
        with patch.dict(
            os.environ,
            {
                "CET_MODEL_BASE_URL": "https://api.deepseek.com",
                "CET_MODEL_API_KEY": "api-key",
                "CET_MODEL_NAME": "deepseek-chat",
                "CET_SESSION_SECRET_KEY": "session-secret",
            },
            clear=True,
        ):
            config = config_module.load_config()

        self.assertEqual(config["server"]["host"], "0.0.0.0")
        self.assertEqual(config["server"]["port"], 5000)
        self.assertTrue(config["db"]["path"].endswith(os.path.join("data", "cet_agent.db")))
        self.assertEqual(config["mineru"]["api_key"], "")
        self.assertEqual(config["mineru"]["base_url"], "https://mineru.net/api/v4")
        self.assertEqual(config["auth"]["admin_usernames"], [])

    def test_load_config_rejects_invalid_port(self):
        env = {
            "CET_MODEL_BASE_URL": "https://api.deepseek.com",
            "CET_MODEL_API_KEY": "api-key",
            "CET_MODEL_NAME": "deepseek-chat",
            "CET_SESSION_SECRET_KEY": "session-secret",
            "CET_PORT": "70000",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as exc:
                config_module.load_config()

        self.assertIn("CET_PORT", str(exc.exception))

    def test_load_config_rejects_missing_required_environment_variables(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as exc:
                config_module.load_config()

        self.assertIn("CET_MODEL_BASE_URL", str(exc.exception))

    def test_load_config_rejects_invalid_auth_session_cleanup_probability(self):
        env = {
            "CET_MODEL_BASE_URL": "https://api.deepseek.com",
            "CET_MODEL_API_KEY": "api-key",
            "CET_MODEL_NAME": "deepseek-chat",
            "CET_SESSION_SECRET_KEY": "session-secret",
            "CET_AUTH_SESSION_CLEANUP_PROBABILITY": "1.5",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as exc:
                config_module.load_config()

        self.assertIn("CET_AUTH_SESSION_CLEANUP_PROBABILITY", str(exc.exception))

    def test_backend_requirements_use_sqlite_without_mysql_deps(self):
        requirements = os.path.join(BACKEND_DIR, "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn("waitress", contents)
        self.assertIn("httpx", contents)
        self.assertNotIn("PyMySQL", contents)
        self.assertNotIn("DBUtils", contents)
        self.assertNotIn("cryptography", contents)

    def test_docker_compose_removes_mysql_and_mounts_data_volume(self):
        compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertNotIn("mysql:", contents)
        self.assertIn("/app/data", contents)
        self.assertIn("/app/uploads", contents)
        self.assertFalse(os.path.exists(os.path.join(ROOT_DIR, "cookies.txt")))

    def test_backend_dockerfile_uses_waitress(self):
        dockerfile = os.path.join(BACKEND_DIR, "Dockerfile")
        with open(dockerfile, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertIn('CMD ["waitress-serve"', contents)
        self.assertNotIn('CMD ["python", "app.py"]', contents)

    def test_sqlite_memory_db_persists_tables_and_translates_placeholders(self):
        db = db_module.DB({"path": ":memory:"})
        try:
            self.assertTrue(db.health_check())
            db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)")
            rowid = db.lastrowid("INSERT INTO items (name) VALUES (%s)", ("alpha",))
            self.assertEqual(rowid, 1)
            row = db.fetchone("SELECT id, name FROM items WHERE id = %s", (1,))
            self.assertIsInstance(row, dict)
            self.assertEqual(row["name"], "alpha")
            fk_row = db.fetchone("PRAGMA foreign_keys")
            self.assertEqual(fk_row["foreign_keys"], 1)
        finally:
            db.close()

    def test_build_messages_does_not_duplicate_latest_user_message(self):
        result = messages.build_messages(FakeDBForBuildMessages(), 1, "writing", "hello")

        user_messages = [item for item in result if item["role"] == "user"]
        self.assertEqual(user_messages, [{"role": "user", "content": "hello"}])

    def test_build_messages_injects_active_question_context(self):
        active_q = {
            "id": 99,
            "exam_level": "CET6",
            "module": "reading",
            "sub_type": "careful_reading",
            "year": 2024,
            "month": 6,
            "title": "Sample Reading",
            "content": {"passage": "Test passage content."},
        }
        result = messages.build_messages(
            FakeDBForBuildMessages(), 1, "reading", "hint please", active_question=active_q
        )
        self.assertIn("Sample Reading", result[0]["content"])
        self.assertIn("Test passage content.", result[0]["content"])

    def test_build_messages_returns_most_recent_50_messages_not_earliest(self):
        db = FakeDBForBuildMessagesWithHistory()
        result = messages.build_messages(db, 1, "writing", "new-message")

        history_messages = [m for m in result if m["role"] in ("user", "assistant")]
        self.assertEqual(history_messages[0]["content"], "message-10")
        self.assertEqual(history_messages[-2]["content"], "message-59")

    def test_health_endpoint_is_public(self):
        app = self._create_test_app()
        client = app.test_client()

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "db": True})

    def test_profile_returns_username_and_role_for_authenticated_user(self):
        app = self._create_test_app()
        client = app.test_client()

        response = client.get("/profile", headers={"X-Test-Auth": "1"})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["username"], "alice")
        self.assertEqual(body["role"], "student")

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
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with tempfile.TemporaryDirectory() as uploads_dir, patch.object(
            profile_module, "_uploads_dir", return_value=uploads_dir
        ):
            response = client.post(
                "/profile/avatar",
                data={"file": (io.BytesIO(png_bytes), "avatar.png")},
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

        with patch.object(
            auth_module, "hash_password", side_effect=AssertionError("hash_password should not be called")
        ):
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

    def test_authenticated_request_can_clean_up_expired_auth_sessions(self):
        app = self._create_test_app(session_overrides={"auth_session_cleanup_probability": 1})
        client = app.test_client()
        client.set_cookie(auth_module.SESSION_COOKIE_NAME, "valid-session")

        response = client.get("/profile")

        self.assertEqual(response.status_code, 200)
        executed_sql = [sql for sql, _args in app.extensions["db"].executed]
        self.assertIn("DELETE FROM auth_sessions WHERE expires_at <= ?", executed_sql)

    def test_authenticated_request_can_skip_expired_auth_session_cleanup(self):
        app = self._create_test_app(session_overrides={"auth_session_cleanup_probability": 0})
        client = app.test_client()
        client.set_cookie(auth_module.SESSION_COOKIE_NAME, "valid-session")

        response = client.get("/profile")

        self.assertEqual(response.status_code, 200)
        executed_sql = [sql for sql, _args in app.extensions["db"].executed]
        self.assertNotIn("DELETE FROM auth_sessions WHERE expires_at <= ?", executed_sql)

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
        self.assertIn("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", executed_sql)

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

    def test_end_to_end_sqlite_auth_roles_seed_questions_and_workspace(self):
        app = self._create_real_sqlite_app(admin_usernames=["designated_admin"])
        try:
            # 1. Seeded 4 sample questions exist
            student_client = app.test_client()
            admin_client = app.test_client()

            # First user -> automatically admin
            res1 = admin_client.post("/auth/register", json={"username": "firstadmin", "password": "password123"})
            self.assertEqual(res1.status_code, 201)
            self.assertEqual(res1.get_json()["role"], "admin")

            # Second user -> student
            res2 = student_client.post("/auth/register", json={"username": "student1", "password": "password123"})
            self.assertEqual(res2.status_code, 201)
            self.assertEqual(res2.get_json()["role"], "student")

            # Designated admin user -> admin even when not first
            res3 = app.test_client().post(
                "/auth/register", json={"username": "designated_admin", "password": "password123"}
            )
            self.assertEqual(res3.status_code, 201)
            self.assertEqual(res3.get_json()["role"], "admin")

            # Profile returns role
            prof_res = student_client.get("/profile")
            self.assertEqual(prof_res.status_code, 200)
            self.assertEqual(prof_res.get_json()["role"], "student")

            # Student cannot access admin endpoints
            forbidden = student_client.get("/admin/papers")
            self.assertEqual(forbidden.status_code, 403)
            self.assertEqual(forbidden.get_json()["error_code"], "FORBIDDEN")

            # Question bank seeded with 4 questions
            q_list = student_client.get("/questions")
            self.assertEqual(q_list.status_code, 200)
            q_body = q_list.get_json()
            self.assertEqual(q_body["total"], 4)
            self.assertNotIn("answer", q_body["items"][0])

            # Filter careful_reading and submit objective answers
            cr_list = student_client.get("/questions?sub_type=careful_reading").get_json()
            self.assertEqual(cr_list["total"], 1)
            cr_q = cr_list["items"][0]

            # Create session bound to this question
            sess_res = student_client.post("/sessions", json={"module": "reading", "question_id": cr_q["id"]})
            self.assertEqual(sess_res.status_code, 201)
            sess = sess_res.get_json()
            self.assertEqual(sess["active_question_id"], cr_q["id"])
            self.assertEqual(sess["active_question"]["id"], cr_q["id"])

            # Save draft answer in workspace
            ws_res = student_client.put(
                f"/sessions/{sess['id']}/workspace",
                json={"draft_answer": {"46": "B", "47": "C"}},
            )
            self.assertEqual(ws_res.status_code, 200)
            self.assertEqual(ws_res.get_json()["draft_answer"], {"46": "B", "47": "C"})

            # Submit answers (4/5 correct: 46=B, 47=C, 48=B, 49=A, 50=D wrong)
            sub_res = student_client.post(
                f"/questions/{cr_q['id']}/submit",
                json={
                    "session_id": sess["id"],
                    "user_answers": {"46": "B", "47": "C", "48": "B", "49": "A", "50": "D"},
                },
            )
            self.assertEqual(sub_res.status_code, 200)
            sub_body = sub_res.get_json()
            self.assertEqual(sub_body["score"], 4.0)
            self.assertEqual(sub_body["total"], 5.0)
            self.assertIn("correct_answers", sub_body["answer"])

            # Verify get_session returns active_question and draft_answer
            get_sess = student_client.get(f"/sessions/{sess['id']}").get_json()
            self.assertEqual(get_sess["active_question_id"], cr_q["id"])
            self.assertEqual(get_sess["draft_answer"], {"46": "B", "47": "C"})

            # Verify list_sessions returns active_question_id
            list_sess = student_client.get("/sessions").get_json()
            self.assertEqual(list_sess["reading"][0]["active_question_id"], cr_q["id"])
        finally:
            app.extensions["db"].close()

    def test_admin_paper_upload_parse_publish_and_question_crud(self):
        app = self._create_real_sqlite_app(model_client_class=FakeToolModelClient)
        try:
            admin_client = app.test_client()
            reg = admin_client.post("/auth/register", json={"username": "admin1", "password": "password123"})
            self.assertEqual(reg.status_code, 201)

            with tempfile.TemporaryDirectory() as papers_dir, patch(
                "questions._papers_upload_dir", return_value=papers_dir
            ):
                md_content = b"# 2025-06 CET-6\n\nAI tools are transforming university classrooms."
                upload_res = admin_client.post(
                    "/admin/papers/upload",
                    data={
                        "file": (io.BytesIO(md_content), "2025_06_cet6.md"),
                        "year": "2025",
                        "month": "6",
                        "exam_level": "CET6",
                        "set_no": "1",
                        "title": "2025年6月 CET-6 真题卷一",
                    },
                    content_type="multipart/form-data",
                )
                self.assertEqual(upload_res.status_code, 201)
                paper = upload_res.get_json()["paper"]
                self.assertIn("AI tools", paper["raw_markdown"])

                # Parse paper into draft questions
                parse_res = admin_client.post(f"/admin/papers/{paper['id']}/parse", json={})
                self.assertEqual(parse_res.status_code, 200)
                parsed = parse_res.get_json()
                self.assertEqual(len(parsed["questions"]), 1)
                draft_q = parsed["questions"][0]
                self.assertEqual(draft_q["status"], "draft")

                # Student cannot see draft question yet
                student_client = app.test_client()
                student_client.post("/auth/register", json={"username": "stu2", "password": "password123"})
                self.assertEqual(student_client.get(f"/questions/{draft_q['id']}").status_code, 404)

                # Publish paper
                pub_res = admin_client.post(f"/admin/papers/{paper['id']}/publish")
                self.assertEqual(pub_res.status_code, 200)
                self.assertEqual(pub_res.get_json()["published_count"], 1)
                self.assertEqual(student_client.get(f"/questions/{draft_q['id']}").status_code, 200)

                # Individual Question CRUD
                create_q = admin_client.post(
                    "/admin/questions",
                    json={
                        "exam_level": "CET4",
                        "module": "translation",
                        "sub_type": "paragraph_translation",
                        "year": 2025,
                        "month": 6,
                        "title": "自定义翻译题",
                        "content": {"directions": "Translate", "source_text": "你好世界"},
                        "answer": {"reference_translation": "Hello world."},
                    },
                )
                self.assertEqual(create_q.status_code, 201)
                qid = create_q.get_json()["id"]

                upd_q = admin_client.put(
                    f"/admin/questions/{qid}",
                    json={"title": "更新后的翻译题"},
                )
                self.assertEqual(upd_q.status_code, 200)
                self.assertEqual(upd_q.get_json()["title"], "更新后的翻译题")

                del_q = admin_client.delete(f"/admin/questions/{qid}")
                self.assertEqual(del_q.status_code, 200)
                self.assertTrue(del_q.get_json()["deleted"])
        finally:
            app.extensions["db"].close()

    def test_mineru_client_presign_upload_and_zip_result_download(self):
        client = MinerUClient({"api_key": "test-key", "base_url": "https://mineru.net/api/v4"})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("nested/full.md", "# Extracted Title\n\nPassage text")
        zip_bytes = buf.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(b"%PDF-1.4 fake")
            tmp_pdf.flush()

            mock_http = MagicMock()
            mock_http.__enter__.return_value = mock_http
            mock_http.__exit__.return_value = None

            post_resp = MagicMock()
            post_resp.json.return_value = {
                "code": 0,
                "data": {"batch_id": "batch-123", "file_urls": ["https://upload.example/put"]},
            }
            put_resp = MagicMock()

            status_resp = MagicMock()
            status_resp.json.return_value = {
                "code": 0,
                "data": {
                    "extract_result": [
                        {"state": "done", "full_zip_url": "https://cdn.example/result.zip"}
                    ]
                },
            }
            zip_resp = MagicMock()
            zip_resp.content = zip_bytes

            mock_http.post.return_value = post_resp
            mock_http.put.return_value = put_resp
            mock_http.get.side_effect = [status_resp, zip_resp]

            with patch("services.mineru_client.httpx.Client", return_value=mock_http):
                upload_info = client.upload_and_create_task(tmp_pdf.name, "paper.pdf")
                self.assertEqual(upload_info["task_id"], "batch:batch-123")
                self.assertEqual(upload_info["status"], "parsing")

                res = client.get_task_result(upload_info["task_id"])
                self.assertEqual(res["status"], "done")
                self.assertIn("Extracted Title", res["raw_markdown"])

    def test_agent_tool_calling_emits_sse_events_and_binds_question(self):
        app = self._create_real_sqlite_app(model_client_class=FakeToolModelClient)
        try:
            client = app.test_client()
            client.post("/auth/register", json={"username": "stu_tool", "password": "password123"})
            sess = client.post("/sessions", json={"module": "reading"}).get_json()
            self.assertIsNone(sess["active_question_id"])

            resp = client.post(
                f"/sessions/{sess['id']}/messages",
                json={"content": "给我出一道阅读真题"},
            )
            self.assertEqual(resp.status_code, 200)
            raw_sse = b"".join(resp.response).decode("utf-8")

            self.assertIn('"event": "tool_call"', raw_sse)
            self.assertIn('"name": "search_questions"', raw_sse)
            self.assertIn('"name": "start_question_practice"', raw_sse)
            self.assertIn('"event": "question_loaded"', raw_sse)
            self.assertIn('"event": "token"', raw_sse)
            self.assertIn('"event": "done"', raw_sse)

            updated = client.get(f"/sessions/{sess['id']}").get_json()
            self.assertIsNotNone(updated["active_question_id"])
            self.assertIsNotNone(updated["active_question"])
        finally:
            app.extensions["db"].close()

    def test_banked_cloze_submit_and_answer_key_and_record_result_tools(self):
        app = self._create_real_sqlite_app(model_client_class=FakeToolModelClient)
        try:
            client = app.test_client()
            client.post("/auth/register", json={"username": "stu_cloze", "password": "password123"})
            cloze_list = client.get("/questions?sub_type=banked_cloze").get_json()
            self.assertEqual(cloze_list["total"], 1)
            cloze_q = cloze_list["items"][0]
            self.assertEqual(len(cloze_q["content"]["word_bank"]), 15)
            self.assertEqual(len(cloze_q["content"]["blank_numbers"]), 10)

            sub_res = client.post(
                f"/questions/{cloze_q['id']}/submit",
                json={"user_answers": {"26": "F", "27": "D"}},
            ).get_json()
            self.assertEqual(sub_res["score"], 2.0)
            self.assertEqual(sub_res["total"], 10.0)

            sess = client.post("/sessions", json={"module": "writing"}).get_json()
            writing_q = client.get("/questions?module=writing").get_json()["items"][0]
            db = app.extensions["db"]

            ans_res, loaded = messages._execute_tool(db, 1, sess["id"], "get_answer_key", {"question_id": writing_q["id"]})
            self.assertIsNone(loaded)
            self.assertIn("reference_essay", ans_res["answer"])

            rec_res, _ = messages._execute_tool(
                db,
                1,
                sess["id"],
                "record_practice_result",
                {"question_id": writing_q["id"], "score": 12.5, "total": 15, "feedback_summary": "Good structure"},
            )
            self.assertTrue(rec_res["recorded"])
            self.assertIsInstance(rec_res["attempt_id"], int)
        finally:
            app.extensions["db"].close()

    def test_file_sqlite_db_startup_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "nested", "cet.db")
            config = {
                "db": {"path": db_path},
                "auth": {"admin_usernames": []},
                "mineru": {"api_key": "", "base_url": "https://mineru.net/api/v4"},
                "model": {"base_url": "http://example.com", "api_key": "key", "model": "test-model"},
                "session": {"secret_key": "secret", "cookie_secure": False, "auth_session_cleanup_probability": 0},
                "cors": {"allowed_origins": ["http://localhost:8080"]},
            }
            with patch.object(app_module, "load_config", return_value=config), patch.object(
                app_module, "ModelClient", FakeModelClient
            ):
                app1 = app_module.create_app()
                app2 = app_module.create_app()
                row = app2.extensions["db"].fetchone("SELECT COUNT(*) AS total FROM questions")
                self.assertEqual(row["total"], 4)
                app1.extensions["db"].close()
                app2.extensions["db"].close()

    def test_model_client_handles_bracketed_ipv6_in_no_proxy(self):
        from services.model_client import ModelClient

        with patch.dict(
            os.environ,
            {
                "http_proxy": "http://127.0.0.1:7890",
                "https_proxy": "http://127.0.0.1:7890",
                "no_proxy": "localhost,127.0.0.1,::1,[::1]",
                "NO_PROXY": "localhost,127.0.0.1,[::1]",
            },
            clear=False,
        ):
            client = ModelClient(
                {"base_url": "https://api.example.com/v1", "api_key": "test-key", "model": "test-model"}
            )
            self.assertIsNotNone(client.client)
            self.assertNotIn("[::1]", os.environ["no_proxy"])
            self.assertIn("::1", os.environ["no_proxy"])

    def test_model_client_separates_parallel_tool_calls_with_colliding_indices(self):
        from contextlib import nullcontext
        from services.model_client import ModelClient

        chunks = [
            {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_a",
                                    "type": "function",
                                    "function": {"name": "get_answer_key", "arguments": '{"question_id": 2}'},
                                }
                            ],
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-2",
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_b",
                                    "type": "function",
                                    "function": {
                                        "name": "record_practice_result",
                                        "arguments": '{"question_id": 2, "score": 10, "total": 15}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-3",
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "id": "call_c",
                                    "type": "function",
                                    "function": {"name": "get_answer_key", "arguments": '{"question_id": 3}'},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        ]

        client = ModelClient(
            {"base_url": "https://api.example.com/v1", "api_key": "test-key", "model": "test-model"}
        )
        with patch.object(client.chat_model.client, "create", return_value=nullcontext(iter(chunks))):
            events = list(client.chat_completion_stream_events([{"role": "user", "content": "hi"}], tools=[]))

        tool_evts = [e for e in events if e["type"] == "tool_calls"]
        self.assertEqual(len(tool_evts), 1)
        calls = tool_evts[0]["tool_calls"]
        self.assertEqual([c["name"] for c in calls], ["get_answer_key", "record_practice_result", "get_answer_key"])
        self.assertEqual(calls[0]["id"], "call_a")
        self.assertEqual(calls[1]["id"], "call_b")
        self.assertEqual(calls[2]["id"], "call_c")
        self.assertEqual(json.loads(calls[2]["arguments"]), {"question_id": 3})

    def test_langchain_create_agent_pipeline_handles_tools_limits_and_markup(self):
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, AIMessageChunk
        from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
        from pydantic import PrivateAttr

        class FakeLangChainModel(BaseChatModel):
            _state: dict = PrivateAttr(default_factory=lambda: {"calls": 0})
            _bound_tools: list = PrivateAttr(default_factory=list)

            @property
            def _llm_type(self) -> str:
                return "fake-langchain-test"

            def bind_tools(self, tools, *, tool_choice=None, **kwargs):
                clone = self.model_copy()
                clone._state = self._state
                clone._bound_tools = list(tools)
                return clone

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                self._state["calls"] += 1
                call_no = self._state["calls"]
                if not self._bound_tools:
                    return ChatResult(
                        generations=[ChatGeneration(message=AIMessage(content="# 翻译批改报告\n\n总分：32/40"))]
                    )
                if call_no == 1:
                    return ChatResult(
                        generations=[
                            ChatGeneration(
                                message=AIMessage(
                                    content="<tool_call><function=search_questions></function></tool_call>",
                                    tool_calls=[
                                        {
                                            "id": "lc_1",
                                            "name": "search_questions",
                                            "args": {"module": "translation"},
                                            "type": "tool_call",
                                        }
                                    ],
                                )
                            )
                        ]
                    )
                if call_no == 2:
                    return ChatResult(
                        generations=[
                            ChatGeneration(
                                message=AIMessage(
                                    content="",
                                    tool_calls=[
                                        {
                                            "id": "lc_2",
                                            "name": "start_question_practice",
                                            "args": {"id": 2},
                                            "type": "tool_call",
                                        },
                                        {
                                            "id": "lc_3",
                                            "name": "get_answer_key",
                                            "args": {"id": 2},
                                            "type": "tool_call",
                                        },
                                    ],
                                )
                            )
                        ]
                    )
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=AIMessage(
                                content="",
                                tool_calls=[
                                    {
                                        "id": f"lc_loop_{call_no}",
                                        "name": "get_answer_key",
                                        "args": {"id": 2},
                                        "type": "tool_call",
                                    }
                                ],
                            )
                        )
                    ]
                )

            def _stream(self, messages, stop=None, run_manager=None, **kwargs):
                res = self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                msg = res.generations[0].message
                yield ChatGenerationChunk(
                    message=AIMessageChunk(
                        content=msg.content,
                        tool_call_chunks=[
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "args": json.dumps(tc["args"]),
                                "index": i,
                            }
                            for i, tc in enumerate(msg.tool_calls)
                        ],
                    )
                )

        shared_model = FakeLangChainModel()

        class FakeLangChainClientWrapper:
            def __init__(self, config):
                self.model = shared_model

            def get_chat_model(self):
                return self.model

        app = self._create_real_sqlite_app(model_client_class=FakeLangChainClientWrapper)
        try:
            client = app.test_client()
            client.post("/auth/register", json={"username": "stu_lc", "password": "password123"})
            sess = client.post("/sessions", json={"module": "translation"}).get_json()

            resp = client.post(
                f"/sessions/{sess['id']}/messages",
                json={"content": "请帮我找翻译题并生成翻译批改报告"},
            )
            self.assertEqual(resp.status_code, 200)
            raw_sse = b"".join(resp.response).decode("utf-8")

            self.assertIn('"event": "tool_call"', raw_sse)
            self.assertIn('"event": "question_loaded"', raw_sse)
            self.assertIn("翻译批改报告", raw_sse)
            self.assertNotIn("<tool_call>", raw_sse)
            self.assertNotIn("<function=search_questions>", raw_sse)
            self.assertIn('"event": "done"', raw_sse)

            updated = client.get(f"/sessions/{sess['id']}").get_json()
            self.assertEqual(updated["active_question_id"], 2)
            assistant_msgs = [m for m in updated["messages"] if m["role"] == "assistant"]
            self.assertEqual(assistant_msgs[-1]["content"], "# 翻译批改报告\n\n总分：32/40")
        finally:
            app.extensions["db"].close()

    def test_tool_markup_is_stripped_and_final_report_generated_after_max_tool_rounds(self):
        class LeakyLoopModelClient:
            def __init__(self, config):
                self.calls = 0

            def chat_completion_stream_events(self, messages, tools=None):
                self.calls += 1
                if tools is not None:
                    yield {"type": "token", "content": "<tool_ca"}
                    yield {"type": "token", "content": "ll><function=get_answer_key><parameter_id>2</parameter></function></tool_call>"}
                    yield {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": f"call_{self.calls}",
                                "name": "get_answer_key",
                                "arguments": json.dumps({"id": 2}),
                            }
                        ],
                    }
                else:
                    yield {"type": "token", "content": "# 翻译批改报告\n\n总分：28/40"}

        app = self._create_real_sqlite_app(model_client_class=LeakyLoopModelClient)
        try:
            client = app.test_client()
            client.post("/auth/register", json={"username": "stu_report", "password": "password123"})
            translation_q = client.get("/questions?module=translation").get_json()["items"][0]
            sess = client.post(
                "/sessions",
                json={"module": "translation", "question_id": translation_q["id"]},
            ).get_json()

            resp = client.post(
                f"/sessions/{sess['id']}/messages",
                json={"content": "请批改我的翻译"},
            )
            self.assertEqual(resp.status_code, 200)
            raw_sse = b"".join(resp.response).decode("utf-8")

            self.assertNotIn("<tool_call>", raw_sse)
            self.assertNotIn("<function=get_answer_key>", raw_sse)
            self.assertIn("翻译批改报告", raw_sse)
            self.assertIn('"event": "done"', raw_sse)

            detail = client.get(f"/sessions/{sess['id']}").get_json()
            assistant_msgs = [m for m in detail["messages"] if m["role"] == "assistant"]
            self.assertEqual(len(assistant_msgs), 1)
            self.assertEqual(assistant_msgs[0]["content"], "# 翻译批改报告\n\n总分：28/40")
        finally:
            app.extensions["db"].close()

    def test_execute_tool_falls_back_to_id_or_active_question_id(self):
        app = self._create_real_sqlite_app(model_client_class=FakeToolModelClient)
        try:
            client = app.test_client()
            client.post("/auth/register", json={"username": "stu_fallback", "password": "password123"})
            translation_q = client.get("/questions?module=translation").get_json()["items"][0]
            sess = client.post(
                "/sessions",
                json={"module": "translation", "question_id": translation_q["id"]},
            ).get_json()
            db = app.extensions["db"]

            res_by_id, _ = messages._execute_tool(db, 1, sess["id"], "get_answer_key", {"id": translation_q["id"]})
            self.assertEqual(res_by_id["question_id"], translation_q["id"])

            res_by_active, _ = messages._execute_tool(
                db, 1, sess["id"], "get_answer_key", {}, active_question_id=translation_q["id"]
            )
            self.assertEqual(res_by_active["question_id"], translation_q["id"])
        finally:
            app.extensions["db"].close()

    def _create_real_sqlite_app(self, admin_usernames=None, model_client_class=FakeModelClient):
        config = {
            "db": {"path": ":memory:"},
            "auth": {"admin_usernames": admin_usernames or []},
            "mineru": {"api_key": "", "base_url": "https://mineru.net/api/v4"},
            "model": {"base_url": "http://example.com", "api_key": "key", "model": "test-model"},
            "session": {"secret_key": "secret", "cookie_secure": False, "auth_session_cleanup_probability": 0},
            "cors": {"allowed_origins": ["http://localhost:8080"]},
        }
        importlib.reload(app_module)
        with patch.object(app_module, "load_config", return_value=config), patch.object(
            app_module, "ModelClient", model_client_class
        ):
            app = app_module.create_app()
            app.testing = True
            return app

    def _create_test_app(self, db_overrides=None, db_class=FakeDB, session_overrides=None):
        config = {
            "db": {"path": ":memory:"},
            "auth": {"admin_usernames": []},
            "mineru": {"api_key": "", "base_url": "https://mineru.net/api/v4"},
            "model": {"base_url": "http://example.com", "api_key": "key", "model": "test-model"},
            "session": {"secret_key": "secret", "cookie_secure": False, "auth_session_cleanup_probability": 0},
            "cors": {"allowed_origins": ["http://localhost:8080"]},
        }
        if db_overrides:
            config["db"].update(db_overrides)
        if session_overrides:
            config["session"].update(session_overrides)

        importlib.reload(app_module)

        with patch.object(app_module, "load_config", return_value=config), patch.object(
            app_module, "DB", db_class
        ), patch.object(app_module, "ModelClient", FakeModelClient), patch.object(
            app_module, "get_user_by_session", return_value={"id": 1, "username": "alice", "role": "student"}
        ):
            app = app_module.create_app()
            app.testing = True
            original_before_request = app.before_request_funcs[None][0]

            def patched_before_request():
                if request.headers.get("X-Test-Auth") == "1":
                    g.db = app.extensions["db"]
                    g.model_client = app.extensions["model_client"]
                    g.mineru_client = app.extensions["mineru_client"]
                    g.user_id = 1
                    g.username = "alice"
                    g.role = "student"
                    return None
                return original_before_request()

            app.before_request_funcs[None][0] = patched_before_request
            return app


if __name__ == "__main__":
    unittest.main()
