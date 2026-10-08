import base64
import json
import logging
import os
import runpy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import database
from app.config import AISettings
from app.database import build_engine, get_db, initialize_database
from app.models import Chat, User
from app.routers import chat as chat_router
from app.services import ai as ai_service
from app.services import chats as chat_service
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

    def make_signed_in_pair(self):
        # 계정마다 별도 쿠키 저장소와 실제 가입·로그인 사용
        other = self.enterContext(TestClient(self.app))
        accounts = []
        for client, username, password in (
            (self.client, "alice_access", "alice-isolation-test-password"),
            (other, "bob_access", "bob-isolation-test-password"),
        ):
            signup = client.post(
                "/api/auth/signup", json={"username": username, "password": password}
            )
            self.assertEqual(signup.status_code, 201)
            user = signup.json()
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            login = client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json(), user)
            self.assertEqual(client.get("/api/auth/me").json(), user)
            accounts.append((client, user))
        return accounts

    def seed_user_chats(self, user_id, label, count=7):
        # 두 사용자의 기록을 구분할 문구와 같은 시각 기준 사용
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        pairs = [(f"{label}-question-{number}", f"{label}-answer-{number}")
                 for number in range(count)]
        with Session(self.engine) as db:
            for number, (question, answer) in enumerate(pairs):
                db.add(Chat(
                    user_id=user_id,
                    question=question,
                    answer=answer,
                    created_at=start + timedelta(seconds=number),
                ))
            db.commit()
        return pairs

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

    def set_session_cookie(self, payload, secret_key=None):
        # 테스트용 키로 서명한 쿠키를 실제 세션 미들웨어에 전달
        data = base64.b64encode(json.dumps(payload).encode("utf-8"))
        signer = TimestampSigner(self.secret_key if secret_key is None else secret_key)
        self.client.cookies.clear()
        self.client.cookies.set("session", signer.sign(data).decode("utf-8"))

    def use_real_ai_service(self):
        # 실제 AI 처리·로그를 실행하고 외부 HTTP 전송만 대체
        self.enterContext(patch.object(
            chat_router, "request_chat_completion", ai_service.request_chat_completion
        ))
        self.enterContext(patch.object(
            chat_router, "request_prescription", ai_service.request_prescription
        ))
        settings = AISettings(
            api_key="access-control-ai-test-key",
            api_url="https://example.invalid/test-ai",
            model="access-test-model",
            timeout=1.0,
        )
        self.enterContext(patch.object(ai_service, "get_ai_settings", return_value=settings))
        transport = self.enterContext(patch.object(ai_service.requests, "post"))
        transport.return_value.ok = True
        transport.return_value.json.return_value = {
            "choices": [{"message": {"content": self.answer}}]
        }
        return transport

    def assert_trace_logs(self, records, path, ai_events, db_event=None):
        request = next(record.getMessage() for record in records
                       if record.name == "access_control_test_server")
        self.assertIn(f"method=POST path={path}", request)
        request_id = request.split("request_id=", 1)[1].split()[0]
        self.assertRegex(request_id, r"^[0-9a-f]{12}$")
        for name, expected_count in ai_events.items():
            messages = [record.getMessage() for record in records
                        if record.name == "app.services.ai"
                        and record.getMessage().startswith(name + " ")]
            self.assertEqual(len(messages), expected_count)
            for message in messages:
                self.assertIn(f"user_id={self.user_id} ", message)
                self.assertIn(f"request_id={request_id} ", message)
        db_messages = [record.getMessage() for record in records
                       if record.name == "app.services.chats"]
        if db_event is None:
            self.assertEqual(db_messages, [])
        else:
            self.assertEqual(len(db_messages), 1)
            self.assertTrue(db_messages[0].startswith(db_event + " "))
            self.assertIn(f"user_id={self.user_id}", db_messages[0])

    def assert_safe_failure(self, response, records):
        output = response.text + "\n".join(record.getMessage() for record in records)
        for sensitive in (
            self.password, self.password_hash, self.secret_key, "access-control-ai-test-key",
            "sensitive-sql", "private-db-error", "private-ai-error", "private-timeout",
        ):
            self.assertNotIn(sensitive, output)
        self.assertTrue(all(record.exc_info is None for record in records))

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

    def test_two_clients_save_chats_under_their_session_user(self):
        """두 실제 로그인 계정의 대화 저장 사용자 분리"""
        accounts = self.make_signed_in_pair()
        before_users = self.read_users()
        expected = []
        self.chat_ai.side_effect = ["alice-private-answer", "bob-private-answer"]
        for (client, user), label in zip(accounts, ("alice", "bob")):
            with self.subTest(username=user["username"]):
                question = f"{label}-private-question"
                response = client.post("/api/chat", json={"message": question})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["answer"], f"{label}-private-answer")
                self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], user["id"])
                expected.append((user["id"], question, f"{label}-private-answer"))
                self.assertEqual(client.get("/api/auth/me").json(), user)
        self.assertEqual(self.read_chats(), expected)
        self.assertEqual(self.chat_ai.call_count, 2)
        self.assertEqual(self.read_users(), before_users)

    def test_chat_context_uses_only_each_users_latest_five_pairs(self):
        """각 계정의 최근 5개 대화만 시간순 챗봇 문맥에 포함"""
        accounts = self.make_signed_in_pair()
        histories = [self.seed_user_chats(user["id"], label)
                     for (_, user), label in zip(accounts, ("alice", "bob"))]
        for (client, user), history in zip(accounts, histories):
            with self.subTest(username=user["username"]):
                question = f"{user['username']}-current-question"
                response = client.post("/api/chat", json={"message": question})
                self.assertEqual(response.status_code, 200)
                expected = []
                for prior_question, prior_answer in history[-5:]:
                    expected.extend([
                        {"role": "user", "content": prior_question},
                        {"role": "assistant", "content": prior_answer},
                    ])
                expected.append({"role": "user", "content": question})
                messages = self.chat_ai.call_args.args[0]
                self.assertEqual(messages[0]["role"], "system")
                self.assertEqual(messages[1:], expected)
                self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], user["id"])
        self.assertEqual(self.chat_ai.call_count, 2)

    def test_prescription_context_uses_only_each_users_latest_five_pairs(self):
        """각 계정의 최근 5개 대화만 처방 입력에 포함 및 처방 미저장"""
        accounts = self.make_signed_in_pair()
        histories = [self.seed_user_chats(user["id"], label)
                     for (_, user), label in zip(accounts, ("alice", "bob"))]
        before = self.read_chats()
        for (client, user), history in zip(accounts, histories):
            with self.subTest(username=user["username"]):
                response = client.post("/api/prescription")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), self.prescription)
                transcript = "\n".join(f"손님: {question}\n주인: {answer}"
                                       for question, answer in history[-5:])
                messages = self.prescription_ai.call_args.args[0]
                self.assertEqual(messages[1], {
                    "role": "user",
                    "content": f"아래는 손님과 나눈 대화입니다.\n\n{transcript}",
                })
                self.assertEqual(self.prescription_ai.call_args.kwargs["user_id"], user["id"])
        self.assertEqual(self.prescription_ai.call_count, 2)
        self.assertEqual(self.read_chats(), before)

    def test_other_users_history_does_not_allow_prescription_for_empty_user(self):
        """본인 대화가 없으면 다른 계정 기록으로 처방 생성 불가"""
        (client, user), (other, other_user) = self.make_signed_in_pair()
        self.seed_user_chats(other_user["id"], "bob")
        before = self.read_chats()
        response = client.post("/api/prescription")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "No chats to prescribe"})
        self.prescription_ai.assert_not_called()
        self.assertEqual(other.post("/api/prescription").status_code, 200)
        self.assertEqual(self.prescription_ai.call_args.kwargs["user_id"], other_user["id"])
        self.assertEqual(client.get("/api/auth/me").json(), user)
        self.assertEqual(self.read_chats(), before)

    def test_chat_without_own_history_does_not_use_other_users_history(self):
        """본인 대화가 없으면 타인 기록 없이 현재 질문만 AI에 전달"""
        (client, user), (_, other_user) = self.make_signed_in_pair()
        self.seed_user_chats(other_user["id"], "bob")
        before = self.read_chats()
        response = client.post("/api/chat", json={"message": "alice-first-question"})
        self.assertEqual(response.status_code, 200)
        messages = self.chat_ai.call_args.args[0]
        self.assertEqual(messages[1:], [{"role": "user", "content": "alice-first-question"}])
        self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], user["id"])
        self.assertEqual(self.read_chats(), before + [(user["id"], "alice-first-question", self.answer)])

    def test_supplied_ids_do_not_change_chat_owner_or_context(self):
        """본문·쿼리·헤더의 타인 ID가 챗봇 저장·문맥 대상을 바꾸지 않음"""
        accounts = self.make_signed_in_pair()
        histories = [self.seed_user_chats(user["id"], label)
                     for (_, user), label in zip(accounts, ("alice", "bob"))]
        for index, ((client, user), history) in enumerate(zip(accounts, histories)):
            with self.subTest(username=user["username"]):
                other_id = accounts[1 - index][1]["id"]
                question = f"{user['username']}-spoofed-request"
                response = client.post(
                    "/api/chat",
                    params={"user_id": other_id},
                    json={"message": question, "user_id": other_id},
                    headers={"X-User-ID": str(other_id)},
                )
                self.assertEqual(response.status_code, 200)
                expected = []
                for prior_question, prior_answer in history[-5:]:
                    expected.extend([
                        {"role": "user", "content": prior_question},
                        {"role": "assistant", "content": prior_answer},
                    ])
                expected.append({"role": "user", "content": question})
                self.assertEqual(self.chat_ai.call_args.args[0][1:], expected)
                self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], user["id"])
                with Session(self.engine) as db:
                    saved = db.get(Chat, response.json()["id"])
                    self.assertEqual(saved.user_id, user["id"])
                    self.assertEqual(saved.question, question)
                self.assertEqual(client.get("/api/auth/me").json(), user)
        self.assertEqual(self.chat_ai.call_count, 2)

    def test_supplied_ids_do_not_change_prescription_context(self):
        """본문·쿼리·헤더의 타인 ID가 처방 입력 대상을 바꾸지 않음"""
        accounts = self.make_signed_in_pair()
        histories = [self.seed_user_chats(user["id"], label)
                     for (_, user), label in zip(accounts, ("alice", "bob"))]
        before = self.read_chats()
        for index, ((client, user), history) in enumerate(zip(accounts, histories)):
            with self.subTest(username=user["username"]):
                other_id = accounts[1 - index][1]["id"]
                response = client.post(
                    "/api/prescription",
                    params={"user_id": other_id},
                    json={"user_id": other_id},
                    headers={"X-User-ID": str(other_id)},
                )
                self.assertEqual(response.status_code, 200)
                transcript = "\n".join(f"손님: {question}\n주인: {answer}"
                                       for question, answer in history[-5:])
                self.assertEqual(self.prescription_ai.call_args.args[0][1]["content"],
                                 f"아래는 손님과 나눈 대화입니다.\n\n{transcript}")
                self.assertEqual(self.prescription_ai.call_args.kwargs["user_id"], user["id"])
                self.assertEqual(client.get("/api/auth/me").json(), user)
        self.assertEqual(self.prescription_ai.call_count, 2)
        self.assertEqual(self.read_chats(), before)

    def test_one_clients_logout_keeps_other_clients_protected_access(self):
        """한 계정 로그아웃 이후 다른 계정의 챗봇·처방 접근 유지"""
        (client, _), (other, other_user) = self.make_signed_in_pair()
        history = self.seed_user_chats(other_user["id"], "bob", count=2)
        before = self.read_chats()
        self.assertEqual(client.post("/api/auth/logout").status_code, 200)
        self.assert_protected_requests_are_blocked()
        self.assertEqual(other.get("/api/auth/me").json(), other_user)
        self.assertIn("session", other.cookies)
        response = other.post("/api/chat", json={"message": "bob-after-alice-logout"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.chat_ai.call_args.kwargs["user_id"], other_user["id"])
        expected = before + [(other_user["id"], "bob-after-alice-logout", self.answer)]
        self.assertEqual(self.read_chats(), expected)
        self.assertEqual(other.post("/api/prescription").status_code, 200)
        transcript = "\n".join(f"손님: {question}\n주인: {answer}"
                               for question, answer in history + [("bob-after-alice-logout", self.answer)])
        self.assertEqual(self.prescription_ai.call_args.args[0][1]["content"],
                         f"아래는 손님과 나눈 대화입니다.\n\n{transcript}")
        self.assertEqual(self.prescription_ai.call_args.kwargs["user_id"], other_user["id"])
        self.assertEqual(self.read_chats(), expected)

    def test_tampered_cookie_blocks_protected_services(self):
        """사용자 ID 변조 쿠키의 실제 챗봇·처방 접근 차단"""
        self.login()
        payload, signature = self.client.cookies.get("session").split(".", 1)
        data = json.loads(base64.b64decode(payload))
        data["user_id"] = self.user_id + 1000
        changed = base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
        self.client.cookies.clear()
        self.client.cookies.set("session", f"{changed}.{signature}")
        self.assert_protected_requests_are_blocked()
        self.assertEqual(self.read_chats(), [])

    def test_cookie_signed_with_other_key_blocks_protected_services(self):
        """다른 키로 서명한 쿠키의 실제 챗봇·처방 접근 차단"""
        self.set_session_cookie({"user_id": self.user_id})
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.set_session_cookie({"user_id": self.user_id}, "other-access-test-key")
        self.assert_protected_requests_are_blocked()

    def test_expired_cookie_blocks_protected_services(self):
        """세션 유효 기간 만료 이후 실제 챗봇·처방 접근 차단"""
        timestamp = 1_700_000_000
        with patch.object(TimestampSigner, "get_timestamp", return_value=timestamp):
            self.login()
        with patch.object(TimestampSigner, "get_timestamp",
                          return_value=timestamp + 14 * 24 * 60 * 60 + 1):
            self.assert_protected_requests_are_blocked()

    def test_signed_invalid_user_ids_are_rejected_before_lookup(self):
        """정상 서명 쿠키의 잘못된 ID 타입을 DB 조회 전 거부"""
        self.set_session_cookie({"user_id": self.user_id})
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        for index, value in enumerate((None, str(self.user_id), True, False, 1.0, [], {})):
            with self.subTest(case=index):
                self.set_session_cookie({"user_id": value})
                with patch.object(Session, "get", side_effect=AssertionError("Unexpected lookup")):
                    self.assert_protected_requests_are_blocked()

    def test_nonexistent_user_cookie_blocks_protected_services(self):
        """정상 서명·정수 ID라도 DB 사용자가 없으면 보호 기능 차단"""
        self.set_session_cookie({"user_id": self.user_id + 1000})
        self.assert_protected_requests_are_blocked()

    def test_supplied_ids_without_cookie_do_not_authenticate(self):
        """쿠키 없이 본문·쿼리·헤더 ID로 보호 API 인증 불가"""
        with patch.object(chat_router, "get_recent_chats") as recent:
            with patch.object(chat_router, "save_chat") as save:
                for path in ("/api/chat", "/api/prescription"):
                    with self.subTest(path=path):
                        response = self.client.post(
                            path, params={"user_id": self.user_id},
                            json={"message": "유효한 질문", "user_id": self.user_id},
                            headers={"X-User-ID": str(self.user_id)},
                        )
                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.json(), {"detail": "Not authenticated"})
                recent.assert_not_called()
                save.assert_not_called()
        self.chat_ai.assert_not_called()
        self.prescription_ai.assert_not_called()

    def test_authentication_lookup_failure_blocks_services_and_recovers(self):
        """사용자 조회 장애의 안전한 500·rollback·서비스 미실행 및 복구"""
        self.seed_chat()
        self.login()
        before = self.read_chats()

        def fail_user_lookup(connection, cursor, statement, parameters, context, executemany):
            if "FROM USERS" in statement.upper():
                raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

        original_rollback = Session.rollback
        event.listen(self.engine, "before_cursor_execute", fail_user_lookup)
        try:
            with patch.object(Session, "rollback", autospec=True,
                              side_effect=original_rollback) as rollback:
                with patch.object(chat_router, "get_recent_chats") as recent:
                    with patch.object(chat_router, "save_chat") as save:
                        for path in ("/api/chat", "/api/prescription"):
                            with self.subTest(path=path):
                                with self.assertLogs(level=logging.INFO) as captured:
                                    response = self.client.post(path, json={"message": "유효한 질문"})
                                self.assertEqual(response.status_code, 500)
                                self.assertEqual(response.json(), {"detail": "Failed to retrieve user"})
                                self.assertFalse(self.request_db.in_transaction())
                                request = next(record.getMessage() for record in captured.records
                                               if record.name == "access_control_test_server")
                                request_id = request.split("request_id=", 1)[1].split()[0]
                                failure = [record.getMessage() for record in captured.records
                                           if record.name == "app.dependencies"]
                                self.assertEqual(failure, [
                                    f"auth_lookup_failure request_id={request_id} reason=db_error"
                                ])
                                self.assert_safe_failure(response, captured.records)
                        recent.assert_not_called()
                        save.assert_not_called()
                self.assertEqual(rollback.call_count, 2)
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_user_lookup)
        self.chat_ai.assert_not_called()
        self.prescription_ai.assert_not_called()
        self.assertEqual(self.read_chats(), before)
        self.assertEqual(self.client.get("/api/auth/me").json()["id"], self.user_id)
        self.assertEqual(self.client.post("/api/chat", json={"message": "복구 질문"}).status_code, 200)
        self.assertEqual(self.client.post("/api/prescription").status_code, 200)

    def test_chat_ai_failure_and_timeout_do_not_save_and_recover(self):
        """실제 AI 서비스의 챗봇 502·504·안전한 로그·대화 미저장 및 복구"""
        self.seed_chat()
        self.login()
        transport = self.use_real_ai_service()
        for error, status in (
            (requests.ConnectionError("private-ai-error"), 502),
            (requests.Timeout("private-timeout"), 504),
        ):
            with self.subTest(status=status):
                before = self.read_chats()
                transport.reset_mock()
                transport.side_effect = error
                with self.assertLogs(level=logging.INFO) as captured:
                    response = self.client.post("/api/chat", json={"message": "실패 질문"})
                self.assertEqual(response.status_code, status)
                detail = "AI response timed out" if status == 504 else "AI request failed"
                self.assertEqual(response.json(), {"detail": detail})
                transport.assert_called_once()
                self.assert_trace_logs(captured.records, "/api/chat", {
                    "ai_call_start": 1, "ai_call_failure": 1, "ai_call_success": 0,
                })
                self.assert_safe_failure(response, captured.records)
                self.assertEqual(self.read_chats(), before)
                transport.side_effect = None
                self.assertEqual(self.client.post("/api/chat", json={"message": "복구 질문"}).status_code, 200)
                self.assertEqual(len(self.read_chats()), len(before) + 1)

    def test_prescription_ai_failure_and_timeout_preserve_history_and_recover(self):
        """실제 AI 서비스의 처방 502·504·안전한 로그·대화 보존 및 복구"""
        self.seed_chat()
        self.login()
        before = self.read_chats()
        transport = self.use_real_ai_service()
        transport.return_value.json.return_value = {
            "choices": [{"message": {"content": json.dumps(self.prescription)}}]
        }
        for error, status in (
            (requests.ConnectionError("private-ai-error"), 502),
            (requests.Timeout("private-timeout"), 504),
        ):
            with self.subTest(status=status):
                transport.reset_mock()
                transport.side_effect = error
                with self.assertLogs(level=logging.INFO) as captured:
                    response = self.client.post("/api/prescription")
                self.assertEqual(response.status_code, status)
                detail = "AI response timed out" if status == 504 else "AI request failed"
                self.assertEqual(response.json(), {"detail": detail})
                transport.assert_called_once()
                self.assert_trace_logs(captured.records, "/api/prescription", {
                    "ai_call_start": 1, "ai_call_failure": 1, "ai_call_success": 0,
                })
                self.assert_safe_failure(response, captured.records)
                transport.side_effect = None
                with self.assertLogs(level=logging.INFO) as recovered:
                    success = self.client.post("/api/prescription")
                self.assertEqual(success.json(), self.prescription)
                self.assert_trace_logs(recovered.records, "/api/prescription", {
                    "ai_call_start": 1, "ai_call_success": 1, "ai_call_failure": 0,
                })
                self.assertEqual(self.read_chats(), before)

    def test_invalid_prescription_returns_502_without_saving_and_recovers(self):
        """잘못된 처방 형식의 기존 재시도·502·대화 보존 및 복구"""
        self.seed_chat()
        self.login()
        before = self.read_chats()
        transport = self.use_real_ai_service()
        transport.return_value.json.return_value = {
            "choices": [{"message": {"content": "private-invalid-prescription"}}]
        }
        with self.assertLogs(level=logging.INFO) as captured:
            response = self.client.post("/api/prescription")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "AI request failed"})
        self.assertEqual(transport.call_count, 2)
        self.assert_trace_logs(captured.records, "/api/prescription", {
            "ai_call_start": 2, "ai_call_success": 2, "ai_call_failure": 2,
        })
        self.assertNotIn("private-invalid-prescription", response.text + str(captured.output))
        self.assert_safe_failure(response, captured.records)
        transport.return_value.json.return_value = {
            "choices": [{"message": {"content": json.dumps(self.prescription)}}]
        }
        self.assertEqual(self.client.post("/api/prescription").json(), self.prescription)
        self.assertEqual(self.read_chats(), before)

    def test_chat_commit_failure_rolls_back_and_recovers(self):
        """실제 commit 장애의 500·rollback·실패 로그·대화 미저장 및 복구"""
        self.seed_chat()
        self.login()
        before = self.read_chats()
        self.use_real_ai_service()

        def fail_commit(connection):
            raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

        original_rollback = Session.rollback
        event.listen(self.engine, "commit", fail_commit)
        try:
            with patch.object(Session, "rollback", autospec=True,
                              side_effect=original_rollback) as rollback:
                with self.assertLogs(level=logging.INFO) as captured:
                    response = self.client.post("/api/chat", json={"message": "저장 실패 질문"})
                self.assertEqual(rollback.call_count, 2)
        finally:
            event.remove(self.engine, "commit", fail_commit)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to save chat"})
        self.assert_trace_logs(captured.records, "/api/chat", {
            "ai_call_start": 1, "ai_call_success": 1, "ai_call_failure": 0,
        }, db_event="db_save_failure")
        self.assert_safe_failure(response, captured.records)
        self.assertFalse(self.request_db.in_transaction())
        self.assertEqual(self.read_chats(), before)
        self.assertEqual(self.client.post("/api/chat", json={"message": "저장 복구 질문"}).status_code, 200)
        self.assertEqual(len(self.read_chats()), len(before) + 1)

    def test_transport_failures_return_safe_errors_and_leave_server_usable(self):
        self.login()
        transport = self.use_real_ai_service()
        cases = ('timeout', 'connection', 'http_error', 'invalid_json', 'invalid_structure')
        for failure in cases:
            with self.subTest(failure=failure):
                transport.reset_mock(return_value=True, side_effect=True)
                transport.return_value.ok = True
                if failure == 'timeout':
                    transport.side_effect = requests.Timeout('private-ai-error')
                elif failure == 'connection':
                    transport.side_effect = requests.ConnectionError('private-ai-error')
                elif failure == 'http_error':
                    transport.return_value.ok = False
                    transport.return_value.status_code = 503
                elif failure == 'invalid_json':
                    transport.return_value.json.side_effect = ValueError('private-ai-error')
                else:
                    transport.return_value.json.return_value = {'choices': []}
                before = self.read_chats()
                with self.assertLogs(level=logging.INFO) as captured:
                    response = self.client.post('/api/chat', json={'message': '실패 질문'})
                self.assertEqual(response.status_code, 504 if failure == 'timeout' else 502)
                self.assertEqual(response.json(), {'detail': 'AI response timed out' if failure == 'timeout' else 'AI request failed'})
                self.assertEqual(self.read_chats(), before)
                self.assert_trace_logs(captured.records, '/api/chat', {
                    'ai_call_start': 1, 'ai_call_success': 0, 'ai_call_failure': 1,
                })
                self.assert_safe_failure(response, captured.records)
                self.assertEqual(self.client.get('/health').status_code, 200)
                self.assertEqual(self.client.get('/api/me/chats').status_code, 200)

    def test_real_ai_success_logs_share_request_and_user_ids(self):
        """실제 AI 성공 로그의 요청·사용자 추적과 commit 이후 저장 로그 확인"""
        self.login()
        self.use_real_ai_service()
        committed = []

        def mark_commit(db):
            committed.append(True)

        original_info = chat_service.logger.info

        def log_after_commit(message, *args, **kwargs):
            if message.startswith("db_save_success"):
                self.assertEqual(committed, [True])
            return original_info(message, *args, **kwargs)

        event.listen(Session, "after_commit", mark_commit)
        try:
            with patch.object(chat_service.logger, "info", side_effect=log_after_commit):
                with self.assertLogs(level=logging.INFO) as captured:
                    response = self.client.post("/api/chat", json={"message": "성공 질문"})
        finally:
            event.remove(Session, "after_commit", mark_commit)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(committed, [True])
        self.assert_trace_logs(captured.records, "/api/chat", {
            "ai_call_start": 1, "ai_call_success": 1, "ai_call_failure": 0,
        }, db_event="db_save_success")
        logs = "\n".join(record.getMessage() for record in captured.records)
        for sensitive in ("성공 질문", self.answer, self.password, self.password_hash,
                          self.secret_key, "access-control-ai-test-key"):
            self.assertNotIn(sensitive, logs)
        self.assertEqual(self.read_chats(), [(self.user_id, "성공 질문", self.answer)])


if __name__ == "__main__":
    unittest.main()
