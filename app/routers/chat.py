from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.chat import ChatRequest, ChatResponse, PrescriptionResponse
from app.services.ai import (
    AICallError,
    AITimeoutError,
    build_chat_messages,
    build_prescription_messages,
    request_chat_completion,
    request_prescription,
)
from app.services.chats import ChatSaveError, get_recent_chats, save_chat


class BadRequestRoute(APIRoute):
    """Answer request validation failures on this router with HTTP 400 and a plain detail."""

    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def bad_request_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(status_code=400, detail="Invalid message") from None

        return bad_request_handler


router = APIRouter(prefix="/api", route_class=BadRequestRoute)


@router.post("/chat", response_model=ChatResponse)
def create_chat(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # rollback 이후 사용자 재조회 방지를 위한 ID 선확보
    user_id = user.id
    messages = build_chat_messages(get_recent_chats(db, user_id), payload.message)
    # End the read transaction so no database lock is held while waiting for the AI.
    db.rollback()
    try:
        answer = request_chat_completion(
            messages,
            user_id=user_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except AITimeoutError:
        raise HTTPException(status_code=504, detail="AI response timed out") from None
    except AICallError:
        raise HTTPException(status_code=502, detail="AI request failed") from None
    # The chat bubble shows one paragraph; line breaks from the model are folded into spaces.
    answer = " ".join(answer.split())
    try:
        return save_chat(db, user_id, payload.message, answer)
    except ChatSaveError:
        raise HTTPException(status_code=500, detail="Failed to save chat") from None


@router.post("/prescription", response_model=PrescriptionResponse)
def create_prescription(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # rollback 이후 사용자 재조회 방지를 위한 ID 선확보
    user_id = user.id
    recent_chats = get_recent_chats(db, user_id)
    messages = build_prescription_messages(recent_chats)
    db.rollback()
    if not recent_chats:
        raise HTTPException(status_code=400, detail="No chats to prescribe")
    try:
        return request_prescription(
            messages,
            user_id=user_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except AITimeoutError:
        raise HTTPException(status_code=504, detail="AI response timed out") from None
    except AICallError:
        raise HTTPException(status_code=502, detail="AI request failed") from None
