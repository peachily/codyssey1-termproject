import unittest

from app.services.auth import hash_password, verify_password


class PasswordServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "test-password123"
        cls.password_hash = hash_password(cls.password)

    def test_hash_uses_argon2_without_storing_plaintext(self):
        """Argon2 해시 생성 및 평문 미포함"""
        self.assertTrue(self.password_hash.startswith("$argon2id$"))
        self.assertNotIn(self.password, self.password_hash)

    def test_same_password_produces_distinct_valid_hashes(self):
        """무작위 salt 및 생성된 해시 검증"""
        another_hash = hash_password(self.password)
        self.assertNotEqual(self.password_hash, another_hash)
        self.assertTrue(verify_password(self.password, self.password_hash))
        self.assertTrue(verify_password(self.password, another_hash))

    def test_correct_password_is_accepted(self):
        """올바른 비밀번호 검증 성공"""
        self.assertTrue(verify_password(self.password, self.password_hash))

    def test_incorrect_password_is_rejected(self):
        """잘못된 비밀번호 검증 실패"""
        self.assertFalse(verify_password("wrong-password123", self.password_hash))

    def test_password_whitespace_is_preserved(self):
        """비밀번호 앞뒤 공백 보존"""
        for password in (
            " test-password123",
            "test-password123 ",
            " test-password123 ",
        ):
            with self.subTest(password=password):
                password_hash = hash_password(password)
                self.assertTrue(verify_password(password, password_hash))
                self.assertFalse(verify_password(password.strip(), password_hash))

    def test_invalid_hash_is_rejected_without_raising(self):
        """빈 해시 및 잘못된 해시 형식 처리"""
        for password_hash in (
            "",
            "not-a-hash",
            "$argon2id$invalid",
            "$argon2id$v=19$m=65536,t=3,p=4$invalidsalt$invaliddigest",
        ):
            with self.subTest(password_hash=password_hash):
                self.assertFalse(verify_password(self.password, password_hash))


if __name__ == "__main__":
    unittest.main()
