import json
import sys
import tempfile
import unittest
from pathlib import Path

# Support both running this file directly and unittest discovery from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_outputs import evaluate_row, read_jsonl, summarize


class EvaluateOutputsTests(unittest.TestCase):
    def test_correction_success_and_harmful_change_are_distinguished(self):
        successful = evaluate_row({
            "case_id": "1", "condition": "clean", "strategy": "correction",
            "initial_answer": "Lyon", "final_answer": "Paris",
            "gold_answers": ["Paris"], "foil_answers": ["Lyon"],
        })
        harmful = evaluate_row({
            "case_id": "2", "condition": "misleading", "strategy": "correction",
            "initial_answer": "Paris", "final_answer": "Lyon",
            "gold_answers": ["Paris"], "foil_answers": ["Lyon"],
        })
        self.assertEqual(successful["correction_success"], 1)
        self.assertEqual(successful["harmful_change"], 0)
        self.assertEqual(harmful["correction_success"], 0)
        self.assertEqual(harmful["harmful_change"], 1)
        self.assertEqual(harmful["foil_adoption"], 1)

    def test_alias_mention_is_diagnostic_not_exact_match(self):
        row = evaluate_row({
            "case_id": "3", "condition": "misleading", "strategy": "correction",
            "initial_answer": "Canberra",
            "final_answer": "The evidence contradicts the draft. The capital of Australia is Canberra.",
            "gold_answers": ["Canberra"],
            "foil_answers": ["Sydney"],
        })
        self.assertEqual(row["final_exact_match"], 0)
        self.assertEqual(row["final_gold_alias_mentioned"], 1)
        self.assertEqual(row["final_foil_alias_mentioned"], 0)
        self.assertEqual(row["manual_factuality_label"], "")
        self.assertEqual(row["manual_review_notes"], "")

    def test_summary_denominators_use_initial_state(self):
        rows = [
            evaluate_row({"case_id": "1", "condition": "clean", "strategy": "x",
                          "initial_answer": "Paris", "final_answer": "Paris",
                          "gold_answers": ["Paris"]}),
            evaluate_row({"case_id": "2", "condition": "clean", "strategy": "x",
                          "initial_answer": "Rome", "final_answer": "Paris",
                          "gold_answers": ["Paris"]}),
        ]
        summary = summarize(rows)[0]
        self.assertEqual(summary["n"], 2)
        self.assertEqual(summary["correction_success_count"], 1)
        self.assertEqual(summary["preserved_correct_count"], 1)
        self.assertEqual(summary["initial_accuracy"], "0.500000")
        self.assertEqual(summary["final_accuracy"], "1.000000")

    def test_jsonl_reader(self):
        row = {
            "case_id": "1", "condition": "no_retrieval", "strategy": "baseline",
            "initial_answer": "Paris", "final_answer": "Paris",
            "gold_answers": ["Paris"]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outputs.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual(len(read_jsonl(path)), 1)

    def test_unicode_subscript_in_chemical_formula_matches_ascii(self):
        row = evaluate_row({
            "case_id": "chem_1", "condition": "clean", "strategy": "baseline",
            "initial_answer": "H₂O", "final_answer": "H₂O",
            "gold_answers": ["H2O"],
        })
        self.assertEqual(row["initial_exact_match"], 1)
        self.assertEqual(row["final_exact_match"], 1)


if __name__ == "__main__":
    unittest.main()
