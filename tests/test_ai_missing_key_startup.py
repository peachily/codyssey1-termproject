"""Verify env-file loading and server startup in a fresh process, without AI traffic."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest


class MissingKeyStartupTests(unittest.TestCase):
    def test_env_file_without_ai_key_starts_and_returns_safe_502(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / '.env'
            env_file.write_text(
                f'SECRET_KEY={secrets.token_urlsafe(32)}\n'
                f'DATABASE_URL=sqlite:///{root / "test.db"}\n'
                'SESSION_HTTPS_ONLY=false\n'
                'AI_API_URL=https://example.invalid/chat\n'
                'AI_MODEL=test-model\nAI_TIMEOUT=1\n', encoding='utf-8',
            )
            environment = {key: value for key, value in os.environ.items()
                           if key not in {'SECRET_KEY', 'DATABASE_URL', 'SESSION_HTTPS_ONLY',
                                          'CODYSSEY_API_KEY', 'AI_API_URL', 'AI_MODEL', 'AI_TIMEOUT'}}
            source = r'''
import io, logging, os, sys
from unittest.mock import patch
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import func, select
# The same --env-file loading path used by the documented Uvicorn command.
uvicorn.Config('app.main:app', env_file=sys.argv[1], log_config=None)
from app.main import app
from app.database import SessionLocal
from app.models import Chat
from app.config import get_ai_settings
assert get_ai_settings().api_key == ''
assert get_ai_settings().timeout == 1
assert get_ai_settings().model == 'test-model'
logs = io.StringIO()
handler = logging.StreamHandler(logs)
logging.getLogger('app').addHandler(handler)
logging.getLogger('app').setLevel(logging.INFO)
with patch('app.services.ai.requests.post') as transport, TestClient(app) as client:
    assert client.get('/health').json() == {'status': 'ok'}
    credentials = {'username': 'missing_key_user', 'password': 'missing-key-test-password'}
    assert client.post('/api/auth/signup', json=credentials).status_code == 201
    assert client.post('/api/auth/login', json=credentials).status_code == 200
    logs.truncate(0)
    logs.seek(0)
    result = client.post('/api/chat', json={'message': '키 없는 상태의 질문'})
    assert result.status_code == 502
    assert result.json() == {'detail': 'AI request failed'}
    transport.assert_not_called()
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/api/auth/me').status_code == 200
    assert client.get('/api/me/chats').json() == {'chats': []}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Chat)) == 0
    assert 'ai_call_failure' in logs.getvalue()
    assert 'reason=missing_api_key' in logs.getvalue()
    assert 'request_id=' in logs.getvalue()
    assert 'user_id=' in logs.getvalue()
    assert 'db_save_success' not in logs.getvalue()
    for private in (os.environ['SECRET_KEY'], credentials['password'], '키 없는 상태의 질문'):
        assert private not in result.text + logs.getvalue()
    assert 'missing_api_key' not in result.text
print('missing-key startup, HTTP 502, no AI transport, no saved chat, server healthy: OK')
'''
            result = subprocess.run(
                [sys.executable, '-c', source, str(env_file)],
                cwd=Path(__file__).parents[1], env=environment,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('server healthy: OK', result.stdout)
