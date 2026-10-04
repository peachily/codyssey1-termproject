import logging
import time

import requests

from app.config import AISettings, get_ai_settings

logger = logging.getLogger(__name__)


class AICallError(Exception):
    """The AI API call failed or returned an unusable response."""


class AITimeoutError(AICallError):
    """The AI API did not respond within the configured timeout."""


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
