import base64
import json
import logging
import os
import runpy
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import database
from app.database import build_engine, get_db, initialize_database
from app.models import User
from app.routers import auth as auth_router
from app.services.auth import hash_password


class CurrentUserRouteTests(unittest.TestCase):
    username = "current_user"
    password = "current-user-test-password"
    other_username = "other_user"
    other_password = "other-current-test-password"
    secret_key = "current-user-route-test-secret"
    request_id = "current-user-test-request"

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)
        cls.other_hash = hash_password(cls.other_password)

    def setUp(self):
        # 실제 사용자·운영 DB와 분리된 테스트 데이터
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'current-user.db'}")
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
        self.app = self.make_app()
        self.client = self.enterContext(TestClient(self.app))

    def make_app(self, https_only=False):
        # 운영 서버의 세션 설정을 테스트 앱에 재사용
        environment = {
            "SECRET_KEY": self.secret_key,
            "SESSION_HTTPS_ONLY": str(https_only).lower(),
            "DATABASE_URL": "sqlite:///:memory:",
        }
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(database, "engine", self.engine):
                server = runpy.run_path(str(main_path), run_name="current_user_test_server")
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

        # 추가 세션 항목 준비·조회는 테스트 앱에서만 제공
        @app.post("/test-session")
        def set_session(payload: dict, request: Request):
            request.session.clear()
            request.session.update(payload)
            return dict(request.session)

        @app.get("/test-session")
        def read_session(request: Request):
            return dict(request.session)

        app.include_router(auth_router.router)
        return app

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

    def snapshot(self):
        with Session(self.engine) as db:
            return [
                (user.id, user.username, user.password_hash, user.created_at)
                for user in db.scalars(select(User).order_by(User.id))
            ]

    def cookie(self, response):
        cookies = SimpleCookie()
        cookies.load(response.headers["set-cookie"])
        return cookies["session"]

    def assert_unauthenticated(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Not authenticated"})

    def test_me_without_login_returns_401_and_no_session(self):
        """비로그인 현재 사용자 조회의 401 응답"""
        response = self.client.get("/api/auth/me")
        self.assert_unauthenticated(response)
        self.assertNotIn("session", self.client.cookies)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_me_returns_only_authenticated_user_identity(self):
        """로그인 후 현재 사용자의 공개 식별 정보만 반환"""
        self.login()
        with self.assertNoLogs("app.dependencies", level=logging.DEBUG):
            response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        for sensitive in (self.password, self.password_hash, self.secret_key):
            self.assertNotIn(sensitive, response.text)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_logout_removes_cookie_and_next_me_returns_401(self):
        """로그아웃 200·쿠키 만료 및 후속 현재 사용자 조회 차단"""
        self.login()
        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "logged out"})
        self.assertEqual(self.cookie(response)["expires"], "Thu, 01 Jan 1970 00:00:00 GMT")
        self.assertNotIn("session", self.client.cookies)
        self.assert_unauthenticated(self.client.get("/api/auth/me"))
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_anonymous_and_repeated_logout_return_200_without_lookup(self):
        """비로그인·반복 로그아웃의 200 응답 및 DB 조회 없음"""
        with patch.object(Session, "get", side_effect=AssertionError("Unexpected lookup")):
            for index in range(2):
                with self.subTest(case=index):
                    response = self.client.post("/api/auth/logout")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"message": "logged out"})
                    self.assertNotIn("session", self.client.cookies)

    def test_logout_allows_invalid_session_ids_without_authentication(self):
        """무효 사용자 ID의 세션도 인증 없이 로그아웃 가능"""
        for index, value in enumerate((True, str(self.user_id), None, self.other_id + 1000)):
            with self.subTest(case=index):
                self.client.post("/test-session", json={"user_id": value})
                self.assert_unauthenticated(self.client.get("/api/auth/me"))
                with patch.object(Session, "get", side_effect=AssertionError("Unexpected lookup")):
                    response = self.client.post("/api/auth/logout")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"message": "logged out"})
                self.assertNotIn("session", self.client.cookies)

    def test_me_rejects_deleted_user(self):
        """로그인 이후 삭제된 사용자의 현재 정보 조회 거부"""
        self.login()
        with Session(self.engine) as db:
            db.delete(db.get(User, self.user_id))
            db.commit()
        self.assert_unauthenticated(self.client.get("/api/auth/me"))

    def test_me_uses_cookie_user_and_ignores_supplied_ids(self):
        """본문·쿼리·헤더 ID보다 세션의 현재 사용자 사용"""
        self.login()
        response = self.client.request(
            "GET",
            f"/api/auth/me?user_id={self.other_id}",
            json={"user_id": self.other_id},
            headers={"X-User-ID": str(self.other_id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})

    def test_logout_does_not_affect_other_client(self):
        """클라이언트별 현재 사용자 분리 및 독립 로그아웃"""
        other = self.enterContext(TestClient(self.app))
        self.login()
        self.login(other, self.other_username, self.other_password)
        self.assertEqual(self.client.get("/api/auth/me").json()["id"], self.user_id)
        self.assertEqual(other.get("/api/auth/me").json()["id"], self.other_id)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assert_unauthenticated(self.client.get("/api/auth/me"))
        self.assertEqual(
            other.get("/api/auth/me").json(),
            {"id": self.other_id, "username": self.other_username},
        )

    def test_me_preserves_existing_session_items(self):
        """현재 사용자 조회의 기존 세션 내용 보존"""
        session = {"user_id": self.user_id, "marker": "keep-on-read"}
        self.client.post("/test-session", json=session)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.get("/test-session").json(), session)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_me_database_failure_is_safe_and_retry_recovers(self):
        """현재 사용자 조회 장애의 안전한 500 및 재요청 복구"""
        self.login()

        def fail_lookup(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                raise OperationalError(
                    "sensitive-sql",
                    {"password": self.password, "password_hash": self.password_hash},
                    Exception("private-db-error"),
                )

        event.listen(self.engine, "before_cursor_execute", fail_lookup)
        try:
            with self.assertLogs("app.dependencies", level=logging.ERROR) as captured:
                response = self.client.get("/api/auth/me")
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_lookup)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to retrieve user"})
        output = response.text + "\n".join(captured.output)
        for sensitive in (
            self.password, self.password_hash, self.secret_key, "sensitive-sql", "private-db-error"
        ):
            self.assertNotIn(sensitive, output)
        self.assertEqual(
            captured.records[0].getMessage(),
            f"auth_lookup_failure request_id={self.request_id} reason=db_error",
        )
        self.assertIsNone(captured.records[0].exc_info)
        self.assertEqual(self.client.get("/test-session").json(), {"user_id": self.user_id})
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_https_logout_expires_cookie_and_blocks_me(self):
        """HTTPS 쿠키 로그아웃 및 현재 사용자 조회 차단"""
        client = self.enterContext(TestClient(self.make_app(True), base_url="https://testserver"))
        self.login(client)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)
        response = client.post("/api/auth/logout")
        self.assertTrue(self.cookie(response)["secure"])
        self.assertNotIn("session", client.cookies)
        self.assert_unauthenticated(client.get("/api/auth/me"))

    def test_me_rejects_tampered_cookie(self):
        """현재 사용자 조회에 전달된 변조 쿠키 거부"""
        self.login()
        payload, signature = self.client.cookies.get("session").split(".", 1)
        session = json.loads(base64.b64decode(payload))
        session["user_id"] = self.other_id
        changed = base64.b64encode(json.dumps(session).encode()).decode()
        self.client.cookies.clear()
        response = self.client.get(
            "/api/auth/me", headers={"Cookie": f"session={changed}.{signature}"}
        )
        self.assert_unauthenticated(response)


if __name__ == "__main__":
    unittest.main()
