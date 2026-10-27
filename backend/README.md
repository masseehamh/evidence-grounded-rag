# Evidence-Grounded RAG backend (notebook v8 extraction)

This is a first-pass standalone FastAPI extraction from `Evidence_Grounded_RAG_notebook_fixed_v8.ipynb`.

Routes: `GET /health`, `GET /api/health`, `POST /api/upload` (TXT only), and `POST /api/ask`.

## Local run
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Limitations before deployment
- Syntax-checked only; the real models have not yet been loaded/tested in this standalone file.
- It loads MiniLM, DeBERTa NLI, and FLAN-T5-small on startup. Free hosting may not have enough RAM/disk and cold starts may be slow.
- Uploaded documents are stored in memory and disappear when the service restarts.
- Set the frontend API base URL to the deployed backend URL after deployment.
- Do not commit ngrok tokens or other secrets.
