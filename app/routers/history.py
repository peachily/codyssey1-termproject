import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.chat import ChatHistoryResponse
from app.services.chats import list_user_chats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/me", tags=["history"])


@router.get("/chats", response_model=ChatHistoryResponse)
def history(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = user.id
    try:
        return {"chats": list_user_chats(db, user_id)}
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "db_read_failure user_id=%s request_id=%s",
            user_id, getattr(request.state, "request_id", None),
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve chats") from None
