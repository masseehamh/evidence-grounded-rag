#!/usr/bin/env python3
"""Create a blinded review sheet and separate key for the multisource-v1 batch."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from controlled_output_utils import extract_answer  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    default_dir = HERE / "serialized" / "controlled-multisource-v1" / "stratified-24"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=default_dir / "model_inputs.jsonl")
    parser.add_argument("--outputs", type=Path, default=default_dir / "model_outputs.jsonl")
    parser.add_argument("--key", type=Path, default=default_dir / "evaluation_key.jsonl")
    parser.add_argument("--outdir", type=Path, default=default_dir / "human-review")
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args()

    try:
        inputs = read_jsonl(args.inputs)
        outputs = read_jsonl(args.outputs)
        keys = read_jsonl(args.key)
        input_by_id = {row["input_id"]: row for row in inputs}
        output_by_id = {row["input_id"]: row for row in outputs}
        key_by_id = {row["input_id"]: row for row in keys}
        if any(len(table) != len(source) for table, source in (
            (input_by_id, inputs), (output_by_id, outputs), (key_by_id, keys)
        )):
            raise ValueError("Inputs, outputs, and key must each have unique input IDs")
        if input_by_id.keys() != output_by_id.keys() or input_by_id.keys() != key_by_id.keys():
            raise ValueError("Input, output, and evaluation-key IDs must match exactly")
        if any(row.get("strategy") != "selective_correction" for row in outputs):
            raise ValueError("This packet builder expects selective-correction outputs only")

        rng = random.Random(args.seed)
        ids = list(input_by_id)
        rng.shuffle(ids)
        packet, reference_key = [], []
        for index, input_id in enumerate(ids, start=1):
            model_input = input_by_id[input_id]
            output = output_by_id[input_id]
            key = key_by_id[input_id]
            review_id = f"review_{index:03d}"
            answer, _status = extract_answer("selective_correction", output.get("raw_response", output["final_answer"]))
            packet.append({
                "review_id": review_id,
                "question": model_input["question"],
                "draft_answer": model_input["draft_answer"],
                "passages": json.dumps(model_input["passages"], ensure_ascii=False),
                "model_answer": answer,
                "observed_action": "",
                "evidence_relation_round1": "",
                "action_appropriateness_round1": "",
                "source_attribution_round1": "",
                "review_notes_round1": "",
                "factuality_label_round2": "",
                "review_notes_round2": "",
            })
            reference_key.append({
                "review_id": review_id,
                "input_id": input_id,
                "item_id": key["item_id"],
                "scenario_id": key["scenario_id"],
                "draft_state": key["draft_state"],
                "answerability": key["answerability"],
                "gold_answer": key["truth_key"]["gold_answer"],
                "false_claim": key["truth_key"]["false_claim"],
                "truth_relation_by_source": json.dumps(
                    key["annotation_key"]["truth_relation_by_source"], ensure_ascii=False
                ),
            })
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.outdir.mkdir(parents=True, exist_ok=True)
    write_csv(args.outdir / "review_packet.csv", packet)
    write_csv(args.outdir / "reference_key.csv", reference_key)
    print(f"Prepared {len(packet)} blinded review rows in {args.outdir}")
    print("Keep reference_key.csv closed until round-one evidence/action/source review is saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
