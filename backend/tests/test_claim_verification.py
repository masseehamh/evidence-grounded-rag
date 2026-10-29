"""Regression tests for direct user-claim verification.

Run from the backend directory with: python -m unittest discover -s tests
No live model or web-search access is required.
"""
import json
import unittest
from unittest.mock import patch

import app


class ClaimRoutingTests(unittest.TestCase):
    def test_explicit_claim_check_is_routed_directly(self):
        self.assertTrue(app.looks_like_claim_check(
            "Verify this claim: The Eiffel Tower is located in Rome."
        ))

    def test_first_person_assertion_is_routed_directly(self):
        self.assertTrue(app.looks_like_claim_check(
            "I am Superman and invincible."
        ))

    def test_ordinary_fact_question_remains_question_answering(self):
        self.assertFalse(app.looks_like_claim_check(
            "When was the Eiffel Tower completed?"
        ))

    def test_claim_extraction_preserves_user_subject_and_proposition(self):
        claims = app.extract_user_claims(
            "Verify this claim: I am Superman and I can fly."
        )
        self.assertEqual(claims, ["I am Superman and I can fly."])

    def test_model_cannot_mark_supported_without_exact_evidence_excerpt(self):
        fake = {
            "claims": [{
                "claim": "I am Superman.",
                "status": "SUPPORTED",
                "evidence": "Superman can fly.",
                "reason": "The passage mentions Superman.",
            }]
        }
        with patch.object(app, "cloudflare_chat", return_value=json.dumps(fake)):
            result = app.verify_user_claims(
                "I am Superman.",
                "Superman is a fictional character who can fly."
            )
        self.assertEqual(result[0]["status"], "NOT_ENOUGH_EVIDENCE")
        self.assertEqual(result[0]["evidence"], "")

    def test_model_status_and_excerpt_are_kept_when_excerpt_is_verbatim(self):
        fake = {
            "claims": [{
                "claim": "The Eiffel Tower is in Rome.",
                "status": "CONTRADICTED",
                "evidence": "The Eiffel Tower is in Paris, France.",
                "reason": "The location conflicts.",
            }]
        }
        evidence = "The Eiffel Tower is in Paris, France."
        with patch.object(app, "cloudflare_chat", return_value=json.dumps(fake)):
            result = app.verify_user_claims(
                "Verify this claim: The Eiffel Tower is in Rome.", evidence
            )
        self.assertEqual(result[0]["status"], "CONTRADICTED")
        self.assertEqual(result[0]["evidence"], evidence)


if __name__ == "__main__":
    unittest.main()
