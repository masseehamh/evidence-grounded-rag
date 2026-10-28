import json
import unittest
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from evaluate_outputs import normalize
from run_pilot import select_cases


DATASET = Path(__file__).with_name("cases.audited.v1.jsonl")
OFFICIAL_DOMAINS = ("nasa.gov", "nist.gov", "usgs.gov", "noaa.gov", "si.edu")
REQUIRED_FIELDS = {
    "dataset_version", "case_id", "category", "question", "gold_answers", "foil_answers",
    "evidence_clean", "evidence_misleading", "evidence_misleading_type",
    "evidence_misleading_note", "source_url", "source_title", "source_publisher",
    "source_accessed_at",
}


class AuditedDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_dataset_has_25_unique_cases_across_domains(self):
        ids = [row["case_id"] for row in self.rows]
        self.assertEqual(len(self.rows), 25)
        self.assertEqual(len(set(ids)), 25)
        self.assertEqual(len(Counter(row["category"] for row in self.rows)), 8)
        self.assertTrue(all(case_id.startswith("audit_") for case_id in ids))

    def test_each_case_has_official_source_and_counterfactual_provenance(self):
        for row in self.rows:
            self.assertTrue(REQUIRED_FIELDS.issubset(row), row.get("case_id"))
            parsed = urlparse(row["source_url"])
            self.assertEqual(parsed.scheme, "https", row["case_id"])
            self.assertTrue(
                any(parsed.hostname == domain or parsed.hostname.endswith(f".{domain}")
                    for domain in OFFICIAL_DOMAINS),
                row["source_url"],
            )
            self.assertEqual(row["dataset_version"], "audited-v1")
            self.assertEqual(row["evidence_misleading_type"], "synthetic_counterfactual")
            note = row["evidence_misleading_note"].lower()
            self.assertIn("generated false counterfactual", note)
            self.assertTrue("not text" in note or "not source text" in note)
            self.assertTrue(row["gold_answers"])
            self.assertTrue(row["foil_answers"])
            normalized_gold = {normalize(value) for value in row["gold_answers"]}
            normalized_foil = {normalize(value) for value in row["foil_answers"]}
            self.assertFalse(normalized_gold & normalized_foil, row["case_id"])
            self.assertNotEqual(row["evidence_clean"], row["evidence_misleading"])

    def test_case_range_can_select_remaining_twenty_without_repeating_first_five(self):
        selected = select_cases(self.rows, start=6, limit=20)
        self.assertEqual(len(selected), 20)
        self.assertEqual(selected[0]["case_id"], "audit_006")
        self.assertEqual(selected[-1]["case_id"], "audit_025")

    def test_case_range_rejects_start_after_dataset(self):
        with self.assertRaisesRegex(ValueError, "No cases available"):
            select_cases(self.rows, start=26, limit=20)


if __name__ == "__main__":
    unittest.main()
