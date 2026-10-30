"""Tests for explainable evidence ranking and source handling."""
import json
import unittest
from unittest.mock import patch

import app
from evidence_selection import (
    assess_source_authority, domain_from_url, relevance_score, select_evidence,
)


class EvidenceSelectionTests(unittest.TestCase):
    def test_official_domain_has_higher_authority_than_unknown_domain(self):
        official = assess_source_authority({"url": "https://www.cdc.gov/example"})
        unknown = assess_source_authority({"url": "https://random-blog.example/post"})
        self.assertGreater(official["authority_score"], unknown["authority_score"])
        self.assertEqual(official["trust_level"], "allowlisted_domain_unverified_page")

    def test_domain_allowlist_does_not_claim_page_verified(self):
        result = assess_source_authority({"url": "https://www.nasa.gov/news"})
        self.assertIn("unverified_page", result["trust_level"])

    def test_non_https_and_blocked_domains_are_not_trusted(self):
        self.assertEqual(domain_from_url("http://cdc.gov/a"), "")
        self.assertEqual(assess_source_authority({"url": "https://reddit.com/post"})["trust_level"], "blocked_domain")

    def test_relevant_passage_scores_above_unrelated_passage(self):
        claim = "What causes ocean temperatures to rise?"
        relevant = "Ocean temperatures rise as greenhouse gases trap more heat."
        unrelated = "The football team won its final match last Sunday."
        self.assertGreater(relevance_score(claim, relevant), relevance_score(claim, unrelated))

    def test_selection_returns_reasons_scores_and_deduplicates_passages(self):
        sources = [
            {"title": "Official", "url": "https://www.nasa.gov/climate", "passage": "Ocean temperatures rise as greenhouse gases trap more heat."},
            {"title": "Copy", "url": "https://example.org/copy", "passage": "Ocean temperatures rise as greenhouse gases trap more heat."},
            {"title": "Unrelated", "url": "https://example.org/sports", "passage": "The football team won its final match last Sunday."},
        ]
        result = select_evidence("What causes ocean temperatures to rise?", sources, top_k=5)
        self.assertGreaterEqual(result["candidate_count"], 3)
        self.assertEqual(len(result["selected_sources"]), 1)
        selected = result["selected_sources"][0]
        self.assertIn("selection_score", selected)
        self.assertTrue(selected["selection_reasons"])
        self.assertTrue(selected["independent_corroboration"])
        self.assertNotIn("not counted as independent corroboration", " ".join(selected["selection_reasons"]))

    def test_empty_sources_return_empty_selection(self):
        result = select_evidence("A claim", [])
        self.assertEqual(result["selected_sources"], [])
        self.assertEqual(result["candidate_count"], 0)

    def test_verifier_receives_claim_specific_selected_evidence(self):
        sources = [
            {"title": "Ocean report", "url": "https://www.nasa.gov/climate",
             "passage": "Ocean temperatures rise as greenhouse gases trap more heat."},
            {"title": "Sports report", "url": "https://example.org/sports",
             "passage": "The football team won its final match last Sunday."},
        ]
        response = {"claims": [{
            "claim": "Ocean temperatures rise as greenhouse gases trap more heat.",
            "status": "SUPPORTED",
            "evidence": "Ocean temperatures rise as greenhouse gases trap more heat.",
            "reason": "The passage directly supports the claim.",
        }]}
        with patch.object(app, "cloudflare_chat", return_value=json.dumps(response)) as model:
            result = app.verify_claims(
                "What causes ocean temperatures to rise?",
                "Ocean temperatures rise as greenhouse gases trap more heat.",
                "fallback evidence",
                source_records=sources,
            )
        self.assertEqual(result[0]["status"], "SUPPORTED")
        selection = result[0]["evidence_selection"]
        self.assertEqual(selection["selected_sources"][0]["title"], "Ocean report")
        self.assertEqual(selection["candidate_count"], 2)
        sent_prompt = json.loads(model.call_args.args[0][1]["content"])
        self.assertIn("evidence_by_claim", sent_prompt)
        self.assertNotIn("Sports report", sent_prompt["evidence_by_claim"][0]["evidence"])


if __name__ == "__main__":
    unittest.main()
