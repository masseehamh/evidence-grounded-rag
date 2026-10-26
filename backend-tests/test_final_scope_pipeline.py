"""Regression tests for the reported final-demo failure + the final scope.

Reported failure: question "When did Gandhi assume leadership of the Indian
National Congress?" with evidence containing "Assuming leadership of the Indian
National Congress in 1921, Gandhi led nationwide campaigns ..." produced the
original answer "India", a corrected answer about moving to South Africa in
1893, and an overall CONTAINS HALLUCINATION while the page showed a hard-coded
SUPPORTED badge on that corrected answer.

These tests run the notebook's own code with the stand-in models (stubs.py);
they check the decision logic, not real-model quality.
"""
import pytest
from conftest import script_generator
from fastapi.testclient import TestClient

QUESTION = "When did Gandhi assume leadership of the Indian National Congress?"
LEADERSHIP_SENTENCE = ("Assuming leadership of the Indian National Congress in 1921, "
                       "Gandhi led nationwide campaigns for reducing poverty.")
SOUTH_AFRICA_SENTENCE = "In 1893, Gandhi moved to South Africa to work as a lawyer."
EVIDENCE = (
    "Mohandas Gandhi returned to India in 1915 and soon became involved in the "
    "struggle against British rule. " + LEADERSHIP_SENTENCE +
    " " + SOUTH_AFRICA_SENTENCE +
    " He experienced racial discrimination there."
)
EINSTEIN_Q = "What year is described as Einstein's annus mirabilis (miracle year)?"
EINSTEIN_EVIDENCE = ("In 1905, sometimes described as his annus mirabilis (miracle year), "
                     "he published four groundbreaking papers.")
NOT_SUFFICIENT = "The available evidence is not sufficient to provide a verified answer."
STATUSES = {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}


def run(ns, question, evidence, generated, plain=""):
    script_generator(ns, generated, plain)
    return ns["run_full_rag_pipeline"](question, evidence, verbose=False)


def expected_overall(claims):
    statuses = [c["status"] for c in claims]
    if "CONTRADICTED" in statuses:
        return "CONTAINS HALLUCINATION"
    if "NOT ENOUGH EVIDENCE" in statuses:
        return "NEEDS VERIFICATION"
    return "FULLY SUPPORTED"


@pytest.fixture(params=["realistic-nli-stub", "worst-case-neutral-nli"])
def api(request, make_ns):
    """The notebook namespace WITH its FastAPI app, under two NLI behaviours."""
    from stubs import FakeNLI, AlwaysNeutralNLI
    nli = FakeNLI if request.param == "realistic-nli-stub" else AlwaysNeutralNLI
    ns = make_ns(nli, with_api=True)
    return ns, TestClient(ns["app"])


# ------------------------------------------------- the reported failure
class TestGandhiScenario:
    def test_wrong_shape_answer_is_not_supported(self, ns):
        """'India' cannot answer a When-question, so it is never SUPPORTED."""
        r = run(ns, QUESTION, EVIDENCE, "India")
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "NOT ENOUGH EVIDENCE", claim
        assert claim["support_basis"] is None

    def test_corrected_answer_is_the_date_in_the_relevant_sentence(self, ns):
        r = run(ns, QUESTION, EVIDENCE, "India")
        correction = r["correction"]
        assert correction["corrected_answer"] == "1921"
        assert correction["correction_source"] == "evidence_extraction"
        assert LEADERSHIP_SENTENCE in correction["corrected_evidence"]
        assert r["corrected_status"] == "SUPPORTED"

    def test_no_unrelated_sentence_is_pasted_into_the_answer(self, ns):
        """The reported fix pasted the true-but-unrelated 1893 South Africa line."""
        r = run(ns, QUESTION, EVIDENCE, "India")
        corrected = r["correction"]["corrected_answer"]
        assert "South Africa" not in corrected
        assert "1893" not in corrected
        assert corrected == "1921"

    def test_original_answer_is_reported_honestly(self, ns):
        r = run(ns, QUESTION, EVIDENCE, "India")
        assert r["generated_answer"] == "India"
        assert r["verification"]["original_answer"] == "India"
        assert r["correction"]["original_answer"] == "India"
        assert r["correction"]["claims_removed"][0]["claim"] == "India"

    def test_overall_status_agrees_with_the_claim_statuses(self, ns):
        r = run(ns, QUESTION, EVIDENCE, "India")
        assert r["verification"]["overall_status"] == expected_overall(
            r["verification"]["claims"])

    def test_evidence_is_preserved_for_every_claim(self, ns):
        r = run(ns, QUESTION, EVIDENCE, "India")
        for claim in r["verification"]["claims"]:
            assert claim["evidence"], claim          # why it was accepted/rejected


# ------------------------------------------- status consistency, in general
class TestStatusConsistency:
    @pytest.mark.parametrize("generated,expected_claim", [
        ("1905", "SUPPORTED"),
        ("1906", "CONTRADICTED"),
    ])
    def test_full_pipeline_statuses(self, ns, generated, expected_claim):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, generated)
        claim = r["verification"]["claims"][0]
        assert claim["status"] == expected_claim, claim
        assert r["verification"]["overall_status"] == expected_overall(
            r["verification"]["claims"])
        assert r["corrected_status"] in STATUSES
        # the wrong value is never left in the corrected answer
        if expected_claim == "CONTRADICTED":
            assert generated not in r["correction"]["corrected_answer"]

    def test_corrected_answer_with_unsupported_info_is_never_supported(self, ns):
        """The badge on the corrected answer comes from ITS claim statuses, not
        from a hard-coded value."""
        correction = {
            "original_answer": "1905",
            "corrected_answer": "The year 1906 is described as the annus mirabilis.",
        }
        status = ns["corrected_answer_status"](EINSTEIN_Q, EINSTEIN_EVIDENCE, correction)
        assert status in {"CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}

    def test_fully_supported_answer_keeps_a_supported_status(self, ns):
        r = run(ns, EINSTEIN_Q, EINSTEIN_EVIDENCE, "1905")
        assert r["verification"]["overall_status"] == "FULLY SUPPORTED"
        assert r["corrected_status"] == "SUPPORTED"
        assert r["correction"]["corrected_answer"] == "1905"

    def test_insufficient_evidence_is_said_plainly(self, ns):
        r = run(ns, "What year did Einstein win the Nobel Prize?", EVIDENCE, "1905")
        assert r["correction"]["corrected_answer"] == NOT_SUFFICIENT
        assert r["corrected_status"] == "NOT_ENOUGH_EVIDENCE"
        assert "1905" not in r["correction"]["corrected_answer"]

    def test_corrected_status_vocabulary(self, ns):
        for question, evidence, generated in [
            (QUESTION, EVIDENCE, "India"),
            (EINSTEIN_Q, EINSTEIN_EVIDENCE, "1905"),
            (EINSTEIN_Q, EINSTEIN_EVIDENCE, "1906"),
        ]:
            r = run(ns, question, evidence, generated)
            assert r["corrected_status"] in STATUSES, r


# --------------------------------- wrong value + relevant-sentence evidence
class TestRelevantEvidenceIsUsed:
    def test_off_topic_copy_is_contradicted_by_the_relevant_sentence(self, ns):
        """The answer span sits in an unrelated sentence; the sentence that
        actually discusses the question gives a different year -> CONTRADICTED,
        and that relevant sentence is the evidence shown for the claim."""
        evidence = ("The project started in 1906 and was completed later. " +
                    EINSTEIN_EVIDENCE)
        r = run(ns, EINSTEIN_Q, evidence, "1906")
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "CONTRADICTED", claim
        assert claim["evidence"] == EINSTEIN_EVIDENCE
        corrected = r["correction"]["corrected_answer"]
        assert "1906" not in corrected and "1905" in corrected

    def test_extraction_picks_the_sentence_that_answers_the_question(self, ns):
        r = run(ns, QUESTION, EVIDENCE, "I don't have enough information to answer this question.",
                plain="I don't have enough information to answer this question.")
        assert r["correction"]["corrected_answer"] == "1921"
        assert r["corrected_status"] == "SUPPORTED"


# ---------------------------------------------------- document upload mode
class TestDocumentMode:
    def test_relevant_passage_is_used_for_the_uploaded_document(self, api):
        ns, client = api
        script_generator(ns, "India")
        doc = ("The Eiffel Tower is a famous landmark located in Paris, France. "
               "It was completed in 1889.\n\n" + EVIDENCE + "\n\n"
               "Photosynthesis is the process plants use to convert sunlight into "
               "chemical energy.")
        up = client.post("/api/upload", files={"file": ("gandhi.txt", doc.encode(), "text/plain")})
        assert up.status_code == 200, up.text
        body = client.post("/api/ask", json={
            "question": QUESTION, "mode": "document",
            "document_id": up.json()["document_id"],
        }).json()
        assert body["claims"][0]["status"] == "NOT_ENOUGH_EVIDENCE"
        assert body["corrected_answer"] == "1921"
        assert body["corrected_status"] == "SUPPORTED"
        assert body["sources"] and body["sources"][0]["title"] == "gandhi.txt"
        # the passage shown as the source is the one that answers the question
        assert any("1921" in s["passage"] for s in body["sources"])

    def test_off_topic_question_reports_insufficient_evidence(self, api):
        ns, client = api
        script_generator(ns, "India")
        doc = "Photosynthesis is the process plants use to convert sunlight into chemical energy."
        up = client.post("/api/upload", files={"file": ("plants.txt", doc.encode(), "text/plain")})
        body = client.post("/api/ask", json={
            "question": QUESTION, "mode": "document",
            "document_id": up.json()["document_id"],
        }).json()
        assert body["verification_status"] == "NOT ENOUGH EVIDENCE"
        assert body["corrected_answer"] == NOT_SUFFICIENT
        assert body["corrected_status"] == "NOT_ENOUGH_EVIDENCE"


# ------------------------------------------------------- API contract / scope
class TestApiContract:
    def test_reported_failure_through_the_api(self, api):
        ns, client = api
        script_generator(ns, "India")
        body = client.post("/api/ask", json={
            "question": QUESTION, "mode": "manual", "evidence": EVIDENCE,
        }).json()
        assert body["original_answer"] == "India"
        assert body["claims"][0]["status"] == "NOT_ENOUGH_EVIDENCE"
        assert body["verification_status"] == "NEEDS VERIFICATION"
        assert body["corrected_answer"] == "1921"
        assert body["corrected_status"] == "SUPPORTED"
        assert "South Africa" not in body["corrected_answer"]
        # the badge and the claim list can never disagree
        # (the API sends statuses with underscores, the pipeline with spaces)
        assert body["verification_status"] == expected_overall(
            [{"status": c["status"].replace("_", " ")} for c in body["claims"]])

    def test_overall_status_is_derived_from_the_returned_claims(self, api):
        ns, client = api
        script_generator(ns, "1906")
        body = client.post("/api/ask", json={
            "question": EINSTEIN_Q, "mode": "manual", "evidence": EINSTEIN_EVIDENCE,
        }).json()
        assert body["claims"][0]["status"] == "CONTRADICTED"
        assert body["verification_status"] == "CONTAINS HALLUCINATION"
        assert body["corrected_status"] in STATUSES

    @pytest.mark.parametrize("payload,fragment", [
        ({"question": QUESTION, "mode": "web"}, "mode"),
        ({"question": QUESTION, "mode": "search"}, "mode"),
    ])
    def test_automatic_web_retrieval_is_removed(self, api, payload, fragment):
        _, client = api
        r = client.post("/api/ask", json=payload)
        assert r.status_code == 400
        assert fragment in r.json()["detail"].lower()
        assert "manual" in r.json()["detail"] and "document" in r.json()["detail"]
