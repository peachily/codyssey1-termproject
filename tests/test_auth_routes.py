import unittest

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.routers.auth import AuthValidationRoute
from app.schemas.auth import AuthRequest


class AuthValidationRouteTests(unittest.TestCase):
    def setUp(self):
        # DB·AI·운영 서버와 분리된 테스트 앱
        app = FastAPI()
        router = APIRouter(prefix="/api/auth", route_class=AuthValidationRoute)
        self.received_passwords = []

        @router.post("/validate")
        def validate_input(payload: AuthRequest):
            self.received_passwords.append(payload.password)
            return {"username": payload.username}

        @router.get("/http-error/{status_code}")
        def raise_http_error(status_code: int):
            raise HTTPException(
                status_code=status_code,
                detail="Test error",
                headers={"X-Test-Error": "preserved"},
            )

        @router.get("/unexpected-error")
        def raise_unexpected_error():
            raise RuntimeError("Test failure")

        app.include_router(router)

        @app.post("/default-validation")
        def default_validation(payload: AuthRequest):
            return {"username": payload.username}

        self.client = self.enterContext(TestClient(app))

    def make_payload(self, **overrides):
        return {"username": "user_123", "password": "test-password123", **overrides}

    def assert_bad_request(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid username or password"})
        self.assertEqual(self.received_passwords, [])

    def test_valid_input_preserves_password_and_normalizes_username(self):
        """정상 요청 및 비밀번호 원문 전달"""
        password = "  test-password123  "
        response = self.client.post(
            "/api/auth/validate",
            json=self.make_payload(username="  user_123  ", password=password),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "user_123"})
        self.assertEqual(self.received_passwords, [password])
        self.assertNotIn(password, response.text)

    def test_missing_fields_return_400(self):
        """필수 입력 누락의 HTTP 400 응답"""
        for field in ("username", "password"):
            with self.subTest(field=field):
                payload = self.make_payload()
                del payload[field]
                self.assert_bad_request(self.client.post("/api/auth/validate", json=payload))

    def test_invalid_fields_return_400(self):
        """타입·공백·길이·문자 검증 실패의 HTTP 400 응답"""
        invalid_values = {
            "username": (None, 123, True, [], {}, "", "   ", "ab", "a" * 31, "User_123"),
            "password": (None, 123, True, [], {}, "", " " * 8, "1234567", "p" * 129),
        }
        for field, values in invalid_values.items():
            for index, value in enumerate(values):
                with self.subTest(field=field, case=index):
                    response = self.client.post(
                        "/api/auth/validate", json=self.make_payload(**{field: value})
                    )
                    self.assert_bad_request(response)

    def test_missing_or_non_object_body_returns_400(self):
        """요청 본문 누락 및 잘못된 본문 형태 차단"""
        self.assert_bad_request(self.client.post("/api/auth/validate"))
        for index, body in enumerate(([], "invalid-body", 123)):
            with self.subTest(case=index):
                self.assert_bad_request(self.client.post("/api/auth/validate", json=body))

    def test_malformed_json_returns_400_without_input(self):
        """잘못된 JSON의 HTTP 400 응답 및 입력값 미노출"""
        password = "json-test-secret123"
        response = self.client.post(
            "/api/auth/validate",
            content='{"username":"user_123","password":"' + password + '"',
            headers={"Content-Type": "application/json"},
        )
        self.assert_bad_request(response)
        self.assertNotIn(password, response.text)

    def test_validation_error_response_excludes_password(self):
        """검증 오류 응답의 비밀번호 미노출"""
        for index, payload in enumerate(
            (
                self.make_payload(username="INVALID", password="valid-test-secret123"),
                self.make_payload(password="pvQ7x"),
            )
        ):
            with self.subTest(case=index):
                response = self.client.post("/api/auth/validate", json=payload)
                self.assert_bad_request(response)
                self.assertNotIn(payload["password"], response.text)

    def test_other_http_errors_are_preserved(self):
        """다른 HTTP 오류의 상태·본문·헤더 유지"""
        for status_code in (401, 409, 500):
            with self.subTest(status_code=status_code):
                response = self.client.get(f"/api/auth/http-error/{status_code}")
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json(), {"detail": "Test error"})
                self.assertEqual(response.headers["X-Test-Error"], "preserved")

    def test_unexpected_error_is_not_converted_to_400(self):
        """입력 검증 외 예외의 변환 제외"""
        with self.assertRaisesRegex(RuntimeError, "Test failure"):
            self.client.get("/api/auth/unexpected-error")

    def test_default_route_keeps_422(self):
        """일반 라우터의 기본 HTTP 422 응답 유지"""
        response = self.client.post("/default-validation", json={"username": "user_123"})
        self.assertEqual(response.status_code, 422)
        self.assertIsInstance(response.json()["detail"], list)
        self.assertEqual(self.received_passwords, [])


if __name__ == "__main__":
    unittest.main()
