#!/usr/bin/env python3
"""Select one item per multisource-v2 evidence scenario × draft-state cell."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

SCENARIOS = (
    "single_true_higher", "single_true_lower", "single_false_higher", "single_false_lower",
    "independent_agreement_true", "independent_agreement_false",
    "independent_conflict_true_higher", "independent_conflict_false_higher",
    "independent_conflict_equal", "dependent_agreement_false",
    "irrelevant_only", "true_plus_irrelevant",
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
    default_dir = here / "serialized" / "controlled-multisource-v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=default_dir / "model_inputs.jsonl")
    parser.add_argument("--key", type=Path, default=default_dir / "evaluation_key.jsonl")
    parser.add_argument("--output-dir", type=Path, default=default_dir / "stratified-24")
    parser.add_argument("--seed", type=int, default=20261102)
    args = parser.parse_args()
    try:
        inputs, keys = read_jsonl(args.inputs), read_jsonl(args.key)
        input_by_id = {r["input_id"]: r for r in inputs}
        key_by_id = {r["input_id"]: r for r in keys}
        if len(input_by_id) != len(inputs) or len(key_by_id) != len(keys):
            raise ValueError("Inputs and evaluation key must have unique IDs")
        if input_by_id.keys() != key_by_id.keys():
            raise ValueError("Input IDs and evaluation-key IDs do not match")
        cells: dict[tuple[str, str], list[str]] = defaultdict(list)
        for row in keys:
            cells[(row["scenario_id"], row["draft_state"])].append(row["input_id"])
        expected = {(scenario, state) for scenario in SCENARIOS for state in DRAFT_STATES}
        if set(cells) != expected or any(not cells[cell] for cell in expected):
            raise ValueError("Input set does not cover all 24 expected strata")
        rng = random.Random(args.seed)
        selected = [rng.choice(cells[cell]) for cell in sorted(expected)]
        rng.shuffle(selected)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "model_inputs.jsonl", [input_by_id[x] for x in selected])
    write_jsonl(args.output_dir / "evaluation_key.jsonl", [key_by_id[x] for x in selected])
    manifest = {
        "batch_version": "controlled-multisource-v2-stratified-24",
        "selection_seed": args.seed,
        "n_rows": len(selected),
        "strata": [
            {"scenario_id": key_by_id[x]["scenario_id"], "draft_state": key_by_id[x]["draft_state"]}
            for x in selected
        ],
        "note": "Development-only balanced sample; one item per scenario × draft-state cell.",
    }
    (args.output_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Prepared {len(selected)} balanced v2 rows in {args.output_dir}; no inference was performed.")
    print("Keep evaluation_key.jsonl separate from model context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
