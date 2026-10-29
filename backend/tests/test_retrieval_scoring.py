"""Regression tests for retrieval relevance scoring."""
import unittest
import app


class RetrievalScoringTests(unittest.TestCase):
    def test_plural_and_inflected_terms_match(self):
        self.assertGreater(app.retrieval_score("How do vaccines prevent infections?", "A vaccine prevents infection."), 0)

    def test_exact_relevant_passage_scores_above_unrelated_passage(self):
        question = "What causes ocean temperatures to rise?"
        relevant = "Ocean temperatures rise as greenhouse gases trap more heat."
        unrelated = "The football team won its final match last Sunday."
        self.assertGreater(app.retrieval_score(question, relevant), app.retrieval_score(question, unrelated))

    def test_shared_number_does_not_make_unrelated_passage_relevant(self):
        question = "What was the population in 2020?"
        unrelated = "The football team scored 2020 points in a fictional season."
        self.assertLess(app.retrieval_score(question, unrelated), 0.6)

    def test_empty_question_or_passage_scores_zero(self):
        self.assertEqual(app.retrieval_score("", "Some passage."), 0.0)
        self.assertEqual(app.retrieval_score("Some question?", ""), 0.0)


if __name__ == "__main__":
    unittest.main()
