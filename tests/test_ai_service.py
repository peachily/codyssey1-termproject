import os
import unittest
from unittest.mock import Mock, patch

import requests

from app.services import ai

ENVIRONMENT = {
    "CODYSSEY_API_KEY": "test-key",
    "AI_API_URL": "https://example.test/v1/chat/completions",
    "AI_MODEL": "test-model",
    "AI_TIMEOUT": "7",
}
MESSAGES = [{"role": "user", "content": "private question"}]


def api_response(payload=None, status_code=200):
    response = Mock(status_code=status_code, ok=status_code < 400)
    if isinstance(payload, Exception):
        response.json.side_effect = payload
    else:
        response.json.return_value = payload
    return response


def completion(content="private answer"):
    return api_response({"choices": [{"message": {"role": "assistant", "content": content}}]})


class ChatCompletionTests(unittest.TestCase):
    def call(self, result, environment=ENVIRONMENT, **kwargs):
        """Run one AI call against a mocked HTTP result and keep the mock for assertions."""
        side_effect = result if isinstance(result, Exception) else None
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(ai.requests, "post", return_value=result, side_effect=side_effect) as self.post:
                return ai.request_chat_completion(MESSAGES, **kwargs)

    def test_success_returns_answer_and_sends_contract_request(self):
        answer = self.call(completion())
        self.assertEqual(answer, "private answer")
        self.post.assert_called_once_with(
            "https://example.test/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={"model": "test-model", "messages": MESSAGES},
            timeout=7.0,
        )

    def test_timeout_raises_timeout_error(self):
        for error in (requests.ReadTimeout(), requests.ConnectTimeout()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ai.AITimeoutError):
                    self.call(error)

    def test_other_failures_raise_call_error_but_not_timeout(self):
        failures = {
            "connection": requests.ConnectionError(),
            "http 401": api_response(status_code=401),
            "http 500": api_response(status_code=500),
            "invalid json": api_response(ValueError("not json")),
            "missing choices": api_response({}),
            "empty choices": api_response({"choices": []}),
            "null message": api_response({"choices": [{"message": None}]}),
            "non-string content": completion(content=None),
            "blank content": completion(content="   "),
        }
        for name, result in failures.items():
            with self.subTest(name=name):
                with self.assertRaises(ai.AICallError) as raised:
                    self.call(result)
                self.assertNotIsInstance(raised.exception, ai.AITimeoutError)

    def test_missing_api_key_fails_without_sending_request(self):
        with self.assertRaises(ai.AICallError):
            self.call(completion(), environment={})
        self.post.assert_not_called()

    def test_success_logs_start_and_success_with_trace_ids(self):
        with self.assertLogs("app.services.ai", level="INFO") as logs:
            self.call(completion(), user_id=12, request_id="abc123")
        self.assertEqual(len(logs.output), 2)
        self.assertIn("ai_call_start user_id=12 request_id=abc123 model=test-model", logs.output[0])
        self.assertRegex(logs.output[1], r"ai_call_success user_id=12 request_id=abc123 latency_ms=\d+$")

    def test_failure_logs_reason_without_success(self):
        cases = {
            "timeout": requests.ReadTimeout(),
            "connection_error": requests.ConnectionError(),
            "http_status_502": api_response(status_code=502),
            "invalid_response": api_response({}),
        }
        for reason, result in cases.items():
            with self.subTest(reason=reason):
                with self.assertLogs("app.services.ai", level="INFO") as logs:
                    with self.assertRaises(ai.AICallError):
                        self.call(result, user_id=12, request_id="abc123")
                self.assertIn("ai_call_start", logs.output[0])
                self.assertIn(f"ai_call_failure user_id=12 request_id=abc123 reason={reason}", logs.output[1])
                self.assertNotIn("ai_call_success", "\n".join(logs.output))

    def test_logs_never_contain_api_key_or_conversation(self):
        results = (completion(), requests.ConnectionError("https://example.test test-key"), api_response(status_code=500))
        for result in results:
            with self.assertLogs("app.services.ai", level="INFO") as logs:
                try:
                    self.call(result)
                except ai.AICallError:
                    pass
            output = "\n".join(logs.output)
            for secret in ("test-key", "private question", "private answer"):
                self.assertNotIn(secret, output)
