"""Manual scenario check (not part of the pytest suite).

Runs the notebook's own FastAPI app with stand-in models and prints, for each
of the five report scenarios, the RAW backend JSON and what the frontend would
DISPLAY after normalizeResult() + the App.jsx rendering rules. Asserts the key
expectations too, so it exits non-zero if a regression appears.

    python manual_scenarios_check.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient  # noqa: E402
from notebook_harness import load_notebook  # noqa: E402
from stubs import FakeNLI  # noqa: E402

ns = load_notebook(nli=FakeNLI(), with_api=True)
client = TestClient(ns["app"])

Q = "What year is described as Einstein's annus mirabilis (miracle year)?"
EINSTEIN_EV = ("In 1905, sometimes described as his annus mirabilis (miracle year), "
               "he published four groundbreaking papers.")
BIO_EV = ("Albert Einstein was born in Ulm, Germany in 1879. He studied at the Swiss "
          "Federal Polytechnic in Zurich. He became a Swiss citizen in 1901. He later "
          "moved to the United States and became a professor at the Institute for "
          "Advanced Study in Princeton. He died in 1955.")
KANSAS = ("Five people were infected and three died in the past year in Kansas "
          "from listeria that might be linked to Blue Bell Creameries products.")


def display(conf):
    """Mirror of App.jsx: Math.round(Number(confidence))% after normalizeConfidence."""
    if conf is None:
        return None
    n = float(conf)
    n = max(0.0, min(100.0, n * 100 if n <= 1 else n))
    return f"{round(n)}%"


def run(name, question, evidence, answer, plain="", expect=None):
    ns["generate_answer"] = lambda q, c, max_length=128: answer
    ns["generate_answer_plain"] = lambda q, c, max_length=128: plain
    body = client.post("/api/ask", json={"question": question, "mode": "manual",
                                         "evidence": evidence}).json()
    print("=" * 78)
    print("SCENARIO:", name)
    print("overall:", body.get("verification_status"))
    print("original:", repr(body.get("original_answer")))
    print("corrected:", repr(body.get("corrected_answer")))
    for c in body.get("claims", []):
        print(f"  claim   : {c['claim']!r}")
        print(f"  status  : {c['status']}  nli={c['nli_label']}")
        print(f"  raw confidence      : {c['confidence']!r}")
        print(f"  raw nli_confidence  : {c['nli_confidence']!r}")
        print(f"  DISPLAYED overall   : {display(c['confidence'])}"
              f"   (NLI score: {display(c['nli_confidence'])})")
        # The contract the results page relies on: raw 0-1 probability or null.
        assert c["confidence"] is None or 0.0 < c["confidence"] <= 1.0, c
        assert c["nli_confidence"] is None or 0.0 <= c["nli_confidence"] <= 1.0, c
    print("removed:", [r.get('claim') for r in body.get('removed_claims', [])])
    if expect:
        expect(body)
    return body


def supported_and_correct(body):
    c = body["claims"][0]
    assert body["verification_status"] == "FULLY SUPPORTED", body
    assert c["status"] == "SUPPORTED", c
    assert display(c["confidence"]) not in (None, "0%", "1%"), c   # the reported bug
    assert body["corrected_answer"] == "1905", body


def contradicted_and_corrected(body):
    c = body["claims"][0]
    assert c["status"] == "CONTRADICTED", c
    assert "1906" not in body["corrected_answer"] and "1905" in body["corrected_answer"]


def withheld(body):
    c = body["claims"][0]
    assert c["status"] != "SUPPORTED", c
    assert "1905" not in body["corrected_answer"], body
    assert body["corrected_answer"] == ("The available evidence is not sufficient "
                                        "to provide a verified answer."), body
    assert any(r.get("claim") == "1905" for r in body["removed_claims"]), body


def number_contradicted(body):
    c = body["claims"][0]
    assert c["status"] == "CONTRADICTED", c
    assert c["consistency"]["status"] == "FAIL", c
    assert "three died" in body["corrected_answer"], body


run("1. claim explicitly supported by evidence", Q, EINSTEIN_EV, "1905",
    expect=supported_and_correct)
run("2. claim contradicted by the evidence", Q, EINSTEIN_EV, "1906",
    expect=contradicted_and_corrected)
run("3. evidence insufficient (Nobel prize year)",
    "What year did Einstein win the Nobel Prize?", EINSTEIN_EV, "1905",
    expect=withheld)
run("4. number/percentage claim (Kansas)",
    "How many people died in the Kansas listeria outbreak?", KANSAS,
    "Five people in Kansas have died from listeriosis.",
    expect=number_contradicted)
run("5a. Einstein biography WITHOUT the year; generator answers 1905 anyway",
    Q, BIO_EV, "1905", expect=withheld)
run("5b. Einstein biography WITHOUT the year; generator abstains then retries 1905",
    Q, BIO_EV, "I don't have enough information to answer this question.", plain="1905",
    expect=withheld)
print("=" * 78)
print("ALL SCENARIOS PASSED")
