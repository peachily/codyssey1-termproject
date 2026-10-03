import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Chat

logger = logging.getLogger(__name__)


class ChatSaveError(Exception):
    """The chat transaction could not be committed."""


def save_chat(db: Session, user_id: int, question: str, answer: str) -> Chat:
    chat = Chat(user_id=user_id, question=question, answer=answer)
    try:
        db.add(chat)
        db.flush()
        chat_id = chat.id
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("db_save_failure user_id=%s", user_id)
        raise ChatSaveError("Failed to save chat") from None
    logger.info("db_save_success user_id=%s chat_id=%s", user_id, chat_id)
    return chat


def list_user_chats(db: Session, user_id: int) -> list[Chat]:
    statement = select(Chat).where(Chat.user_id == user_id).order_by(Chat.created_at.desc(), Chat.id.desc())
    return list(db.scalars(statement))


def get_recent_chats(db: Session, user_id: int) -> list[Chat]:
    statement = select(Chat).where(Chat.user_id == user_id).order_by(Chat.created_at.desc(), Chat.id.desc()).limit(5)
    return list(reversed(db.scalars(statement).all()))
