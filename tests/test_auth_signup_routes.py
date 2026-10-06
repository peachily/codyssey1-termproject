import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import build_engine, get_db, initialize_database
from app.models import User
from app.routers import auth as auth_router
from app.services import auth as auth_service
from app.services.auth import DuplicateUsernameError, UserSaveError, verify_password


class SignupRouteTests(unittest.TestCase):
    password = "signup-route-test-password"
    request_id = "signup-route-test-request"

    def setUp(self):
        # 운영 서버·DB와 분리된 테스트 앱 및 SQLite 파일
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'signup-routes.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="signup-route-test-secret")

        def override_db():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)

        @app.middleware("http")
        async def set_request_id(request: Request, call_next):
            request.state.request_id = self.request_id
            return await call_next(request)

        # 기존 세션 준비·조회는 테스트 앱에서만 제공
        @app.post("/test-session/{user_id}")
        def set_session(user_id: int, request: Request):
            request.session["user_id"] = user_id
            return {"user_id": user_id}

        @app.get("/test-session")
        def read_session(request: Request):
            return dict(request.session)

        app.include_router(auth_router.router)
        self.client = self.enterContext(TestClient(app))

    def payload(self, **overrides):
        return {"username": "user_123", "password": self.password, **overrides}

    def signup(self, **overrides):
        return self.client.post("/api/auth/signup", json=self.payload(**overrides))

    def read_users(self):
        with Session(self.engine, expire_on_commit=False) as db:
            return db.scalars(select(User).order_by(User.id)).all()

    def assert_bad_request(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid username or password"})
        self.assertEqual(self.read_users(), [])

    def assert_safe_failure(self, response, captured, status_code, detail):
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response.json(), {"detail": detail})
        output = response.text + "\n".join(captured.output)
        for sensitive in (self.password, "sensitive-sql", "private-db-error"):
            self.assertNotIn(sensitive, output)
        self.assertIn("db_save_failure", "\n".join(captured.output))
        self.assertIn(self.request_id, "\n".join(captured.output))
        self.assertNotIn("db_save_success", "\n".join(captured.output))
        for record in captured.records:
            self.assertIsNone(record.exc_info)

    def test_success_returns_only_user_identity_and_persists_hash(self):
        """회원가입 201 응답·저장 결과·추적 로그 확인"""
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            response = self.signup()

        self.assertEqual(response.status_code, 201)
        stored = self.read_users()
        self.assertEqual(len(stored), 1)
        self.assertEqual(response.json(), {"id": stored[0].id, "username": "user_123"})
        self.assertTrue(verify_password(self.password, stored[0].password_hash))
        self.assertNotIn("password", response.json())
        self.assertNotIn("password_hash", response.json())
        self.assertNotIn("created_at", response.json())
        self.assertNotIn(self.password, response.text)
        self.assertNotIn(stored[0].password_hash, response.text)
        self.assertIn("db_save_success", captured.output[0])
        self.assertIn(self.request_id, captured.output[0])
        self.assertIn(f"user_id={stored[0].id}", captured.output[0])
        self.assertNotIn(self.password, "\n".join(captured.output))
        self.assertNotIn(stored[0].password_hash, "\n".join(captured.output))

    def test_username_trim_and_password_original_reach_service(self):
        """실제 API의 사용자명 정규화 및 비밀번호 공백 보존"""
        password = f"  {self.password}  "
        response = self.signup(username="  user_123  ", password=password)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["username"], "user_123")
        stored = self.read_users()[0]
        self.assertEqual(stored.username, "user_123")
        self.assertTrue(verify_password(password, stored.password_hash))
        self.assertFalse(verify_password(password.strip(), stored.password_hash))

    def test_missing_fields_return_400_without_creating_user(self):
        """필수 필드 누락의 400 응답 및 서비스 미호출"""
        with patch.object(auth_router, "create_user") as create_user:
            for field in ("username", "password"):
                with self.subTest(field=field):
                    payload = self.payload()
                    del payload[field]
                    self.assert_bad_request(
                        self.client.post("/api/auth/signup", json=payload)
                    )
            create_user.assert_not_called()

    def test_invalid_types_and_blank_values_return_400(self):
        """타입 오류·빈 문자열·공백 입력의 400 응답"""
        values = (None, 123, True, [], {}, "", " " * 8, "\t" * 8, "\u3000" * 8)
        with patch.object(auth_router, "create_user") as create_user:
            for field in ("username", "password"):
                for index, value in enumerate(values):
                    with self.subTest(field=field, case=index):
                        self.assert_bad_request(self.signup(**{field: value}))
            create_user.assert_not_called()

    def test_invalid_username_lengths_and_characters_return_400(self):
        """사용자명 길이·허용 문자 검증의 400 응답"""
        values = ("ab", "a" * 31, "  ab  ", "User_123", "한글사용자", "user-name", "user name")
        with patch.object(auth_router, "create_user") as create_user:
            for index, value in enumerate(values):
                with self.subTest(case=index):
                    self.assert_bad_request(self.signup(username=value))
            create_user.assert_not_called()

    def test_username_length_boundaries_are_accepted_after_trim(self):
        """trim 이후 사용자명 3자·30자 가입 확인"""
        for username in ("u_1", "u" * 30):
            with self.subTest(length=len(username)):
                response = self.signup(username=f"  {username}  ")
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["username"], username)
        self.assertEqual(len(self.read_users()), 2)

    def test_invalid_password_lengths_return_400(self):
        """비밀번호 7자·129자 입력의 400 응답"""
        with patch.object(auth_router, "create_user") as create_user:
            for password in ("p" * 7, "p" * 129):
                with self.subTest(length=len(password)):
                    response = self.signup(password=password)
                    self.assert_bad_request(response)
                    self.assertNotIn(password, response.text)
            create_user.assert_not_called()

    def test_password_length_boundaries_are_accepted(self):
        """비밀번호 원문 8자·128자 가입 확인"""
        for length in (8, 128):
            with self.subTest(length=length):
                response = self.signup(username=f"user_{length}", password="p" * length)
                self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.read_users()), 2)

    def test_missing_and_non_object_body_return_400(self):
        """본문 누락·null·비객체 JSON의 400 응답"""
        with patch.object(auth_router, "create_user") as create_user:
            self.assert_bad_request(self.client.post("/api/auth/signup"))
            self.assert_bad_request(
                self.client.post(
                    "/api/auth/signup", content="null", headers={"Content-Type": "application/json"}
                )
            )
            for index, body in enumerate(([], "invalid-body", 123)):
                with self.subTest(case=index):
                    self.assert_bad_request(
                        self.client.post("/api/auth/signup", json=body)
                    )
            create_user.assert_not_called()

    def test_malformed_json_returns_400_without_exposing_input(self):
        """깨진 JSON의 입력값 없는 400 응답"""
        with patch.object(auth_router, "create_user") as create_user:
            response = self.client.post(
                "/api/auth/signup",
                content='{"username":"user_123","password":"' + self.password + '"',
                headers={"Content-Type": "application/json"},
            )
            self.assert_bad_request(response)
            self.assertNotIn(self.password, response.text)
            create_user.assert_not_called()

    def test_validation_error_excludes_password_and_service_logs(self):
        """검증 실패의 비밀번호 미노출 및 저장 로그 미발생"""
        with self.assertNoLogs("app.services.auth", level=logging.DEBUG):
            response = self.signup(username="INVALID")
        self.assert_bad_request(response)
        self.assertNotIn(self.password, response.text)

    def test_duplicate_username_returns_409_and_preserves_original(self):
        """동일·공백 정규화 중복의 409 응답 및 기존 사용자 보존"""
        self.assertEqual(self.signup().status_code, 201)
        original = self.read_users()[0]
        for username in ("user_123", "  user_123  "):
            with self.subTest(username=username):
                with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
                    response = self.signup(username=username, password="other-test-password")
                self.assert_safe_failure(response, captured, 409, "Username already exists")
                self.assertNotIn(original.password_hash, response.text)
                stored = self.read_users()
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0].id, original.id)
                self.assertEqual(stored[0].password_hash, original.password_hash)

    def test_username_unique_conflict_returns_409(self):
        """사전 조회 이후 실제 SQLite UNIQUE 충돌의 409 응답"""
        self.assertEqual(self.signup().status_code, 201)
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            with patch.object(Session, "scalar", return_value=None):
                response = self.signup()
        self.assert_safe_failure(response, captured, 409, "Username already exists")
        self.assertEqual(len(self.read_users()), 1)

    def test_database_failures_return_500_and_allow_next_signup(self):
        """조회·INSERT·commit 실패의 500 응답 및 후속 가입 복구"""
        for phase in ("lookup", "insert", "commit"):
            with self.subTest(phase=phase):
                original_count = len(self.read_users())

                def fail_statement(connection, cursor, statement, parameters, context, executemany):
                    target = "SELECT" if phase == "lookup" else "INSERT"
                    if statement.lstrip().upper().startswith(target):
                        raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

                def fail_commit(connection):
                    raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

                event_name = "commit" if phase == "commit" else "before_cursor_execute"
                callback = fail_commit if phase == "commit" else fail_statement
                event.listen(self.engine, event_name, callback)
                try:
                    with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
                        response = self.signup()
                finally:
                    event.remove(self.engine, event_name, callback)
                self.assert_safe_failure(response, captured, 500, "Failed to save user")
                self.assertEqual(len(self.read_users()), original_count)
                self.assertEqual(self.signup(username=f"recovery_{phase}").status_code, 201)
                self.assertEqual(len(self.read_users()), original_count + 1)

    def test_other_integrity_error_returns_500_instead_of_409(self):
        """사용자명 중복 외 무결성 오류의 500 응답"""
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            with patch.object(auth_service, "hash_password", return_value=None):
                response = self.signup()
        self.assert_safe_failure(response, captured, 500, "Failed to save user")
        self.assertEqual(self.read_users(), [])
        self.assertEqual(self.signup().status_code, 201)

    def test_service_exception_details_are_not_exposed(self):
        """서비스 예외의 고정 오류 응답 변환"""
        cases = (
            (DuplicateUsernameError, 409, "Username already exists"),
            (UserSaveError, 500, "Failed to save user"),
        )
        for error_type, status_code, detail in cases:
            with self.subTest(status_code=status_code):
                error = error_type(f"private-db-error {self.password}")
                with patch.object(auth_router, "create_user", side_effect=error):
                    response = self.signup()
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json(), {"detail": detail})
                self.assertNotIn(self.password, response.text)
                self.assertNotIn("private-db-error", response.text)
        self.assertEqual(self.read_users(), [])

    def test_signup_does_not_create_login_session(self):
        """쿠키 없는 가입 요청의 로그인 세션 미생성"""
        response = self.signup()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("set-cookie", response.headers)
        self.assertNotIn("session", self.client.cookies)
        self.assertEqual(self.client.get("/test-session").json(), {})

    def test_existing_session_is_preserved_on_success_and_errors(self):
        """가입 성공·400·409·500 응답에서 기존 사용자 세션 보존"""
        original_id = self.signup(username="original_user").json()["id"]
        self.client.post(f"/test-session/{original_id}")

        success = self.signup()
        self.assertEqual(success.status_code, 201)
        self.assertNotEqual(success.json()["id"], original_id)
        self.assertEqual(self.client.get("/test-session").json(), {"user_id": original_id})

        invalid = self.signup(username="INVALID")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.get("/test-session").json(), {"user_id": original_id})

        with self.assertLogs("app.services.auth", level=logging.WARNING):
            duplicate = self.signup()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.get("/test-session").json(), {"user_id": original_id})

        with patch.object(auth_router, "create_user", side_effect=UserSaveError):
            failure = self.signup(username="another_user")
        self.assertEqual(failure.status_code, 500)
        self.assertEqual(self.client.get("/test-session").json(), {"user_id": original_id})


if __name__ == "__main__":
    unittest.main()
