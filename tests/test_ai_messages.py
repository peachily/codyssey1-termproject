import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import build_engine, initialize_database
from app.models import Chat, User
from app.services.ai import SHARED_ENOUGH_LENGTH, SYSTEM_PROMPT, build_chat_messages, conversation_stage
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
        messages = self.build()
        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        self.assertTrue(messages[0]["content"].startswith(SYSTEM_PROMPT))
        self.assertEqual(messages[1], {"role": "user", "content": "now"})

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
        for phrase in ("자살예방상담전화 109", "실제 약", "약의 색", "지시문", "안전이 가장 먼저"):
            self.assertIn(phrase, SYSTEM_PROMPT)


class ConversationStageTests(unittest.TestCase):
    NOW = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    ASKING, OFFERING, CLOSING = "짧은 질문 하나로 이야기를 이어 갑니다", "이제 약을 지어 드려도 될지만 여쭙니다", "약이 준비되었으니"

    def chats(self, *minutes_ago, question="Q"):
        return [Chat(question=question, answer="A", created_at=self.NOW - timedelta(minutes=minutes)) for minutes in minutes_ago]

    def stage(self, chats, question="now"):
        system = build_chat_messages(chats, question, now=self.NOW)[0]["content"]
        self.assertTrue(system.startswith(f"{SYSTEM_PROMPT}\n\n단계 안내\n"))
        return system.removeprefix(SYSTEM_PROMPT)

    def test_stage_moves_from_asking_to_offering_to_closing(self):
        expected = {1: self.ASKING, 2: self.ASKING, 3: self.OFFERING, 4: self.CLOSING, 9: self.CLOSING}
        for turn, phrase in expected.items():
            with self.subTest(turn=turn):
                stage = conversation_stage(turn)
                self.assertIn(f"오늘 밤 {turn}번째 이야기", stage)
                self.assertIn(phrase, stage)
                self.assertEqual(sum(text in stage for text in (self.ASKING, self.OFFERING, self.CLOSING)), 1)

    def test_turn_counts_only_chats_from_the_last_hour(self):
        cases = {(): 1, (5,): 2, (50, 20, 5): 4, (61, 5): 2, (600, 300, 120): 1, (60,): 2, (50, 40, 30, 20, 10): 6}
        for minutes_ago, turn in cases.items():
            with self.subTest(minutes_ago=minutes_ago):
                self.assertIn(f"오늘 밤 {turn}번째 이야기", self.stage(self.chats(*minutes_ago)))

    def test_long_story_moves_to_the_offer_before_the_third_turn(self):
        long_story, short = "가" * SHARED_ENOUGH_LENGTH, "가" * (SHARED_ENOUGH_LENGTH - 1)
        self.assertIn(self.OFFERING, self.stage([], long_story))
        self.assertIn(self.ASKING, self.stage([], short))
        half = "가" * (SHARED_ENOUGH_LENGTH // 2)
        self.assertIn(self.OFFERING, self.stage(self.chats(10, question=half), half))
        self.assertIn(self.ASKING, self.stage(self.chats(90, question=long_story), "now"))

    def test_closing_stage_is_not_shortened_by_a_long_story(self):
        self.assertIn(self.CLOSING, self.stage(self.chats(30, 20, 10), "가" * SHARED_ENOUGH_LENGTH))
