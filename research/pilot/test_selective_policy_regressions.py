"""Policy-contract regression fixtures for the v0.5 selective-correction policy.

These tests do NOT call a model and do NOT assert that the existing v0.5 model
outputs pass. They verify that the validator accepts the expected target
structures for six reviewed cases. Semantic correctness still requires review
of the source passages and output content.
"""
from __future__ import annotations

import json
import unittest

from validate_selective_outputs import assess


CASES = [
    {
        "input_id": "msdev_0361",
        "draft_answer": "K56",
        "source_ids": ["S1", "S2"],
        "decision": "correct",
        "evidence_status": "contradicts_draft",
        "answer": "V84",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1", "S2"],
    },
    {
        "input_id": "msdev_0478",
        "draft_answer": "LM-35",
        "source_ids": ["S1", "S2"],
        "decision": "correct",
        "evidence_status": "contradicts_draft",
        "answer": "CM-28",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1"],
    },
    {
        "input_id": "msdev_0205",
        "draft_answer": "violet",
        "source_ids": ["S1"],
        "decision": "correct",
        "evidence_status": "contradicts_draft",
        "answer": "amber",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1"],
    },
    {
        "input_id": "msdev_0134",
        "draft_answer": "violet",
        "source_ids": ["S1", "S2"],
        "decision": "correct",
        "evidence_status": "contradicts_draft",
        "answer": "amber",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1", "S2"],
    },
    {
        "input_id": "msdev_0224",
        "draft_answer": "GH-17",
        "source_ids": ["S1", "S2"],
        "decision": "correct",
        "evidence_status": "contradicts_draft",
        "answer": "RT-71",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1", "S2"],
    },
    {
        "input_id": "msdev_0311",
        "draft_answer": "853",
        "source_ids": ["S1"],
        "decision": "qualify",
        "evidence_status": "contradicts_draft",
        "answer": "The draft answer 853 is unverified. Source S1 reports 143, and the available lower-tier evidence does not resolve which value is correct.",
        "supporting_source_ids": [],
        "contradicting_source_ids": ["S1"],
    },
]


def make_input(case):
    return {
        "input_id": case["input_id"],
        "draft_answer": case["draft_answer"],
        "passages": [{"source_id": source_id, "text": "Fixture passage."}
                     for source_id in case["source_ids"]],
    }


def make_output(case):
    payload = {
        "decision": case["decision"],
        "evidence_status": case["evidence_status"],
        "answer": case["answer"],
        "supporting_source_ids": case["supporting_source_ids"],
        "contradicting_source_ids": case["contradicting_source_ids"],
    }
    return {
        "input_id": case["input_id"],
        "raw_response": json.dumps(payload),
    }


class SelectivePolicyContractRegressionTests(unittest.TestCase):
    def test_expected_target_structures_pass_validator(self):
        """Each policy target must satisfy the current output contract."""
        for case in CASES:
            with self.subTest(input_id=case["input_id"]):
                result = assess(make_output(case), make_input(case))
                self.assertEqual(result["issue_count"], 0, result["issue_codes"])
                self.assertEqual(result["decision"], case["decision"])
                self.assertEqual(result["evidence_status"], "contradicts_draft")

    def test_one_sided_draft_contradiction_is_not_source_conflict(self):
        """A single source contradicting the draft is not source-source conflict."""
        for case in CASES:
            with self.subTest(input_id=case["input_id"]):
                self.assertEqual(case["evidence_status"], "contradicts_draft")
                self.assertTrue(case["contradicting_source_ids"])
                self.assertEqual(case["supporting_source_ids"], [])

    def test_only_lower_tier_case_qualifies_instead_of_unqualified_correction(self):
        case = next(case for case in CASES if case["input_id"] == "msdev_0311")
        self.assertEqual(case["decision"], "qualify")
        self.assertIn("853", case["answer"])
        self.assertIn("143", case["answer"])

    def test_higher_tier_cases_use_correction_target(self):
        for case in CASES:
            if case["input_id"] == "msdev_0311":
                continue
            with self.subTest(input_id=case["input_id"]):
                self.assertEqual(case["decision"], "correct")
                self.assertNotEqual(case["answer"].casefold(), case["draft_answer"].casefold())


if __name__ == "__main__":
    unittest.main()
