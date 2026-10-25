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
- Internet Search is never simulated. In demo mode it is disabled. With a backend configured, the frontend requests Internet Search mode from `POST /api/ask`; the backend must implement actual retrieval and return real sources.

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

Internet Search request:

```json
{
  "question": "What are the latest findings on topic X?",
  "mode": "web"
}
```

Suggested response:

```json
{
  "verification_status": "PARTIALLY_VERIFIED",
  "original_answer": "Original generated answer.",
  "corrected_answer": "Evidence-grounded corrected answer.",
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

Allowed claim statuses in the UI: `SUPPORTED`, `CONTRADICTED`, `NOT_ENOUGH_EVIDENCE`. Verification status is displayed as returned by the backend. Confidence is expected as a number from 0 to 1 or 0 to 100. Missing optional fields are shown as unavailable.

### `POST /api/upload`

`multipart/form-data`, field name `file`. Suggested response:

```json
{
  "document_id": "opaque-document-id",
  "filename": "document.pdf",
  "message": "Document uploaded and ready for questions."
}
```

The upload response shape is provisional. The frontend sends the file and retains the returned `document_id` for a subsequent `/api/ask` request:

```json
{
  "question": "Summarize the document's main finding.",
  "mode": "document",
  "document_id": "opaque-document-id"
}
```

If your pipeline expects the file to be sent with the question in one request, update `src/api.js` and the `handleSubmit` flow accordingly.

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
- Real Internet Search retrieval and trustworthy source metadata: done in the notebook (DuckDuckGo + fetched page text; snippets are never evidence).
- File parsing, chunking, retrieval, and document-ID lifecycle: done for `.txt` uploads (chunking + MiniLM retrieval + existing pipeline).
- Claim extraction, NLI labels/confidence, numeric/entity consistency checks, and correction metadata: done (FLAN-T5 generation -> claims -> MiniLM evidence -> DeBERTa NLI -> number/entity checks -> correction).
- CORS, request size limits, allowed file types, timeouts, and production deployment: partially (CORS open for prototype; size limit and `.txt`-only check present; production hardening still open).

## Tests

Run:

```bash
npm test
```

The built-in Node test suite checks the response normalizer and API URL helper. It does not test model quality or a live backend. Build check:

```bash
npm run build
```

A successful Vite build confirms the frontend bundles; it does not verify that the Python model or API is available.
