#!/usr/bin/env python3
"""Prepare a hidden-key-separated 12-row development batch, one per stratum."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


SCENARIOS = (
    "true_higher", "true_lower", "false_higher", "false_lower",
    "equal_conflict", "irrelevant_only",
)
DRAFT_STATES = ("correct", "incorrect")


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
    default_dir = here / "serialized" / "controlled-v0"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=default_dir / "model_inputs.jsonl")
    parser.add_argument("--key", type=Path, default=default_dir / "evaluation_key.jsonl")
    parser.add_argument(
        "--output-dir", type=Path,
        default=default_dir / "stratified-12-selective-v0.2",
    )
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()

    try:
        inputs = read_jsonl(args.inputs)
        keys = read_jsonl(args.key)
        input_by_id = {row["input_id"]: row for row in inputs}
        key_by_id = {row["input_id"]: row for row in keys}
        if len(input_by_id) != len(inputs) or len(key_by_id) != len(keys):
            raise ValueError("Inputs and key must have unique input IDs")
        if input_by_id.keys() != key_by_id.keys():
            raise ValueError("Input IDs and evaluation-key IDs do not match")
        strata: dict[tuple[str, str], list[str]] = defaultdict(list)
        for key in keys:
            strata[(key["scenario_id"], key["draft_state"])].append(key["input_id"])
        expected = {(scenario, state) for scenario in SCENARIOS for state in DRAFT_STATES}
        if set(strata) != expected or any(not strata[cell] for cell in expected):
            raise ValueError("Expected all 12 evidence-scenario by draft-state strata")

        rng = random.Random(args.seed)
        chosen_ids = [rng.choice(strata[cell]) for cell in sorted(expected)]
        rng.shuffle(chosen_ids)
        selected_inputs = [input_by_id[input_id] for input_id in chosen_ids]
        selected_keys = [key_by_id[input_id] for input_id in chosen_ids]
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "model_inputs.jsonl", selected_inputs)
    write_jsonl(args.output_dir / "evaluation_key.jsonl", selected_keys)
    manifest = {
        "batch_version": "controlled-v0-stratified-12",
        "selection_seed": args.seed,
        "n_rows": len(selected_inputs),
        "strata": [
            {"scenario_id": row["scenario_id"], "draft_state": row["draft_state"]}
            for row in selected_keys
        ],
        "note": "Development-only balanced sample; one item per scenario x draft-state cell.",
    }
    (args.output_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Prepared {len(selected_inputs)} rows, one for each of 12 strata, in {args.output_dir}")
    print("No inference was performed. Keep evaluation_key.jsonl separate from model context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
