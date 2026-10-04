from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_MESSAGE_LENGTH = 2000


class ChatRequest(BaseModel):
    message: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH),
    ]


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    created_at: datetime
