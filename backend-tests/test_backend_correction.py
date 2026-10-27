
import backend.app as app


EVIDENCE = (
    "The Eiffel Tower is in Paris, France. "
    "It was completed in 1889."
)
QUESTION = "Where is the Eiffel Tower, and when was it completed?"


def test_supported_answer_stays_unchanged(monkeypatch):
    original = "The Eiffel Tower is in Paris, France, and was completed in 1889."

    monkeypatch.setattr(app, "generate_answer", lambda q, e: original)
    monkeypatch.setattr(
        app,
        "verify_claims",
        lambda q, answer, evidence: [
            {
                "claim": original,
                "status": "SUPPORTED",
                "reason": "Matches the evidence",
                "evidence": evidence,
            }
        ],
    )

    def unexpected_correction(*args, **kwargs):
        raise AssertionError("Correction should not run for a supported answer")

    monkeypatch.setattr(app, "correct_answer", unexpected_correction)

    result = app.run_rag(QUESTION, EVIDENCE)

    assert result["original_answer"] == original
    assert result["corrected_answer"] == original
    assert result["corrected_status"] == "SUPPORTED"
    assert result["correction_attempted"] is False


def test_contradicted_claim_triggers_correction(monkeypatch):
    original = "The Eiffel Tower is in London and was completed in 1889."
    revised = "The Eiffel Tower is in Paris, France, and was completed in 1889."

    monkeypatch.setattr(app, "generate_answer", lambda q, e: original)

    initial_claims = [
        {
            "claim": "The Eiffel Tower is in London.",
            "status": "CONTRADICTED",
            "reason": "The evidence places it in Paris",
            "evidence": EVIDENCE,
        },
        {
            "claim": "It was completed in 1889.",
            "status": "SUPPORTED",
            "reason": "Matches the evidence",
            "evidence": EVIDENCE,
        },
    ]

    revised_claims = [
        {
            "claim": revised,
            "status": "SUPPORTED",
            "reason": "Matches the evidence",
            "evidence": EVIDENCE,
        }
    ]

    verification_calls = {"count": 0}

    def fake_verify(question, answer, evidence):
        verification_calls["count"] += 1
        if verification_calls["count"] == 1:
            return initial_claims
        return revised_claims

    correction_calls = []

    def fake_correct(question, answer, evidence, removed_claims):
        correction_calls.append(removed_claims)
        return revised

    monkeypatch.setattr(app, "verify_claims", fake_verify)
    monkeypatch.setattr(app, "correct_answer", fake_correct)

    result = app.run_rag(QUESTION, EVIDENCE)

    assert result["correction_attempted"] is True
    assert correction_calls
    assert verification_calls["count"] == 2
    assert result["corrected_status"] == "SUPPORTED"
    assert "Paris" in result["corrected_answer"]
    assert "London" not in result["corrected_answer"]


def test_no_supported_claims_returns_insufficient_answer(monkeypatch):
    original = "The Eiffel Tower is in London."
    revised = "The evidence does not establish the requested answer."

    monkeypatch.setattr(app, "generate_answer", lambda q, e: original)

    initial_claims = [
        {
            "claim": original,
            "status": "CONTRADICTED",
            "reason": "The evidence says Paris",
            "evidence": EVIDENCE,
        }
    ]

    revised_claims = [
        {
            "claim": revised,
            "status": "NOT_ENOUGH_EVIDENCE",
            "reason": "No supported answer",
            "evidence": "",
        }
    ]

    verification_calls = {"count": 0}

    def fake_verify(question, answer, evidence):
        verification_calls["count"] += 1
        if verification_calls["count"] == 1:
            return initial_claims
        return revised_claims

    monkeypatch.setattr(app, "verify_claims", fake_verify)
    monkeypatch.setattr(app, "correct_answer", lambda *args: revised)

    result = app.run_rag(QUESTION, EVIDENCE)

    assert result["correction_attempted"] is True
    assert result["corrected_answer"] == app.INSUFFICIENT_ANSWER
    assert result["corrected_status"] == "NOT_ENOUGH_EVIDENCE"
    assert result["corrected_evidence"] == ""
