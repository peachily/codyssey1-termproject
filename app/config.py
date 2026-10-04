import logging
import math
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_AI_API_URL = "https://copa.codyssey.kr/v1/chat/completions"
DEFAULT_AI_MODEL = "gpt-5-mini"
DEFAULT_AI_TIMEOUT = 30.0


@dataclass(frozen=True)
class AISettings:
    api_key: str = field(repr=False)
    api_url: str
    model: str
    timeout: float


def _read(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _read_timeout() -> float:
    raw = _read("AI_TIMEOUT")
    if not raw:
        return DEFAULT_AI_TIMEOUT
    try:
        timeout = float(raw)
    except ValueError:
        timeout = 0.0
    if not math.isfinite(timeout) or timeout <= 0:
        logger.warning("invalid AI_TIMEOUT, using default %s seconds", DEFAULT_AI_TIMEOUT)
        return DEFAULT_AI_TIMEOUT
    return timeout


def get_ai_settings() -> AISettings:
    """Read AI settings from the environment; blank values use the defaults."""
    return AISettings(
        api_key=_read("CODYSSEY_API_KEY"),
        api_url=_read("AI_API_URL") or DEFAULT_AI_API_URL,
        model=_read("AI_MODEL") or DEFAULT_AI_MODEL,
        timeout=_read_timeout(),
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
