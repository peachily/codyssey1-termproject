import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import build_engine, initialize_database
from app.models import User
from app.services import auth
from app.services.auth import (
    UserLookupError,
    authenticate_user,
    create_user,
    hash_password,
)


class LoginServiceTests(unittest.TestCase):
    username = "login_user"
    password = "login-test-password"
    request_id = "login-test-request"

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        # 운영 DB와 분리된 임시 SQLite 및 실제 Argon2 해시
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.engine = build_engine(f"sqlite:///{Path(directory) / 'login.db'}")
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        user = User(username=self.username, password_hash=self.password_hash)
        self.db.add(user)
        self.db.commit()
        self.user_id = user.id

    def snapshot(self):
        # 별도 Session에서 사용자 변경 여부 확인
        with Session(self.engine) as db:
            return [
                (user.id, user.username, user.password_hash, user.created_at)
                for user in db.scalars(select(User).order_by(User.id))
            ]

    def test_valid_password_returns_database_user(self):
        """올바른 비밀번호의 실제 사용자 반환"""
        user = authenticate_user(self.db, self.username, self.password)
        self.assertIsInstance(user, User)
        self.assertEqual(user.id, self.user_id)
        self.assertEqual(user.username, self.username)
        self.assertEqual(user.password_hash, self.password_hash)

    def test_username_whitespace_is_removed_before_lookup(self):
        """사용자명 앞뒤 공백 제거 후 인증"""
        user = authenticate_user(self.db, f"  {self.username}  ", self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user_id)
        self.assertEqual(user.username, self.username)

    def test_unknown_user_and_wrong_password_return_same_failure(self):
        """사용자 없음·잘못된 비밀번호의 동일한 인증 실패"""
        before = self.snapshot()
        self.assertIsNone(authenticate_user(self.db, "missing_user", self.password))
        self.assertIsNone(authenticate_user(self.db, self.username, "wrong-test-password"))
        self.assertEqual(self.snapshot(), before)

    def test_invalid_stored_hash_returns_authentication_failure(self):
        """잘못된 저장 해시의 인증 실패 및 값 보존"""
        for index, password_hash in enumerate(("not-a-hash", "$argon2id$invalid")):
            with self.subTest(case=index):
                user = self.db.get(User, self.user_id)
                user.password_hash = password_hash
                self.db.commit()
                before = self.snapshot()
                self.assertIsNone(authenticate_user(self.db, self.username, self.password))
                self.assertEqual(self.snapshot(), before)

    def test_password_whitespace_is_preserved(self):
        """비밀번호 원문 공백 보존 및 공백 제거 값의 인증 실패"""
        password = f"  {self.password}  "
        user = self.db.get(User, self.user_id)
        user.password_hash = hash_password(password)
        self.db.commit()
        before = self.snapshot()

        authenticated = authenticate_user(self.db, self.username, password)
        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.id, self.user_id)
        self.assertIsNone(authenticate_user(self.db, self.username, password.strip()))
        self.assertEqual(self.snapshot(), before)

    def test_authentication_only_reads_without_changing_users_or_logs(self):
        """정상·실패 인증의 DB 쓰기·사용자 변경·로그 미발생"""
        before = self.snapshot()
        statements = []

        def capture_statement(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().upper())

        event.listen(self.engine, "before_cursor_execute", capture_statement)
        try:
            with patch.object(self.db, "commit", side_effect=AssertionError("Unexpected commit")):
                with self.assertNoLogs("app.services.auth", level=logging.DEBUG):
                    self.assertIsNotNone(
                        authenticate_user(
                            self.db, self.username, self.password, request_id=self.request_id
                        )
                    )
                    self.assertIsNone(
                        authenticate_user(self.db, self.username, "wrong-test-password")
                    )
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statement)

        self.assertEqual(len(statements), 2)
        self.assertTrue(all(statement.startswith("SELECT") for statement in statements))
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)
        self.assertFalse(self.db.deleted)
        self.assertEqual(self.snapshot(), before)

    def test_database_error_is_separate_and_session_recovers_safely(self):
        """조회 장애의 안전한 예외·rollback 및 Session 복구"""
        before = self.snapshot()

        def fail_lookup(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                raise OperationalError(
                    "sensitive-sql",
                    {"password": self.password, "password_hash": self.password_hash},
                    Exception("private-db-error"),
                )

        event.listen(self.engine, "before_cursor_execute", fail_lookup)
        try:
            with self.assertLogs("app.services.auth", level=logging.ERROR) as captured:
                with patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                    with patch.object(auth, "verify_password") as verify_password:
                        with self.assertRaises(UserLookupError) as raised:
                            authenticate_user(
                                self.db,
                                self.username,
                                self.password,
                                request_id=self.request_id,
                            )
                        verify_password.assert_not_called()
                    rollback.assert_called_once()
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_lookup)

        self.assertEqual(str(raised.exception), "Failed to retrieve user")
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertEqual(
            captured.records[0].getMessage(),
            f"auth_lookup_failure request_id={self.request_id} reason=db_error",
        )
        self.assertEqual(len(captured.records), 1)
        output = str(raised.exception) + "\n".join(captured.output)
        for sensitive in (
            self.password, self.password_hash, "sensitive-sql", "private-db-error"
        ):
            self.assertNotIn(sensitive, output)
        self.assertIsNone(captured.records[0].exc_info)
        self.assertNotIn("db_save_", output)
        self.assertFalse(self.db.in_transaction())
        self.assertTrue(self.db.is_active)
        self.assertEqual(self.snapshot(), before)
        user = authenticate_user(self.db, self.username, self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user_id)

    def test_signup_user_authenticates_with_own_password(self):
        """회원가입 서비스로 생성한 사용자 인증 및 계정 구분"""
        password = "another-login-test-password"
        created = create_user(self.db, "new_user", password)
        before = self.snapshot()

        user = authenticate_user(self.db, "new_user", password)
        self.assertIsNotNone(user)
        self.assertEqual(user.id, created.id)
        self.assertIsNone(authenticate_user(self.db, self.username, password))
        self.assertIsNone(authenticate_user(self.db, "new_user", self.password))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
