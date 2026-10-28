#!/usr/bin/env python3
"""Create separated model-input and evaluation-key files for controlled-v0.

No inference is performed. Generated files default to an ignored local folder.
"""
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


def serialize(records: list[dict[str, Any]], seed: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    pairs = []
    for record in records:
        for draft in record["draft_variants"]:
            for evidence in record["evidence_variants"]:
                passages = [
                    {
                        "source_id": passage["source_id"],
                        "text": passage["text"],
                        "source_status": passage["provenance_label"],
                    }
                    for passage in evidence["prompt_passages"]
                ]
                rng.shuffle(passages)
                pairs.append((record, draft, evidence, passages))

    rng.shuffle(pairs)
    model_inputs, evaluation_key = [], []
    for index, (record, draft, evidence, passages) in enumerate(pairs, start=1):
        input_id = f"dev_{index:04d}"
        model_inputs.append({
            "input_id": input_id,
            "question": record["question"],
            "draft_answer": draft["answer"],
            "passages": passages,
        })
        evaluation_key.append({
            "input_id": input_id,
            "item_id": record["item_id"],
            "draft_state": draft["draft_state"],
            "scenario_id": evidence["scenario_id"],
            "answerability": evidence["answerability"],
            "truth_key": record["truth_key"],
            "annotation_key": evidence["annotation_key"],
        })
    return model_inputs, evaluation_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=here / "cases.controlled.dev.v0.jsonl")
    parser.add_argument("--output-dir", type=Path, default=here / "serialized" / "controlled-v0")
    parser.add_argument("--seed", type=int, default=20261028)
    args = parser.parse_args()

    records = read_jsonl(args.input)
    if not records or len({row["item_id"] for row in records}) != len(records):
        raise ValueError("Input must contain uniquely identified items")
    model_inputs, evaluation_key = serialize(records, args.seed)
    expected = sum(len(row["draft_variants"]) * len(row["evidence_variants"]) for row in records)
    if len(model_inputs) != expected or len(evaluation_key) != expected:
        raise ValueError("Serialization lost or duplicated an item-state combination")
    if [row["input_id"] for row in model_inputs] != [row["input_id"] for row in evaluation_key]:
        raise ValueError("Model-input IDs and evaluation-key IDs are misaligned")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "model_inputs.jsonl", model_inputs)
    write_jsonl(args.output_dir / "evaluation_key.jsonl", evaluation_key)
    print(f"Wrote {len(model_inputs)} model inputs and a separate evaluation key to {args.output_dir}")
    print("No model calls were made. Keep evaluation_key.jsonl out of model context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
