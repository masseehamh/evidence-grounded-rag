
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



def test_demo_override_uses_seeded_answer_and_still_runs_correction(monkeypatch):
    original = app.DEMO_INITIAL_ANSWER
    revised = "The Eiffel Tower is in Paris, France, and was completed in 1889."
    calls = {"verify": 0, "correct": 0}

    def unexpected_generation(*args, **kwargs):
        raise AssertionError("The controlled demo should use its fixed initial answer")

    def fake_verify(question, answer, evidence):
        calls["verify"] += 1
        if calls["verify"] == 1:
            assert answer == original
            return [{
                "claim": "The Eiffel Tower is in London.",
                "status": "CONTRADICTED",
                "reason": "The evidence places it in Paris",
                "evidence": evidence,
            }]
        assert answer == revised
        return [{
            "claim": revised,
            "status": "SUPPORTED",
            "reason": "Matches the evidence",
            "evidence": evidence,
        }]

    def fake_correct(question, answer, evidence, removed_claims):
        calls["correct"] += 1
        return revised

    monkeypatch.setattr(app, "generate_answer", unexpected_generation)
    monkeypatch.setattr(app, "verify_claims", fake_verify)
    monkeypatch.setattr(app, "correct_answer", fake_correct)

    result = app.run_rag(
        app.DEMO_QUESTION,
        app.DEMO_EVIDENCE,
        initial_answer_override=original,
    )

    assert result["original_answer"] == original
    assert "London" in result["original_answer"]
    assert "Paris" in result["corrected_answer"]
    assert "London" not in result["corrected_answer"]
    assert result["correction_attempted"] is True
    assert result["corrected_status"] == "SUPPORTED"
    assert calls == {"verify": 2, "correct": 1}


def test_demo_endpoint_is_unavailable_without_configured_token(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.delenv("DEMO_ACCESS_TOKEN", raising=False)

    try:
        app.api_demo_correction(x_demo_token="anything")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Demo endpoint must be disabled without a token")


def test_demo_endpoint_rejects_wrong_token(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("DEMO_ACCESS_TOKEN", "expected-secret")

    try:
        app.api_demo_correction(x_demo_token="wrong-secret")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Demo endpoint must reject an incorrect token")


def test_demo_endpoint_calls_pipeline_only_with_valid_token(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_TOKEN", "expected-secret")
    captured = {}

    def fake_run_rag(question, evidence, initial_answer_override=None):
        captured.update({
            "question": question,
            "evidence": evidence,
            "initial_answer_override": initial_answer_override,
        })
        return {
            "original_answer": initial_answer_override,
            "corrected_answer": "Paris",
            "corrected_status": "SUPPORTED",
            "correction_attempted": True,
        }

    monkeypatch.setattr(app, "run_rag", fake_run_rag)
    result = app.api_demo_correction(x_demo_token="expected-secret")

    assert captured == {
        "question": app.DEMO_QUESTION,
        "evidence": app.DEMO_EVIDENCE,
        "initial_answer_override": app.DEMO_INITIAL_ANSWER,
    }
    assert result["demo_mode"] is True
    assert "deliberately seeded as incorrect" in result["demo_notice"]
