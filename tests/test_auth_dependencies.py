import base64
import json
import logging
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import database
from app.database import build_engine, get_db, initialize_database
from app.dependencies import get_current_user
from app.models import User
from app.routers import auth as auth_router
from app.schemas.auth import AuthUserResponse
from app.services.auth import hash_password


class CurrentUserDependencyTests(unittest.TestCase):
    username = "dependency_user"
    password = "dependency-test-password"
    other_username = "other_user"
    other_password = "other-dependency-password"
    secret_key = "dependency-test-secret-key"
    request_id = "dependency-test-request"

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)
        cls.other_hash = hash_password(cls.other_password)

    def setUp(self):
        # 운영 데이터와 분리된 임시 DB 및 실제 해시
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'dependencies.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        with Session(self.engine, expire_on_commit=False) as db:
            user = User(username=self.username, password_hash=self.password_hash)
            other = User(username=self.other_username, password_hash=self.other_hash)
            db.add_all([user, other])
            db.commit()
            self.user_id = user.id
            self.other_id = other.id
        self.initial_users = self.snapshot()
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.handled_user_ids = []
        self.app = self.make_app(self.secret_key)
        self.client = self.enterContext(TestClient(self.app))

    def make_app(self, secret_key):
        # 운영 서버의 세션 옵션을 테스트 앱에 재사용
        environment = {
            "SECRET_KEY": secret_key,
            "SESSION_HTTPS_ONLY": "false",
            "DATABASE_URL": "sqlite:///:memory:",
        }
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(database, "engine", self.engine):
                server = runpy.run_path(str(main_path), run_name="dependency_test_server")
        middleware = next(
            item for item in server["app"].user_middleware if item.cls is SessionMiddleware
        )
        app = FastAPI()
        app.add_middleware(middleware.cls, *middleware.args, **middleware.kwargs)

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)

        @app.middleware("http")
        async def set_request_id(request: Request, call_next):
            request.state.request_id = self.request_id
            return await call_next(request)

        # 세션 준비·조회 및 보호 경로는 테스트 앱에서만 제공
        @app.post("/test-session")
        def set_session(payload: dict, request: Request):
            request.session.clear()
            request.session.update(payload)
            return dict(request.session)

        @app.get("/test-session")
        def read_session(request: Request):
            return dict(request.session)

        @app.get("/test-current-user", response_model=AuthUserResponse)
        @app.post("/test-current-user", response_model=AuthUserResponse)
        def protected(user: User = Depends(get_current_user)) -> AuthUserResponse:
            self.handled_user_ids.append(user.id)
            return AuthUserResponse(id=user.id, username=user.username)

        app.include_router(auth_router.router)
        return app

    def snapshot(self):
        with Session(self.engine) as db:
            return [
                (user.id, user.username, user.password_hash, user.created_at)
                for user in db.scalars(select(User).order_by(User.id))
            ]

    def request(self, session):
        return Request({
            "type": "http",
            "session": session,
            "state": {"request_id": self.request_id},
            "headers": [],
        })

    def login(self, client=None, username=None, password=None):
        client = self.client if client is None else client
        response = client.post(
            "/api/auth/login",
            json={
                "username": self.username if username is None else username,
                "password": self.password if password is None else password,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response

    def assert_unauthenticated(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Not authenticated"})
        self.assertEqual(self.handled_user_ids, [])
        for sensitive in (self.password, self.password_hash, self.secret_key):
            self.assertNotIn(sensitive, response.text)

    def test_valid_session_returns_attached_database_user_without_changes(self):
        """실제 ORM 사용자 반환 및 DB·세션·트랜잭션 유지"""
        session = {"user_id": self.user_id, "marker": "keep-on-read"}
        request = self.request(session)
        with patch.object(self.db, "commit", side_effect=AssertionError("Unexpected commit")):
            with patch.object(self.db, "rollback", side_effect=AssertionError("Unexpected rollback")):
                with self.assertNoLogs("app.dependencies", level=logging.DEBUG):
                    user = get_current_user(request, self.db)

        self.assertIsInstance(user, User)
        self.assertEqual(user.id, self.user_id)
        self.assertEqual(user.username, self.username)
        self.assertEqual(user.password_hash, self.password_hash)
        self.assertIs(inspect(user).session, self.db)
        self.assertEqual(request.session, {"user_id": self.user_id, "marker": "keep-on-read"})
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_missing_id_and_invalid_types_are_rejected_before_lookup(self):
        """세션 ID 누락·문자열·bool·float·null·컨테이너 거부"""
        sessions = [{}, {"username": self.username}]
        sessions.extend({"user_id": value} for value in (
            None, str(self.user_id), True, False, float(self.user_id), 1.5,
            [self.user_id], {"id": self.user_id},
        ))
        with patch.object(self.db, "get", side_effect=AssertionError("Unexpected lookup")):
            for index, session in enumerate(sessions):
                with self.subTest(case=index):
                    with self.assertRaises(HTTPException) as raised:
                        get_current_user(self.request(session), self.db)
                    self.assertEqual(raised.exception.status_code, 401)
                    self.assertEqual(raised.exception.detail, "Not authenticated")

    def test_invalid_session_container_is_rejected(self):
        """딕셔너리가 아닌 세션의 인증 실패"""
        with patch.object(self.db, "get", side_effect=AssertionError("Unexpected lookup")):
            for index, session in enumerate((None, [], [self.user_id], "invalid-session", True)):
                with self.subTest(case=index):
                    with self.assertRaises(HTTPException) as raised:
                        get_current_user(self.request(session), self.db)
                    self.assertEqual(raised.exception.status_code, 401)

    def test_login_cookie_identifies_current_user(self):
        """실제 로그인 쿠키로 후속 보호 요청 인증"""
        self.login()
        response = self.client.get("/test-current-user")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        self.assertEqual(self.handled_user_ids, [self.user_id])
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_missing_cookie_does_not_allow_protected_handler(self):
        """쿠키 없는 요청의 401 및 보호 함수 미실행"""
        response = self.client.get("/test-current-user")
        self.assert_unauthenticated(response)

    def test_signed_invalid_user_id_types_return_401_without_lookup(self):
        """서명된 쿠키의 잘못된 ID 타입도 조회 전 거부"""
        for index, value in enumerate((None, str(self.user_id), True, False, 1.0, [], {})):
            with self.subTest(case=index):
                self.client.post("/test-session", json={"user_id": value})
                with patch.object(Session, "get", side_effect=AssertionError("Unexpected lookup")):
                    response = self.client.get("/test-current-user")
                self.assert_unauthenticated(response)

    def test_nonexistent_database_user_returns_401(self):
        """유효한 정수 ID라도 DB 사용자가 없으면 인증 실패"""
        self.client.post("/test-session", json={"user_id": self.other_id + 1000})
        self.assert_unauthenticated(self.client.get("/test-current-user"))

    def test_deleted_user_is_rejected_on_next_request(self):
        """로그인 이후 삭제된 DB 사용자의 쿠키 거부"""
        self.login()
        with Session(self.engine) as db:
            db.delete(db.get(User, self.user_id))
            db.commit()
        self.assert_unauthenticated(self.client.get("/test-current-user"))

    def test_tampered_cookie_cannot_choose_another_user(self):
        """쿠키 사용자 ID 변조 시 서명 검증 실패와 401"""
        self.login()
        cookie = self.client.cookies.get("session")
        payload, signature = cookie.split(".", 1)
        data = json.loads(base64.b64decode(payload))
        data["user_id"] = self.other_id
        changed = base64.b64encode(json.dumps(data).encode()).decode()
        self.client.cookies.clear()
        response = self.client.get(
            "/test-current-user", headers={"Cookie": f"session={changed}.{signature}"}
        )
        self.assert_unauthenticated(response)

    def test_cookie_signed_with_other_key_returns_401(self):
        """다른 서버 키로 서명된 쿠키의 인증 실패"""
        self.login()
        other = self.enterContext(TestClient(self.make_app("other-dependency-test-key")))
        response = other.get(
            "/test-current-user", headers={"Cookie": f"session={self.client.cookies.get('session')}"}
        )
        self.assert_unauthenticated(response)

    def test_expired_cookie_returns_401(self):
        """쿠키 유지 기간 만료 후 보호 요청 거부"""
        timestamp = 1_700_000_000
        with patch.object(TimestampSigner, "get_timestamp", return_value=timestamp):
            self.login()
        with patch.object(
            TimestampSigner, "get_timestamp", return_value=timestamp + 14 * 24 * 60 * 60 + 1
        ):
            response = self.client.get("/test-current-user")
        self.assert_unauthenticated(response)

    def test_body_query_and_header_ids_cannot_authenticate_without_cookie(self):
        """임의 본문·쿼리·헤더 ID로 인증을 대신하지 못함"""
        response = self.client.post(
            f"/test-current-user?user_id={self.user_id}",
            json={"user_id": self.user_id},
            headers={"X-User-ID": str(self.user_id)},
        )
        self.assert_unauthenticated(response)

    def test_body_query_and_header_ids_do_not_override_cookie_user(self):
        """외부 ID 전달에도 세션 쿠키의 본인 사용자 반환"""
        self.login()
        response = self.client.post(
            f"/test-current-user?user_id={self.other_id}",
            json={"user_id": self.other_id},
            headers={"X-User-ID": str(self.other_id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        self.assertEqual(self.handled_user_ids, [self.user_id])

    def test_clients_receive_only_their_session_user(self):
        """각 클라이언트 쿠키에 해당하는 DB 사용자 식별"""
        other = self.enterContext(TestClient(self.app))
        self.login()
        self.login(other, self.other_username, self.other_password)
        own_response = self.client.get("/test-current-user")
        other_response = other.get("/test-current-user")
        self.assertEqual(own_response.json(), {"id": self.user_id, "username": self.username})
        self.assertEqual(other_response.json(), {"id": self.other_id, "username": self.other_username})

    def test_database_error_returns_safe_500_and_recovers(self):
        """현재 사용자 조회 장애의 안전한 500·rollback·복구"""
        self.login()
        previous = self.client.get("/test-session").json()

        def fail_lookup(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                raise OperationalError(
                    "sensitive-sql",
                    {"password": self.password, "password_hash": self.password_hash},
                    Exception("private-db-error"),
                )

        original_rollback = Session.rollback
        event.listen(self.engine, "before_cursor_execute", fail_lookup)
        try:
            with self.assertLogs("app.dependencies", level=logging.ERROR) as captured:
                with patch.object(
                    Session, "rollback", autospec=True, side_effect=original_rollback
                ) as rollback:
                    response = self.client.get("/test-current-user")
                    rollback.assert_called_once()
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_lookup)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to retrieve user"})
        self.assertEqual(self.handled_user_ids, [])
        self.assertEqual(
            captured.records[0].getMessage(),
            f"auth_lookup_failure request_id={self.request_id} reason=db_error",
        )
        output = response.text + "\n".join(captured.output)
        for sensitive in (
            self.password, self.password_hash, self.secret_key, "sensitive-sql", "private-db-error"
        ):
            self.assertNotIn(sensitive, output)
        self.assertIsNone(captured.records[0].exc_info)
        self.assertEqual(self.client.get("/test-session").json(), previous)
        self.assertEqual(self.snapshot(), self.initial_users)
        self.assertEqual(self.client.get("/test-current-user").status_code, 200)


if __name__ == "__main__":
    unittest.main()
