import logging
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app import database
from app.database import build_engine, get_db, initialize_database
from app.models import Chat, User
from app.routers import chat as chat_router
from app.services.auth import hash_password


class AccessControlTests(unittest.TestCase):
    username = "access_user"
    password = "access-control-test-password"
    secret_key = "access-control-test-secret-key"
    answer = "테스트 AI 답변"
    prescription = {"keyword": "ANXIETY", "color": "BLUE", "message": "편히 쉬어가요."}

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        # 실제 서버·사용자 정보와 분리된 임시 DB
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'access-control.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        with Session(self.engine, expire_on_commit=False) as db:
            user = User(username=self.username, password_hash=self.password_hash)
            db.add(user)
            db.commit()
            self.user_id = user.id

        environment = {
            "SECRET_KEY": self.secret_key,
            "SESSION_HTTPS_ONLY": "false",
            "DATABASE_URL": "sqlite:///:memory:",
        }
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(database, "engine", self.engine):
                server = runpy.run_path(str(main_path), run_name="access_control_test_server")
        self.app = server["app"]

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                self.request_db = db
                yield db

        # DB 의존성만 교체하고 실제 세션·사용자 인증 유지
        self.app.dependency_overrides[get_db] = override_db
        self.addCleanup(self.app.dependency_overrides.clear)
        self.chat_ai = self.enterContext(
            patch.object(chat_router, "request_chat_completion", return_value=self.answer)
        )
        self.prescription_ai = self.enterContext(
            patch.object(chat_router, "request_prescription", return_value=self.prescription)
        )
        self.client = self.enterContext(TestClient(self.app))

    def login(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        return response

    def seed_chat(self):
        with Session(self.engine) as db:
            db.add(Chat(user_id=self.user_id, question="이전 질문", answer="이전 답변"))
            db.commit()

    def read_chats(self):
        with Session(self.engine) as db:
            return [
                (chat.user_id, chat.question, chat.answer)
                for chat in db.scalars(select(Chat).order_by(Chat.id))
            ]

    def read_users(self):
        with Session(self.engine) as db:
            return [
                (user.id, user.username, user.password_hash, user.created_at)
                for user in db.scalars(select(User).order_by(User.id))
            ]

    def assert_protected_requests_are_blocked(self):
        # 인증 실패 시 대화 조회·저장과 AI 호출까지 진행되지 않는지 확인
        with patch.object(chat_router, "get_recent_chats") as recent:
            with patch.object(chat_router, "save_chat") as save:
                with self.assertNoLogs("app.services.chats", level=logging.DEBUG):
                    for path in ("/api/chat", "/api/prescription"):
                        with self.subTest(path=path):
                            response = self.client.post(path, json={"message": "유효한 질문"})
                            self.assertEqual(response.status_code, 401)
                            self.assertEqual(response.json(), {"detail": "Not authenticated"})
                recent.assert_not_called()
                save.assert_not_called()
        self.chat_ai.assert_not_called()
        self.prescription_ai.assert_not_called()

    def capture_user_queries(self):
        queries = []

        def capture_statement(connection, cursor, statement, parameters, context, executemany):
            normalized = statement.upper()
            if normalized.lstrip().startswith("SELECT") and "FROM USERS" in normalized:
                queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture_statement)
        self.addCleanup(event.remove, self.engine, "before_cursor_execute", capture_statement)
        return queries

    def test_signup_does_not_grant_protected_access(self):
        """회원가입 이후에도 로그인 전 보호 기능 차단"""
        response = self.client.post(
            "/api/auth/signup",
            json={"username": "new_access_user", "password": "new-access-test-password"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("session", self.client.cookies)
        self.assert_protected_requests_are_blocked()
        self.assertEqual(self.read_chats(), [])

    def test_login_cookie_allows_chat_and_saves_authenticated_user(self):
        """실제 로그인 쿠키의 챗봇 응답 및 인증된 사용자 대화 저장"""
        before = self.read_users()
        self.login()
        response = self.client.post("/api/chat", json={"message": "  오늘의 질문  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"id", "question", "answer", "created_at"})
        self.assertEqual(response.json()["question"], "오늘의 질문")
        self.assertEqual(response.json()["answer"], self.answer)
        self.assertTrue(response.json()["created_at"].endswith("Z"))
        self.assertEqual(self.read_chats(), [(self.user_id, "오늘의 질문", self.answer)])
        self.chat_ai.assert_called_once()
        self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], self.user_id)
        self.assertRegex(self.chat_ai.call_args.kwargs["request_id"], r"^[0-9a-f]{12}$")
        self.prescription_ai.assert_not_called()
        self.assertEqual(self.read_users(), before)

    def test_login_cookie_allows_prescription_without_saving(self):
        """실제 로그인 쿠키의 처방 응답 및 기존 대화 보존"""
        self.seed_chat()
        before = self.read_chats()
        self.login()
        response = self.client.post("/api/prescription")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.prescription)
        self.prescription_ai.assert_called_once()
        self.assertEqual(self.prescription_ai.call_args.kwargs["user_id"], self.user_id)
        self.assertRegex(self.prescription_ai.call_args.kwargs["request_id"], r"^[0-9a-f]{12}$")
        self.chat_ai.assert_not_called()
        self.assertEqual(self.read_chats(), before)

    def test_missing_cookie_blocks_requests_before_protected_services(self):
        """비로그인 요청의 401 및 AI·대화 조회·저장 미실행"""
        self.seed_chat()
        before = self.read_chats()
        self.assert_protected_requests_are_blocked()
        self.assertEqual(self.read_chats(), before)

    def test_logout_blocks_requests_before_protected_services(self):
        """로그아웃 후 실제 쿠키 제거 및 보호 요청 차단"""
        self.seed_chat()
        before = self.read_chats()
        self.login()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("session", self.client.cookies)
        self.assert_protected_requests_are_blocked()
        self.assertEqual(self.read_chats(), before)

    def test_deleted_user_cookie_blocks_requests_before_protected_services(self):
        """유효한 로그인 쿠키가 있어도 삭제된 DB 사용자 거부"""
        self.login()
        with Session(self.engine) as db:
            db.delete(db.get(User, self.user_id))
            db.commit()
        self.assertIn("session", self.client.cookies)
        self.assert_protected_requests_are_blocked()
        self.assertEqual(self.read_chats(), [])

    def test_chat_ai_runs_without_transaction_or_user_requery(self):
        """실제 인증 후 챗봇 AI 진입 시 트랜잭션 종료·사용자 재조회 없음"""
        self.seed_chat()
        self.login()
        user_queries = self.capture_user_queries()

        def answer(messages, **trace):
            self.assertFalse(self.request_db.in_transaction())
            self.assertEqual(len(user_queries), 1)
            self.assertEqual(trace["user_id"], self.user_id)
            return self.answer

        self.chat_ai.side_effect = answer
        response = self.client.post("/api/chat", json={"message": "새 질문"})
        self.assertEqual(response.status_code, 200)
        self.chat_ai.assert_called_once()
        self.assertEqual(len(user_queries), 1)
        self.assertEqual(self.read_chats()[-1], (self.user_id, "새 질문", self.answer))

    def test_prescription_ai_runs_without_transaction_or_user_requery(self):
        """실제 인증 후 처방 AI 진입 시 트랜잭션 종료·사용자 재조회 없음"""
        self.seed_chat()
        before = self.read_chats()
        self.login()
        user_queries = self.capture_user_queries()

        def prescribe(messages, **trace):
            self.assertFalse(self.request_db.in_transaction())
            self.assertEqual(len(user_queries), 1)
            self.assertEqual(trace["user_id"], self.user_id)
            return self.prescription

        self.prescription_ai.side_effect = prescribe
        response = self.client.post("/api/prescription")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.prescription)
        self.prescription_ai.assert_called_once()
        self.assertEqual(len(user_queries), 1)
        self.assertEqual(self.read_chats(), before)


if __name__ == "__main__":
    unittest.main()
