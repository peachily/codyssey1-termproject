import base64
import json
import os
import runpy
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from starlette.middleware.sessions import SessionMiddleware


class SessionTestCase(unittest.TestCase):
    def load_server(self, https_only=False, secret_key="session-test-secret-key"):
        # 실제 환경 변수·DB와 분리된 서버 구성
        environment = {
            "SECRET_KEY": secret_key,
            "SESSION_HTTPS_ONLY": str(https_only).lower(),
            "DATABASE_URL": "sqlite:///:memory:",
        }
        with patch.dict(os.environ, environment, clear=True):
            from app import database

            engine = database.build_engine("sqlite:///:memory:")
            self.addCleanup(engine.dispose)
            with patch.object(database, "engine", engine):
                return runpy.run_path(
                    str(Path(__file__).resolve().parents[1] / "app" / "main.py"),
                    run_name="auth_session_test_server",
                )

    def make_client(self, https_only=False, secret_key="session-test-secret-key"):
        server = self.load_server(https_only, secret_key)
        middleware = next(
            item for item in server["app"].user_middleware if item.cls is SessionMiddleware
        )
        app = FastAPI()
        # 실제 서버의 세션 미들웨어 설정 재사용
        app.add_middleware(middleware.cls, *middleware.args, **middleware.kwargs)

        @app.post("/test-session/{user_id}")
        def save_session(user_id: int, request: Request):
            request.session.clear()
            request.session["user_id"] = user_id
            return {"user_id": user_id}

        @app.get("/test-session")
        def read_session(request: Request):
            return dict(request.session)

        @app.delete("/test-session")
        def clear_session(request: Request):
            request.session.clear()
            return {"message": "Session cleared"}

        base_url = "https://testserver" if https_only else "http://testserver"
        return self.enterContext(TestClient(app, base_url=base_url))

    def read_cookie(self, response):
        cookies = SimpleCookie()
        cookies.load(response.headers["set-cookie"])
        return cookies["session"]


class SessionCookieTests(SessionTestCase):
    def test_request_without_cookie_has_empty_session(self):
        """쿠키 없는 요청의 빈 세션 처리"""
        client = self.make_client()
        response = client.get("/test-session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
        self.assertNotIn("set-cookie", response.headers)

    def test_session_is_preserved_between_requests(self):
        """서명된 쿠키를 통한 세션 유지"""
        client = self.make_client()
        response = client.post("/test-session/12")
        self.assertEqual(response.status_code, 200)
        self.assertIn("session", client.cookies)
        self.assertEqual(client.get("/test-session").json(), {"user_id": 12})

    def test_clear_session_removes_cookie(self):
        """세션 삭제 및 쿠키 만료 처리"""
        client = self.make_client()
        client.post("/test-session/12")
        response = client.delete("/test-session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.read_cookie(response)["expires"], "Thu, 01 Jan 1970 00:00:00 GMT")
        self.assertNotIn("session", client.cookies)
        self.assertEqual(client.get("/test-session").json(), {})

    def test_tampered_user_id_is_rejected(self):
        """사용자 ID를 변조한 쿠키 거부"""
        client = self.make_client()
        client.post("/test-session/12")
        cookie = client.cookies.get("session")
        payload, signature = cookie.split(".", 1)
        data = json.loads(base64.b64decode(payload))
        data["user_id"] = 99
        changed_payload = base64.b64encode(json.dumps(data).encode()).decode()
        client.cookies.clear()

        response = client.get(
            "/test-session", headers={"Cookie": f"session={changed_payload}.{signature}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    def test_cookie_signed_with_different_key_is_rejected(self):
        """다른 비밀값으로 서명한 쿠키 거부"""
        first = self.make_client()
        first.post("/test-session/12")
        cookie = first.cookies.get("session")
        second = self.make_client(secret_key="different-session-test-key")

        response = second.get("/test-session", headers={"Cookie": f"session={cookie}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    def test_expired_cookie_is_rejected(self):
        """유지 기간이 지난 세션 쿠키 거부"""
        client = self.make_client()
        with patch.object(TimestampSigner, "get_timestamp", return_value=1_700_000_000):
            client.post("/test-session/12")
        with patch.object(
            TimestampSigner, "get_timestamp", return_value=1_700_000_000 + 14 * 24 * 60 * 60 + 1
        ):
            response = client.get("/test-session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    def test_clients_keep_separate_sessions(self):
        """서로 다른 클라이언트의 세션 분리"""
        first = self.make_client()
        second = self.make_client()
        first.post("/test-session/12")
        second.post("/test-session/34")
        self.assertEqual(first.get("/test-session").json(), {"user_id": 12})
        self.assertEqual(second.get("/test-session").json(), {"user_id": 34})

    def test_local_cookie_has_expected_attributes(self):
        """로컬 쿠키의 속성 및 14일 유지 기간 확인"""
        client = self.make_client()
        cookie = self.read_cookie(client.post("/test-session/12"))
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "lax")
        self.assertEqual(cookie["max-age"], str(14 * 24 * 60 * 60))
        self.assertEqual(cookie["path"], "/")
        self.assertFalse(cookie["secure"])

    def test_https_cookie_is_not_sent_over_http(self):
        """HTTPS 쿠키의 Secure 속성 및 HTTP 전송 차단"""
        client = self.make_client(https_only=True)
        cookie = self.read_cookie(client.post("/test-session/12"))
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "lax")
        self.assertEqual(client.get("/test-session").json(), {"user_id": 12})
        self.assertEqual(client.get("http://testserver/test-session").json(), {})


class SessionServerTests(SessionTestCase):
    def test_server_paths_are_preserved_in_both_environments(self):
        """세션 연결 후 기존 서버 경로 유지"""
        for https_only in (False, True):
            with self.subTest(https_only=https_only):
                server = self.load_server(https_only)
                base_url = "https://testserver" if https_only else "http://testserver"
                with TestClient(server["app"], base_url=base_url) as client:
                    response = client.get("/health")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"status": "ok"})
                    response = client.get("/api/unknown", headers={"Accept": "text/html"})
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.headers["content-type"], "application/json")
                    for path in ("/api/chat", "/api/prescription"):
                        response = client.post(path, json={"message": "test message"})
                        self.assertEqual(response.status_code, 401)

    def test_invalid_settings_prevent_server_configuration(self):
        """잘못된 설정의 서버 구성 차단"""
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        cases = (
            ({}, "SECRET_KEY must be set to a non-blank value"),
            ({"SECRET_KEY": ""}, "SECRET_KEY must be set to a non-blank value"),
            ({"SECRET_KEY": " \t\n"}, "SECRET_KEY must be set to a non-blank value"),
            (
                {"SECRET_KEY": "session-test-secret-key", "SESSION_HTTPS_ONLY": "invalid"},
                "SESSION_HTTPS_ONLY must be true or false",
            ),
        )
        for index, (environment, message) in enumerate(cases):
            with self.subTest(case=index):
                with patch.dict(
                    os.environ, {"DATABASE_URL": "sqlite:///:memory:", **environment}, clear=True
                ):
                    with self.assertRaises(RuntimeError) as captured:
                        runpy.run_path(str(main_path), run_name="auth_session_test_server")
                self.assertEqual(str(captured.exception), message)


class FrontendSessionTests(SessionTestCase):
    def setUp(self):
        server = self.load_server()
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        self.html = "<html><body>Test frontend</body></html>"
        (root / "index.html").write_text(self.html, encoding="utf-8")
        (root / "assets").mkdir()
        (root / "assets" / "test.css").write_text("body { color: black; }", encoding="utf-8")
        app = FastAPI()
        app.mount("/", server["FrontendFiles"](directory=root, html=True))
        self.client = self.enterContext(TestClient(app))

    def test_frontend_files_and_spa_fallback_are_preserved(self):
        """정적 파일 및 React 화면 경로 유지"""
        for path in ("/", "/chat"):
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Accept": "text/html"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, self.html)
        response = self.client.get("/assets/test.css")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "body { color: black; }")

    def test_reserved_backend_paths_do_not_return_frontend_html(self):
        """API·health 경로의 React 화면 반환 차단"""
        for path in ("/api/unknown", "/health/unknown"):
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Accept": "text/html"})
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(self.html, response.text)

    def test_missing_assets_and_non_html_requests_keep_404(self):
        """없는 파일 및 JSON 요청의 화면 대체 차단"""
        for path, accept in (
            ("/assets/missing", "text/html"),
            ("/missing.css", "text/html"),
            ("/chat", "application/json"),
        ):
            with self.subTest(path=path, accept=accept):
                response = self.client.get(path, headers={"Accept": accept})
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
