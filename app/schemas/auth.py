from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class AuthRequest(BaseModel):
    """회원가입·로그인 공통 입력 확인"""

    # 문자열 엄격 검증 및 오류 문구의 입력값 숨김
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)

    # 사용자명 앞뒤 공백 제거 및 형식 검증
    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=30,
            pattern=r"^[a-z0-9_]{3,30}$",
        ),
    ]

    # 비밀번호 원문 유지 및 객체 출력에서 숨김
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        """공백만 있는 비밀번호 차단"""
        if not value.strip():
            raise ValueError("Password must not be blank")
        return value


class AuthUserResponse(BaseModel):
    """인증 API의 사용자 식별 정보 응답"""

    id: int
    username: str
