# Verity RAG — Frontend

A beginner-friendly React + Vite frontend for **Evidence-Grounded RAG with Automated Hallucination Detection and Correction**. It is intentionally separate from the existing Python/Colab project and does not rewrite or emulate the AI/ML pipeline.

## Requirements

- Node.js 18+ (Node.js 20 LTS recommended)
- npm
- VS Code (recommended)

## Run locally

1. Extract this folder and open it in VS Code.
2. Open the integrated terminal in this folder.
3. Install dependencies:

   ```bash
   npm install
   ```

4. Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` when your FastAPI service is available. For example:

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8000
   ```

5. Start the development server:

   ```bash
   npm run dev
   ```

6. Open the local URL printed by Vite (usually `http://localhost:5173`).

To create a production build, run `npm run build`. To preview that build, run `npm run preview`.

## Demo mode vs real backend

- **Demo mode** is clearly labelled and uses static, illustrative sample results only. It does not call an AI model, search the internet, or claim that sample output is real.
- **Backend mode** is active when `VITE_API_BASE_URL` is set. Requests are sent to the configured API. If the API is unavailable or returns an error, the UI displays an error and does not silently fall back to sample output.
- **Scope:** only two evidence modes exist in the final demo — **Manual evidence** and **Upload document**. Automatic online retrieval was removed: `buildAskPayload` rejects `mode: "web"`, the UI has no Internet-search card, and `POST /api/ask` answers 400 for it.

Environment variables are read at build/start time by Vite. Restart the dev server after editing `.env`.

## Connecting to the live Google Colab backend (real models)

The same frontend talks to either backend — only `VITE_API_BASE_URL` changes.

1. **In Colab**, open `Evidence_Grounded_RAG_V7_short_answer_fix_(1).ipynb` and run it top to bottom
   (installs, model downloads, pipeline cells, then the **FastAPI + ngrok** cell).
   - The ngrok cell prints `FastAPI is ready: https://<something>.ngrok-free.dev`.
   - If the runtime is fresh, it asks once for your ngrok authtoken through a **hidden prompt**,
     or reads the Colab secret `NGROK_AUTH_TOKEN` if you have added one. The value is never printed
     or saved into the notebook.
   - Copy that HTTPS URL — it changes every time the runtime restarts.
2. **In `.env`**, comment out the `VITE_API_BASE_URL=http://127.0.0.1:8765` line and set
   `VITE_API_BASE_URL=https://<your-url>.ngrok-free.dev`.
3. **Restart the dev server** (`npm run dev`) — Vite reads `.env` only at start-up.
4. The header shows the configured backend and the health indicator turns green once `/api/health`
   answers.
5. **Verify all five scenarios** against the live API from the project root:

   ```bash
   cd backend-tests
   python verify_live_api.py https://<your-url>.ngrok-free.dev
   ```

   It checks the grounding invariants over plain HTTP and exits non-zero on any failure.

**If the Colab runtime stops**, the tunnel URL dies: the frontend shows a clear message telling you to
restart the runtime, re-run the FastAPI + ngrok cell, and paste the new URL — it never falls back to
sample data silently. To go back to the local fallback backend, restore
`VITE_API_BASE_URL=http://127.0.0.1:8765` (started with `cd backend-tests && python serve_test_api.py`).

## API contract (implemented by the notebook FastAPI app)

These are the integration contracts agreed between the backend notebook and this frontend. The notebook's FastAPI app exposes them; adapt `src/api.js` only if the backend changes.

### `GET /health` and `GET /api/health`

Implemented response:

```json
{
  "status": "ok",
  "service": "evidence-grounded-rag-api"
}
```

The UI considers the backend available when this request returns a successful HTTP response. Both paths are registered by the notebook's FastAPI app (`GET /health` and its alias `GET /api/health`).

### `POST /api/ask`

`Content-Type: application/json`

Manual evidence request:

```json
{
  "question": "What does the provided evidence say about the system?",
  "mode": "manual",
  "evidence": "Paste source text here."
}
```

Document request (send it after `POST /api/upload` returned a `document_id`):

```json
{
  "question": "When did Gandhi assume leadership of the Indian National Congress?",
  "mode": "document",
  "document_id": "the id returned by POST /api/upload"
}
```

Suggested response:

```json
{
  "verification_status": "PARTIALLY_VERIFIED",
  "original_answer": "Original generated answer.",
  "corrected_answer": "Evidence-grounded corrected answer.",
  "corrected_status": "SUPPORTED",
  "corrected_evidence": "The evidence sentence the corrected answer was taken from, when it was extracted.",
  "claims": [
    {
      "claim": "A claim from the answer.",
      "status": "SUPPORTED",
      "evidence": "A relevant excerpt from a retrieved source.",
      "nli_label": "entailment",
      "confidence": 0.94,
      "consistency": {
        "status": "PASS",
        "details": "Numbers and entities match the evidence."
      }
    }
  ],
  "removed_claims": [],
  "sources": [
    {
      "title": "Source title",
      "url": "https://example.org/source"
    }
  ]
}
```

Allowed claim statuses in the UI: `SUPPORTED`, `CONTRADICTED`, `NOT_ENOUGH_EVIDENCE`. Verification status is displayed as returned by the backend. `corrected_status` (SUPPORTED / CONTRADICTED / NOT_ENOUGH_EVIDENCE) drives the badge on the corrected-answer card; if a backend omits it, the card shows a neutral `UNCHECKED` badge instead of a hard-coded one. Confidence is expected as a number from 0 to 1 or 0 to 100. Missing optional fields are shown as unavailable.

### `POST /api/upload`

`multipart/form-data`, field name `file`. **Only plain-text `.txt` files, up to 2 MB.** The client checks
both limits first (`validateUploadFile` in `src/api.js`) and shows the reason immediately; the backend
enforces them again:

| Case | Backend response | Message shown |
|---|---|---|
| not a `.txt` file | `415` | "This notebook currently supports .txt uploads only." |
| larger than 2 MB | `413` | "File is too large. Maximum size is 2 MB." |
| empty file | `400` | "The uploaded text file is empty." |

Suggested response:

```json
{
  "document_id": "opaque-document-id",
  "filename": "einstein.txt",
  "message": "Text document ready."
}
```

The frontend keeps the returned `document_id` for a subsequent `/api/ask` request:

```json
{
  "question": "Summarize the document's main finding.",
  "mode": "document",
  "document_id": "opaque-document-id"
}
```

If your pipeline expects the file to be sent with the question in one request, update `src/api.js` and the `handleSubmit` flow accordingly.

### Errors and timeouts

Every request in `src/api.js` fails with a readable message instead of hanging:

| Situation | Message |
|---|---|
| backend unreachable | "Could not reach the backend. Check that FastAPI is running and VITE_API_BASE_URL is correct." |
| no answer within the timeout (15 s health, 60 s upload, 180 s question) | "The backend did not answer in time…" |
| HTTP error with JSON `detail` | the backend's own `detail` text |
| HTML error page (expired tunnel) or non-JSON body | explains that the tunnel/backend returned a web page, with recovery hints |

## Deployment (Render Static Site)

The frontend is a plain static Vite site — deploying it does **not** deploy the backend. The backend runs
separately (the notebook's FastAPI + ngrok cell in Colab, or `python backend-tests/serve_test_api.py`
locally).

Exact settings for the existing Render Static Site:

| Setting | Value |
|---|---|
| Service type | Static Site |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |
| Runtime environment variable | `VITE_API_BASE_URL` = origin of the running backend, e.g. `https://xxxx.ngrok-free.dev` (no trailing slash) |

**Important:** Vite inlines `VITE_API_BASE_URL` at **build** time. On Render it must be set as an
environment variable on the service and the site must be **re-deployed** (Render → Manual Deploy) after
any change to it; editing the variable alone does not update an already-built site.

Configuration rules:

- Never hardcode the ngrok/backend URL in `src/` — it always comes from `VITE_API_BASE_URL`.
- `.env` is gitignored; only `.env.example` (no secrets) is committed. Local development copies the
  backend URL into `.env`.
- The backend currently sends `Access-Control-Allow-Origin: *` (prototype setting, noted in the notebook).
  For anything beyond the demo, restrict `allow_origins` to the Render site origin.

## FastAPI integration notes

1. Expose the endpoints above in FastAPI, calling your existing RAG, claim extraction, NLI verification, and correction functions. Do not duplicate the model in the frontend.
2. Configure CORS for the Vite origin during development, for example `http://localhost:5173`. Restrict origins appropriately for deployment.
3. Set `VITE_API_BASE_URL` to the API origin and restart Vite.
4. Check the header in the app: it should change from **Demo mode** to **API configured**. The health indicator separately reports whether the backend responds.
5. The frontend expects JSON for `/api/ask`. If your current Gradio/Python function uses a different schema, add an adapter endpoint in FastAPI or map the response in `src/api.js`.

## Backend features status

The FastAPI adapter that wraps the notebook functions already exists and is used by this frontend:

- FastAPI adapter around the existing Python/Colab functions: done (notebook cell with the FastAPI app).
- `/api/ask`, `/api/upload`, and `/api/health` request/response formats: done (see above).
- Automatic web retrieval: **removed from the final demo scope** (the final application accepts pasted evidence and uploaded documents only).
- File parsing, chunking, retrieval, and document-ID lifecycle: done for `.txt` uploads (chunking + MiniLM retrieval + existing pipeline).
- Claim extraction, NLI labels/confidence, numeric/entity consistency checks, and correction metadata: done (FLAN-T5 generation -> claims -> MiniLM evidence -> DeBERTa NLI -> number/entity checks -> correction).
- CORS, request size limits, allowed file types, timeouts, and production deployment: CORS open for prototype (`allow_origins=["*"]`), `.txt`-only + 2 MB limits enforced on both sides, client-side timeouts for health/upload/ask; production hardening (restricted origins) still open.

## Tests

Run:

```bash
npm test
```

The built-in Node test suite checks the response normalizer, the API URL helper, upload validation and
the honest-UI guards. `tests/e2e_backend.test.js` additionally drives a **running** backend (both supported
workflows, contradicted/insufficient cases and bad uploads) when `E2E_API_URL` is set — see
`../backend-tests/README.md`. It does not test model quality. Build check:

```bash
npm run build
```

A successful Vite build confirms the frontend bundles; it does not verify that the Python model or API is available.
