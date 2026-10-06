from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute


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
