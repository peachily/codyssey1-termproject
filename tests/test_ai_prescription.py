import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import ai


def output(keyword="ANXIETY", message="오늘은 여기까지만 해도 괜찮아요.", **extra):
    return json.dumps({"keyword": keyword, "message": message, **extra}, ensure_ascii=False)


class PrescriptionMessageTests(unittest.TestCase):
    def test_conversation_is_sent_as_one_transcript_in_order(self):
        chats = [SimpleNamespace(question=f"Q{number}", answer=f"A{number}") for number in range(2)]
        messages = ai.build_prescription_messages(chats)
        self.assertEqual(messages[0], {"role": "system", "content": ai.PRESCRIPTION_PROMPT})
        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        self.assertTrue(messages[1]["content"].endswith("손님: Q0\n주인: A0\n손님: Q1\n주인: A1"))

    def test_prompt_lists_every_keyword_and_keeps_safety_rules(self):
        for phrase in (*ai.PRESCRIPTION_COLORS, "자살예방상담전화 109", "실제 약", "JSON"):
            self.assertIn(phrase, ai.PRESCRIPTION_PROMPT)


class PrescriptionParsingTests(unittest.TestCase):
    def test_each_keyword_maps_to_fixed_color(self):
        expected = {"ANXIETY": "BLUE", "SADNESS": "PURPLE", "LONELINESS": "PINK", "STRESS": "GREEN", "EXHAUSTION": "YELLOW"}
        self.assertEqual(ai.PRESCRIPTION_COLORS, expected)
        for keyword, color in expected.items():
            with self.subTest(keyword=keyword):
                self.assertEqual(
                    ai.parse_prescription(output(keyword)),
                    {"keyword": keyword, "color": color, "message": "오늘은 여기까지만 해도 괜찮아요."},
                )

    def test_color_from_ai_is_ignored(self):
        self.assertEqual(ai.parse_prescription(output("SADNESS", color="RED"))["color"], "PURPLE")

    def test_wrapped_or_untidy_output_is_accepted(self):
        cases = {
            "code fence": f"```json\n{output()}\n```",
            "surrounding text": f"처방입니다.\n{output()}\n편히 쉬세요.",
            "lowercase keyword": output(" anxiety "),
            "message whitespace": output(message="  오늘은 여기까지만\n해도   괜찮아요. "),
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    ai.parse_prescription(content),
                    {"keyword": "ANXIETY", "color": "BLUE", "message": "오늘은 여기까지만 해도 괜찮아요."},
                )

    def test_invalid_output_raises_call_error(self):
        invalid = {
            "not json": "오늘은 푹 쉬세요.",
            "broken json": '{"keyword": "ANXIETY", "message": ',
            "list": '["ANXIETY", "괜찮아요."]',
            "missing keyword": '{"message": "괜찮아요."}',
            "missing message": '{"keyword": "ANXIETY"}',
            "unknown keyword": output("ANGER"),
            "color as keyword": output("BLUE"),
            "null keyword": output(None),
            "blank message": output(message="   "),
            "non-string message": output(message=123),
        }
        for name, content in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(ai.AICallError) as raised:
                    ai.parse_prescription(content)
                self.assertNotIsInstance(raised.exception, ai.AITimeoutError)


class PrescriptionRequestTests(unittest.TestCase):
    MESSAGES = [{"role": "user", "content": "private conversation"}]

    def test_valid_output_returns_prescription(self):
        with patch.object(ai, "request_chat_completion", return_value=output("STRESS")) as completion:
            result = ai.request_prescription(self.MESSAGES, user_id=12, request_id="abc123")
        self.assertEqual(result["color"], "GREEN")
        completion.assert_called_once_with(self.MESSAGES, user_id=12, request_id="abc123")

    def test_invalid_output_logs_failure_without_content(self):
        with patch.object(ai, "request_chat_completion", return_value="private answer"):
            with self.assertLogs("app.services.ai", level="ERROR") as logs:
                with self.assertRaises(ai.AICallError):
                    ai.request_prescription(self.MESSAGES, user_id=12, request_id="abc123")
        self.assertIn("ai_call_failure user_id=12 request_id=abc123 reason=invalid_prescription", logs.output[0])
        self.assertNotIn("private", "\n".join(logs.output))

    def test_call_errors_pass_through(self):
        for error in (ai.AITimeoutError("timeout"), ai.AICallError("http_status_500")):
            with self.subTest(error=str(error)):
                with patch.object(ai, "request_chat_completion", side_effect=error):
                    with self.assertRaises(type(error)):
                        ai.request_prescription(self.MESSAGES)
