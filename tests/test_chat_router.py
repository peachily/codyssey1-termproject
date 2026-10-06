import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import build_engine, get_db, initialize_database
from app.models import Chat, User
from app.routers import chat as chat_router
from app.services import ai as ai_service
from app.services.ai import AICallError, AITimeoutError
from app.services.prompts import SYSTEM_PROMPT
from app.services.chats import ChatSaveError


class RouterTestCase(unittest.TestCase):
    """Temporary database, a signed-in test user and a mocked AI call."""

    path = None
    ai_target = None
    ai_result = None

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(directory.name) / 'router.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        with Session(self.engine) as db:
            db.add_all([User(id=1, username='alice', password_hash='hash'), User(id=2, username='bob', password_hash='hash')])
            db.commit()

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                self.request_db = db
                yield db

        self.app = FastAPI()
        # 인증 대체 제거 시 공통 의존성에서 사용할 테스트 세션
        self.app.add_middleware(SessionMiddleware, secret_key="chat-router-test-secret-key")
        self.app.include_router(chat_router.router)
        self.app.dependency_overrides[get_db] = override_db
        self.app.dependency_overrides[chat_router.get_current_user] = lambda: User(id=1, username='alice')
        self.client = TestClient(self.app)

        patcher = patch.object(*self.ai_target, return_value=self.ai_result)
        self.ai = patcher.start()
        self.addCleanup(patcher.stop)

    def seed(self, count, user_id=1):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with Session(self.engine) as db:
            for number in range(count):
                db.add(Chat(user_id=user_id, question=f"Q{number}", answer=f"A{number}", created_at=start + timedelta(seconds=number)))
            db.commit()

    def chat_count(self):
        with Session(self.engine) as db:
            return db.scalar(select(func.count()).select_from(Chat))

    def post(self, **kwargs):
        return self.client.post(self.path, **kwargs)


class ChatRouterTests(RouterTestCase):
    path = "/api/chat"
    ai_target = (chat_router, "request_chat_completion")
    ai_result = "AI answer"

    def test_success_returns_contract_response_and_saves_chat(self):
        response = self.post(json={"message": "  hello  "})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"id", "question", "answer", "created_at"})
        self.assertEqual((body["question"], body["answer"]), ("hello", "AI answer"))
        self.assertTrue(body["created_at"].endswith("Z"))
        self.assertEqual(datetime.fromisoformat(body["created_at"]).utcoffset(), timedelta(0))
        with Session(self.engine) as db:
            saved = db.get(Chat, body["id"])
            self.assertEqual((saved.user_id, saved.question, saved.answer), (1, "hello", "AI answer"))

    def test_answer_line_breaks_are_folded_into_one_paragraph(self):
        self.ai.return_value = "첫 문장입니다.\n\n둘째 문장인가요?  \n"
        body = self.post(json={"message": "hello"}).json()
        self.assertEqual(body["answer"], "첫 문장입니다. 둘째 문장인가요?")
        with Session(self.engine) as db:
            self.assertEqual(db.get(Chat, body["id"]).answer, body["answer"])

    def test_ai_receives_own_recent_chats_and_trace_user(self):
        self.seed(6)
        self.seed(3, user_id=2)
        self.post(json={"message": "now"})
        messages = self.ai.call_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertTrue(messages[0]["content"].startswith(SYSTEM_PROMPT))
        self.assertEqual(
            [message["content"] for message in messages[1:]],
            [text for number in range(1, 6) for text in (f"Q{number}", f"A{number}")] + ["now"],
        )
        self.assertEqual(self.ai.call_args.kwargs["user_id"], 1)

    def test_read_transaction_is_closed_before_ai_call(self):
        self.seed(1)
        self.ai.side_effect = lambda *args, **kwargs: self.assertFalse(self.request_db.in_transaction()) or "AI answer"
        self.assertEqual(self.post(json={"message": "now"}).status_code, 200)

    def test_message_length_boundary(self):
        self.assertEqual(self.post(json={"message": " " + "가" * 2000 + " "}).status_code, 200)
        self.assertEqual(self.post(json={"message": "가" * 2001}).status_code, 400)

    def test_invalid_message_is_rejected_with_400_detail(self):
        invalid = [{}, {"message": None}, {"message": 123}, {"message": ["hello"]}, {"message": ""}, {"message": "  \n\t "}, [], "hello"]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self.post(json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"detail": "Invalid message"})
        for kwargs in ({}, {"content": "{not json", "headers": {"content-type": "application/json"}}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.post(**kwargs).status_code, 400)
        self.ai.assert_not_called()
        self.assertEqual(self.chat_count(), 0)

    def test_unauthenticated_request_is_rejected_before_validation(self):
        del self.app.dependency_overrides[chat_router.get_current_user]
        for payload in ({"message": "hello"}, {}):
            with self.subTest(payload=payload):
                response = self.post(json=payload)
                self.assertEqual(response.status_code, 401)
                self.assertIsInstance(response.json()["detail"], str)
        self.ai.assert_not_called()
        self.assertEqual(self.chat_count(), 0)

    def test_ai_failures_map_to_gateway_errors_without_saving(self):
        for error, status in ((AITimeoutError("timeout"), 504), (AICallError("http_status_500"), 502)):
            with self.subTest(status=status):
                self.ai.side_effect = error
                response = self.post(json={"message": "hello"})
                self.assertEqual(response.status_code, status)
                self.assertIsInstance(response.json()["detail"], str)
                self.assertNotIn("http_status_500", response.text)
                self.assertEqual(self.chat_count(), 0)

    def test_save_failure_returns_500_contract_detail(self):
        with patch.object(chat_router, "save_chat", side_effect=ChatSaveError("Failed to save chat")):
            response = self.post(json={"message": "hello"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to save chat"})
        self.assertEqual(self.chat_count(), 0)

    def test_server_keeps_serving_after_failures(self):
        self.ai.side_effect = AITimeoutError("timeout")
        self.assertEqual(self.post(json={"message": "hello"}).status_code, 504)
        self.ai.side_effect = None
        self.assertEqual(self.post(json={"message": "hello"}).status_code, 200)


class PrescriptionRouterTests(RouterTestCase):
    path = "/api/prescription"
    ai_target = (ai_service, "request_chat_completion")
    ai_result = '{"keyword": "LONELINESS", "color": "RED", "message": "오늘 밤은 혼자가 아니에요."}'

    def test_success_returns_server_mapped_color_without_saving(self):
        self.seed(2)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"keyword": "LONELINESS", "color": "PINK", "message": "오늘 밤은 혼자가 아니에요."})
        self.assertEqual(self.chat_count(), 2)

    def test_ai_receives_own_recent_chats_and_trace_user(self):
        self.seed(6)
        self.seed(3, user_id=2)
        self.post()
        transcript = self.ai.call_args.args[0][1]["content"]
        expected = "\n".join(f"손님: Q{number}\n주인: A{number}" for number in range(1, 6))
        self.assertTrue(transcript.endswith(expected))
        self.assertNotIn("Q0", transcript)
        self.assertEqual(self.ai.call_args.kwargs["user_id"], 1)

    def test_read_transaction_is_closed_before_ai_call(self):
        self.seed(1)
        self.ai.side_effect = lambda *args, **kwargs: self.assertFalse(self.request_db.in_transaction()) or self.ai_result
        self.assertEqual(self.post().status_code, 200)

    def test_no_chats_is_rejected_without_ai_call(self):
        self.seed(3, user_id=2)
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "No chats to prescribe"})
        self.ai.assert_not_called()

    def test_unauthenticated_request_is_rejected(self):
        self.seed(1)
        del self.app.dependency_overrides[chat_router.get_current_user]
        self.assertEqual(self.post().status_code, 401)
        self.ai.assert_not_called()

    def test_ai_failures_map_to_gateway_errors(self):
        self.seed(1)
        for error, status in ((AITimeoutError("timeout"), 504), (AICallError("http_status_500"), 502)):
            with self.subTest(status=status):
                self.ai.side_effect = error
                response = self.post()
                self.assertEqual(response.status_code, status)
                self.assertNotIn("http_status_500", response.text)
        self.assertEqual(self.chat_count(), 1)

    def test_invalid_prescription_output_returns_502(self):
        self.seed(1)
        for content in ("오늘은 푹 쉬세요.", '{"keyword": "ANGER", "message": "괜찮아요."}', '{"keyword": "ANXIETY", "message": " "}'):
            with self.subTest(content=content):
                self.ai.return_value = content
                response = self.post()
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"detail": "AI request failed"})

    def test_server_keeps_serving_after_failures(self):
        self.seed(1)
        self.ai.return_value = "not json"
        self.assertEqual(self.post().status_code, 502)
        self.ai.return_value = self.ai_result
        self.assertEqual(self.post().status_code, 200)
