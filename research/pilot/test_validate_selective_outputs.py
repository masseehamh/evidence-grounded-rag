import json
import unittest

from validate_selective_outputs import assess, validate_batch


def response(**overrides):
    payload = {
        "decision": "preserve",
        "evidence_status": "supports_draft",
        "answer": "Paris",
        "supporting_source_ids": ["S1"],
        "contradicting_source_ids": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def model_input(**overrides):
    payload = {
        "input_id": "case-1",
        "draft_answer": "Paris",
        "passages": [
            {"source_id": "S1", "text": "Paris is the capital."},
            {"source_id": "S2", "text": "Unrelated passage."},
        ],
    }
    payload.update(overrides)
    return payload


def output(raw_response):
    return {"input_id": "case-1", "raw_response": raw_response}


class ValidateSelectiveOutputsTests(unittest.TestCase):
    def test_valid_response_has_no_issues(self):
        result = assess(output(response()), model_input())
        self.assertEqual(result["issue_count"], 0)
        self.assertEqual(result["issue_codes"], "")
        self.assertEqual(result["answer"], "Paris")

    def test_malformed_json_is_flagged(self):
        result = assess(output('{"decision":'), model_input())
        self.assertIn("invalid_json", result["issue_codes"])
        self.assertGreater(result["issue_count"], 0)

    def test_missing_fields_are_reported(self):
        result = assess(output('{"decision":"abstain"}'), model_input())
        self.assertIn("missing_fields:", result["issue_codes"])

    def test_invalid_decision_and_evidence_status_are_reported(self):
        result = assess(
            output(response(decision="guess", evidence_status="maybe")),
            model_input(),
        )
        self.assertIn("invalid_decision", result["issue_codes"])
        self.assertIn("invalid_evidence_status", result["issue_codes"])

    def test_non_string_answer_is_reported(self):
        result = assess(output(response(answer=42)), model_input())
        self.assertIn("answer_not_string", result["issue_codes"])

    def test_source_id_arrays_must_be_string_arrays(self):
        result = assess(
            output(response(supporting_source_ids="S1", contradicting_source_ids=[2])),
            model_input(),
        )
        self.assertIn("supporting_ids_not_string_array", result["issue_codes"])
        self.assertIn("contradicting_ids_not_string_array", result["issue_codes"])

    def test_duplicate_source_ids_are_reported(self):
        result = assess(
            output(response(supporting_source_ids=["S1", "S1"])),
            model_input(),
        )
        self.assertIn("duplicate_supporting_id", result["issue_codes"])

    def test_overlapping_source_arrays_are_reported(self):
        result = assess(
            output(response(supporting_source_ids=["S1"], contradicting_source_ids=["S1"])),
            model_input(),
        )
        self.assertIn("source_arrays_overlap", result["issue_codes"])

    def test_unknown_source_ids_are_reported(self):
        result = assess(
            output(response(supporting_source_ids=["S9"])),
            model_input(),
        )
        self.assertIn("unknown_source_id", result["issue_codes"])

    def test_conflicting_status_requires_both_source_relations(self):
        result = assess(
            output(response(evidence_status="conflicting",
                            supporting_source_ids=["S1"],
                            contradicting_source_ids=[])),
            model_input(),
        )
        self.assertIn("status_conflicting_without_both_relations", result["issue_codes"])

    def test_supports_draft_cannot_have_contradicting_ids(self):
        result = assess(
            output(response(evidence_status="supports_draft",
                            supporting_source_ids=["S1"],
                            contradicting_source_ids=["S2"])),
            model_input(),
        )
        self.assertIn("status_supports_but_contradiction_ids_present", result["issue_codes"])

    def test_contradicts_draft_cannot_have_supporting_ids(self):
        result = assess(
            output(response(evidence_status="contradicts_draft",
                            supporting_source_ids=["S1"],
                            contradicting_source_ids=["S2"])),
            model_input(),
        )
        self.assertIn("status_contradicts_but_support_ids_present", result["issue_codes"])

    def test_irrelevant_status_cannot_have_answer_bearing_ids(self):
        result = assess(
            output(response(evidence_status="irrelevant",
                            supporting_source_ids=["S1"],
                            contradicting_source_ids=[])),
            model_input(),
        )
        self.assertIn("status_irrelevant_but_answer_bearing_ids_present", result["issue_codes"])

    def test_correct_decision_with_unchanged_answer_is_flagged(self):
        result = assess(
            output(response(decision="correct", answer="Paris")),
            model_input(draft_answer="Paris"),
        )
        self.assertIn("decision_correct_but_answer_unchanged", result["issue_codes"])

    def test_preserve_decision_without_draft_value_is_flagged(self):
        result = assess(
            output(response(decision="preserve", answer="Rome")),
            model_input(draft_answer="Paris"),
        )
        self.assertIn("decision_preserve_but_draft_value_not_visible", result["issue_codes"])

    def test_qualify_with_empty_answer_is_flagged(self):
        result = assess(
            output(response(decision="qualify", answer="")),
            model_input(),
        )
        self.assertIn("decision_qualify_with_empty_answer", result["issue_codes"])

    def test_abstain_with_nonempty_answer_is_flagged_for_review(self):
        result = assess(
            output(response(decision="abstain", answer="Paris")),
            model_input(),
        )
        self.assertIn("decision_abstain_with_nonempty_answer_review", result["issue_codes"])

    def test_empty_abstention_is_not_misreported_as_missing_answer(self):
        result = assess(
            output(response(decision="abstain", evidence_status="insufficient",
                            answer="", supporting_source_ids=[],
                            contradicting_source_ids=[])),
            model_input(),
        )
        self.assertEqual(result["answer"], "")
        self.assertEqual(result["parser_status"], "valid_json_empty_answer")
        self.assertEqual(result["issue_count"], 0)


class ValidateBatchIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.inputs = [
            {"input_id": "case-1", "draft_answer": "Paris", "passages": []},
            {"input_id": "case-2", "draft_answer": "Rome", "passages": []},
        ]
        self.outputs = [
            {"input_id": "case-1", "raw_response": response()},
            {"input_id": "case-2", "raw_response": response()},
        ]

    def test_complete_one_to_one_batch_is_accepted(self):
        by_id = validate_batch(self.inputs, self.outputs)
        self.assertEqual(set(by_id), {"case-1", "case-2"})

    def test_duplicate_input_ids_are_rejected(self):
        inputs = self.inputs + [dict(self.inputs[0])]
        with self.assertRaisesRegex(ValueError, "Input IDs must be unique"):
            validate_batch(inputs, self.outputs)

    def test_duplicate_output_ids_are_rejected(self):
        outputs = self.outputs + [dict(self.outputs[0])]
        with self.assertRaisesRegex(ValueError, "Duplicate output input_id"):
            validate_batch(self.inputs, outputs)

    def test_missing_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing output.*case-2"):
            validate_batch(self.inputs, self.outputs[:1])

    def test_unknown_output_input_id_is_rejected(self):
        outputs = [
            self.outputs[0],
            {"input_id": "case-unknown", "raw_response": response()},
        ]
        with self.assertRaisesRegex(ValueError, "unknown input_id: case-unknown"):
            validate_batch(self.inputs, outputs)

    def test_empty_output_batch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "No outputs to validate"):
            validate_batch(self.inputs, [])

    def test_input_without_input_id_is_rejected(self):
        inputs = [
            dict(self.inputs[0]),
            {"draft_answer": "Rome", "passages": []},
        ]
        with self.assertRaisesRegex(ValueError, "Every input must contain input_id"):
            validate_batch(inputs, self.outputs)


if __name__ == "__main__":
    unittest.main()
