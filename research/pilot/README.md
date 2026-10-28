# Controlled Evidence-Correction Pilot

This folder contains a dependency-free output evaluator and a runner that uses the same Cloudflare Workers AI inference function as the Verity RAG backend.

## Important research caveat

`cases.smoke.jsonl` contains five illustrative smoke-test cases. `cases.audited.v1.jsonl` is a 25-case, source-checked starter set, not a validated benchmark or publication-ready dataset. Its clean evidence is paraphrased from the linked authoritative source pages. Every misleading passage is a synthetic false counterfactual; it is not quoted from or attributed to those sources. The case file records source title, publisher, access date, and this counterfactual status for review. See `DATASET_AUDIT.md` for scope, source checks, and limitations.

## Requirements

- Python 3.10+
- Install `backend/requirements.txt`
- Set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` as environment variables. The runner uses `CLOUDFLARE_MODEL` if set; otherwise it uses the backend default.
- Never put API credentials in the repository, command-line arguments, output files, or URLs.

## Run a smoke experiment

From the repository root:

```bash
python research/pilot/run_pilot.py --limit 2 --output research/pilot/outputs.jsonl
python research/pilot/evaluate_outputs.py --input research/pilot/outputs.jsonl --outdir research/pilot/results
python -m unittest discover -s research/pilot -p 'test_*.py' -v
```

The runner uses five model calls per case: one initial answer without evidence, then retrieval-only and correction runs with both clean and misleading evidence. A two-case smoke run therefore makes about ten calls. This is an engineering smoke test, not a full research protocol.

## Run the source-checked starter set

This set has 25 cases, so a complete run makes about 125 model calls. It may incur inference cost and takes longer than the smoke run. From the repository root:

```bash
python research/pilot/run_pilot.py --input research/pilot/cases.audited.v1.jsonl --limit 25 --output research/pilot/outputs.audited-v1.jsonl
python research/pilot/evaluate_outputs.py --input research/pilot/outputs.audited-v1.jsonl --outdir research/pilot/results/audited-v1
```

To continue after a five-case batch without repeating it, use a new output file and select cases 6–25:

```bash
python research/pilot/run_pilot.py --input research/pilot/cases.audited.v1.jsonl --start 6 --limit 20 --output research/pilot/outputs.audited-v1.cases-6-25.jsonl
python research/pilot/evaluate_outputs.py --input research/pilot/outputs.audited-v1.cases-6-25.jsonl --outdir research/pilot/results/audited-v1-cases-6-25
```

The manual GitHub Actions workflow also has an `audited-v1` dataset choice, a 1-based start case, and limits up to 25 cases. Its default remains the small smoke set. The output JSONL and per-example CSV carry dataset and source provenance metadata.

The output JSONL is local and intentionally not committed, because it contains model outputs. Do not use `--append` when re-running the same cases unless you want repeated records.

## Manual review workflow

1. Open `research/pilot/results/per_example.csv` and fill in `manual_factuality_label` and `manual_review_notes` for the rows you adjudicate. Suggested labels are `correct`, `correct_with_caveat`, `mixed_correct_answer_and_error`, `incorrect`, `incorrect_foil`, and `unsupported_or_abstention`.
2. Re-run the evaluator with the reviewed CSV to carry labels into the summary:

   ```bash
   python research/pilot/evaluate_outputs.py --input research/pilot/outputs.jsonl --outdir research/pilot/results --reviewed-per-example research/pilot/results/per_example.csv
   ```

   The evaluator checks that the reviewed rows match the current outputs by case, condition, and strategy. It rejects stale or mismatched review files.
3. Read `summary.csv` for the unchanged exact-match metrics and the manual-label counts. The manual counts reflect only rows with a non-empty label; they do not replace the exact-match results.

## Interpretation

- `no_retrieval/no_correction`: the original answer is left unchanged.
- `clean/retrieval_only` and `misleading/retrieval_only`: the model answers using each evidence condition.
- `clean/generative_correction` and `misleading/generative_correction`: the same no-retrieval initial answer is passed to a separate correction call using the condition's evidence.

The evaluator uses exact-match aliases and token F1, which are only smoke-test metrics for short factoid answers. It also reports whether a gold/foil alias phrase appears in the final answer; these columns and `manual_review_flags` are **diagnostics only**, not semantic correctness judgments. Rows are flagged when the answer mentions a gold alias without exact matching, mentions a foil alias, mentions both gold and foil, or loses exact match after starting correct. The `exact_match_loss_*` columns describe changes in exact-match status only; they do not establish factual harm. The per-example CSV includes `manual_factuality_label` and `manual_review_notes` fields for human adjudication. Summary manual counts are reported separately and only include labels actually entered by a reviewer. For publication-quality work, replace these cases with a properly sourced and audited dataset, freeze prompts/model settings, include sufficient samples, use paired statistical analysis, and manually validate any semantic evaluator.

## Data format

Each case needs `case_id`, `question`, `gold_answers`, `foil_answers`, `evidence_clean`, `evidence_misleading`, and `source_url`. Source-checked cases also include `dataset_version`, `category`, `source_title`, `source_publisher`, `source_accessed_at`, `evidence_misleading_type`, and `evidence_misleading_note`. Keep the same `case_id` across evidence conditions.
