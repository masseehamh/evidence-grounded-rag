"""Regression coverage for conversational-vs-verification routing."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import app


class ConversationRoutingTests(unittest.TestCase):
    def test_im_batman_is_conversation_in_web_mode(self):
        with patch.object(app, "respond_to_casual_statement", return_value="Nice try, Bruce.") as reply:
            result = app.api_ask(app.AskRequest(question="im batman", mode="web"))
        reply.assert_called_once_with("im batman")
        self.assertEqual(result["verification_mode"], "conversation")
        self.assertEqual(result["corrected_answer"], "Nice try, Bruce.")
        self.assertEqual(result["claims"], [])

    def test_hi_in_manual_mode_does_not_require_evidence(self):
        with patch.object(app, "respond_to_casual_statement", return_value="Hey!"):
            result = app.api_ask(app.AskRequest(question="hi", mode="manual"))
        self.assertEqual(result["verification_mode"], "conversation")
        self.assertEqual(result["corrected_answer"], "Hey!")

    def test_fact_check_whether_is_not_casual_and_extracts_claim(self):
        question = "Fact-check whether Batman is a real person."
        self.assertFalse(app.looks_like_casual_statement(question))
        self.assertTrue(app.looks_like_claim_check(question))
        self.assertEqual(app.extract_user_claims(question), ["Batman is a real person."])

    def test_factual_web_question_stays_on_evidence_pipeline(self):
        sources = [{"title": "Python docs", "url": "https://docs.python.org/", "passage": "Python was created by Guido van Rossum."}]
        expected = {"verification_status": "FULLY SUPPORTED", "claims": [], "sources": []}
        with patch.object(app, "search_web_evidence", return_value=sources) as search, \
             patch.object(app, "run_rag", return_value=expected) as rag:
            result = app.api_ask(app.AskRequest(question="Who developed Python?", mode="web"))
        search.assert_called_once()
        rag.assert_called_once()
        self.assertEqual(result["sources"], sources)

    def test_model_failure_is_an_api_error_not_a_success_result(self):
        with patch.object(app, "respond_to_casual_statement", side_effect=RuntimeError("Cloudflare inference timed out.")):
            with self.assertRaises(HTTPException) as caught:
                app.api_ask(app.AskRequest(question="hi", mode="manual"))
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn("timed out", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
