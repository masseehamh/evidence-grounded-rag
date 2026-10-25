# Backend tests

These tests run **your notebook's own code cells** (the notebook is loaded from the folder above this one)
with lightweight stand-ins for MiniLM, DeBERTa and FLAN-T5 (`stubs.py`). Real spaCy is used.

**What this proves:** the notebook's decision logic (claim splitting, number/entity checks, status rules,
correction, FastAPI adapter) behaves correctly for the Einstein example, unsupported questions and
contradicted answers.
**What it does NOT prove:** how the real DeBERTa / FLAN-T5 behave. For that, run the new cells
"8c. Regression tests for the short-answer fix" inside the notebook in Colab.

## Run

```bash
cd backend-tests
pip install -r requirements-test.txt
python -m spacy download en_core_web_sm
python -m pytest -v
```

## Frontend <-> API end-to-end test (optional)

Terminal 1 (starts the notebook's real FastAPI app with stand-in models on port 8765):

```bash
cd backend-tests
python serve_test_api.py
```

Terminal 2:

```bash
cd evidence-grounded-rag-frontend
npm install
# macOS/Linux:
E2E_API_URL=http://127.0.0.1:8765 npm test
# Windows PowerShell:
$env:E2E_API_URL="http://127.0.0.1:8765"; npm test
```

Without `E2E_API_URL`, `npm test` skips the end-to-end tests and runs the rest.
