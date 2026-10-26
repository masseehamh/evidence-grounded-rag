"""Pre-demo acceptance suite (Tests 1-4 + the frontend/backend API contract).

Every case uses the evidence wording from the acceptance document. The tests run
the notebook's own pipeline and FastAPI adapter with the stand-in models
(stubs.py) and real spaCy -- see backend-tests/README.md for what that does and
does not prove.
"""
import pytest
from conftest import script_generator
from fastapi.testclient import TestClient
from stubs import FakeNLI, AlwaysNeutralNLI

# --------------------------------------------------------------- Test 1 inputs
GANDHI_Q = "When did Gandhi assume leadership of the Indian National Congress?"
GANDHI_EVIDENCE = (
    "Assuming leadership of the Indian National Congress in 1921, Gandhi led nationwide "
    "campaigns for easing poverty, expanding women's rights, building religious and ethnic "
    "amity, ending untouchability, and achieving swaraj or self-rule."
)

NOT_SUFFICIENT = "The available evidence is not sufficient to provide a verified answer."
CLAIM_VOCAB = {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}
OVERALL_VOCAB = {"FULLY SUPPORTED", "CONTAINS HALLUCINATION", "NEEDS VERIFICATION"}


@pytest.fixture(params=[FakeNLI, AlwaysNeutralNLI], ids=["realistic-nli-stub", "worst-case-neutral-nli"])
def api(request, make_ns):
    """The notebook namespace WITH its FastAPI app, under two NLI behaviours."""
    ns = make_ns(request.param, with_api=True)
    return ns, TestClient(ns["app"])


def run_pipeline(ns, question, evidence, generated):
    script_generator(ns, generated)
    return ns["run_full_rag_pipeline"](question, evidence, verbose=False)


def expected_overall(result):
    statuses = [c["status"] for c in result["verification"]["claims"]]
    if "CONTRADICTED" in statuses:
        return "CONTAINS HALLUCINATION"
    if "NOT ENOUGH EVIDENCE" in statuses:
        return "NEEDS VERIFICATION"
    if not statuses:
        return "NEEDS VERIFICATION"
    return "FULLY SUPPORTED"


# ============================================================ Test 1: supported
class TestAcceptance1SupportedAnswer:
    @pytest.mark.parametrize("generated", ["1921", "India"])
    def test_answer_identifies_1921_and_is_supported(self, ns, generated):
        """The model answers correctly (1921) or badly (India); either way the
        system must end on 1921, grounded in the supplied sentence."""
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, generated)
        correction = r["correction"]
        assert correction["corrected_answer"] == "1921", correction
        assert r["corrected_status"] == "SUPPORTED"
        # the sentence that establishes 1921 is preserved for the user
        assert "1921" in correction.get("corrected_evidence", "") or generated == "1921"

    def test_correct_model_answer_is_verified_not_assumed(self, ns):
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, "1921")
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "SUPPORTED", claim
        assert claim["evidence"] == GANDHI_EVIDENCE          # relevant evidence shown
        assert r["verification"]["overall_status"] == "FULLY SUPPORTED"
        assert r["correction"]["corrected_answer"] == "1921"  # returned untouched

    def test_bad_model_answer_is_corrected_and_its_claim_is_not_supported(self, ns):
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, "India")
        claim = r["verification"]["claims"][0]
        assert claim["status"] != "SUPPORTED", claim          # 'India' is never supported here
        assert claim["evidence"], "the claim still shows why it was rejected"

    def test_summary_and_claim_badges_agree(self, ns):
        """The headline status must be a pure function of the claim statuses."""
        for generated in ("1921", "India", "1919"):
            r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, generated)
            assert r["verification"]["overall_status"] == expected_overall(r), generated
            assert r["corrected_status"] in CLAIM_VOCAB, generated


# ======================================================== Test 2: contradicted
class TestAcceptance2ContradictedClaim:
    @pytest.mark.parametrize("wrong", ["1919", "1925"])
    def test_wrong_year_is_contradicted_by_the_evidence(self, ns, wrong):
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, wrong)
        claim = r["verification"]["claims"][0]
        assert claim["status"] == "CONTRADICTED", claim
        assert r["verification"]["overall_status"] == "CONTAINS HALLUCINATION"

    def test_the_contradicted_claim_is_not_presented_as_supported(self, ns):
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, "1919")
        assert r["verification"]["claims"][0]["status"] != "SUPPORTED"
        assert "1919" not in r["correction"]["corrected_answer"]
        assert r["corrected_status"] in CLAIM_VOCAB

    def test_the_correction_uses_only_facts_from_the_evidence(self, ns):
        r = run_pipeline(ns, GANDHI_Q, GANDHI_EVIDENCE, "1919")
        corrected = r["correction"]["corrected_answer"]
        # the replacement must be the evidence sentence itself, verbatim
        assert " ".join(corrected.split()) == GANDHI_EVIDENCE
        assert "1921" in corrected


# ==================================================== Test 3: insufficient evidence
class TestAcceptance3InsufficientEvidence:
    QUESTIONS = [
        "What year did Einstein win the Nobel Prize?",
        "Who wrote the Indian constitution?",
        "What is the capital of Australia?",
    ]

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_system_says_the_evidence_is_insufficient(self, ns, question):
        r = run_pipeline(ns, question, GANDHI_EVIDENCE, "1905")   # 1905 comes from model memory
        assert r["correction"]["corrected_answer"] == NOT_SUFFICIENT
        assert r["corrected_status"] == "NOT_ENOUGH_EVIDENCE"

    @pytest.mark.parametrize("question", QUESTIONS)
    def test_it_does_not_guess_from_model_memory(self, ns, question):
        r = run_pipeline(ns, question, GANDHI_EVIDENCE, "1905")
        corrected = r["correction"]["corrected_answer"]
        assert "1905" not in corrected
        for claim in r["verification"]["claims"]:
            assert claim["status"] != "SUPPORTED", claim

    def test_summary_claims_and_corrected_panel_are_consistent(self, ns):
        r = run_pipeline(ns, self.QUESTIONS[0], GANDHI_EVIDENCE, "1905")
        assert r["verification"]["overall_status"] == expected_overall(r)
        assert r["verification"]["overall_status"] == "NEEDS VERIFICATION"
        assert r["corrected_status"] == "NOT_ENOUGH_EVIDENCE"


# ======================================================= Test 4: document evidence
class TestAcceptance4DocumentEvidence:
    DOC = ("Albert Einstein was a physicist born in Ulm.\n\n"
           "In 1905, sometimes described as his annus mirabilis (miracle year), he published "
           "four groundbreaking papers.\n\n"
           "He received the Nobel Prize in Physics in 1921.")
    DOC_Q = "What year is described as Einstein's annus mirabilis (miracle year)?"

    def _ask_document(self, api, question, generated):
        ns, client = api
        script_generator(ns, generated)
        up = client.post("/api/upload",
                         files={"file": ("evidence.txt", self.DOC.encode(), "text/plain")})
        assert up.status_code == 200, up.text
        body = client.post("/api/ask", json={
            "question": question, "mode": "document",
            "document_id": up.json()["document_id"],
        })
        assert body.status_code == 200, body.text
        return body.json()

    def test_relevant_passage_is_retrieved_and_answer_is_grounded(self, api):
        body = self._ask_document(api, self.DOC_Q, "1905")
        assert body["claims"][0]["status"] == "SUPPORTED", body["claims"][0]
        assert body["verification_status"] == "FULLY SUPPORTED"
        assert body["corrected_answer"] == "1905"
        assert body["corrected_status"] == "SUPPORTED"
        assert any("1905" in s["passage"] for s in body["sources"]), body["sources"]
        assert body["sources"][0]["title"] == "evidence.txt"

    def test_unsupported_question_against_the_same_document(self, api):
        """The document relevance gate (DOC_MIN_RELEVANCE) fires BEFORE generation:
        no answer is ever produced from passages unrelated to the question, so the
        headline is the document gate's own label (NOT ENOUGH EVIDENCE) rather than
        the claim-derived NEEDS VERIFICATION of the manual path. What must hold is
        that summary, corrected panel and absence of guessed content all agree."""
        body = self._ask_document(api, GANDHI_Q, "1905")
        assert body["verification_status"] == "NOT ENOUGH EVIDENCE"
        assert body["corrected_answer"] == NOT_SUFFICIENT
        assert body["corrected_status"] == "NOT_ENOUGH_EVIDENCE"
        assert "1905" not in body["corrected_answer"]          # never guessed from memory
        assert body["claims"] == [], "no claim is invented when no answer was generated"
        assert "insufficient" in body["message"].lower()        # summary explains why
        assert body["sources"], "closest passages are still shown for transparency"

    def test_irrelevant_document_reports_insufficient_evidence(self, api):
        ns, client = api
        script_generator(ns, "1905")
        up = client.post("/api/upload", files={
            "file": ("plants.txt", b"Photosynthesis converts sunlight into chemical energy.",
                     "text/plain")})
        body = client.post("/api/ask", json={
            "question": self.DOC_Q, "mode": "document",
            "document_id": up.json()["document_id"]}).json()
        assert body["verification_status"] == "NOT ENOUGH EVIDENCE"
        assert body["corrected_status"] == "NOT_ENOUGH_EVIDENCE"


# ============================== Test 5 (backend half): API <-> frontend contract
class TestApiContractMatchesFrontend:
    # Every top-level and per-claim field src/api.js normalizeResult() reads.
    TOP_LEVEL = {"verification_status", "original_answer", "corrected_answer",
                 "corrected_status", "corrected_evidence", "claims", "removed_claims", "sources"}
    PER_CLAIM = {"claim", "status", "evidence", "nli_label", "confidence",
                 "nli_confidence", "support_basis", "consistency"}

    @pytest.mark.parametrize("generated,expected_status", [
        ("1921", "FULLY SUPPORTED"),
        ("1919", "CONTAINS HALLUCINATION"),
        ("India", "NEEDS VERIFICATION"),
    ])
    def test_response_shape_and_vocabularies(self, api, generated, expected_status):
        ns, client = api
        script_generator(ns, generated)
        body = client.post("/api/ask", json={
            "question": GANDHI_Q, "mode": "manual", "evidence": GANDHI_EVIDENCE}).json()
        assert self.TOP_LEVEL <= set(body), set(body)
        assert body["verification_status"] == expected_status
        assert body["corrected_status"] in CLAIM_VOCAB
        assert body["claims"], body
        for claim in body["claims"]:
            assert self.PER_CLAIM <= set(claim), set(claim)
            assert claim["status"] in CLAIM_VOCAB, claim["status"]
            assert claim["confidence"] is None or 0 <= claim["confidence"] <= 1, claim
            assert claim["consistency"]["status"] in {"PASS", "FAIL", "NOT_CHECKED"}, claim
            assert claim["evidence"], claim                 # evidence always accompanies a claim

    def test_headline_status_is_derived_from_the_returned_claims(self, api):
        ns, client = api
        script_generator(ns, "1919")
        body = client.post("/api/ask", json={
            "question": GANDHI_Q, "mode": "manual", "evidence": GANDHI_EVIDENCE}).json()
        statuses = [c["status"] for c in body["claims"]]
        expected = ("CONTAINS HALLUCINATION" if "CONTRADICTED" in statuses else
                    "NEEDS VERIFICATION" if "NOT_ENOUGH_EVIDENCE" in statuses else
                    "FULLY SUPPORTED")
        assert body["verification_status"] == expected

    def test_no_web_or_mock_mode_is_exposed(self, api):
        _, client = api
        for mode in ("web", "search", "internet"):
            r = client.post("/api/ask", json={"question": GANDHI_Q, "mode": mode})
            assert r.status_code == 400
            assert "manual" in r.json()["detail"] and "document" in r.json()["detail"]
