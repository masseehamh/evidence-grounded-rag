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
**NOT verified:** the live Colab tunnel — the saved URL (`shakily-country-unstamped.ngrok-free.dev`) answers
`ERR_NGROK_3200` because the runtime is stopped. Real-model verification requires running the notebook in
Colab and then `verify_live_api.py <new-url>`.
