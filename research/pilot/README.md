# Controlled Evidence-Correction Pilot

This folder contains a lightweight, dependency-free evaluator for a small paired experiment. It does not call an LLM and does not fabricate experimental results. Model outputs must be generated separately and saved as JSONL.

## Input format

Each JSONL line represents one model run for one question/condition/strategy:

```json
{
  "case_id": "qa_001",
  "condition": "clean",
  "strategy": "generative_correction",
  "initial_answer": "Paris",
  "final_answer": "Paris",
  "gold_answers": ["Paris"],
  "foil_answers": ["Lyon"]
}
```

Allowed condition labels are descriptive, not enforced: `no_retrieval`, `clean`, `misleading`, `irrelevant`, `conflicting`. Strategy labels are also free text, e.g. `no_correction`, `retrieval_only`, `generative_correction`, `evidence_bound`.

For the no-correction baseline, set `final_answer` equal to `initial_answer`. Keep `case_id` identical across paired conditions and strategies. Use lists of accepted gold-answer aliases and foil-answer aliases.

## Run

Python 3.10+; no third-party packages required:

```bash
python research/pilot/evaluate_outputs.py --input research/pilot/outputs.jsonl --outdir research/pilot/results
python -m unittest research/pilot/test_evaluate_outputs.py
```

The evaluator writes:
- `per_example.csv`: normalized answers, exact-match transitions and token F1;
- `summary.csv`: counts and rates grouped by condition and strategy.

## Metrics and caveats

The script reports exact-match accuracy, mean token F1, correction success among initially incorrect answers, harmful-change rate among initially correct answers, preservation rate, and foil adoption. It uses simple normalized exact match, so it is appropriate only as a smoke-test metric for short-answer pilot items. Open-ended outputs require human adjudication or a validated semantic evaluator; manually audit a sample and report uncertainty.

Do not treat the included unit-test examples as research data. Do not use the pilot evaluator to claim a paper result until the dataset, prompts, model versions, and evaluation protocol are frozen.
