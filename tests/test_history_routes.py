import os
import runpy
import secrets
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import database
from app.database import build_engine, get_db
from app.models import Chat
from app.routers import chat, history
from app.services.chats import get_recent_chats


class HistoryTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.engine = build_engine(f"sqlite:///{root / 'history.db'}")
        self.addCleanup(self.engine.dispose)
        with patch.dict(os.environ, {"SECRET_KEY": secrets.token_urlsafe(32), "SESSION_HTTPS_ONLY": "false"}):
            with patch.object(database, "engine", self.engine):
                self.app = runpy.run_path(str(Path(__file__).parents[1] / 'app/main.py'))['app']
        def db_session():
            with Session(self.engine, expire_on_commit=False) as session:
                yield session
        self.app.dependency_overrides[get_db] = db_session
        self.client = self.enterContext(TestClient(self.app))
        self.other = self.enterContext(TestClient(self.app))
        for client, name in ((self.client, 'history_a'), (self.other, 'history_b')):
            payload = {'username': name, 'password': 'history-test-password'}
            self.assertEqual(client.post('/api/auth/signup', json=payload).status_code, 201)
            response = client.post('/api/auth/login', json=payload)
            self.assertEqual(response.status_code, 200)
        self.user_id = self.client.get('/api/auth/me').json()['id']
        self.other_id = self.other.get('/api/auth/me').json()['id']

    def seed(self, user_id, instant, question='질문', answer='답변'):
        with Session(self.engine, expire_on_commit=False) as db:
            row = Chat(user_id=user_id, question=question, answer=answer,
                       created_at=datetime.fromisoformat(instant))
            db.add(row)
            db.commit()
            return row.id

    def test_anonymous_and_logged_out_are_rejected(self):
        with TestClient(self.app) as anonymous:
            self.assertEqual(anonymous.get('/api/me/chats?user_id=1').status_code, 401)
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/me/chats').status_code, 401)

    def test_empty_history(self):
        self.assertEqual(self.client.get('/api/me/chats').json(), {'chats': []})

    def test_own_records_only_and_supplied_id_is_ignored(self):
        mine = self.seed(self.user_id, '2026-10-01T00:00:00+00:00')
        theirs = self.seed(self.other_id, '2026-10-01T00:00:00+00:00', '다른 사용자')
        self.assertEqual([r['id'] for r in self.client.get(f'/api/me/chats?user_id={self.other_id}').json()['chats']], [mine])
        self.assertEqual([r['id'] for r in self.other.get('/api/me/chats').json()['chats']], [theirs])

    def test_latest_first_including_id_ties_and_more_than_five(self):
        ids = [self.seed(self.user_id, '2026-10-01T00:00:00+00:00', str(i)) for i in range(7)]
        response = self.client.get('/api/me/chats')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['id'] for r in response.json()['chats']], list(reversed(ids)))
        with Session(self.engine) as db:
            self.assertEqual([r.id for r in get_recent_chats(db, self.user_id)], ids[-5:])

    def test_fields_utc_and_korean_year_boundary(self):
        self.seed(self.user_id, '2026-12-31T15:00:00+00:00')
        row = self.client.get('/api/me/chats').json()['chats'][0]
        self.assertEqual(set(row), {'id', 'question', 'answer', 'created_at'})
        self.assertEqual((row['question'], row['answer']), ('질문', '답변'))
        self.assertTrue(row['created_at'].endswith('Z'))
        instant = datetime.fromisoformat(row['created_at'])
        self.assertEqual(instant.tzinfo, timezone.utc)
        self.assertEqual(str(instant.astimezone(ZoneInfo('Asia/Seoul')).date()), '2027-01-01')

    def test_read_failure_is_safe_and_recovers(self):
        with patch.object(history, 'list_user_chats', side_effect=OperationalError('private-sql', {}, Exception('private-detail'))):
            with self.assertLogs('app.routers.history', level='ERROR') as logs:
                response = self.client.get('/api/me/chats')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'detail': 'Failed to retrieve chats'})
        self.assertNotIn('private-', response.text + str(logs.output))
        self.assertEqual(self.client.get('/api/me/chats').status_code, 200)

    def test_chat_context_prescription_and_relogin_keep_history(self):
        with patch.object(chat, 'request_chat_completion', return_value='첫 답변') as ai:
            self.assertEqual(self.client.post('/api/chat', json={'message': '첫 질문'}).status_code, 200)
            self.assertEqual(self.client.post('/api/chat', json={'message': '둘째 질문'}).status_code, 200)
            self.assertEqual([m['content'] for m in ai.call_args.args[0][1:]], ['첫 질문', '첫 답변', '둘째 질문'])
            before = self.client.get('/api/me/chats').json()
            with patch.object(chat, 'request_prescription', return_value={'keyword': 'STRESS', 'color': 'GREEN', 'message': '쉬어가요'}):
                self.assertEqual(self.client.post('/api/prescription').status_code, 200)
            self.assertEqual(self.client.get('/api/me/chats').json(), before)
            self.assertEqual(self.client.post('/api/chat', json={'message': '처방 후 질문'}).status_code, 200)
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/me/chats').status_code, 401)
        self.client.post('/api/auth/login', json={'username': 'history_a', 'password': 'history-test-password'})
        self.assertEqual(len(self.client.get('/api/me/chats').json()['chats']), 3)
