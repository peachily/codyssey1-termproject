import os
import unittest
from unittest.mock import patch

from app.config import get_session_settings


class SessionSettingsTests(unittest.TestCase):
    def setUp(self):
        # 실제 환경 변수와 분리된 테스트 설정
        self.secret_key = "config-test-secret-key"
        self.enterContext(patch.dict(os.environ, {"SECRET_KEY": self.secret_key}, clear=True))

    def test_valid_secret_key_is_read(self):
        """정상 세션 비밀값 읽기"""
        settings = get_session_settings()
        self.assertEqual(settings.secret_key, self.secret_key)

    def test_missing_secret_key_is_rejected(self):
        """세션 비밀값 누락 차단"""
        del os.environ["SECRET_KEY"]
        with self.assertNoLogs("app.config", level="DEBUG"):
            with self.assertRaises(RuntimeError) as captured:
                get_session_settings()
        self.assertEqual(
            str(captured.exception), "SECRET_KEY must be set to a non-blank value"
        )

    def test_empty_or_blank_secret_key_is_rejected(self):
        """빈 값 및 공백만 있는 세션 비밀값 차단"""
        for index, value in enumerate(("", "   ", "\t\n", "\u3000")):
            with self.subTest(case=index):
                os.environ["SECRET_KEY"] = value
                with self.assertNoLogs("app.config", level="DEBUG"):
                    with self.assertRaises(RuntimeError) as captured:
                        get_session_settings()
                self.assertEqual(
                    str(captured.exception), "SECRET_KEY must be set to a non-blank value"
                )

    def test_valid_secret_key_whitespace_is_preserved(self):
        """유효한 세션 비밀값의 원문 보존"""
        for prefix, suffix in ((" ", ""), ("", " "), ("\t", "\n")):
            with self.subTest(prefix=repr(prefix), suffix=repr(suffix)):
                value = prefix + self.secret_key + suffix
                os.environ["SECRET_KEY"] = value
                self.assertEqual(get_session_settings().secret_key, value)

    def test_secret_key_is_hidden_from_object_representation(self):
        """객체 출력의 세션 비밀값 숨김"""
        for raw in ("false", "true"):
            with self.subTest(https_only=raw):
                os.environ["SESSION_HTTPS_ONLY"] = raw
                settings = get_session_settings()
                self.assertNotIn(self.secret_key, repr(settings))
                self.assertNotIn(self.secret_key, str(settings))
                self.assertEqual(settings.secret_key, self.secret_key)

    def test_missing_or_blank_https_setting_defaults_to_false(self):
        """HTTPS 설정 누락 및 빈 값의 기본값 확인"""
        for index, raw in enumerate((None, "", " \t\n", "\u3000")):
            with self.subTest(case=index):
                if raw is None:
                    os.environ.pop("SESSION_HTTPS_ONLY", None)
                else:
                    os.environ["SESSION_HTTPS_ONLY"] = raw
                self.assertIs(get_session_settings().https_only, False)

    def test_https_setting_accepts_normalized_true_and_false(self):
        """HTTPS 설정의 대소문자 및 앞뒤 공백 정규화"""
        cases = (
            ("true", True),
            ("false", False),
            ("TRUE", True),
            ("FALSE", False),
            (" \tTrUe\n", True),
            (" \tFaLsE\n", False),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                os.environ["SESSION_HTTPS_ONLY"] = raw
                self.assertIs(get_session_settings().https_only, expected)

    def test_invalid_https_setting_is_rejected_without_secret_output(self):
        """잘못된 HTTPS 설정 차단 및 오류·로그의 비밀값 미노출"""
        for raw in ("1", "0", "yes", "no", "on", "off", "invalid", "true false"):
            with self.subTest(raw=raw):
                os.environ["SESSION_HTTPS_ONLY"] = raw
                with self.assertNoLogs("app.config", level="DEBUG"):
                    with self.assertRaises(RuntimeError) as captured:
                        get_session_settings()
                error_text = str(captured.exception)
                self.assertEqual(error_text, "SESSION_HTTPS_ONLY must be true or false")
                self.assertNotIn(self.secret_key, error_text)

    def test_settings_read_current_environment_on_each_call(self):
        """설정 호출별 현재 환경 변수 반영"""
        first = get_session_settings()
        os.environ["SECRET_KEY"] = "updated-config-test-secret-key"
        os.environ["SESSION_HTTPS_ONLY"] = "true"
        second = get_session_settings()

        self.assertEqual(first.secret_key, self.secret_key)
        self.assertIs(first.https_only, False)
        self.assertEqual(second.secret_key, "updated-config-test-secret-key")
        self.assertIs(second.https_only, True)


if __name__ == "__main__":
    unittest.main()
