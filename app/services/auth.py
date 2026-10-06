from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

# Argon2로 비밀번호를 해시하고 검증할 공통 도구
_password_hasher = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """비밀번호 원문을 유지한 채 저장용 Argon2 해시를 생성"""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """입력 비밀번호를 검증하며 인식할 수 없는 해시는 인증 실패로 처리"""
    try:
        return _password_hasher.verify(password, password_hash)
    except UnknownHashError:
        return False
