"""HTTP-level tests of the notebook's FastAPI adapter (the same app the frontend calls),
including the manual-evidence path used by the website."""
import pytest
from fastapi.testclient import TestClient
from conftest import script_generator
from stubs import FakeNLI, AlwaysNeutralNLI

EVID = ("In 1905, sometimes described as his annus mirabilis (miracle year), "
        "he published four groundbreaking papers.")
Q = "What year is described as Einstein's annus mirabilis (miracle year)?"
NOT_SUFFICIENT = "The available evidence is not sufficient to provide a verified answer."


@pytest.fixture(params=[FakeNLI, AlwaysNeutralNLI], ids=["realistic-nli-stub", "worst-case-neutral-nli"])
def api(request, make_ns):
    ns = make_ns(request.param, with_api=True)
    return ns, TestClient(ns["app"])


def ask(api, **body):
    ns, client = api
    return client.post("/api/ask", json=body)


def test_health(api):
    r = api[1].get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_manual_einstein_exact_website_scenario(api):
    script_generator(api[0], "1905")
    r = ask(api, question=Q, mode="manual", evidence=EVID)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verification_status"] == "FULLY SUPPORTED"
    assert body["original_answer"] == "1905" and body["corrected_answer"] == "1905"
    claim = body["claims"][0]
    assert claim["status"] == "SUPPORTED"
    assert claim["evidence"] == EVID
    assert claim["consistency"]["status"] == "PASS"          # what the results page displays
    assert "Numbers:" in claim["consistency"]["details"]
    assert claim["nli_confidence"] is not None
    if claim["support_basis"] == "answer_span_in_evidence":
        # Heuristic (deterministic) support: no NLI score is presented as the overall confidence.
        assert claim["confidence"] is None
    else:
        # The NLI judged the rebuilt question+answer statement and found it entailed,
        # so the NLI score is the reported overall confidence for this supported claim.
        assert claim["support_basis"] == "nli_entailment"
        assert claim["nli_label"] == "entailment"
        assert claim["confidence"] == claim["nli_confidence"]
    assert body["removed_claims"] == []


def test_manual_evidence_with_surrounding_whitespace_and_newlines(api):
    script_generator(api[0], "1905")
    r = ask(api, question="  " + Q + "  ", mode="manual", evidence="\n  " + EVID + "\n\n")
    assert r.json()["claims"][0]["status"] == "SUPPORTED"


def test_manual_unsupported_question(api):
    script_generator(api[0], "1905")
    r = ask(api, question="What year did Einstein win the Nobel Prize?", mode="manual", evidence=EVID)
    body = r.json()
    assert body["claims"][0]["status"] == "NOT_ENOUGH_EVIDENCE"
    assert body["verification_status"] == "NEEDS VERIFICATION"
    assert body["corrected_answer"] == "The available evidence is not sufficient to provide a verified answer."
    assert len(body["removed_claims"]) == 1


def test_manual_contradicted_answer(api):
    script_generator(api[0], "1906")
    body = ask(api, question=Q, mode="manual", evidence=EVID).json()
    assert body["claims"][0]["status"] == "CONTRADICTED"
    assert body["verification_status"] == "CONTAINS HALLUCINATION"
    assert body["claims"][0]["consistency"]["status"] == "FAIL"
    assert "1906" not in body["corrected_answer"] and "1905" in body["corrected_answer"]


# The website test the report describes: a biography passage that never states the
# annus mirabilis year, while the generator answers "1905" anyway (from memory).
BIOGRAPHY = ("Albert Einstein was born in Ulm, Germany in 1879. He studied at the Swiss "
             "Federal Polytechnic in Zurich. He became a Swiss citizen in 1901. He later "
             "moved to the United States and became a professor at the Institute for "
             "Advanced Study in Princeton. He died in 1955.")


def test_einstein_biography_without_the_year_is_not_verified(api):
    """Evidence that does not establish the year must not report it as verified."""
    script_generator(api[0], "1905")
    body = ask(api, question=Q, mode="manual", evidence=BIOGRAPHY).json()
    claim = body["claims"][0]
    assert claim["status"] == "NOT_ENOUGH_EVIDENCE"
    assert claim["nli_label"] == "neutral"            # neutral is never proof of support
    assert claim["consistency"]["status"] == "FAIL"
    assert "does not contain" in claim["consistency"]["details"]
    assert body["verification_status"] == "NEEDS VERIFICATION"
    assert body["corrected_answer"] == NOT_SUFFICIENT
    assert "1905" not in body["corrected_answer"]
    assert any(r.get("claim") == "1905" for r in body["removed_claims"])


def test_confidence_is_a_0_to_1_probability_not_a_percentage(api):
    """Regression for the 'overall confidence shows 1%' bug.

    The results page renders Math.round(confidence)%, so the API must send either
    null (deterministic span support) or a raw 0-1 probability. Sending an
    already-divided/mis-scaled value such as 0.01 (or a raw 0-1 fraction the UI
    never scaled) is what made supported claims render as '1%'.
    """
    script_generator(api[0], "1905")
    body = ask(api, question=Q, mode="manual", evidence=EVID).json()
    for claim in body["claims"]:
        assert claim["confidence"] is None or 0.0 < claim["confidence"] <= 1.0, claim
        assert claim["nli_confidence"] is None or 0.0 <= claim["nli_confidence"] <= 1.0, claim
    supported = next(c for c in body["claims"] if c["status"] == "SUPPORTED")
    # An NLI-score-backed supported claim carries that score, in 0-1 form.
    if supported["support_basis"] == "nli_entailment":
        assert supported["confidence"] >= 1 / 3        # top label of a 3-way softmax
    else:
        assert supported["confidence"] is None         # deterministic support: no model score


def test_response_matches_the_frontend_status_vocabulary(api):
    script_generator(api[0], "1905")
    body = ask(api, question=Q, mode="manual", evidence=EVID).json()
    allowed = {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}
    assert all(c["status"] in allowed for c in body["claims"])
    assert set(body) >= {"verification_status", "original_answer", "corrected_answer",
                         "claims", "removed_claims", "sources"}


@pytest.mark.parametrize("payload,fragment", [
    ({"question": "", "mode": "manual", "evidence": EVID}, "question"),
    ({"question": Q, "mode": "manual", "evidence": "   "}, "evidence"),
    ({"question": Q, "mode": "manual"}, "evidence"),
    ({"question": Q, "mode": "nonsense", "evidence": EVID}, "mode"),
    ({"question": Q, "mode": "document", "document_id": "missing"}, "upload"),
])
def test_bad_requests_get_clear_400s(api, payload, fragment):
    r = ask(api, **payload)
    assert r.status_code == 400 and fragment in r.text.lower()


def test_document_mode_end_to_end(api):
    ns, client = api
    script_generator(ns, "1905")
    doc = ("Albert Einstein was a physicist.\n\n" + EVID + "\n\n"
           "Mount Everest is the highest mountain above sea level.")
    up = client.post("/api/upload", files={"file": ("einstein.txt", doc.encode(), "text/plain")})
    assert up.status_code == 200
    r = client.post("/api/ask", json={"question": Q, "mode": "document", "document_id": up.json()["document_id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["claims"][0]["status"] == "SUPPORTED"
    assert body["sources"] and body["sources"][0]["title"] == "einstein.txt"


def test_upload_rejects_non_txt(api):
    r = api[1].post("/api/upload", files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 415
