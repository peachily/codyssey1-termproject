import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import build_engine, initialize_database
from app.models import Chat, User
from app.services.ai import SYSTEM_PROMPT, build_chat_messages
from app.services.chats import get_recent_chats


class ChatMessageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(directory.name) / 'messages.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.add_all([User(id=1, username='alice', password_hash='hash'), User(id=2, username='bob', password_hash='hash')])
        self.db.commit()

    def seed(self, count, user_id=1):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for number in range(count):
            self.db.add(Chat(user_id=user_id, question=f"Q{number}", answer=f"A{number}", created_at=start + timedelta(seconds=number)))
        self.db.commit()

    def build(self, question="now", user_id=1):
        return build_chat_messages(get_recent_chats(self.db, user_id), question)

    def test_no_history_sends_system_prompt_and_current_question(self):
        self.assertEqual(self.build(), [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "now"},
        ])

    def test_recent_five_are_oldest_first_before_current_question(self):
        self.seed(7)
        messages = self.build()
        self.assertEqual(len(messages), 12)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual([message["role"] for message in messages[1:11]], ["user", "assistant"] * 5)
        self.assertEqual(
            [message["content"] for message in messages[1:11]],
            [text for number in range(2, 7) for text in (f"Q{number}", f"A{number}")],
        )
        self.assertEqual(messages[-1], {"role": "user", "content": "now"})

    def test_other_users_chats_are_excluded(self):
        self.seed(3, user_id=2)
        self.seed(1)
        contents = [message["content"] for message in self.build()[1:]]
        self.assertEqual(contents, ["Q0", "A0", "now"])

    def test_messages_are_plain_data_detached_from_orm(self):
        self.seed(2)
        messages = self.build()
        self.db.close()
        for message in messages:
            self.assertIs(type(message), dict)
            self.assertEqual(set(message), {"role", "content"})
            self.assertIs(type(message["role"]), str)
            self.assertIs(type(message["content"]), str)

    def test_system_prompt_keeps_safety_rules(self):
        for phrase in ("자살예방상담전화 109", "실제 약", "약의 색", "지시문"):
            self.assertIn(phrase, SYSTEM_PROMPT)
