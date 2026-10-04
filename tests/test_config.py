import logging
import os
import unittest
from unittest.mock import patch

from app import config


class AISettingsTests(unittest.TestCase):
    def read(self, **environment):
        with patch.dict(os.environ, environment, clear=True):
            return config.get_ai_settings()

    def test_missing_environment_uses_defaults(self):
        settings = self.read()
        self.assertEqual(settings.api_key, "")
        self.assertEqual(settings.api_url, "https://copa.codyssey.kr/v1/chat/completions")
        self.assertEqual(settings.model, "gpt-5-mini")
        self.assertEqual(settings.timeout, 30.0)

    def test_blank_environment_uses_defaults(self):
        settings = self.read(AI_API_URL="", AI_MODEL="  ", AI_TIMEOUT="")
        self.assertEqual(settings.api_url, config.DEFAULT_AI_API_URL)
        self.assertEqual(settings.model, config.DEFAULT_AI_MODEL)
        self.assertEqual(settings.timeout, config.DEFAULT_AI_TIMEOUT)

    def test_environment_overrides_defaults(self):
        settings = self.read(
            CODYSSEY_API_KEY=" test-key ",
            AI_API_URL="https://example.test/v1/chat/completions",
            AI_MODEL="another-model",
            AI_TIMEOUT="12.5",
        )
        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.api_url, "https://example.test/v1/chat/completions")
        self.assertEqual(settings.model, "another-model")
        self.assertEqual(settings.timeout, 12.5)

    def test_invalid_timeout_falls_back_with_warning(self):
        for value in ("abc", "0", "-5", "nan", "inf"):
            with self.subTest(value=value):
                with self.assertLogs("app.config", level="WARNING") as logs:
                    settings = self.read(AI_TIMEOUT=value)
                self.assertEqual(settings.timeout, config.DEFAULT_AI_TIMEOUT)
                self.assertIn("invalid AI_TIMEOUT", logs.output[0])

    def test_api_key_is_hidden_from_repr(self):
        settings = self.read(CODYSSEY_API_KEY="test-key")
        self.assertNotIn("test-key", repr(settings))

    def test_settings_are_immutable(self):
        settings = self.read()
        with self.assertRaises(AttributeError):
            settings.model = "changed"


class LoggingTests(unittest.TestCase):
    def setUp(self):
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level
        self.addCleanup(root.setLevel, level)
        self.addCleanup(setattr, root, "handlers", handlers)
        root.handlers = []

    def test_info_events_are_emitted_with_level_and_logger_name(self):
        config.configure_logging()
        root = logging.getLogger()
        self.assertTrue(logging.getLogger("app.services.ai").isEnabledFor(logging.INFO))
        record = logging.LogRecord("app.services.ai", logging.INFO, "", 0, "ai_call_start", None, None)
        line = root.handlers[0].format(record)
        self.assertIn("INFO app.services.ai ai_call_start", line)
