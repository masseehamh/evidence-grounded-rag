"""Run the five required scenarios against a RUNNING RAG API over plain HTTP.

    # live Colab backend (real MiniLM / DeBERTa / FLAN-T5):
    python verify_live_api.py https://xxxx.ngrok-free.dev

    # local fallback backend (notebook code, stand-in models):
    python verify_live_api.py http://127.0.0.1:8765

HARD checks (any failure => exit code 1). These are invariants of the
evidence-grounding contract, independent of which model produced the answer:

  * every response carries the fields the results page renders
  * claim confidence is a 0-1 probability or null, never a percentage
  * a SUPPORTED claim containing a number/percentage only when that number
    occurs in the supplied evidence
  * no number appears in the corrected answer unless it occurs in the evidence

Model-dependent expectations (does the generator contradict, does NLI say
entailment, ...) are reported separately as PASS / WARN so a miss can never be
mistaken for a structural failure.
"""
import json
import re
import sys
import urllib.error
import urllib.request

TIMEOUT = 300  # real FLAN-T5 + DeBERTa on CPU can take a while per request

HARD = []   # (scenario, check, detail)
SOFT = []   # (scenario, check, ok, detail)


def hard(scenario, ok, check, detail=""):
    HARD.append((scenario, check, detail))
    if not ok:
        HARD[-1] = (scenario, "FAIL: " + check, detail)
    return ok


def soft(scenario, ok, check, detail=""):
    SOFT.append((scenario, check, ok, detail))


def http(base, path, payload=None, method=None):
    url = base.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method or ("POST" if data else "GET"),
        headers={"Content-Type": "application/json", "ngrok-skip-browser-warning": "1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return 0, str(exc)


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    "million": 1000000, "billion": 1000000000,
}


def numeric_tokens(text):
    """Digits and number-words in a normalised form, so '1,200' == '1200' and
    'four' == '4'. Both evidence and claims go through this."""
    tokens = set()
    for raw in re.findall(r"\d[\d,\.]*", text or ""):
        tokens.add(raw.strip(",.").replace(",", "").replace(".", ""))
    for word in re.findall(r"[A-Za-z\-']+", (text or "").lower()):
        for part in re.split(r"[-']", word):
            if part in NUMBER_WORDS:
                tokens.add(str(NUMBER_WORDS[part]))
    return {t for t in tokens if t}


def structural_checks(scenario, body):
    """Fields the frontend renders, for one /api/ask response."""
    if not hard(scenario, isinstance(body, dict), "response is a JSON object", str(body)[:200]):
        return
    status = body.get("verification_status")
    hard(scenario, isinstance(status, str) and status.strip() != "",
         "verification_status is a non-empty string", repr(status))
    hard(scenario, isinstance(body.get("claims"), list), "claims is a list",
         type(body.get("claims")).__name__)
    hard(scenario, "corrected_answer" in body and isinstance(body.get("corrected_answer"), str),
         "corrected_answer is a string", repr(body.get("corrected_answer"))[:120])
    hard(scenario, "original_answer" in body, "original_answer present",
         type(body.get("original_answer")).__name__)
    for i, claim in enumerate(body.get("claims") or []):
        if not isinstance(claim, dict):
            hard(scenario, False, f"claim {i} is an object", repr(claim)[:120])
            continue
        st = str(claim.get("status", "")).upper()
        hard(scenario, st in {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"},
             f"claim {i} status vocabulary", repr(claim.get("status")))
        conf = claim.get("confidence")
        hard(scenario, conf is None or (isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0),
             f"claim {i} confidence is a 0-1 fraction or null (never a percentage)",
             repr(conf))
        nli_conf = claim.get("nli_confidence")
        hard(scenario,
             nli_conf is None or (isinstance(nli_conf, (int, float)) and 0.0 <= nli_conf <= 1.0),
             f"claim {i} nli_confidence is a 0-1 fraction or null", repr(nli_conf))
        cons = claim.get("consistency")
        if cons is not None:
            c_status = str((cons or {}).get("status", "")).upper()
            hard(scenario, c_status in {"PASS", "FAIL", "NOT_CHECKED"},
                 f"claim {i} number/entity check status", repr(c_status))


def grounding_checks(scenario, body, evidence):
    """Numbers may only be supported by evidence that actually contains them."""
    if not isinstance(body, dict) or not isinstance(body.get("claims"), list):
        return
    evidence_nums = numeric_tokens(evidence)
    for i, claim in enumerate(body["claims"]):
        if not isinstance(claim, dict) or str(claim.get("status", "")).upper() != "SUPPORTED":
            continue
        claim_nums = numeric_tokens(claim.get("claim", ""))
        missing = sorted(claim_nums - evidence_nums)
        hard(scenario, not missing,
             f"claim {i} SUPPORTED only for numbers present in the evidence",
             f"claim {claim.get('claim')!r} asserts {missing} not found in the evidence"
             if missing else "")
        ev_text = str(claim.get("evidence") or "")
        hard(scenario, bool(ev_text.strip()),
             f"claim {i} SUPPORTED carries the supporting evidence text",
             f"claim {claim.get('claim')!r} has empty evidence")
    corrected = str(body.get("corrected_answer") or "")
    missing = sorted(numeric_tokens(corrected) - evidence_nums)
    hard(scenario, not missing,
         "corrected answer contains no number absent from the evidence",
         f"corrected answer {corrected!r} asserts {missing} not found in the evidence"
         if missing else "")


# ---------------------------------------------------------------- scenarios --
Q_YEAR = "What year is described as Einstein's annus mirabilis (miracle year)?"
EV_SUPPORTED = ("In 1905, sometimes described as his annus mirabilis (miracle year), "
                "Albert Einstein published four groundbreaking papers on the photoelectric "
                "effect, Brownian motion, special relativity and mass-energy equivalence.")
EV_CONTRADICTED = ("In this account of events, Einstein's miracle year was 1906, when he "
                   "published four groundbreaking papers on the photoelectric effect.")
EV_BIOGRAPHY = ("Albert Einstein was born on 14 March 1879 in Ulm, in the German Empire. "
                "In 1895 he attempted admission to the Swiss Federal Polytechnic in Zurich, "
                "and in 1896 he renounced his German citizenship and became Swiss. After "
                "graduating from the Polytechnic in 1900, he worked at the Swiss patent "
                "office in Bern from 1902. He was appointed professor at the University of "
                "Zurich in 1909, joined the Prussian Academy of Sciences in Berlin in 1914, "
                "was awarded the Nobel Prize in Physics in 1921, emigrated to the United "
                "States in 1933, and died on 18 April 1955 in Princeton, New Jersey.")
EV_NUMBERS = ("The prototype was evaluated on a test set containing 120 examples. Measured "
              "accuracy on the held-out set was 91%. No results were reported for a 40% "
              "reduction in hallucinations across all settings.")

SCENARIOS = [
    {
        "name": "1. claim explicitly supported by the evidence",
        "question": Q_YEAR,
        "evidence": EV_SUPPORTED,
        "soft": lambda b: soft("1", any(
            str(c.get("status", "")).upper() == "SUPPORTED" for c in b.get("claims", [])),
            "at least one claim is SUPPORTED",
            "overall=" + str(b.get("verification_status"))),
    },
    {
        "name": "2. claim contradicted by the evidence",
        "question": Q_YEAR,
        "evidence": EV_CONTRADICTED,
        "soft": lambda b: soft("2", any(
            str(c.get("status", "")).upper() == "CONTRADICTED" for c in b.get("claims", [])),
            "at least one claim is CONTRADICTED (generator disagreed with the evidence)",
            "if the generator simply repeated the evidence, the contradiction path was not "
            "exercised here - backend-tests/manual_scenarios_check.py scripts the generator "
            "to force it"),
    },
    {
        "name": "3. evidence insufficient for the question",
        "question": "In what year did Albert Einstein receive the Nobel Prize?",
        "evidence": EV_SUPPORTED,
        "soft": lambda b: soft("3", str(b.get("verification_status", "")).upper()
                               != "FULLY SUPPORTED", "overall is not FULLY SUPPORTED",
                               "overall=" + str(b.get("verification_status"))),
    },
    {
        "name": "4. Einstein biography that never states the annus mirabilis year",
        "question": Q_YEAR,
        "evidence": EV_BIOGRAPHY,
        "soft": lambda b: soft("4", str(b.get("verification_status", "")).upper()
                               not in {"FULLY SUPPORTED"},
                               "the year is not reported as verified by this evidence",
                               "overall=" + str(b.get("verification_status"))
                               + " | corrected=" + str(b.get("corrected_answer"))[:120]),
    },
    {
        "name": "5. answer containing a number / percentage",
        "question": "What accuracy is reported on the held-out set, and how many examples "
                    "were used?",
        "evidence": EV_NUMBERS,
        "soft": lambda b: soft("5", any(
            numeric_tokens(c.get("claim", "")) and
            str((c.get("consistency") or {}).get("status", "")).upper() in
            {"PASS", "FAIL", "NOT_CHECKED"} for c in b.get("claims", [])),
            "a numeric claim ran through the number/entity check",
            "overall=" + str(b.get("verification_status"))),
        "soft2": lambda b: soft("5", any(
            numeric_tokens(c.get("claim", "")) and
            str(c.get("status", "")).upper() == "SUPPORTED" for c in b.get("claims", [])),
            "a numeric claim is SUPPORTED (needs the real generator to answer 91%/120)",
            "overall=" + str(b.get("verification_status"))),
    },
]


def main(base):
    status, body = http(base, "/api/health")
    if status != 200:
        if status == 0:
            print(f"HEALTH CHECK FAILED: could not reach {base} ({body})")
        else:
            print(f"HEALTH CHECK FAILED: HTTP {status} {body[:300]}")
        print("If this is a Colab/ngrok URL, restart the runtime and re-run the "
              "FastAPI + ngrok cell.")
        return 1
    print(f"health: HTTP {status} {body[:120]}")

    # Distinguish the local stand-in backend from the real Colab pipeline.
    # GET (not POST) so the probe cannot overwrite a scripted answer.
    # 405 = the route exists but rejects GET -> the test-only /__set_answer route.
    # 404 = no such route -> the notebook's own FastAPI app.
    code, _ = http(base, "/__set_answer")
    scripted = code == 405
    generator = ("SCRIPTED stand-in generator (local fallback backend)"
                 if scripted else "no /__set_answer route -> real FLAN-T5 generator")
    print(f"generator: {generator}")
    print("-" * 78)

    for sc in SCENARIOS:
        print("SCENARIO:", sc["name"])
        status, body = http(base, "/api/ask", payload={
            "question": sc["question"], "mode": "manual", "evidence": sc["evidence"]})
        if status != 200:
            hard(sc["name"], False, "HTTP 200 from /api/ask", f"HTTP {status} {body[:300]}")
            print(f"  HTTP {status} - see above")
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            hard(sc["name"], False, "response parses as JSON", body[:300])
            print("  non-JSON response:", body[:200].replace("\n", " "))
            continue

        structural_checks(sc["name"], data)
        grounding_checks(sc["name"], data, sc["evidence"])
        print(f"  overall : {data.get('verification_status')}")
        print(f"  original: {str(data.get('original_answer'))[:100]!r}")
        print(f"  corrected: {str(data.get('corrected_answer'))[:100]!r}")
        for claim in data.get("claims", []) or []:
            if not isinstance(claim, dict):
                continue
            conf = claim.get("confidence")
            shown = "-" if conf is None else f"{round(conf * 100 if conf <= 1 else conf)}%"
            print(f"    - {str(claim.get('claim'))[:70]!r}")
            print(f"      status={claim.get('status')} nli={claim.get('nli_label')} "
                  f"confidence={conf!r} (displayed {shown}) "
                  f"check={(claim.get('consistency') or {}).get('status')}")
        sc["soft"](data)
        if "soft2" in sc:
            sc["soft2"](data)

    print("-" * 78)
    failed = [h for h in HARD if h[1].startswith("FAIL:")]
    print(f"HARD grounding/contract checks: {len(HARD) - len(failed)} passed, "
          f"{len(failed)} failed")
    for scenario, check, detail in failed:
        print(f"  FAILED [{scenario}] {check[6:]}: {detail}")
    warn = 0
    for scenario, check, ok, detail in SOFT:
        print(f"  {'PASS' if ok else 'WARN'} [{scenario}] {check}"
              + ("" if ok else f"  -> {detail}"))
        warn += 0 if ok else 1
    print()
    if failed:
        print("RESULT: FAILED - the evidence-grounding contract was violated.")
        return 1
    print(f"RESULT: PASSED - all structural and grounding checks held"
          f"{' (' + str(warn) + ' model-dependent expectation(s) not met, see WARN above)' if warn else ''}.")
    print(f"generator was: {generator}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
