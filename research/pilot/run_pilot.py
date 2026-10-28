#!/usr/bin/env python3
"""Run a paired evidence-correction pilot with the project's Cloudflare model.

This script produces model outputs, not research conclusions. The default data
are illustrative smoke cases; the source-checked starter set is still not a
validated benchmark. Requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Import the same inference function used by the application so the pilot uses
# the configured Cloudflare model and existing error handling.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from backend.app import DEFAULT_MODEL, cloudflare_chat
except Exception as exc:  # dependency/configuration errors should be actionable
    raise SystemExit(
        "Could not import backend.app. Install backend/requirements.txt first. "
        f"Details: {exc}"
    ) from exc


def ask(messages: list[dict[str, str]], max_tokens: int = 180) -> str:
    return cloudflare_chat(messages, max_tokens=max_tokens)


def generate_initial(question: str) -> str:
    return ask([
        {"role": "system", "content": (
            "Answer the question concisely. If uncertain, say you are uncertain. "
            "Do not explain your reasoning."
        )},
        {"role": "user", "content": question},
    ])


def answer_with_evidence(question: str, evidence: str) -> str:
    return ask([
        {"role": "system", "content": (
            "Answer the question using the supplied evidence. Give a concise answer. "
            "If the evidence does not answer the question, say that it is insufficient. "
            "Do not add an explanation."
        )},
        {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{evidence}"},
    ])


def correct_with_evidence(question: str, initial_answer: str, evidence: str) -> str:
    return ask([
        {"role": "system", "content": (
            "Review the draft answer against the supplied evidence. Correct it only "
            "when the evidence supports a change. If the evidence is insufficient or "
            "ambiguous, preserve the answer and explicitly say that the evidence is "
            "insufficient to verify it. Return a concise answer only."
        )},
        {"role": "user", "content": (
            f"Question: {question}\n\nDraft answer: {initial_answer}"
            f"\n\nEvidence:\n{evidence}"
        )},
    ])


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            required = (
                "case_id", "question", "gold_answers", "foil_answers",
                "evidence_clean", "evidence_misleading", "source_url",
            )
            missing = [key for key in required if key not in case]
            if missing:
                raise ValueError(f"Line {line_no} missing fields: {missing}")
            if case.get("dataset_version"):
                audit_fields = (
                    "category", "source_title", "source_publisher", "source_accessed_at",
                    "evidence_misleading_type", "evidence_misleading_note",
                )
                missing_audit_fields = [key for key in audit_fields if not case.get(key)]
                if missing_audit_fields:
                    raise ValueError(
                        f"Line {line_no} missing source-audit fields: {missing_audit_fields}"
                    )
                if urlparse(str(case["source_url"])).scheme != "https":
                    raise ValueError(f"Line {line_no} source_url must use HTTPS")
                if case["evidence_misleading_type"] != "synthetic_counterfactual":
                    raise ValueError(
                        f"Line {line_no} misleading evidence must be labeled synthetic_counterfactual"
                    )
            cases.append(case)
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases


def select_cases(cases: list[dict[str, Any]], start: int, limit: int) -> list[dict[str, Any]]:
    """Select a 1-based case range, rejecting empty or invalid ranges."""
    if start < 1:
        raise ValueError("Case start must be at least 1")
    if limit < 1:
        raise ValueError("Case limit must be at least 1")
    selected = cases[start - 1:start - 1 + limit]
    if not selected:
        raise ValueError(f"No cases available starting at case {start}")
    return selected


def write_record(handle, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("research/pilot/cases.smoke.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("research/pilot/outputs.jsonl"))
    parser.add_argument("--limit", type=int, default=5, help="Maximum cases; default 5")
    parser.add_argument("--start", type=int, default=1, help="1-based starting case number; default 1")
    parser.add_argument("--pause", type=float, default=0.25, help="Pause between model calls")
    parser.add_argument("--append", action="store_true", help="Append instead of replacing output")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.start < 1:
        parser.error("--start must be at least 1")
    if args.pause < 0:
        parser.error("--pause cannot be negative")

    try:
        all_cases = load_cases(args.input)
        cases = select_cases(all_cases, args.start, args.limit)
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    model_name = __import__("os").getenv("CLOUDFLARE_MODEL", DEFAULT_MODEL)
    print(f"Model: {model_name}")
    actual_end = args.start + len(cases) - 1
    print(f"Cases: {args.start}-{actual_end} ({len(cases)}); estimated calls: {len(cases) * 5}")
    versions = sorted({str(case.get("dataset_version", "illustrative-smoke-v1")) for case in cases})
    print(f"Dataset version(s): {', '.join(versions)}")
    print("Misleading-condition passages are synthetic counterfactuals, not factual sources.")

    try:
        with args.output.open(mode, encoding="utf-8") as out:
            for index, case in enumerate(cases, start=1):
                print(f"[{index}/{len(cases)}] {case['case_id']}: generating initial answer")
                initial = generate_initial(case["question"])
                time.sleep(args.pause)
                provenance = {
                    "dataset_version": case.get("dataset_version", "illustrative-smoke-v1"),
                    "category": case.get("category", "illustrative_smoke"),
                    "source_title": case.get("source_title", ""),
                    "source_publisher": case.get("source_publisher", ""),
                    "source_accessed_at": case.get("source_accessed_at", ""),
                    "evidence_misleading_type": case.get("evidence_misleading_type", "synthetic_counterfactual"),
                    "evidence_misleading_note": case.get("evidence_misleading_note", ""),
                }
                write_record(out, {
                    "case_id": case["case_id"], "condition": "no_retrieval",
                    "strategy": "no_correction", "initial_answer": initial,
                    "final_answer": initial, "gold_answers": case["gold_answers"],
                    "foil_answers": case["foil_answers"], "source_url": case["source_url"],
                    "model": model_name, "record_type": "smoke_experiment",
                    **provenance,
                })

                for condition, evidence_key in (
                    ("clean", "evidence_clean"),
                    ("misleading", "evidence_misleading"),
                ):
                    evidence = case[evidence_key]
                    print(f"  - {condition}: retrieval-only")
                    retrieved = answer_with_evidence(case["question"], evidence)
                    write_record(out, {
                        "case_id": case["case_id"], "condition": condition,
                        "strategy": "retrieval_only", "initial_answer": retrieved,
                        "final_answer": retrieved, "gold_answers": case["gold_answers"],
                        "foil_answers": case["foil_answers"], "source_url": case["source_url"],
                        "model": model_name, "record_type": "smoke_experiment",
                        **provenance,
                    })
                    time.sleep(args.pause)
                    print(f"  - {condition}: generative correction")
                    corrected = correct_with_evidence(case["question"], initial, evidence)
                    write_record(out, {
                        "case_id": case["case_id"], "condition": condition,
                        "strategy": "generative_correction", "initial_answer": initial,
                        "final_answer": corrected, "gold_answers": case["gold_answers"],
                        "foil_answers": case["foil_answers"], "source_url": case["source_url"],
                        "model": model_name, "record_type": "smoke_experiment",
                        **provenance,
                    })
                    time.sleep(args.pause)
    except Exception as exc:
        print(f"Model run failed: {exc}", file=sys.stderr)
        print(f"Partial outputs, if any, are in {args.output}", file=sys.stderr)
        return 1

    print(f"Wrote model outputs to {args.output}")
    print("Next: evaluate with evaluate_outputs.py and manually inspect flagged examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
