import logging
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import build_engine, initialize_database
from app.models import Chat, User
from app.services.chats import ChatSaveError, get_recent_chats, list_user_chats, save_chat


class ChatServiceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.url = f"sqlite:///{Path(directory.name) / 'chats.db'}"
        self.engine = build_engine(self.url)
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.add_all([User(id=1, username='alice', password_hash='hash'), User(id=2, username='bob', password_hash='hash')])
        self.db.commit()

    def seed(self, count, user_id=1):
        for number in range(count):
            self.db.add(Chat(user_id=user_id, question=str(number), answer='A', created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=number // 2)))
        self.db.commit()

    def test_recent_boundaries_and_user_isolation(self):
        self.seed(7, user_id=2)
        for count in (0, 1, 5, 6, 10):
            with self.subTest(count=count):
                self.db.query(Chat).filter(Chat.user_id == 1).delete()
                self.db.commit()
                self.seed(count)
                recent = get_recent_chats(self.db, 1)
                self.assertEqual([chat.question for chat in recent], [str(i) for i in range(max(0, count - 5), count)])
                self.assertTrue(all(chat.user_id == 1 for chat in recent))

    def test_history_is_latest_first_with_id_tiebreaker(self):
        self.seed(7)
        self.seed(2, user_id=2)
        self.assertEqual([chat.question for chat in list_user_chats(self.db, 1)], list(map(str, reversed(range(7)))))
        self.assertEqual(list_user_chats(self.db, 999), [])

    def test_queries_and_serialization_need_one_select_each(self):
        self.seed(20)
        self.db.expunge_all()
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                statements.append(statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        self.addCleanup(event.remove, self.engine, 'before_cursor_execute', capture)
        for query in (list_user_chats, get_recent_chats):
            statements.clear()
            rows = query(self.db, 1)
            values = [(row.id, row.question, row.answer, row.created_at, row.user_id) for row in rows]
            self.assertTrue(values)
            self.assertEqual(len(statements), 1)

    def test_index_serves_filter_and_order_without_temp_sort(self):
        self.seed(20)
        for suffix in ('', ' LIMIT 5'):
            plan = self.db.execute(text('EXPLAIN QUERY PLAN SELECT * FROM chats WHERE user_id = 1 ORDER BY created_at DESC, id DESC' + suffix)).all()
            detail = ' '.join(row[3] for row in plan)
            self.assertIn('ix_chats_user_created_id', detail)
            self.assertNotIn('TEMP B-TREE', detail)

    def test_save_commits_and_persists_without_sensitive_log_content(self):
        with self.assertLogs('app.services.chats', level=logging.INFO) as captured:
            chat = save_chat(self.db, 1, 'private-question', 'private-answer')
        self.assertEqual(chat.user_id, 1)
        self.assertEqual(chat.created_at.utcoffset(), timedelta(0))
        self.assertIn('db_save_success', captured.output[0])
        self.assertNotIn('private', str(captured.output))
        self.db.close()
        self.engine.dispose()
        reopened = build_engine(self.url)
        try:
            with Session(reopened) as session:
                persisted = session.get(Chat, chat.id)
                self.assertEqual(persisted.question, 'private-question')
                self.assertEqual(persisted.answer, 'private-answer')
        finally:
            reopened.dispose()

    def test_failed_commit_rolls_back_and_session_can_be_reused(self):
        def fail_commit(connection):
            raise OperationalError('sensitive-sql', {}, Exception('secret'))
        event.listen(self.engine, 'commit', fail_commit)
        try:
            with self.assertLogs('app.services.chats', level=logging.INFO) as captured:
                with self.assertRaisesRegex(ChatSaveError, '^Failed to save chat$'):
                    save_chat(self.db, 1, 'private-question', 'private-answer')
        finally:
            event.remove(self.engine, 'commit', fail_commit)
        self.assertIn('db_save_failure', str(captured.output))
        self.assertNotIn('db_save_success', str(captured.output))
        self.assertNotIn('secret', str(captured.output))
        self.assertNotIn('private', str(captured.output))
        self.assertEqual(self.db.scalars(select(Chat)).all(), [])
        save_chat(self.db, 1, 'retry', 'ok')
        self.assertEqual(len(list_user_chats(self.db, 1)), 1)


if __name__ == '__main__':
    unittest.main()
