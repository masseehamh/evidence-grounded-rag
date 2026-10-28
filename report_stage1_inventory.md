# Stage 1 — Project inventory and report plan

## Project reviewed

**Project:** Evidence-Grounded RAG with Hallucination Detection and Correction  
**Workspace inspected:** `Evidence_Grounded_RAG_V7_short_answer_fix_(1).ipynb`, `CHANGES.md`, the frontend README/package/configuration and source, backend test harness and tests, plus the attached prior report PDF.  
**Inspection date:** 25 October 2026.

## Implementation inventory

| Area | Evidence found | Report treatment |
|---|---|---|
| Core implementation | Google Colab/Jupyter notebook; Python pipeline. No separately maintained backend package was present. | Explain the notebook as the backend source of truth. |
| Answer generation | FLAN-T5-small, loaded through Transformers for inference. A second prompt format is tried after an abstention. | Pretrained inference only; no fine-tuning evidence. |
| Retrieval | Sentence Transformers `all-MiniLM-L6-v2`; cosine semantic score blended with lexical overlap (0.7/0.3); three passages for uploaded documents. | Describe as retrieval/embedding, not training. |
| Claim verification | `cross-encoder/nli-deberta-v3-small` NLI; spaCy `en_core_web_sm` parses claims and named entities. | NLI is a model signal combined with deterministic checks. |
| Additional checks | Claim splitting, answer-type conformance, question-word coverage, verbatim answer span, number/action and named-entity consistency, conservative correction and abstention. | Explain rules and limits; do not equate heuristics with proof of truth. |
| Evidence workflows | Pasted evidence, or uploaded `.txt` file (2,000,000-byte maximum), chunked by paragraphs/sentences with a 60-word target and indexed in memory. Automatic web retrieval is excluded in the final interface. | State final scope accurately; describe retired web retrieval only as development history. |
| API | Notebook FastAPI adapter: `GET /health`, `GET /api/health`, `POST /api/ask`, `POST /api/upload`; ephemeral in-memory document IDs. | Include endpoint and lifecycle table. |
| Frontend | React 18, Vite 6, JavaScript; manual/document modes, API status, result and claim display; demo mode is labelled illustrative. | Explain separation from the Python pipeline. |
| Persistence | No database found. Uploaded documents live in an in-memory dictionary and vanish on runtime restart. | No database schema/table. |
| Evaluation dataset | Optional `wandb/RAGTruth-processed` load, labelled test examples and notebook evaluation routines (including 20/40/100-example defaults). Saved execution evidence establishing final real-model metrics was not located in inspected source files. | Do not report computed metrics without saved output or a reproduced run. Distinguish available method from verified results. |
| Tests | Pytest notebook harness uses fake MiniLM, DeBERTa and FLAN-T5; real spaCy is used. Node frontend tests and optional end-to-end API tests. `CHANGES.md` records prior runs, including 181 pytest checks and 42 frontend checks, plus build and API checks. These are historical development records, not this report's new test run. | Attribute test claims and label stubs. User asked staged drafting; no fresh test runs are implied. |
| Known result | Gandhi question: tests force generator output `India`; deterministic pipeline extracts `1921`, marks original unsupported and corrected answer supported. Tests use stubs, so live model quality remains unverified. | Present as a regression scenario verified under test doubles, not as live model performance. |
| Security/deployment | API CORS permits all origins in prototype; no auth/persistence was found; ngrok/Colab setup documented. | Identify prototype limitations without claiming production readiness. |

## Proposed report plan

1. Deliver the first editable installment with preliminary pages, Chapters 1–4, implementation inventory, diagrams, requirements, and initial references.
2. Add Chapters 5–6 grounded in notebook, frontend, and test code; use only saved test evidence for qualitative outcomes and explicitly report the lack of verified live-model metrics.
3. Add Chapters 7–8, expand citations from primary papers and official documentation, add captions and appendices as needed.
4. Assemble and format a cumulative report. A genuine 80–100-page report requires substantial project-specific explanation and appendices; do not fill pages with repetition. Page-count target will be pursued only where content supports it.

## Information still needed from student

- Student name and USN/registration number
- College, department, university, course/semester
- Guide name/designation and academic year
- Signature/date details required by institution

All are placeholders in the draft. The attached reference PDF is not treated as authority to overwrite the supplied eight-chapter structure or to copy personal details.
