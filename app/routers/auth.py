from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import AuthRequest, AuthUserResponse
from app.services.auth import DuplicateUsernameError, UserSaveError, create_user


class AuthValidationRoute(APIRoute):
    """인증 입력 검증 오류의 HTTP 400 변환"""

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def auth_request_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError:
                # 입력값 및 검증 오류 원문 미포함
                raise HTTPException(
                    status_code=400,
                    detail="Invalid username or password",
                ) from None

        return auth_request_handler


router = APIRouter(prefix="/api/auth", route_class=AuthValidationRoute)


@router.post("/signup", response_model=AuthUserResponse, status_code=201)
def signup(
    payload: AuthRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    """회원가입 및 사용자 저장 오류의 HTTP 응답 변환"""
    try:
        user = create_user(
            db,
            payload.username,
            payload.password,
            request_id=getattr(request.state, "request_id", None),
        )
    except DuplicateUsernameError:
        raise HTTPException(status_code=409, detail="Username already exists") from None
    except UserSaveError:
        raise HTTPException(status_code=500, detail="Failed to save user") from None

    return AuthUserResponse(id=user.id, username=user.username)
