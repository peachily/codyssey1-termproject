import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """세션 ID 타입·DB 사용자 확인 및 조회 오류 처리"""
    session = request.session
    user_id = session.get("user_id") if isinstance(session, dict) else None
    # bool을 정수 사용자 ID로 허용하지 않도록 정확한 타입 확인
    if type(user_id) is not int:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user = db.get(User, user_id)
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "auth_lookup_failure request_id=%s reason=db_error",
            getattr(request.state, "request_id", None),
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve user") from None

    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
