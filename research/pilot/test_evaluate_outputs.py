import json
import sys
import tempfile
import unittest
from pathlib import Path

# Support both running this file directly and unittest discovery from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_outputs import (
    evaluate_row,
    merge_manual_reviews,
    read_jsonl,
    read_manual_reviews,
    summarize,
)


class EvaluateOutputsTests(unittest.TestCase):
    def test_correction_success_and_exact_match_loss_are_distinguished(self):
        successful = evaluate_row({
            "case_id": "1", "condition": "clean", "strategy": "correction",
            "initial_answer": "Lyon", "final_answer": "Paris",
            "gold_answers": ["Paris"], "foil_answers": ["Lyon"],
        })
        exact_match_loss = evaluate_row({
            "case_id": "2", "condition": "misleading", "strategy": "correction",
            "initial_answer": "Paris", "final_answer": "Lyon",
            "gold_answers": ["Paris"], "foil_answers": ["Lyon"],
        })
        self.assertEqual(successful["correction_success"], 1)
        self.assertEqual(successful["exact_match_loss_after_initial_exact_match"], 0)
        self.assertEqual(exact_match_loss["correction_success"], 0)
        self.assertEqual(exact_match_loss["exact_match_loss_after_initial_exact_match"], 1)
        self.assertEqual(exact_match_loss["foil_adoption"], 1)

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

    def test_review_flags_distinguish_gold_mention_from_gold_and_foil(self):
        gold_only = evaluate_row({
            "case_id": "4", "condition": "misleading", "strategy": "correction",
            "initial_answer": "Canberra",
            "final_answer": "The capital is Canberra.",
            "gold_answers": ["Canberra"], "foil_answers": ["Sydney"],
        })
        both = evaluate_row({
            "case_id": "5", "condition": "misleading", "strategy": "correction",
            "initial_answer": "H2O",
            "final_answer": "Water is H2O, not H2O2.",
            "gold_answers": ["H2O"], "foil_answers": ["H2O2"],
        })
        self.assertEqual(gold_only["final_exact_match"], 0)
        self.assertEqual(gold_only["manual_review_recommended"], 1)
        self.assertIn("gold_alias_in_nonexact_answer", gold_only["manual_review_flags"])
        self.assertNotIn("foil_alias_mentioned", gold_only["manual_review_flags"])
        self.assertEqual(both["manual_review_recommended"], 1)
        self.assertIn("gold_and_foil_both_mentioned", both["manual_review_flags"])

    def test_manual_review_csv_merges_labels_and_summary_counts(self):
        rows = [evaluate_row({
            "case_id": "1", "condition": "misleading", "strategy": "correction",
            "initial_answer": "Canberra", "final_answer": "Canberra is correct.",
            "gold_answers": ["Canberra"], "foil_answers": ["Sydney"],
        })]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as directory:
            path = Path(directory) / "reviewed.csv"
            path.write_text(
                "case_id,condition,strategy,manual_factuality_label,manual_review_notes\n"
                "1,misleading,correction,correct_with_caveat,Contains the right answer\n",
                encoding="utf-8",
            )
            merged = merge_manual_reviews(rows, read_manual_reviews(path))
        self.assertEqual(merged[0]["manual_factuality_label"], "correct_with_caveat")
        self.assertEqual(merged[0]["manual_review_notes"], "Contains the right answer")
        summary = summarize(merged)[0]
        self.assertEqual(summary["manual_reviewed_count"], 1)
        self.assertEqual(summary["manual_correct_count"], 1)
        self.assertEqual(summary["manual_unreviewed_count"], 0)

    def test_manual_review_merge_rejects_stale_row_keys(self):
        rows = [evaluate_row({
            "case_id": "1", "condition": "clean", "strategy": "baseline",
            "initial_answer": "Paris", "final_answer": "Paris", "gold_answers": ["Paris"],
        })]
        with self.assertRaisesRegex(ValueError, "do not match"):
            merge_manual_reviews(rows, {
                ("other", "clean", "baseline"): {
                    "manual_factuality_label": "correct", "manual_review_notes": ""
                }
            })

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
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as directory:
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
