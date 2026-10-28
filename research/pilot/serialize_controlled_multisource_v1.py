#!/usr/bin/env python3
"""Separate model-visible inputs from the evaluation key for multisource-v1."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=here / "cases.controlled.multisource.dev.v1.jsonl")
    parser.add_argument("--output-dir", type=Path, default=here / "serialized" / "controlled-multisource-v1")
    parser.add_argument("--seed", type=int, default=20261030)
    args = parser.parse_args()

    records = read_jsonl(args.input)
    if not records or len({r["item_id"] for r in records}) != len(records):
        parser.error("Input must contain uniquely identified items")
    rng = random.Random(args.seed)
    combinations = []
    for item in records:
        for draft in item["draft_variants"]:
            for evidence in item["evidence_variants"]:
                passages = [{
                    "source_id": p["source_id"],
                    "text": p["text"],
                    "source_status": p["provenance_label"],
                    "source_family": p["source_family"],
                    "independence_group": p["independence_group"],
                } for p in evidence["prompt_passages"]]
                rng.shuffle(passages)
                combinations.append((item, draft, evidence, passages))
    rng.shuffle(combinations)

    model_inputs, evaluation_key = [], []
    for idx, (item, draft, ev, passages) in enumerate(combinations, start=1):
        input_id = f"msdev_{idx:04d}"
        model_inputs.append({
            "input_id": input_id,
            "question": item["question"],
            "draft_answer": draft["answer"],
            "passages": passages,
        })
        evaluation_key.append({
            "input_id": input_id,
            "item_id": item["item_id"],
            "draft_state": draft["draft_state"],
            "scenario_id": ev["scenario_id"],
            "answerability": ev["answerability"],
            "truth_key": item["truth_key"],
            "annotation_key": ev["annotation_key"],
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "model_inputs.jsonl", model_inputs)
    write_jsonl(args.output_dir / "evaluation_key.jsonl", evaluation_key)
    print(f"Wrote {len(model_inputs)} allow-listed model inputs and a separate evaluation key to {args.output_dir}")
    print("No model calls were made. Keep evaluation_key.jsonl out of model context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
