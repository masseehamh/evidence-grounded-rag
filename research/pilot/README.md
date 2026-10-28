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

## Controlled synthetic development set

`cases.controlled.dev.v0.jsonl` contains 25 fictional items for prompt and pipeline development only. Each item has two draft states (correct and incorrect) crossed with six evidence scenarios (true/high provenance, true/low provenance, false/high provenance, false/low provenance, equal-provenance conflict, and irrelevant-only evidence): 300 item-state combinations in total. This is a deterministic, balanced fixture, not randomized confirmatory data, a source-grounded benchmark, or evidence of model performance. `generate_controlled_dataset.py` recreates it without making model calls. The schema and one illustrative record are in `controlled_dataset.schema.json` and `controlled_dataset.example.json`.

The JSONL includes hidden answer and annotation fields for evaluation. Build model requests with an allow-list containing only the question, draft answer, and passage source IDs/text/provenance labels. Exclude `truth_key`, `annotation_key`, `draft_state`, `answerability`, and `scenario_id`, including from IDs, filenames, and prompt text. Keep the evaluation key in a separate record. See `SELECTIVE_CORRECTION_PROMPT_V0_2.md` for the current development input contract; `SELECTIVE_CORRECTION_PROMPT_V0.md` records the prompt used in the first five-row batch. For a confirmatory study, version the data, randomize provenance assignments independently of passage truth, and reserve held-out items before prompt tuning.

To produce shuffled model-input rows and a separate evaluation key without inference:

```bash
python research/pilot/serialize_controlled_dataset.py
```

The default output directory is ignored by Git. Give only `model_inputs.jsonl` to a model; retain `evaluation_key.jsonl` separately for scoring. The serializer shuffles row and within-item passage order with a fixed seed, uses opaque row IDs, and maps the controlled-v0 `provenance_label` to the prompt's `source_status` field. Set `--seed` to another value to create a different order.

To run a small development batch with the configured Cloudflare Workers AI account, first set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in the environment. From the repository root:

```bash
python research/pilot/run_controlled_dev.py --limit 5
python research/pilot/evaluate_controlled_dev.py
```

The runner defaults to five rows and all four strategies. That is up to 15 model calls: preserve-draft is local, while retrieval-only, generic correction, and selective correction each make one call per selected row. The script prints the estimate before calling the API. To reduce this to five calls, use `--strategies selective_correction`; to select a specific batch use `--start N --limit N`. Inference can incur account cost. Outputs are local and the runner refuses to overwrite an existing output file; choose a new `--output` path for another run. The evaluator joins responses to the key only after generation and reports exact match/token F1 and gold/foil phrase diagnostics, which are not factuality judgments. The selective policy requests JSON; the shared parser extracts the `answer` field from either plain or Markdown-fenced JSON, and `parser_status` records which format it received.

After the first five-row development batch, a prompt clarification was recorded in `SELECTIVE_CORRECTION_PROMPT_V0_2.md`: source-ID arrays are defined relative to the draft answer and must not overlap. The first batch and its descriptive inspection are documented in `DEVELOPMENT_BATCH_REVIEW_V0_1.md`; the balanced 12-row follow-up is described in `DEVELOPMENT_BATCH_REVIEW_V0_2.md`. Keep outputs from different prompt versions in separate files. The confirmatory protocol now notes that an isolated false passage is not identifiable as false from wording alone and calls for multi-source corroboration conditions.

To prepare the next development batch with one row from each evidence-scenario × draft-state cell (12 total), run:

```bash
python research/pilot/prepare_controlled_stratified_batch.py
python research/pilot/run_controlled_dev.py --input research/pilot/serialized/controlled-v0/stratified-12-selective-v0.2/model_inputs.jsonl --limit 12 --strategies selective_correction
python research/pilot/evaluate_controlled_dev.py --outputs research/pilot/serialized/controlled-v0/stratified-12-selective-v0.2/model_outputs.jsonl --key research/pilot/serialized/controlled-v0/stratified-12-selective-v0.2/evaluation_key.jsonl
```

The preparation step makes no model calls. The run makes 12 calls and uses selective-correction prompt v0.2. It is still a development check, not confirmatory evidence.

## Multi-source controlled-v1 development data

The v0.2 batch showed why the single-passage fixture is limited: a model cannot infer that an isolated false claim is false from wording alone. The new `cases.controlled.multisource.dev.v1.jsonl` adds independent agreement, dependent repeated claims, provenance-weighted conflicts, equal conflicts, irrelevant context, and true evidence mixed with irrelevant context. It contains 25 fictional items, 12 evidence configurations, and 2 draft states (600 combinations). Its design is documented in `MULTISOURCE_CONTROLLED_V1_PROTOCOL.md`; the schema and generator are `controlled_multisource_v1.schema.json` and `generate_controlled_multisource_v1.py`.

To create the allow-listed model inputs and evaluation key, then prepare one item per scenario × draft-state cell (24 total):

```bash
python research/pilot/serialize_controlled_multisource_v1.py
python research/pilot/prepare_controlled_multisource_batch.py
```

The prepared inputs include source-family and independence-group metadata; the answer key remains separate. To run only the v0.3 selective prompt on those 24 development rows:

```bash
python research/pilot/run_controlled_dev.py --input research/pilot/serialized/controlled-multisource-v1/stratified-24/model_inputs.jsonl --limit 24 --strategies selective_correction --prompt-file research/pilot/SELECTIVE_CORRECTION_PROMPT_V0_3.md --prompt-version selective-correction-v0.3
python research/pilot/evaluate_controlled_dev.py --outputs research/pilot/serialized/controlled-multisource-v1/stratified-24/model_outputs.jsonl --key research/pilot/serialized/controlled-multisource-v1/stratified-24/evaluation_key.jsonl
```

That run makes 24 model calls. It is a development probe only; inspect the source attribution and decision diagnostics and obtain human review before drawing factuality conclusions.

The completed v0.3 batch review is in `DEVELOPMENT_BATCH_REVIEW_MULTISOURCE_V1.md`. It reports the one-per-cell observations and flags an irrelevant-distractor construction issue; revise a new dataset version and complete human review before increasing the run size.

Prompt v0.4 was run on the same 24 rows for development debugging (24 calls). Its descriptive comparison is in `DEVELOPMENT_PROMPT_COMPARISON_V03_V04.md`; guided review records are in `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_4.md` and `serialized/controlled-multisource-v1/stratified-24/human-review-v0.4/review_packet_completed.csv`. These guided labels are not independent annotation.

## Multi-source controlled-v2 development data

`cases.controlled.multisource.dev.v2.jsonl` is an immutable fixture revision. It changes the v1 irrelevant-only statement from a maintenance interval to a registry-review note, removing its semantic overlap with the maintenance-token question. It retains v1's 25 fictional items and answer assignments, so it is not a new independent sample. The candidate lower/unknown-only policy is in `SELECTIVE_CORRECTION_PROMPT_V0_5.md`; the design decisions and limits are in `MULTISOURCE_CONTROLLED_V2_PROTOCOL.md`.

Generate and prepare the 600-row serialized dataset and balanced 24-row development slice without inference:

```bash
python research/pilot/generate_controlled_multisource_v2.py
python research/pilot/serialize_controlled_multisource_v1.py --input research/pilot/cases.controlled.multisource.dev.v2.jsonl --output-dir research/pilot/serialized/controlled-multisource-v2
python research/pilot/prepare_controlled_multisource_v2_batch.py
```

To run v0.5 on that slice later, use the repository's configured model credentials. This makes 24 model calls and can incur inference cost:

```bash
python research/pilot/run_controlled_dev.py --input research/pilot/serialized/controlled-multisource-v2/stratified-24/model_inputs.jsonl --limit 24 --strategies selective_correction --prompt-file research/pilot/SELECTIVE_CORRECTION_PROMPT_V0_5.md --prompt-version selective-correction-v0.5 --output research/pilot/serialized/controlled-multisource-v2/stratified-24/model_outputs.v0.5.jsonl
python research/pilot/evaluate_controlled_dev.py --outputs research/pilot/serialized/controlled-multisource-v2/stratified-24/model_outputs.v0.5.jsonl --key research/pilot/serialized/controlled-multisource-v2/stratified-24/evaluation_key.jsonl --outdir research/pilot/serialized/controlled-multisource-v2/stratified-24/results-v0.5
```

The v0.5 24-row run and guided review have been completed. See `DEVELOPMENT_BATCH_REVIEW_MULTISOURCE_V2_V0_5.md` for evaluator diagnostics and `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_5.md` for the guided label record. The evaluator treats an explicit empty `answer` string as a valid abstention rather than copying the full JSON response into the answer column. This remains a one-item-per-cell development probe, not confirmatory evidence.

To flag output-contract inconsistencies without changing model outputs or using the answer key:

```bash
python research/pilot/validate_selective_outputs.py --outputs research/pilot/serialized/controlled-multisource-v2/stratified-24/model_outputs.v0.5.jsonl --out research/pilot/serialized/controlled-multisource-v2/stratified-24/results-v0.5/output_contract_issues.csv
```

The validator is diagnostic only. It checks response structure, source-ID arrays, selected decision/status consistency rules, and whether a `correct` decision changed the draft text. It does not determine factuality or repair the model response.

```bash
python research/pilot/run_controlled_dev.py --input research/pilot/serialized/controlled-multisource-v1/stratified-24/model_inputs.jsonl --limit 24 --strategies selective_correction --prompt-file research/pilot/SELECTIVE_CORRECTION_PROMPT_V0_4.md --prompt-version selective-correction-v0.4 --output research/pilot/serialized/controlled-multisource-v1/stratified-24/model_outputs.v0.4.jsonl
python research/pilot/evaluate_controlled_dev.py --outputs research/pilot/serialized/controlled-multisource-v1/stratified-24/model_outputs.v0.4.jsonl --key research/pilot/serialized/controlled-multisource-v1/stratified-24/evaluation_key.jsonl --outdir research/pilot/serialized/controlled-multisource-v1/stratified-24/results-v0.4
```

This repeated use of development inputs is for prompt debugging only; do not treat a v0.3/v0.4 difference on this single 24-row batch as confirmatory evidence.

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
