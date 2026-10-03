import base64
import json
import os
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app import database, main
from app.models import Chat, User
from app.services.chats import ChatSaveError


class HistoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = database.build_engine(f"sqlite:///{Path(directory.name) / 'test.db'}")
        self.addCleanup(self.engine.dispose)
        database.initialize_database(self.engine)
        self.factory = sessionmaker(self.engine)
        with self.factory() as db:
            db.add_all([User(id=1, username="alice", password_hash="private"), User(id=2, username="bob", password_hash="private")])
            db.commit()
            db.add_all([Chat(user_id=1, question=f"Q{i}", answer="A", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)) for i in range(20)])
            db.add(Chat(user_id=2, question="other user's private question", answer="private"))
            db.commit()
        self.enterContext(patch.object(database, "engine", self.engine))
        self.enterContext(patch.object(database, "SessionLocal", self.factory))
        self.enterContext(patch.dict(os.environ, {"SECRET_KEY": "test-session-key", "SESSION_HTTPS_ONLY": "false"}))
        self.app = main.create_app()
        self.client = self.enterContext(TestClient(self.app))

    def cookie(self, user_id, expired=False):
        signer = TimestampSigner("test-session-key")
        data = base64.b64encode(json.dumps({"user_id": user_id}).encode())
        with patch.object(signer, "get_timestamp", return_value=1) if expired else nullcontext():
            return signer.sign(data).decode()

    def request_as(self, user_id):
        self.client.cookies.set("session", self.cookie(user_id))
        return self.client.get("/api/me/chats?user_id=2")

    def test_own_history_is_latest_first_and_uses_two_queries(self):
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", record)
        self.addCleanup(event.remove, self.engine, "before_cursor_execute", record)
        with self.assertLogs("app.routers.history", level="INFO") as logs:
            response = self.request_as(1)
        self.assertEqual(response.status_code, 200)
        chats = response.json()["chats"]
        self.assertEqual([chat["question"] for chat in chats], [f"Q{i}" for i in reversed(range(20))])
        self.assertEqual(set(chats[0]), {"id", "question", "answer", "created_at"})
        self.assertEqual(chats[0]["created_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(len(statements), 2)
        self.assertIn("request_received", logs.output[0])

    def test_empty_history(self):
        with self.factory() as db:
            db.add(User(id=3, username="empty", password_hash="private"))
            db.commit()
        self.assertEqual(self.request_as(3).json(), {"chats": []})

    def test_absent_tampered_and_expired_sessions_are_unauthorized(self):
        for cookie in (None, self.cookie(1) + "tampered", self.cookie(1, expired=True)):
            with self.subTest(cookie=cookie):
                self.client.cookies.clear()
                if cookie:
                    self.client.cookies.set("session", cookie)
                self.assertEqual(self.client.get("/api/me/chats").status_code, 401)

    def test_invalid_user_ids_are_unauthorized(self):
        for value in (True, [], {}, "1", None, 999):
            with self.subTest(value=value):
                self.assertEqual(self.request_as(value).status_code, 401)

    def test_deleted_user_session_is_unauthorized(self):
        with self.factory() as db:
            db.add(User(id=3, username="removed", password_hash="private"))
            db.commit()
            db.delete(db.get(User, 3))
            db.commit()
        self.assertEqual(self.request_as(3).status_code, 401)

    def test_storage_failure_has_safe_http_response(self):
        @self.app.get("/test-save-error")
        def failure():
            raise ChatSaveError("private database details")
        response = self.client.get("/test-save-error")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to save chat"})

    def test_missing_secret_blocks_startup(self):
        with patch.dict(os.environ, {"SECRET_KEY": ""}):
            app = main.create_app()
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            with TestClient(app):
                pass

    def test_https_setting_adds_secure_cookie_flag(self):
        from fastapi import Request

        with patch.dict(os.environ, {"SESSION_HTTPS_ONLY": "true"}):
            app = main.create_app()
        @app.get("/test-session")
        def write_session(request: Request):
            request.session["user_id"] = 1
            return {"status": "ok"}
        with TestClient(app, base_url="https://testserver") as client:
            response = client.get("/test-session")
        self.assertEqual(response.status_code, 200)
        self.assertIn("secure", response.headers["set-cookie"])
        self.assertIn("httponly", response.headers["set-cookie"])
        self.assertIn("samesite=lax", response.headers["set-cookie"])

    def test_spa_fallback_does_not_capture_api_or_assets(self):
        from fastapi import FastAPI

        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "index.html").write_text("<html>test frontend</html>", encoding="utf-8")
            app = FastAPI()
            app.mount("/", main.FrontendFiles(directory=directory, html=True))
            with TestClient(app) as client:
                self.assertEqual(client.get("/chat", headers={"Accept": "text/html"}).status_code, 200)
                for path in ("/api/unknown", "/health/unknown", "/assets/missing.js"):
                    self.assertEqual(client.get(path, headers={"Accept": "text/html"}).status_code, 404)

    def test_health_root_and_unknown_api(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/unknown", headers={"Accept": "text/html"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
