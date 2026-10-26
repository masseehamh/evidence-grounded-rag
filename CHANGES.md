# What changed (V7 -> V8 final scope + Gandhi failure fix)

## Reported failure
Question: "When did Gandhi assume leadership of the Indian National Congress?" with evidence containing
"Assuming leadership of the Indian National Congress in 1921, Gandhi led nationwide campaigns...".
The app answered **"India"**, the corrected answer pasted the **1893 South Africa** sentence into the reply,
the overall badge said CONTAINS HALLUCINATION while the corrected-answer card showed a **hard-coded**
SUPPORTED pill.

## Root causes
1. **No answer/question conformance check.** FLAN-T5-small often replies with a topical fragment (`India`)
   instead of the value the question asks for (a YEAR for "When...?"). Nothing checked the shape of the
   reply, so the fragment reached verification, where "the word occurs somewhere in the evidence" could be
   mistaken for support.
2. **Off-topic corrections.** `attempt_correction` replaced a contradicted claim with a whole retrieved
   evidence sentence on lexical overlap alone, so a true-but-unrelated sentence (South Africa, 1893) was
   pasted into the "corrected" answer of a question about 1921.
3. **The corrected answer was never re-checked, and its badge was a constant.** `App.jsx` rendered
   `<StatusPill status="SUPPORTED" />` for every corrected answer, which could disagree with the overall
   status computed from the claims next to it.
4. **Claim retrieval preferred sentences that merely CONTAIN the answer span**, not the sentence that
   actually discusses the question.

## Fixes (notebook)
| Cell | Change |
|---|---|
| setup | `ddgs` / `beautifulsoup4` installs removed (web retrieval is out of scope) |
| `question_answer_type` / `answer_matches_question_type` (new) | deterministic shape check: "When"->date, "Where"->place, "Who"->person, "How many"->number; open-ended questions unconstrained |
| `question_relevant_sentence` / `extract_short_answer` (new) | mine the evidence sentence(s) that discuss the question for the unique requested value (verbatim, ambiguity => None). Fallback only, re-verified |
| `verify_claim_improved` / `determine_claim_status` | wrong-shape reply => NOT ENOUGH EVIDENCE (never SUPPORTED); a short answer is also checked against the sentence that answers the question, so a copied span in an unrelated sentence becomes CONTRADICTED with the relevant sentence as its evidence |
| `attempt_correction` / `correct_answer_evidence_grounded` | `replacement_is_grounded`: a replacement must be text from the supplied evidence AND question-relevant, else the claim is removed |
| `run_full_rag_pipeline` | adopts the extracted, re-verified value only when the corrected answer cannot serve; otherwise returns `INSUFFICIENT_ANSWER`. Adds `corrected_status` (derived from the corrected answer's own claim statuses) and `corrected_evidence` |
| Gradio / FastAPI | Internet-search tab and `mode="web"` branch removed (manual + document only); overall status now derived from the same claims the page shows |

## Fixes (frontend)
| File | Change |
|---|---|
| `src/App.jsx` | Internet-search card/notes removed; corrected-answer badge reads `result.corrected_status` (neutral `UNCHECKED` when absent); evidence behind an extracted answer is shown |
| `src/api.js` | `buildAskPayload` rejects modes other than manual/document; `normalizeResult` carries `corrected_status` / `corrected_evidence` and maps overall vocabulary onto pills |
| `src/demoData.js`, `src/styles.css`, `README.md` | web-mode styles/notes dropped; demo data carries a `corrected_status`; API docs updated |

## Verified this session (stand-in models, real notebook code + real spaCy)
`pytest` **133 passed** (93 existing + 40 new in `backend-tests/test_final_scope_pipeline.py`, which covers the
Gandhi scenario end-to-end through the API and document mode, status consistency, and the web-mode 400);
`npm test` **26 passed** with `E2E_API_URL` against the notebook's FastAPI app (5 new scope/badge tests in
`tests/final_scope.test.js`); `npm run build` OK; `verify_live_api.py http://127.0.0.1:8765` -> exit 0;
`manual_scenarios_check.py` -> all scenarios passed.
Gandhi scenario now: original `India` -> NOT ENOUGH EVIDENCE (removed), corrected `1921` taken verbatim from
the leadership sentence, corrected_status SUPPORTED, overall NEEDS VERIFICATION (agrees with the claims),
no "South Africa"/1893 anywhere.
**NOT verified:** the live Colab models (FLAN-T5/DeBERTa/MiniLM) — run the notebook's test cells in Colab
after the models load.

---

# What changed (V6 -> V7 short-answer fix)

## Root cause
FLAN-T5 usually answers factual questions with just the value (`1905`). The verifier then sent that bare
fragment to DeBERTa as the NLI *hypothesis*. NLI judges whether a *statement* follows from the evidence; `1905`
is not a statement, so the label was `neutral` and the claim was marked NOT ENOUGH EVIDENCE and removed.
Retrieval had the same blind spot (a claim made only of digits has no words to match).

## Files changed
| File | Change |
|---|---|
| `Evidence_Grounded_RAG_V7_short_answer_fix.ipynb` | New helper cell before `question_relation_is_missing`; edits to `determine_claim_status`, `verify_claim_improved`, `attempt_correction`, `generate_answer` (+`generate_answer_plain`), `run_full_rag_pipeline`, `trace_answer_flow`, the FastAPI cell; new test cells 8c |
| `evidence-grounded-rag-frontend/src/api.js` | `import.meta.env?.` (fixes crash under Node / `npm test`), new `buildAskPayload` |
| `evidence-grounded-rag-frontend/src/App.jsx` | uses `buildAskPayload`; document mode no longer uploads the file twice |
| `evidence-grounded-rag-frontend/tests/manual_mode.test.js`, `e2e_backend.test.js` | new |
| `backend-tests/` | new (pytest suite, stand-in models, test server) |

Unchanged: MiniLM retrieval, FLAN-T5 generation prompt, DeBERTa NLI, claim splitting, number/entity checks,
the RAGTruth evaluation cells, the Gradio tabs, and the frontend design.

## Confidence display ("1% on supported claims") — root cause and verification

**Root cause.** The results page renders `Math.round(confidence)%`. The backend sends the raw DeBERTa
probability as a 0-1 fraction (`nli_confidence`), but an earlier version of the page fed that fraction
straight into `Math.round()`, so `0.97` became **`1%`** — every supported claim showed 1%. A backend that
additionally mis-scaled the value (dividing an already-fractional score by 100) produced the same symptom
through the API path. Two guards now hold the contract: `normalizeConfidence()` in `src/api.js`
(multiplies values ≤1 by 100, clamps to 0-100, rejects non-numbers) applied to every result the page
renders — demo and backend alike — and `_overall_confidence()` in the notebook, which returns either the
raw 0-1 NLI probability or `null` for deterministic `answer_span_in_evidence` support (the UI then shows
"Grounded by evidence checks" instead of a fake score). Nothing is hardcoded or inflated.

**Verified this session (local, stub models — not the live Colab models):** supported claim displays 95%,
contradicted 90%, insufficient 90%, number-check FAIL cases correct; in the browser, the Einstein question
against a biography that never states the annus mirabilis year yields NOT ENOUGH EVIDENCE, the year is
removed, and the corrected answer withholds it.

**New regression tests:** `backend-tests/test_api.py::test_einstein_biography_without_the_year_is_not_verified`
and `::test_confidence_is_a_0_to_1_probability_not_a_percentage`; `backend-tests/manual_scenarios_check.py`
(a runnable five-scenario check that prints raw vs displayed confidence).

## Colab live-backend connection (this session)

Goal: point the same frontend at the real MiniLM / DeBERTa / FLAN-T5 pipeline in Colab while keeping the
local fallback backend working.

| File | Change |
|---|---|
| `Evidence_Grounded_RAG_V7_short_answer_fix_(1).ipynb` | FastAPI + ngrok cell now obtains the ngrok authtoken from a Colab secret `NGROK_AUTH_TOKEN` or a **hidden `getpass` prompt** and applies it with `ngrok.set_auth_token()` — needed because Colab wipes `/root` on every runtime restart, so a saved config never survives. The token is never printed or written into the notebook. The old cell output that had captured the token in a saved `!cat ngrok.yml` output was **redacted** (the token was committed in notebook output; rotate it at dashboard.ngrok.com if the file was ever shared). |
| `evidence-grounded-rag-frontend/src/api.js` | Sends the `ngrok-skip-browser-warning` header on every request; turns an expired tunnel's HTML error page / network failure into a readable message that says how to recover (re-run the ngrok cell, copy the new URL, restart Vite). Never silently falls back to demo data. |
| `evidence-grounded-rag-frontend/.env`, `.env.example` | Documented the two backends: live Colab URL (commented) and local fallback `http://127.0.0.1:8765` (active). |
| `evidence-grounded-rag-frontend/tests/tunnel_errors.test.js` | New: header, HTML-interstitial, network-failure and HTML-404 messages. |
| `backend-tests/verify_live_api.py` | New: runs the five required scenarios against any running API over HTTP — `python verify_live_api.py https://<tunnel>` (live) or `http://127.0.0.1:8765` (fallback). Hard-fails on grounding-contract violations; model-dependent expectations are WARNs. |
| `evidence-grounded-rag-frontend/README.md` | Step-by-step Colab connection guide. |

**Verified locally (stand-in models):** `pytest` 93 passed, `npm test` 21 passed (with `E2E_API_URL` set),
`npm run build` OK, and `verify_live_api.py http://127.0.0.1:8765` → 52 hard checks passed, exit 0.
**NOT verified:** the live Colab tunnel — the last saved tunnel host (`<your-ngrok-host>.ngrok-free.dev`,
now scrubbed from this file and the notebook outputs) answered `ERR_NGROK_3200` because the runtime was
stopped. Real-model verification requires running the notebook in Colab and then
`verify_live_api.py <new-url>`.

## Pre-demo audit (final polish)

| File | Change |
|---|---|
| `Evidence_Grounded_RAG_V7_short_answer_fix_(1).ipynb` | Scrubbed the temporary ngrok tunnel host from saved cell outputs (execution artifacts) and replaced the one hard-coded reserved-domain check with a read of the `NGROK_DOMAIN` Colab secret — no tunnel URL is hardcoded in source anymore. |
| `evidence-grounded-rag-frontend/src/App.jsx` | The results page now explains the legitimate zero-claims case (document relevance gate withholds the answer) in user-facing language instead of the internal "Confirm that the backend includes a `claims` array" hint; the insufficient note no longer promises a claim list when none exists. |
| `evidence-grounded-rag-frontend/tests/demo_workflow.test.js` | New regression guard for the empty-claims insufficient message. |
| `backend-tests/test_acceptance_suite.py` | New: the 5 required acceptance tests (supported / contradicted / insufficient / document / API contract) as an executable suite. |
| `CHANGES.md` | This section; the earlier reference to the concrete tunnel host was replaced with a placeholder. |

**Verified:** `pytest` 181 passed · `npm test` 42 passed (incl. 8 live E2E) · `npm run build` OK ·
browser walkthrough of both workflows against the real FastAPI app · `verify_live_api.py` PASSED.
