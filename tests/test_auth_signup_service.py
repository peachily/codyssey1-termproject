import logging
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import build_engine, initialize_database
from app.models import User
from app.services import auth
from app.services.auth import (
    DuplicateUsernameError,
    UserSaveError,
    create_user,
    verify_password,
)


class SignupServiceTests(unittest.TestCase):
    password = "signup-test-password"
    request_id = "signup-test-request"

    def setUp(self):
        # 운영 DB와 분리된 임시 SQLite 파일
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.url = f"sqlite:///{Path(directory) / 'signup.db'}"
        self.engine = build_engine(self.url)
        self.addCleanup(self.engine.dispose)
        initialize_database(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)

    def read_users(self):
        # 별도 Session으로 commit 결과 확인
        with Session(self.engine, expire_on_commit=False) as db:
            return db.scalars(select(User).order_by(User.id)).all()

    def assert_safe_logs(self, captured, *forbidden):
        output = "\n".join(captured.output)
        for value in (self.password, "sensitive-sql", "private-db-error", *forbidden):
            self.assertNotIn(value, output)
        for record in captured.records:
            self.assertIsNone(record.exc_info)

    def assert_save_failure(self):
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            with patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                with self.assertRaises(UserSaveError) as raised:
                    create_user(
                        self.db, "user_123", self.password, request_id=self.request_id
                    )
                rollback.assert_called_once()
        self.assertEqual(str(raised.exception), "Failed to save user")
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertIn("db_save_failure", captured.output[0])
        self.assertIn(self.request_id, captured.output[0])
        self.assertNotIn("db_save_success", "\n".join(captured.output))
        self.assert_safe_logs(captured)
        self.assertFalse(self.db.in_transaction())
        self.assertTrue(self.db.is_active)
        self.assertEqual(self.read_users(), [])

    def assert_recovery(self):
        user = create_user(self.db, "recovery_user", self.password)
        self.assertGreater(user.id, 0)
        self.assertEqual([row.username for row in self.read_users()], ["recovery_user"])

    def test_signup_commits_user_and_logs_without_sensitive_content(self):
        """사용자 저장·Argon2 해시·민감정보 없는 성공 로그 확인"""
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            user = create_user(
                self.db, "user_123", self.password, request_id=self.request_id
            )

        self.assertGreater(user.id, 0)
        self.assertEqual(user.username, "user_123")
        stored = self.read_users()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].id, user.id)
        self.assertEqual(stored[0].username, user.username)
        self.assertEqual(stored[0].created_at.utcoffset(), timedelta(0))
        self.assertTrue(stored[0].password_hash.startswith("$argon2id$"))
        self.assertNotIn(self.password, stored[0].password_hash)
        self.assertTrue(verify_password(self.password, stored[0].password_hash))
        self.assertFalse(verify_password("wrong-test-password", stored[0].password_hash))
        self.assertEqual(len(captured.output), 1)
        self.assertIn("db_save_success", captured.output[0])
        self.assertIn(f"user_id={user.id}", captured.output[0])
        self.assertIn(self.request_id, captured.output[0])
        self.assert_safe_logs(captured, stored[0].password_hash)

    def test_username_is_normalized_and_password_whitespace_is_preserved(self):
        """사용자명 공백 제거 및 비밀번호 원문 보존"""
        password = f"  {self.password}  "
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            user = create_user(self.db, "  user_123  ", password)

        self.assertEqual(user.username, "user_123")
        stored = self.read_users()[0]
        self.assertEqual(stored.username, "user_123")
        self.assertTrue(verify_password(password, stored.password_hash))
        self.assertFalse(verify_password(password.strip(), stored.password_hash))
        self.assert_safe_logs(captured, password, stored.password_hash)

    def test_existing_username_is_rejected_without_changing_user(self):
        """정규화된 사용자명 중복 차단 및 기존 사용자 보존"""
        original = create_user(self.db, "user_123", self.password)
        original_id = original.id
        original_hash = original.password_hash
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            with patch.object(auth, "hash_password") as hash_password:
                with patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                    with self.assertRaises(DuplicateUsernameError) as raised:
                        create_user(
                            self.db,
                            "  user_123  ",
                            "another-test-password",
                            request_id=self.request_id,
                        )
                    rollback.assert_called_once()
                hash_password.assert_not_called()

        self.assertEqual(str(raised.exception), "Username already exists")
        stored = self.read_users()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].id, original_id)
        self.assertEqual(stored[0].password_hash, original_hash)
        self.assertFalse(self.db.in_transaction())
        self.assertIn("reason=duplicate_username", captured.output[0])
        self.assertNotIn("db_save_success", "\n".join(captured.output))
        self.assert_safe_logs(captured, original_hash, "another-test-password")
        create_user(self.db, "next_user", self.password)
        self.assertEqual(len(self.read_users()), 2)

    def test_username_unique_violation_after_precheck_is_duplicate(self):
        """사전 조회 이후 실제 사용자명 UNIQUE 충돌 처리"""
        original = create_user(self.db, "user_123", self.password)
        original_hash = original.password_hash
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            # 사전 조회만 제어하고 실제 SQLite UNIQUE 위반 발생
            with patch.object(self.db, "scalar", return_value=None):
                with patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                    with self.assertRaises(DuplicateUsernameError) as raised:
                        create_user(
                            self.db, "user_123", self.password, request_id=self.request_id
                        )
                    rollback.assert_called_once()

        self.assertEqual(str(raised.exception), "Username already exists")
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertIn("db_save_failure", captured.output[0])
        self.assertIn("reason=duplicate_username", captured.output[0])
        self.assertIn(self.request_id, captured.output[0])
        self.assertNotIn("db_save_success", "\n".join(captured.output))
        self.assert_safe_logs(captured, original_hash, "UNIQUE constraint failed")
        self.assertFalse(self.db.in_transaction())
        self.assertTrue(self.db.is_active)
        stored = self.read_users()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].password_hash, original_hash)
        create_user(self.db, "next_user", self.password)
        self.assertEqual(len(self.read_users()), 2)

    def test_other_unique_violation_is_save_failure(self):
        """다른 컬럼의 UNIQUE 오류를 사용자명 중복과 구분"""
        original = create_user(self.db, "original_user", self.password)
        original_hash = original.password_hash
        # 테스트 DB에만 추가한 별도 UNIQUE 제약
        self.db.execute(text("CREATE UNIQUE INDEX test_hash_unique ON users(password_hash)"))
        self.db.commit()
        with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
            with patch.object(auth, "hash_password", return_value=original_hash):
                with patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                    with self.assertRaises(UserSaveError) as raised:
                        create_user(
                            self.db, "user_123", self.password, request_id=self.request_id
                        )
                    rollback.assert_called_once()

        self.assertEqual(str(raised.exception), "Failed to save user")
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertIn("reason=db_error", captured.output[0])
        self.assertNotIn("db_save_success", "\n".join(captured.output))
        self.assert_safe_logs(captured, original_hash, "UNIQUE constraint failed")
        self.assertFalse(self.db.in_transaction())
        self.assertEqual(len(self.read_users()), 1)
        create_user(self.db, "next_user", self.password)
        self.assertEqual(len(self.read_users()), 2)

    def test_not_null_violation_is_save_failure(self):
        """NOT NULL 위반의 저장 실패 처리 및 Session 복구"""
        with patch.object(auth, "hash_password", return_value=None):
            self.assert_save_failure()
        self.assert_recovery()

    def test_failed_duplicate_lookup_rolls_back_without_hashing(self):
        """중복 조회 DB 오류의 rollback 및 해시 미생성"""
        failure = OperationalError("sensitive-sql", {}, Exception("private-db-error"))
        with patch.object(self.db, "scalar", side_effect=failure):
            with patch.object(auth, "hash_password") as hash_password:
                self.assert_save_failure()
                hash_password.assert_not_called()
        self.assert_recovery()

    def test_failed_flush_rolls_back_and_session_can_be_reused(self):
        """INSERT 실패의 rollback 및 후속 저장 확인"""
        def fail_insert(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT"):
                raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

        event.listen(self.engine, "before_cursor_execute", fail_insert)
        try:
            self.assert_save_failure()
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_insert)
        self.assert_recovery()

    def test_failed_commit_rolls_back_without_success_log(self):
        """commit 실패의 사용자 미저장 및 성공 로그 미발생"""
        def fail_commit(connection):
            raise OperationalError("sensitive-sql", {}, Exception("private-db-error"))

        event.listen(self.engine, "commit", fail_commit)
        try:
            self.assert_save_failure()
        finally:
            event.remove(self.engine, "commit", fail_commit)
        self.assert_recovery()

    def test_success_log_is_emitted_after_commit(self):
        """commit 완료 이후 성공 로그 발생 확인"""
        committed = []

        def after_commit(db):
            committed.append(True)

        event.listen(self.db, "after_commit", after_commit)
        try:
            original_info = auth.logger.info

            def log_after_commit(*args, **kwargs):
                self.assertEqual(committed, [True])
                original_info(*args, **kwargs)

            with self.assertLogs("app.services.auth", level=logging.INFO) as captured:
                with patch.object(auth.logger, "info", side_effect=log_after_commit):
                    create_user(self.db, "user_123", self.password)
        finally:
            event.remove(self.db, "after_commit", after_commit)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("db_save_success", captured.output[0])
        self.assertEqual(len(self.read_users()), 1)


if __name__ == "__main__":
    unittest.main()
