import unittest

from pydantic import ValidationError

from app.schemas.auth import AuthRequest


class AuthRequestTests(unittest.TestCase):
    def make_payload(self, **overrides):
        return {"username": "user_123", "password": "test-password123", **overrides}

    def test_valid_input_is_accepted(self):
        """정상 입력 허용"""
        payload = self.make_payload()
        request = AuthRequest.model_validate(payload)
        self.assertEqual(request.username, payload["username"])
        self.assertEqual(request.password, payload["password"])

    def test_required_fields_cannot_be_missing(self):
        """필수 필드 누락 차단"""
        for field in ("username", "password"):
            with self.subTest(field=field):
                payload = self.make_payload()
                del payload[field]
                with self.assertRaises(ValidationError):
                    AuthRequest.model_validate(payload)

    def test_non_string_values_are_rejected(self):
        """null 및 문자열 외 타입 차단"""
        for field in ("username", "password"):
            for value in (None, 123, 1.5, True, [], {}, b"user_123"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError):
                        AuthRequest.model_validate(self.make_payload(**{field: value}))

    def test_username_length_boundaries(self):
        """사용자명 길이 경계값 검증"""
        for length in (3, 30):
            with self.subTest(length=length):
                username = "a" * length
                request = AuthRequest.model_validate(self.make_payload(username=username))
                self.assertEqual(request.username, username)
        for length in (2, 31):
            with self.subTest(length=length):
                with self.assertRaises(ValidationError):
                    AuthRequest.model_validate(self.make_payload(username="a" * length))

    def test_username_character_rules(self):
        """사용자명 허용 문자 검증"""
        for username in ("abc", "123", "a_b", "___"):
            with self.subTest(username=username):
                request = AuthRequest.model_validate(self.make_payload(username=username))
                self.assertEqual(request.username, username)
        for username in ("User123", "사용자", "user-name", "user.name", "user name", "us\ner"):
            with self.subTest(username=username):
                with self.assertRaises(ValidationError):
                    AuthRequest.model_validate(self.make_payload(username=username))

    def test_username_whitespace_is_trimmed_before_validation(self):
        """사용자명 앞뒤 공백 제거 및 길이 검증"""
        for username in (" user_123 ", "\tuser_123\n", " " + "a" * 30 + " "):
            with self.subTest(username=username):
                request = AuthRequest.model_validate(self.make_payload(username=username))
                self.assertEqual(request.username, username.strip())
        with self.assertRaises(ValidationError):
            AuthRequest.model_validate(self.make_payload(username=" ab "))

    def test_empty_and_blank_values_are_rejected(self):
        """빈 문자열 및 공백만 있는 입력 차단"""
        for field in ("username", "password"):
            for value in ("", " " * 8, "\t" * 8, "\n" * 8, "\u3000" * 8):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError):
                        AuthRequest.model_validate(self.make_payload(**{field: value}))

    def test_password_length_boundaries(self):
        """비밀번호 길이 경계값 및 문자 조합 제한 없음"""
        for length in (8, 128):
            with self.subTest(length=length):
                password = "a" * length
                request = AuthRequest.model_validate(self.make_payload(password=password))
                self.assertEqual(request.password, password)
        for length in (7, 129):
            with self.subTest(length=length):
                with self.assertRaises(ValidationError):
                    AuthRequest.model_validate(self.make_payload(password="a" * length))

    def test_password_whitespace_is_preserved(self):
        """비밀번호 원문 및 공백 포함 길이 기준 유지"""
        for password in (
            " test-password123",
            "test-password123 ",
            " test-password123 ",
            "\ttest-password123\n",
            " aaaaaa ",
        ):
            with self.subTest(password=password):
                request = AuthRequest.model_validate(self.make_payload(password=password))
                self.assertEqual(request.password, password)

    def test_password_is_hidden_from_object_representation(self):
        """객체 표현의 비밀번호 숨김"""
        password = "test-password123"
        request = AuthRequest.model_validate(self.make_payload(password=password))
        self.assertNotIn(password, repr(request))
        self.assertNotIn(password, str(request))
        self.assertEqual(request.password, password)

    def test_input_values_are_hidden_from_validation_error_text(self):
        """검증 오류 문자열의 입력값 숨김"""
        for password in ("pvQ7x", "private-password-" * 9):
            with self.subTest(length=len(password)):
                with self.assertRaises(ValidationError) as captured:
                    AuthRequest.model_validate(self.make_payload(password=password))
                error_text = str(captured.exception)
                self.assertNotIn(password, error_text)
                self.assertNotIn("input_value=", error_text)
                self.assertNotIn("input_type=", error_text)


if __name__ == "__main__":
    unittest.main()
