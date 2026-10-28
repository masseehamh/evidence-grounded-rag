#!/usr/bin/env python3
"""Report selective-output contract issues without changing model responses."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from controlled_output_utils import extract_answer, parse_selective_json

DECISIONS = {"preserve", "correct", "qualify", "abstain"}
EVIDENCE_STATUSES = {"supports_draft", "contradicts_draft", "conflicting", "insufficient", "irrelevant"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def norm(text: str) -> str:
    return " ".join(text.casefold().split())




def validate_batch(
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> dict[Any, dict[str, Any]]:
    """Validate one-to-one input/output coverage without modifying either batch."""
    by_id: dict[Any, dict[str, Any]] = {}
    for row in inputs:
        if "input_id" not in row:
            raise ValueError("Every input must contain input_id")
        input_id = row["input_id"]
        if input_id in by_id:
            raise ValueError("Input IDs must be unique")
        by_id[input_id] = row

    if not outputs:
        raise ValueError("No outputs to validate")

    seen_output_ids: set[Any] = set()
    duplicate_output_ids: set[Any] = set()
    for row in outputs:
        input_id = row.get("input_id")
        if input_id not in by_id:
            raise ValueError(f"Output refers to unknown input_id: {input_id}")
        if input_id in seen_output_ids:
            duplicate_output_ids.add(input_id)
        seen_output_ids.add(input_id)

    if duplicate_output_ids:
        duplicate_list = ", ".join(sorted(str(value) for value in duplicate_output_ids))
        raise ValueError(f"Duplicate output input_id(s): {duplicate_list}")

    missing_ids = set(by_id) - seen_output_ids
    if missing_ids:
        missing_list = ", ".join(sorted(str(value) for value in missing_ids))
        raise ValueError(f"Missing output(s) for input_id(s): {missing_list}")

    return by_id


def assess(output: dict[str, Any], model_input: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    response = output.get("raw_response", "")
    parsed, parse_status = parse_selective_json(response)
    answer, answer_status = extract_answer("selective_correction", response)
    if parsed is None:
        issues.append("invalid_json")
        parsed = {}

    required = {"decision", "evidence_status", "answer", "supporting_source_ids", "contradicting_source_ids"}
    missing = required - parsed.keys()
    if missing:
        issues.append("missing_fields:" + ",".join(sorted(missing)))

    decision = parsed.get("decision", "")
    evidence_status = parsed.get("evidence_status", "")
    if decision not in DECISIONS:
        issues.append("invalid_decision")
    if evidence_status not in EVIDENCE_STATUSES:
        issues.append("invalid_evidence_status")
    if not isinstance(parsed.get("answer"), str):
        issues.append("answer_not_string")

    supporting = parsed.get("supporting_source_ids", [])
    contradicting = parsed.get("contradicting_source_ids", [])
    if not isinstance(supporting, list) or not all(isinstance(x, str) for x in supporting):
        issues.append("supporting_ids_not_string_array")
        supporting = []
    if not isinstance(contradicting, list) or not all(isinstance(x, str) for x in contradicting):
        issues.append("contradicting_ids_not_string_array")
        contradicting = []
    if len(set(supporting)) != len(supporting):
        issues.append("duplicate_supporting_id")
    if len(set(contradicting)) != len(contradicting):
        issues.append("duplicate_contradicting_id")
    if set(supporting) & set(contradicting):
        issues.append("source_arrays_overlap")
    input_ids = {p.get("source_id") for p in model_input.get("passages", [])}
    if (set(supporting) | set(contradicting)) - input_ids:
        issues.append("unknown_source_id")

    if evidence_status == "supports_draft" and contradicting:
        issues.append("status_supports_but_contradiction_ids_present")
    if evidence_status == "contradicts_draft" and supporting:
        issues.append("status_contradicts_but_support_ids_present")
    if evidence_status == "conflicting" and (not supporting or not contradicting):
        issues.append("status_conflicting_without_both_relations")
    if evidence_status == "irrelevant" and (supporting or contradicting):
        issues.append("status_irrelevant_but_answer_bearing_ids_present")

    draft = str(model_input.get("draft_answer", ""))
    final_norm = norm(answer)
    if decision == "correct" and final_norm == norm(draft):
        issues.append("decision_correct_but_answer_unchanged")
    if decision == "preserve" and draft and not re.search(
        rf"(?<!\w){re.escape(draft)}(?!\w)", answer, flags=re.IGNORECASE
    ):
        issues.append("decision_preserve_but_draft_value_not_visible")
    if decision == "qualify" and not final_norm:
        issues.append("decision_qualify_with_empty_answer")
    if decision == "abstain" and final_norm:
        issues.append("decision_abstain_with_nonempty_answer_review")

    return {
        "input_id": output.get("input_id", ""),
        "decision": decision,
        "evidence_status": evidence_status,
        "parser_status": answer_status or parse_status,
        "issue_codes": ";".join(issues),
        "issue_count": len(issues),
        "answer": answer,
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    default_dir = here / "serialized" / "controlled-multisource-v2" / "stratified-24"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=default_dir / "model_inputs.jsonl")
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=default_dir / "output_contract_issues.csv")
    args = parser.parse_args()
    try:
        inputs = read_jsonl(args.inputs)
        outputs = read_jsonl(args.outputs)
        by_id = validate_batch(inputs, outputs)
        results = [
            assess(output, by_id[output["input_id"]])
            for output in outputs
        ]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    flagged = sum(row["issue_count"] > 0 for row in results)
    print(f"Reviewed {len(results)} outputs; {flagged} have at least one contract issue or review flag.")
    print(f"Report: {args.out}")
    print("Flags are diagnostic; responses were not modified and no truth key was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
