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

    def test_invalid_output_is_requested_once_more(self):
        with patch.object(ai, "request_chat_completion", side_effect=[output("ANGER"), output("STRESS")]) as completion:
            with self.assertLogs("app.services.ai", level="ERROR") as logs:
                result = ai.request_prescription(self.MESSAGES, user_id=12, request_id="abc123")
        self.assertEqual(result["keyword"], "STRESS")
        self.assertEqual(completion.call_count, 2)
        self.assertIn("reason=invalid_prescription attempt=1", logs.output[0])

    def test_invalid_output_twice_fails_and_logs_without_content(self):
        with patch.object(ai, "request_chat_completion", return_value="private answer") as completion:
            with self.assertLogs("app.services.ai", level="ERROR") as logs:
                with self.assertRaises(ai.AICallError):
                    ai.request_prescription(self.MESSAGES, user_id=12, request_id="abc123")
        self.assertEqual(completion.call_count, 2)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("ai_call_failure user_id=12 request_id=abc123 reason=invalid_prescription attempt=2", logs.output[1])
        self.assertNotIn("private", "\n".join(logs.output))

    def test_call_errors_pass_through(self):
        for error in (ai.AITimeoutError("timeout"), ai.AICallError("http_status_500")):
            with self.subTest(error=str(error)):
                with patch.object(ai, "request_chat_completion", side_effect=error) as completion:
                    with self.assertRaises(type(error)):
                        ai.request_prescription(self.MESSAGES)
                self.assertEqual(completion.call_count, 1)


class PrescriptionMessageTidyTests(unittest.TestCase):
    def test_missing_space_after_sentence_is_restored(self):
        result = ai.parse_prescription(output(message="많이 애쓰셨어요.오늘은 쉬어도 돼요."))
        self.assertEqual(result["message"], "많이 애쓰셨어요. 오늘은 쉬어도 돼요.")

    def test_numbers_and_final_punctuation_are_untouched(self):
        result = ai.parse_prescription(output(message="자살예방상담전화 109에 연락해 주세요."))
        self.assertEqual(result["message"], "자살예방상담전화 109에 연락해 주세요.")

    def test_doubled_polite_ending_is_reduced(self):
        result = ai.parse_prescription(output(message="오래 버텨오셨네요요. 이제는 쉬어도 괜찮아요요"))
        self.assertEqual(result["message"], "오래 버텨오셨네요. 이제는 쉬어도 괜찮아요")
