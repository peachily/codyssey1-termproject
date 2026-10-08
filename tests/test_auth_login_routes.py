import logging
import os
import runpy
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import database
from app.database import build_engine, get_db, initialize_database
from app.models import User
from app.routers import auth as auth_router
from app.services.auth import UserLookupError, hash_password


class LoginRouteTests(unittest.TestCase):
    username = "login_user"
    password = "login-route-test-password"
    other_username = "other_user"
    other_password = "another-login-route-password"
    secret_key = "login-route-test-secret-key"

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)
        cls.other_hash = hash_password(cls.other_password)

    def setUp(self):
        # 실제 서버·사용자 정보와 분리된 임시 DB
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'login-routes.db'}")
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

    def make_app(self, https_only=False, with_frontend=None):
        # 테스트 환경에서 실제 서버의 라우터·세션 설정 재사용
        environment = {
            "SECRET_KEY": self.secret_key,
            "SESSION_HTTPS_ONLY": str(https_only).lower(),
            "DATABASE_URL": "sqlite:///:memory:",
        }
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        if with_frontend is not None:
            root = Path(self.enterContext(tempfile.TemporaryDirectory()))
            isolated_main = root / "app" / "main.py"
            isolated_main.parent.mkdir()
            isolated_main.write_text(main_path.read_text(), encoding="utf-8")
            main_path = isolated_main
            if with_frontend:
                dist = root / "frontend" / "dist"
                dist.mkdir(parents=True)
                (dist / "index.html").write_text("<html>test frontend</html>")
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(database, "engine", self.engine):
                server = runpy.run_path(str(main_path), run_name="login_routes_test_server")
        app = server["app"]

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)

        # 세션 준비·조회는 테스트 앱에서만 제공
        test_routes = APIRouter()

        @test_routes.post("/test-session")
        def set_session(payload: dict, request: Request):
            request.session.clear()
            request.session.update(payload)
            return dict(request.session)

        @test_routes.get("/test-session")
        def read_session(request: Request):
            return dict(request.session)

        # Test-only helpers must precede the catch-all frontend mount.
        app.router.routes[0:0] = test_routes.routes
        return app

    def test_session_flow_with_and_without_frontend_build(self):
        for with_frontend in (False, True):
            with self.subTest(with_frontend=with_frontend):
                app = self.make_app(with_frontend=with_frontend)
                with TestClient(app) as client:
                    client.post("/test-session", json={"user_id": self.other_id, "old": True})
                    self.assertEqual(client.post("/api/auth/login", json=self.payload()).status_code, 200)
                    self.assertEqual(self.session(client), {"user_id": self.user_id})
                    self.assertEqual(client.get("/api/auth/me").json()["id"], self.user_id)
                    self.assertEqual(client.post("/api/auth/logout").status_code, 200)
                    self.assertEqual(self.session(client), {})
                    self.assertEqual(client.get("/api/auth/me").status_code, 401)
                    if with_frontend:
                        self.assertIn("test frontend", client.get("/").text)

    def payload(self, **overrides):
        return {"username": self.username, "password": self.password, **overrides}

    def login(self, **overrides):
        return self.client.post("/api/auth/login", json=self.payload(**overrides))

    def snapshot(self):
        with Session(self.engine) as db:
            return [
                (user.id, user.username, user.password_hash, user.created_at)
                for user in db.scalars(select(User).order_by(User.id))
            ]

    def session(self, client=None):
        client = self.client if client is None else client
        return client.get("/test-session").json()

    def cookie(self, response):
        cookies = SimpleCookie()
        cookies.load(response.headers["set-cookie"])
        return cookies["session"]

    def assert_bad_request(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid username or password"})
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_login_returns_only_identity_and_sets_integer_session_id(self):
        """실제 서버 로그인 200·사용자 응답·세션 쿠키 확인"""
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        self.assertEqual(self.session(), {"user_id": self.user_id})
        self.assertIs(type(self.session()["user_id"]), int)
        self.assertIn("session", self.client.cookies)
        for sensitive in (self.password, self.password_hash, self.secret_key):
            self.assertNotIn(sensitive, response.text)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_username_trim_and_password_whitespace_are_preserved(self):
        """로그인 API의 사용자명 trim 및 비밀번호 공백 보존"""
        password = f"  {self.password}  "
        with Session(self.engine) as db:
            db.get(User, self.user_id).password_hash = hash_password(password)
            db.commit()
        before = self.snapshot()
        response = self.login(username=f"  {self.username}  ", password=password)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], self.username)
        stripped = self.login(password=password.strip())
        self.assertEqual(stripped.status_code, 401)
        self.assertEqual(self.session(), {"user_id": self.user_id})
        self.assertEqual(self.snapshot(), before)

    def test_missing_user_and_wrong_password_have_same_401_response(self):
        """사용자 없음·잘못된 비밀번호의 동일한 401 응답"""
        responses = [
            self.login(username="missing_user"),
            self.login(password="wrong-test-password"),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid username or password"})
            self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(self.session(), {})
        self.assertNotIn("session", self.client.cookies)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_invalid_stored_hash_returns_401_without_session(self):
        """잘못된 저장 해시의 401 응답 및 세션 미생성"""
        with Session(self.engine) as db:
            db.get(User, self.user_id).password_hash = "not-a-hash"
            db.commit()
        before = self.snapshot()
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Invalid username or password"})
        self.assertEqual(self.session(), {})
        self.assertEqual(self.snapshot(), before)

    def test_required_fields_return_400_without_authentication(self):
        """필수 필드 누락의 400 응답 및 인증 서비스 미호출"""
        with patch.object(auth_router, "authenticate_user") as authenticate_user:
            for field in ("username", "password"):
                with self.subTest(field=field):
                    payload = self.payload()
                    del payload[field]
                    self.assert_bad_request(self.client.post("/api/auth/login", json=payload))
            authenticate_user.assert_not_called()

    def test_invalid_types_and_blank_values_return_400(self):
        """문자열 외 타입·빈 값·공백 입력의 400 응답"""
        values = (None, 123, True, [], {}, "", " " * 8, "\t" * 8, "\u3000" * 8)
        with patch.object(auth_router, "authenticate_user") as authenticate_user:
            for field in ("username", "password"):
                for index, value in enumerate(values):
                    with self.subTest(field=field, case=index):
                        self.assert_bad_request(self.login(**{field: value}))
            authenticate_user.assert_not_called()

    def test_invalid_lengths_and_username_characters_return_400(self):
        """길이 경계 및 사용자명 허용 문자 검증"""
        values = {
            "username": ("ab", "u" * 31, "  ab  ", "Login_user", "한글사용자", "user-name"),
            "password": ("p" * 7, "p" * 129),
        }
        with patch.object(auth_router, "authenticate_user") as authenticate_user:
            for field, invalid in values.items():
                for index, value in enumerate(invalid):
                    with self.subTest(field=field, case=index):
                        self.assert_bad_request(self.login(**{field: value}))
            authenticate_user.assert_not_called()

    def test_valid_length_boundaries_authenticate(self):
        """사용자명 3·30자 및 비밀번호 8·128자 로그인 확인"""
        for username, password in (("u_1", "p" * 8), ("u" * 30, "p" * 128)):
            with self.subTest(username_length=len(username), password_length=len(password)):
                with Session(self.engine, expire_on_commit=False) as db:
                    user = User(username=username, password_hash=hash_password(password))
                    db.add(user)
                    db.commit()
                    user_id = user.id
                response = self.login(username=f"  {username}  ", password=password)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"id": user_id, "username": username})
                self.assertEqual(self.session(), {"user_id": user_id})

    def test_missing_or_non_object_body_returns_400(self):
        """본문 누락·null·비객체 JSON의 400 응답"""
        with patch.object(auth_router, "authenticate_user") as authenticate_user:
            self.assert_bad_request(self.client.post("/api/auth/login"))
            self.assert_bad_request(
                self.client.post(
                    "/api/auth/login", content="null", headers={"Content-Type": "application/json"}
                )
            )
            for index, body in enumerate(([], "invalid-body", 123)):
                with self.subTest(case=index):
                    self.assert_bad_request(self.client.post("/api/auth/login", json=body))
            authenticate_user.assert_not_called()

    def test_malformed_json_hides_password(self):
        """깨진 JSON의 비밀번호 없는 400 응답"""
        with patch.object(auth_router, "authenticate_user") as authenticate_user:
            response = self.client.post(
                "/api/auth/login",
                content='{"username":"login_user","password":"' + self.password + '"',
                headers={"Content-Type": "application/json"},
            )
            self.assert_bad_request(response)
            self.assertNotIn(self.password, response.text)
            authenticate_user.assert_not_called()

    def test_validation_failure_does_not_expose_input_or_create_session(self):
        """입력 검증 실패의 정보 미노출·로그·세션 미생성"""
        with self.assertNoLogs("app.services.auth", level=logging.DEBUG):
            response = self.login(username="INVALID")
        self.assert_bad_request(response)
        self.assertNotIn(self.password, response.text)
        self.assertEqual(self.session(), {})

    def test_success_replaces_existing_session_with_database_user_id(self):
        """성공 로그인에서 기존 사용자·세션 항목 제거"""
        self.client.post(
            "/test-session", json={"user_id": self.other_id, "legacy_marker": "remove-on-login"}
        )
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session(), {"user_id": self.user_id})
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_authentication_and_validation_failures_preserve_existing_session(self):
        """400·401 응답에서 기존 로그인 세션 보존"""
        previous = {"user_id": self.other_id, "legacy_marker": "keep-on-failure"}
        self.client.post("/test-session", json=previous)
        cases = (
            ({"username": "missing_user"}, 401),
            ({"password": "wrong-test-password"}, 401),
            ({"username": "INVALID"}, 400),
        )
        for overrides, expected in cases:
            with self.subTest(status=expected, case=tuple(overrides)):
                self.assertEqual(self.login(**overrides).status_code, expected)
                self.assertEqual(self.session(), previous)
        self.assertEqual(self.snapshot(), self.initial_users)

    def test_database_failure_returns_safe_500_and_preserves_session(self):
        """실제 조회 장애의 500·로그 연결·세션 보존·복구"""
        previous = {"user_id": self.other_id, "legacy_marker": "keep-on-failure"}
        self.client.post("/test-session", json=previous)

        def fail_lookup(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                raise OperationalError(
                    "sensitive-sql",
                    {"password": self.password, "password_hash": self.password_hash},
                    Exception("private-db-error"),
                )

        event.listen(self.engine, "before_cursor_execute", fail_lookup)
        try:
            with self.assertLogs("login_routes_test_server", level=logging.INFO) as incoming:
                with self.assertLogs("app.services.auth", level=logging.ERROR) as captured:
                    response = self.login()
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_lookup)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to retrieve user"})
        request_id = incoming.records[0].getMessage().split("request_id=", 1)[1].split()[0]
        self.assertEqual(
            captured.records[0].getMessage(),
            f"auth_lookup_failure request_id={request_id} reason=db_error",
        )
        output = response.text + "\n".join(captured.output)
        for sensitive in (
            self.password, self.password_hash, self.secret_key, "sensitive-sql", "private-db-error"
        ):
            self.assertNotIn(sensitive, output)
        self.assertIsNone(captured.records[0].exc_info)
        self.assertEqual(self.session(), previous)
        self.assertEqual(self.snapshot(), self.initial_users)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.session(), {"user_id": self.user_id})

    def test_lookup_exception_message_is_not_exposed(self):
        """조회 예외 원문을 고정 HTTP 오류로 변환"""
        failure = UserLookupError(f"private-db-error {self.password} {self.password_hash}")
        with patch.object(auth_router, "authenticate_user", side_effect=failure):
            response = self.login()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Failed to retrieve user"})
        self.assertNotIn("private-db-error", response.text)
        self.assertEqual(self.session(), {})

    def test_http_cookie_uses_existing_server_options(self):
        """기존 서버의 HttpOnly·SameSite·유지 시간 확인"""
        response = self.login()
        cookie = self.cookie(response)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "lax")
        self.assertEqual(cookie["max-age"], str(14 * 24 * 60 * 60))
        self.assertEqual(cookie["path"], "/")
        self.assertFalse(cookie["secure"])

    def test_https_cookie_is_secure_and_not_sent_over_http(self):
        """HTTPS 로그인 쿠키의 Secure 및 HTTP 전송 차단"""
        app = self.make_app(https_only=True)
        client = self.enterContext(TestClient(app, base_url="https://testserver"))
        response = client.post("/api/auth/login", json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.cookie(response)["secure"])
        self.assertEqual(self.session(client), {"user_id": self.user_id})
        self.assertEqual(client.get("http://testserver/test-session").json(), {})

    def test_clients_keep_independent_login_sessions(self):
        """서로 다른 클라이언트의 로그인 세션 분리"""
        other = self.enterContext(TestClient(self.app))
        self.assertEqual(self.login().status_code, 200)
        response = other.post(
            "/api/auth/login",
            json={"username": self.other_username, "password": self.other_password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session(), {"user_id": self.user_id})
        self.assertEqual(self.session(other), {"user_id": self.other_id})

    def test_client_supplied_user_id_does_not_choose_authenticated_user(self):
        """요청 본문의 임의 사용자 ID를 인증 식별에 사용하지 않음"""
        response = self.login(user_id=self.other_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.user_id, "username": self.username})
        self.assertEqual(self.session(), {"user_id": self.user_id})


if __name__ == "__main__":
    unittest.main()
