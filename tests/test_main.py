import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import main
from app.database import build_engine, get_db
from app.models import User
from app.routers import chat as chat_router


class ServerAssemblyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(directory.name) / 'server.db'}")
        self.addCleanup(self.engine.dispose)
        patcher = patch.object(main, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        main.app.dependency_overrides[get_db] = override_db
        self.addCleanup(main.app.dependency_overrides.clear)

    def sign_in(self):
        with Session(self.engine) as db:
            db.add(User(id=1, username="alice", password_hash="hash"))
            db.commit()
        main.app.dependency_overrides[chat_router.get_current_user] = lambda: User(id=1, username="alice")

    def test_startup_creates_tables_and_shutdown_releases_engine(self):
        self.assertEqual(inspect(self.engine).get_table_names(), [])
        with patch.object(self.engine, "dispose", wraps=self.engine.dispose) as dispose:
            with TestClient(main.app):
                self.assertEqual(set(inspect(self.engine).get_table_names()), {"users", "chats"})
                dispose.assert_not_called()
            dispose.assert_called_once()

    def test_health_is_kept_and_not_logged_as_api_request(self):
        with TestClient(main.app) as client:
            with self.assertNoLogs("app.main", level="INFO"):
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_routes_are_registered_and_require_sign_in(self):
        with TestClient(main.app) as client:
            for path in ("/api/chat", "/api/prescription"):
                with self.subTest(path=path):
                    response = client.post(path, json={"message": "hello"})
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["content-type"], "application/json")

    def test_unknown_api_path_is_json_404_not_frontend_fallback(self):
        with TestClient(main.app) as client:
            response = client.get("/api/unknown", headers={"accept": "text/html"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["content-type"], "application/json")

    def test_api_request_is_logged_and_shares_request_id_with_ai_call(self):
        with patch.object(chat_router, "request_chat_completion", return_value="AI answer") as ai:
            with TestClient(main.app) as client:
                self.sign_in()
                with self.assertLogs("app.main", level="INFO") as logs:
                    response = client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(logs.output), 1)
        self.assertRegex(logs.output[0], r"request_received request_id=[0-9a-f]{12} method=POST path=/api/chat$")
        self.assertIn(f"request_id={ai.call_args.kwargs['request_id']} ", logs.output[0])

    def test_each_request_gets_its_own_request_id(self):
        with TestClient(main.app) as client:
            with self.assertLogs("app.main", level="INFO") as logs:
                client.post("/api/chat", json={"message": "hello"})
                client.post("/api/chat", json={"message": "hello"})
        ids = {line.split("request_id=")[1].split()[0] for line in logs.output}
        self.assertEqual(len(ids), 2)
