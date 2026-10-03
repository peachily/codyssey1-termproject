import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app import database


class ModelTests(unittest.TestCase):
    def setUp(self):
        from app.models import Chat, User

        self.Chat, self.User = Chat, User
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = database.build_engine(f"sqlite:///{Path(directory.name) / 'test.db'}")
        self.addCleanup(self.engine.dispose)
        database.initialize_database(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)

    def add_user(self):
        user = self.User(username="alice", password_hash="already-hashed")
        self.session.add(user)
        self.session.commit()
        return user

    def test_duplicate_username_is_rejected(self):
        self.add_user()
        self.session.add(self.User(username="alice", password_hash="other-hash"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_chat_requires_existing_user(self):
        self.session.add(self.Chat(user_id=999, question="Q", answer="A"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_user_deletion_cannot_cascade_into_chat_history(self):
        user = self.add_user()
        self.session.add(self.Chat(user_id=user.id, question="Q", answer="A"))
        self.session.commit()
        self.session.delete(user)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()
        self.assertEqual(self.session.query(self.Chat).count(), 1)

    def test_required_columns_reject_null(self):
        user = self.add_user()
        statements = [
            "INSERT INTO users (username, password_hash, created_at) VALUES (NULL, 'hash', CURRENT_TIMESTAMP)",
            "INSERT INTO users (username, password_hash, created_at) VALUES ('bob', NULL, CURRENT_TIMESTAMP)",
            "INSERT INTO users (username, password_hash, created_at) VALUES ('bob', 'hash', NULL)",
        ]
        for column in ("user_id", "question", "answer", "created_at"):
            values = {"user_id": str(user.id), "question": "'Q'", "answer": "'A'", "created_at": "CURRENT_TIMESTAMP"}
            values[column] = "NULL"
            statements.append(f"INSERT INTO chats ({', '.join(values)}) VALUES ({', '.join(values.values())})")
        for statement in statements:
            with self.subTest(statement=statement), self.assertRaises(IntegrityError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))

    def test_timestamps_round_trip_as_utc(self):
        user = self.add_user()
        self.assertEqual(user.created_at.utcoffset(), timedelta(0))
        local_time = datetime(2026, 10, 4, 12, tzinfo=timezone(timedelta(hours=9)))
        chat = self.Chat(user_id=user.id, question="Q", answer="A", created_at=local_time)
        self.session.add(chat)
        self.session.commit()
        self.assertEqual(chat.created_at, local_time.astimezone(timezone.utc))
        self.assertEqual(chat.created_at.tzinfo, timezone.utc)

    def test_naive_timestamp_is_rejected(self):
        self.session.add(self.User(username="alice", password_hash="hash", created_at=datetime(2026, 1, 1)))
        with self.assertRaisesRegex(StatementError, "timezone-aware"):
            self.session.commit()

    def test_history_index_supports_user_and_order(self):
        indexes = inspect(self.engine).get_indexes("chats")
        self.assertIn(["user_id", "created_at", "id"], [index["column_names"] for index in indexes])

    def test_application_lifespan_creates_tables_and_preserves_health(self):
        from app import main

        async def run_lifespan():
            with patch.object(database, "engine", self.engine):
                with patch.object(database, "initialize_database", wraps=database.initialize_database) as initialize:
                    with patch.object(self.engine, "dispose", wraps=self.engine.dispose) as dispose:
                        async with main.app.router.lifespan_context(main.app):
                            initialize.assert_called_once_with(self.engine)
                            self.assertEqual(main.health(), {"status": "ok"})
                        dispose.assert_called_once_with()

        asyncio.run(run_lifespan())


if __name__ == "__main__":
    unittest.main()
