#!/usr/bin/env python3
"""Join controlled-v0 model responses to the separate key and write diagnostics."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate_outputs import evaluate_row, summarize  # noqa: E402
from controlled_output_utils import extract_answer, parse_selective_json  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} in {path} must be an object")
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No evaluated rows to write to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    default_dir = HERE / "serialized" / "controlled-v0"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=default_dir / "model_outputs.jsonl")
    parser.add_argument("--key", type=Path, default=default_dir / "evaluation_key.jsonl")
    parser.add_argument(
        "--inputs", type=Path, default=None,
        help="Allow-listed inputs for source-ID diagnostics (default: model_inputs.jsonl beside --key)",
    )
    parser.add_argument(
        "--outdir", type=Path, default=None,
        help="Report directory (default: results beside --key)",
    )
    args = parser.parse_args()
    if args.inputs is None:
        args.inputs = args.key.parent / "model_inputs.jsonl"
    if args.outdir is None:
        args.outdir = args.key.parent / "results"
    try:
        outputs = read_jsonl(args.outputs)
        if not outputs:
            raise ValueError(
                "No model-output records found. The inference run may have stopped before "
                "the first response; configure Cloudflare credentials and rerun the runner first."
            )
        keys = read_jsonl(args.key)
        inputs_by_id = {}
        if args.inputs.exists():
            inputs = read_jsonl(args.inputs)
            inputs_by_id = {row["input_id"]: row for row in inputs}
            if len(inputs_by_id) != len(inputs):
                raise ValueError("Model inputs contain duplicate input IDs")
        key_by_id = {row["input_id"]: row for row in keys}
        if len(key_by_id) != len(keys):
            raise ValueError("Evaluation key contains duplicate input IDs")
        seen = set()
        evaluated = []
        for output in outputs:
            input_id = output.get("input_id")
            strategy = output.get("strategy")
            if not input_id or input_id not in key_by_id:
                raise ValueError(f"Output has unknown or missing input_id: {input_id}")
            record_key = (input_id, strategy)
            if record_key in seen:
                raise ValueError(f"Duplicate output for input_id/strategy: {record_key}")
            seen.add(record_key)
            key = key_by_id[input_id]
            if "initial_answer" not in output or "final_answer" not in output:
                raise ValueError(f"Output {record_key} lacks initial/final answer")
            final_answer = output["final_answer"]
            parser_status = output.get("parser_status", "")
            parsed_response = None
            if strategy == "selective_correction" and output.get("raw_response"):
                parsed_response, _ = parse_selective_json(output["raw_response"])
                final_answer, parser_status = extract_answer(strategy, output["raw_response"])
            eval_input = {
                "case_id": f"{key['item_id']}:{key['draft_state']}",
                "condition": f"{key['scenario_id']}__draft_{key['draft_state']}",
                "strategy": strategy,
                "initial_answer": output["initial_answer"],
                "final_answer": final_answer,
                "gold_answers": [key["truth_key"]["gold_answer"]],
                "foil_answers": [key["truth_key"]["false_claim"]],
            }
            row = evaluate_row(eval_input)
            row.update({
                "input_id": input_id,
                "item_id": key["item_id"],
                "draft_state": key["draft_state"],
                "scenario_id": key["scenario_id"],
                "answerability": key["answerability"],
                "parser_status": parser_status,
                "model": output.get("model", ""),
                "prompt_version": output.get("prompt_version", ""),
                "raw_response": output.get("raw_response", ""),
                "gold_answer": key["truth_key"]["gold_answer"],
                "false_claim": key["truth_key"]["false_claim"],
                "truth_relation_by_source": json.dumps(
                    key["annotation_key"]["truth_relation_by_source"], ensure_ascii=False
                ),
                "decision": parsed_response.get("decision", "") if parsed_response else "",
                "evidence_status": parsed_response.get("evidence_status", "") if parsed_response else "",
                "supporting_source_ids": ",".join(parsed_response.get("supporting_source_ids", [])) if parsed_response else "",
                "contradicting_source_ids": ",".join(parsed_response.get("contradicting_source_ids", [])) if parsed_response else "",
            })
            if input_id in inputs_by_id and parsed_response is not None:
                source_truth = key["annotation_key"]["truth_relation_by_source"]
                supporting = set(parsed_response.get("supporting_source_ids", []))
                contradicting = set(parsed_response.get("contradicting_source_ids", []))
                input_sources = {
                    passage["source_id"] for passage in inputs_by_id[input_id].get("passages", [])
                }
                relation_correct = 0
                for source_id, truth_relation in source_truth.items():
                    if truth_relation == "irrelevant":
                        expected = "neither"
                    else:
                        supports_draft = (
                            (truth_relation == "supports_truth" and key["draft_state"] == "correct")
                            or (truth_relation == "contradicts_truth" and key["draft_state"] == "incorrect")
                        )
                        expected = "support" if supports_draft else "contradict"
                    actual = (
                        "both" if source_id in supporting and source_id in contradicting
                        else "support" if source_id in supporting
                        else "contradict" if source_id in contradicting
                        else "neither"
                    )
                    relation_correct += int(actual == expected)
                denom = len(source_truth)
                row.update({
                    "source_id_arrays_disjoint": int(not (supporting & contradicting)),
                    "source_ids_valid": int(not ((supporting | contradicting) - input_sources)),
                    "draft_relative_source_classification_accuracy": relation_correct / denom if denom else "",
                })
            else:
                row.update({
                    "source_id_arrays_disjoint": "",
                    "source_ids_valid": "",
                    "draft_relative_source_classification_accuracy": "",
                })
            evaluated.append(row)
        summary = summarize(evaluated)
        for aggregate in summary:
            group = [r for r in evaluated if r["condition"] == aggregate["condition"] and r["strategy"] == aggregate["strategy"]]
            aggregate["source_id_arrays_disjoint_count"] = sum(
                int(r["source_id_arrays_disjoint"]) for r in group if r["source_id_arrays_disjoint"] != ""
            )
            aggregate["source_ids_valid_count"] = sum(
                int(r["source_ids_valid"]) for r in group if r["source_ids_valid"] != ""
            )
            attributed = [r["draft_relative_source_classification_accuracy"] for r in group if r["draft_relative_source_classification_accuracy"] != ""]
            aggregate["mean_draft_relative_source_classification_accuracy"] = (
                sum(attributed) / len(attributed) if attributed else ""
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 2

    write_csv(args.outdir / "per_example.csv", evaluated)
    write_csv(args.outdir / "summary.csv", summary)
    print(f"Evaluated {len(evaluated)} model outputs across {len(summary)} scenario/draft/strategy groups.")
    print(f"Per-example results: {args.outdir / 'per_example.csv'}")
    print(f"Summary: {args.outdir / 'summary.csv'}")
    print("Exact match and token F1 are lexical diagnostics, not factuality judgments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
