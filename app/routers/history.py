import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.chats import list_user_chats

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    created_at: datetime


class HistoryResponse(BaseModel):
    chats: list[ChatHistory]


@router.get("/api/me/chats", response_model=HistoryResponse)
def get_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info("request_received path=/api/me/chats user_id=%s", user.id)
    return {"chats": list_user_chats(db, user.id)}
