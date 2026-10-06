import logging
import sqlite3

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User

logger = logging.getLogger(__name__)

# Argon2로 비밀번호를 해시하고 검증할 공통 도구
_password_hasher = PasswordHash((Argon2Hasher(),))


class DuplicateUsernameError(Exception):
    """사용자명 중복"""


class UserSaveError(Exception):
    """사용자 저장 실패"""


def hash_password(password: str) -> str:
    """비밀번호 원문을 유지한 채 저장용 Argon2 해시를 생성"""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """입력 비밀번호를 검증하며 인식할 수 없는 해시는 인증 실패로 처리"""
    try:
        return _password_hasher.verify(password, password_hash)
    except UnknownHashError:
        return False


def _is_duplicate_username(error: IntegrityError) -> bool:
    """SQLite 사용자명 UNIQUE 위반 확인"""
    return (
        isinstance(error.orig, sqlite3.IntegrityError)
        and getattr(error.orig, "sqlite_errorcode", None)
        == sqlite3.SQLITE_CONSTRAINT_UNIQUE
        and str(error.orig) == "UNIQUE constraint failed: users.username"
    )


def create_user(
    db: Session,
    username: str,
    password: str,
    *,
    request_id: str | None = None,
) -> User:
    """검증된 입력으로 사용자 저장 및 중복·DB 실패 처리"""
    username = username.strip()
    try:
        existing_id = db.scalar(select(User.id).where(User.username == username))
        if existing_id is not None:
            db.rollback()
            logger.warning(
                "db_save_failure request_id=%s reason=duplicate_username", request_id
            )
            raise DuplicateUsernameError("Username already exists")

        user = User(username=username, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        user_id = user.id
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        # 사전 조회 이후의 가입 충돌도 DB 제약으로 확인
        if isinstance(error, IntegrityError) and _is_duplicate_username(error):
            logger.warning(
                "db_save_failure request_id=%s reason=duplicate_username", request_id
            )
            raise DuplicateUsernameError("Username already exists") from None
        logger.error("db_save_failure request_id=%s reason=db_error", request_id)
        raise UserSaveError("Failed to save user") from None

    logger.info("db_save_success request_id=%s user_id=%s", request_id, user_id)
    return user
