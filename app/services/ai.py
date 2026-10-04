import json
import logging
import re
import time
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import requests

from app.config import AISettings, get_ai_settings
from app.models import Chat
from app.services.prompts import (
    PRESCRIPTION_PROMPT,
    STAGE_ASKING,
    STAGE_CLOSING,
    STAGE_OFFERING,
    STAGE_TEMPLATE,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

CONVERSATION_WINDOW = timedelta(hours=1)
SHARED_ENOUGH_LENGTH = 100
# An unusable prescription is requested once more; call failures and timeouts are not retried.
PRESCRIPTION_ATTEMPTS = 2

PRESCRIPTION_COLORS = {
    "ANXIETY": "BLUE",
    "SADNESS": "PURPLE",
    "LONELINESS": "PINK",
    "STRESS": "GREEN",
    "EXHAUSTION": "YELLOW",
}

class AICallError(Exception):
    """The AI API call failed or returned an unusable response."""


class AITimeoutError(AICallError):
    """The AI API did not respond within the configured timeout."""


def conversation_stage(turn: int, shared_length: int = 0) -> str:
    """Pick the guide for this turn; a long story moves to the offer before the third turn."""
    if turn >= 4:
        guide = STAGE_CLOSING
    elif turn == 3 or shared_length >= SHARED_ENOUGH_LENGTH:
        guide = STAGE_OFFERING
    else:
        guide = STAGE_ASKING
    return STAGE_TEMPLATE.format(turn=turn, guide=guide)


def build_chat_messages(
    recent_chats: Sequence[Chat], question: str, *, now: datetime | None = None
) -> list[dict[str, str]]:
    """Build the system prompt with the stage guide, the oldest-first recent Q/A and the current question."""
    since = (now or datetime.now(timezone.utc)) - CONVERSATION_WINDOW
    tonight = [chat.question for chat in recent_chats if chat.created_at >= since]
    stage = conversation_stage(len(tonight) + 1, sum(map(len, tonight)) + len(question))
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{stage}"}]
    for chat in recent_chats:
        messages.append({"role": "user", "content": chat.question})
        messages.append({"role": "assistant", "content": chat.answer})
    messages.append({"role": "user", "content": question})
    return messages


def build_prescription_messages(recent_chats: Sequence[Chat]) -> list[dict[str, str]]:
    """Send the conversation as one transcript so the model classifies it instead of continuing it."""
    lines = []
    for chat in recent_chats:
        lines.append(f"손님: {chat.question}")
        lines.append(f"주인: {chat.answer}")
    transcript = "\n".join(lines)
    return [
        {"role": "system", "content": PRESCRIPTION_PROMPT},
        {"role": "user", "content": f"아래는 손님과 나눈 대화입니다.\n\n{transcript}"},
    ]


def parse_prescription(content: str) -> dict[str, str]:
    """Validate the AI output and attach the fixed color; any color from the AI is ignored."""
    start, end = content.find("{"), content.rfind("}")
    try:
        data = json.loads(content[start:end + 1])
        keyword, message = data["keyword"], data["message"]
    except (ValueError, LookupError, TypeError):
        raise AICallError("invalid_prescription") from None
    if not isinstance(keyword, str) or not isinstance(message, str):
        raise AICallError("invalid_prescription")
    keyword = keyword.strip().upper()
    # Fold line breaks, restore a missing space after sentence punctuation and drop a doubled ending.
    message = " ".join(re.sub(r"([.!?])(?=[가-힣])", r"\1 ", message).split())
    message = re.sub(r"요요(?=[.,!?]|$)", "요", message)
    if keyword not in PRESCRIPTION_COLORS or not message:
        raise AICallError("invalid_prescription")
    return {"keyword": keyword, "color": PRESCRIPTION_COLORS[keyword], "message": message}


def request_prescription(
    messages: list[dict[str, str]],
    *,
    user_id: int | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    for attempt in range(1, PRESCRIPTION_ATTEMPTS + 1):
        content = request_chat_completion(messages, user_id=user_id, request_id=request_id)
        try:
            return parse_prescription(content)
        except AICallError as error:
            logger.error(
                "ai_call_failure user_id=%s request_id=%s reason=%s attempt=%d",
                user_id, request_id, error, attempt,
            )
            if attempt == PRESCRIPTION_ATTEMPTS:
                raise


def request_chat_completion(
    messages: list[dict[str, str]],
    *,
    user_id: int | None = None,
    request_id: str | None = None,
) -> str:
    settings = get_ai_settings()
    logger.info("ai_call_start user_id=%s request_id=%s model=%s", user_id, request_id, settings.model)
    started = time.perf_counter()
    try:
        answer = _post(settings, messages)
    except AICallError as error:
        # The error message is a short reason code, never the prompt, answer or API key.
        logger.error(
            "ai_call_failure user_id=%s request_id=%s reason=%s latency_ms=%d",
            user_id, request_id, error, _elapsed_ms(started),
        )
        raise
    logger.info(
        "ai_call_success user_id=%s request_id=%s latency_ms=%d",
        user_id, request_id, _elapsed_ms(started),
    )
    return answer


def _post(settings: AISettings, messages: list[dict[str, str]]) -> str:
    if not settings.api_key:
        raise AICallError("missing_api_key")
    try:
        response = requests.post(
            settings.api_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            json={"model": settings.model, "messages": messages},
            timeout=settings.timeout,
        )
    except requests.Timeout:
        raise AITimeoutError("timeout") from None
    except requests.RequestException:
        raise AICallError("connection_error") from None
    if not response.ok:
        raise AICallError(f"http_status_{response.status_code}")
    try:
        answer = response.json()["choices"][0]["message"]["content"]
    except (ValueError, LookupError, TypeError):
        raise AICallError("invalid_response") from None
    if not isinstance(answer, str) or not answer.strip():
        raise AICallError("invalid_response")
    return answer


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
