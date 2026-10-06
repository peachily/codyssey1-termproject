import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import database, main
from app.database import build_engine, get_db
from app.models import Chat, User
from app.routers import chat as chat_router
from app.services.auth import verify_password


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

        self.override_db = override_db
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

    def test_signup_is_registered_and_shares_request_id_with_save_log(self):
        """실제 서버의 회원가입·저장·추적 로그 및 세션 미생성 확인"""
        password = "server-signup-test-password"
        with TestClient(main.app) as client:
            with self.assertLogs("app", level="INFO") as captured:
                response = client.post(
                    "/api/auth/signup",
                    json={"username": "  user_123  ", "password": password},
                )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers["content-type"], "application/json")
            self.assertNotIn("set-cookie", response.headers)
            self.assertNotIn("session", client.cookies)
            for path in ("/api/chat", "/api/prescription"):
                with self.subTest(path=path):
                    self.assertEqual(
                        client.post(path, json={"message": "test message"}).status_code,
                        401,
                    )

        user_id = response.json()["id"]
        self.assertEqual(response.json(), {"id": user_id, "username": "user_123"})
        with Session(self.engine) as db:
            stored = db.get(User, user_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.username, "user_123")
            self.assertTrue(verify_password(password, stored.password_hash))
            password_hash = stored.password_hash
        request_log = next(
            record.getMessage() for record in captured.records if record.name == "app.main"
        )
        save_log = next(
            record.getMessage()
            for record in captured.records
            if record.name == "app.services.auth"
        )
        self.assertRegex(
            request_log,
            r"^request_received request_id=[0-9a-f]{12} method=POST path=/api/auth/signup$",
        )
        request_id = request_log.split("request_id=", 1)[1].split()[0]
        self.assertEqual(save_log, f"db_save_success request_id={request_id} user_id={user_id}")
        self.assertNotIn(password, response.text + "\n".join(captured.output))
        self.assertNotIn(password_hash, response.text + "\n".join(captured.output))

    def test_signup_and_frontend_paths_work_with_static_mount(self):
        """정적 파일 제공 환경의 실제 서버 라우터 등록 순서 검증"""
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        main_path = root / "app" / "main.py"
        main_path.parent.mkdir()
        # 실제 서버 소스를 임시 경로에서 실행해 정적 파일 분기 확인
        main_path.write_text(Path(main.__file__).read_text(encoding="utf-8"), encoding="utf-8")
        frontend = root / "frontend" / "dist"
        (frontend / "assets").mkdir(parents=True)
        html = "<html><body>Test signup frontend</body></html>"
        (frontend / "index.html").write_text(html, encoding="utf-8")
        (frontend / "assets" / "test.css").write_text("body { color: black; }", encoding="utf-8")

        with patch.object(database, "engine", self.engine):
            server = runpy.run_path(str(main_path), run_name="signup_static_test_server")
        app = server["app"]
        app.dependency_overrides[get_db] = self.override_db
        self.addCleanup(app.dependency_overrides.clear)
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/signup",
                json={"username": "static_user", "password": "static-test-password"},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers["content-type"], "application/json")
            self.assertEqual(response.json()["username"], "static_user")
            user_id = response.json()["id"]
            login = client.post(
                "/api/auth/login",
                json={"username": "static_user", "password": "static-test-password"},
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(
                client.get("/api/auth/me").json(), {"id": user_id, "username": "static_user"}
            )
            self.assertEqual(client.post("/api/auth/logout").json(), {"message": "logged out"})
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            for path in ("/", "/chat"):
                with self.subTest(path=path):
                    page = client.get(path, headers={"Accept": "text/html"})
                    self.assertEqual(page.status_code, 200)
                    self.assertEqual(page.text, html)
            asset = client.get("/assets/test.css")
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.text, "body { color: black; }")
            missing_api = client.get("/api/unknown", headers={"Accept": "text/html"})
            self.assertEqual(missing_api.status_code, 404)
            self.assertEqual(missing_api.headers["content-type"], "application/json")
            for path in ("/api/chat", "/api/prescription"):
                with self.subTest(path=path):
                    self.assertEqual(
                        client.post(path, json={"message": "test message"}).status_code,
                        401,
                    )

    def test_authentication_flow_with_real_server_app(self):
        """실제 서버의 가입·로그인·챗봇·처방·로그아웃 및 후속 차단 확인"""
        payload = {"username": "server_auth_user", "password": "  server-auth-password  "}
        chat_ai = self.enterContext(patch.object(
            chat_router, "request_chat_completion", return_value="server-flow-answer"
        ))
        prescription = {"keyword": "STRESS", "color": "GREEN", "message": "잠시 쉬어가요."}
        prescription_ai = self.enterContext(patch.object(
            chat_router, "request_prescription", return_value=prescription
        ))
        with TestClient(main.app) as client:
            signup = client.post("/api/auth/signup", json=payload)
            self.assertEqual(signup.status_code, 201)
            expected = signup.json()
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            login = client.post("/api/auth/login", json=payload)
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json(), expected)
            me = client.get("/api/auth/me")
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json(), expected)
            chat = client.post("/api/chat", json={"message": "서버 흐름 질문"})
            self.assertEqual(chat.status_code, 200)
            self.assertEqual(chat.json()["answer"], "server-flow-answer")
            self.assertEqual(chat_ai.call_args.kwargs["user_id"], expected["id"])
            with Session(self.engine) as db:
                saved = db.get(Chat, chat.json()["id"])
                self.assertEqual(saved.user_id, expected["id"])
                self.assertEqual(saved.question, "서버 흐름 질문")
            result = client.post("/api/prescription")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), prescription)
            self.assertEqual(prescription_ai.call_args.kwargs["user_id"], expected["id"])
            logout = client.post("/api/auth/logout")
            self.assertEqual(logout.status_code, 200)
            self.assertEqual(logout.json(), {"message": "logged out"})
            self.assertNotIn("session", client.cookies)
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            for path in ("/api/chat", "/api/prescription"):
                with self.subTest(path=path):
                    self.assertEqual(client.post(path, json={"message": "차단 질문"}).status_code, 401)
            chat_ai.assert_called_once()
            prescription_ai.assert_called_once()
            self.assertEqual(client.post("/api/auth/logout").status_code, 200)
            self.assertEqual(client.get("/health").json(), {"status": "ok"})

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
