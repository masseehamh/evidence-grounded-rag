import json
import unittest

from controlled_output_utils import extract_answer, parse_selective_json


class ParseSelectiveJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        parsed, status = parse_selective_json('{"answer":"Paris"}')
        self.assertEqual(parsed, {"answer": "Paris"})
        self.assertEqual(status, "valid_json")

    def test_parses_json_markdown_fence_case_insensitively(self):
        parsed, status = parse_selective_json('```JSON\n{"answer":"Paris"}\n```')
        self.assertEqual(parsed, {"answer": "Paris"})
        self.assertEqual(status, "valid_json_fenced")

    def test_rejects_malformed_json(self):
        parsed, status = parse_selective_json('{"answer":')
        self.assertIsNone(parsed)
        self.assertEqual(status, "invalid_json")

    def test_rejects_non_object_json(self):
        parsed, status = parse_selective_json('["Paris"]')
        self.assertIsNone(parsed)
        self.assertEqual(status, "invalid_json_not_object")

    def test_missing_answer_is_not_treated_as_empty_answer(self):
        response = '{"decision":"abstain"}'
        answer, status = extract_answer("selective_correction", response)
        self.assertEqual(answer, response)
        self.assertEqual(status, "invalid_json_missing_answer")

    def test_explicit_empty_answer_is_valid_empty_answer(self):
        answer, status = extract_answer(
            "selective_correction",
            '{"decision":"abstain","answer":""}',
        )
        self.assertEqual(answer, "")
        self.assertEqual(status, "valid_json_empty_answer")

    def test_whitespace_only_answer_is_valid_empty_answer(self):
        answer, status = extract_answer(
            "selective_correction",
            '{"decision":"abstain","answer":"   "}',
        )
        self.assertEqual(answer, "")
        self.assertEqual(status, "valid_json_empty_answer")

    def test_non_string_answer_is_not_accepted_as_an_answer(self):
        response = '{"answer":123}'
        answer, status = extract_answer("selective_correction", response)
        self.assertEqual(answer, response)
        self.assertEqual(status, "invalid_json_missing_answer")

    def test_non_selective_strategy_returns_plain_text(self):
        answer, status = extract_answer("baseline", "  Paris  ")
        self.assertEqual(answer, "Paris")
        self.assertEqual(status, "not_applicable")

    def test_extracts_nonempty_answer_and_trims_outer_whitespace(self):
        answer, status = extract_answer(
            "selective_correction",
            '{"answer":"  Paris  "}',
        )
        self.assertEqual(answer, "Paris")
        self.assertEqual(status, "valid_json")


if __name__ == "__main__":
    unittest.main()
