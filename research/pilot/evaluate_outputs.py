#!/usr/bin/env python3
"""Evaluate paired short-answer correction outputs without external dependencies.

This is a pilot evaluator, not a semantic judge. Exact match is suitable only for
short-answer smoke tests; use adjudicated semantic evaluation for publication.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def normalize(text: Any) -> str:
    text = str(text or "").lower().translate(SUBSCRIPT_DIGITS).strip()
    text = re.sub(r"^\s*(?:answer\s*:\s*)", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def as_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)] if str(value).strip() else []


def matches(answer: Any, aliases: Iterable[str]) -> bool:
    normalized = normalize(answer)
    return bool(normalized) and any(normalized == normalize(alias) for alias in aliases)


def mentions_alias(answer: Any, aliases: Iterable[str]) -> bool:
    """Diagnostic only: whether any normalized gold/foil phrase occurs in the answer.

    This is not a factuality or semantic-correctness judgment.
    """
    answer_tokens = normalize(answer).split()
    if not answer_tokens:
        return False
    for alias in aliases:
        alias_tokens = normalize(alias).split()
        if not alias_tokens or len(alias_tokens) > len(answer_tokens):
            continue
        width = len(alias_tokens)
        if any(answer_tokens[i:i + width] == alias_tokens
               for i in range(len(answer_tokens) - width + 1)):
            return True
    return False


def token_f1(answer: Any, aliases: Iterable[str]) -> float:
    """Maximum token F1 against any gold alias; multiset-aware."""
    pred_tokens = normalize(answer).split()
    if not pred_tokens:
        return 0.0
    best = 0.0
    for alias in aliases:
        gold_tokens = normalize(alias).split()
        if not gold_tokens:
            continue
        remaining: dict[str, int] = defaultdict(int)
        for token in gold_tokens:
            remaining[token] += 1
        overlap = 0
        for token in pred_tokens:
            if remaining[token] > 0:
                overlap += 1
                remaining[token] -= 1
        if overlap:
            precision = overlap / len(pred_tokens)
            recall = overlap / len(gold_tokens)
            score = 2 * precision * recall / (precision + recall)
            best = max(best, score)
    return best


def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    required = ("case_id", "condition", "strategy", "initial_answer", "final_answer")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"Missing required fields {missing} in row: {row}")
    gold = as_aliases(row.get("gold_answers", row.get("gold_answer")))
    foil = as_aliases(row.get("foil_answers", row.get("foil_answer")))
    if not gold:
        raise ValueError(f"Missing gold answer(s) for case {row['case_id']}")

    initial_correct = matches(row["initial_answer"], gold)
    final_correct = matches(row["final_answer"], gold)
    gold_mentioned = mentions_alias(row["final_answer"], gold)
    foil_mentioned = mentions_alias(row["final_answer"], foil) if foil else False
    review_flags = []
    if gold_mentioned and not final_correct:
        review_flags.append("gold_alias_in_nonexact_answer")
    if foil_mentioned:
        review_flags.append("foil_alias_mentioned")
    if gold_mentioned and foil_mentioned:
        review_flags.append("gold_and_foil_both_mentioned")
    if initial_correct and not final_correct:
        review_flags.append("exact_match_loss_after_initial_exact_match")
    return {
        "case_id": str(row["case_id"]),
        "dataset_version": str(row.get("dataset_version", "") or ""),
        "category": str(row.get("category", "") or ""),
        "condition": str(row["condition"]),
        "strategy": str(row["strategy"]),
        "initial_answer": str(row["initial_answer"]),
        "final_answer": str(row["final_answer"]),
        "gold_answers": " || ".join(gold),
        "source_url": str(row.get("source_url", "") or ""),
        "source_title": str(row.get("source_title", "") or ""),
        "source_publisher": str(row.get("source_publisher", "") or ""),
        "source_accessed_at": str(row.get("source_accessed_at", "") or ""),
        "evidence_misleading_type": str(row.get("evidence_misleading_type", "") or ""),
        "evidence_misleading_note": str(row.get("evidence_misleading_note", "") or ""),
        "initial_exact_match": int(initial_correct),
        "final_exact_match": int(final_correct),
        "accuracy_change": int(final_correct) - int(initial_correct),
        "correction_success": int((not initial_correct) and final_correct),
        "exact_match_loss_after_initial_exact_match": int(initial_correct and (not final_correct)),
        "preserved_correct": int(initial_correct and final_correct),
        "foil_adoption": int(matches(row["final_answer"], foil)) if foil else 0,
        # Phrase-presence diagnostics help flag elaborated answers for review;
        # they must not be interpreted as correctness labels.
        "final_gold_alias_mentioned": int(gold_mentioned),
        "final_foil_alias_mentioned": int(foil_mentioned),
        "manual_review_recommended": int(bool(review_flags)),
        "manual_review_flags": ";".join(review_flags),
        "manual_factuality_label": str(row.get("manual_factuality_label", "") or ""),
        "manual_review_notes": str(row.get("manual_review_notes", "") or ""),
        "initial_token_f1": round(token_f1(row["initial_answer"], gold), 6),
        "final_token_f1": round(token_f1(row["final_answer"], gold), 6),
    }


def rate(numerator: int, denominator: int) -> str:
    return "" if denominator == 0 else f"{numerator / denominator:.6f}"


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["condition"], row["strategy"])].append(row)

    summaries = []
    for (condition, strategy), group in sorted(groups.items()):
        n = len(group)
        initial_correct = sum(r["initial_exact_match"] for r in group)
        final_correct = sum(r["final_exact_match"] for r in group)
        initially_wrong = n - initial_correct
        labels = [str(r.get("manual_factuality_label", "") or "").strip().lower()
                  for r in group]
        reviewed = sum(bool(label) for label in labels)
        correct_labels = {"correct", "correct_with_caveat"}
        incorrect_labels = {"incorrect", "incorrect_foil"}
        mixed_labels = {"mixed", "mixed_correct_answer_and_error"}
        abstention_labels = {"abstention", "unsupported_or_abstention"}
        summaries.append({
            "condition": condition,
            "strategy": strategy,
            "n": n,
            "initial_accuracy": rate(initial_correct, n),
            "final_accuracy": rate(final_correct, n),
            "accuracy_delta": f"{(final_correct - initial_correct) / n:.6f}" if n else "",
            "correction_success_count": sum(r["correction_success"] for r in group),
            "correction_success_rate_among_initially_wrong": rate(
                sum(r["correction_success"] for r in group), initially_wrong
            ),
            "exact_match_loss_count": sum(r["exact_match_loss_after_initial_exact_match"] for r in group),
            "exact_match_loss_rate_among_initially_exact_matched": rate(
                sum(r["exact_match_loss_after_initial_exact_match"] for r in group), initial_correct
            ),
            "preserved_correct_count": sum(r["preserved_correct"] for r in group),
            "preservation_rate_among_initially_correct": rate(
                sum(r["preserved_correct"] for r in group), initial_correct
            ),
            "foil_adoption_count": sum(r["foil_adoption"] for r in group),
            "foil_adoption_rate": rate(sum(r["foil_adoption"] for r in group), n),
            "final_gold_alias_mention_rate_diagnostic": rate(
                sum(r["final_gold_alias_mentioned"] for r in group), n
            ),
            "final_foil_alias_mention_rate_diagnostic": rate(
                sum(r["final_foil_alias_mentioned"] for r in group), n
            ),
            "manual_review_recommended_count": sum(
                int(r.get("manual_review_recommended", 0)) for r in group
            ),
            "gold_alias_nonexact_count_diagnostic": sum(
                int(r["final_gold_alias_mentioned"] and not r["final_exact_match"])
                for r in group
            ),
            "gold_and_foil_both_mentioned_count_diagnostic": sum(
                int(r["final_gold_alias_mentioned"] and r["final_foil_alias_mentioned"])
                for r in group
            ),
            "manual_reviewed_count": reviewed,
            "manual_correct_count": sum(label in correct_labels for label in labels),
            "manual_mixed_count": sum(label in mixed_labels for label in labels),
            "manual_incorrect_count": sum(label in incorrect_labels for label in labels),
            "manual_abstention_count": sum(label in abstention_labels for label in labels),
            "manual_other_label_count": sum(
                bool(label) and label not in correct_labels | mixed_labels | incorrect_labels | abstention_labels
                for label in labels
            ),
            "manual_unreviewed_count": n - reviewed,
            "mean_initial_token_f1": f"{sum(r['initial_token_f1'] for r in group) / n:.6f}",
            "mean_final_token_f1": f"{sum(r['final_token_f1'] for r in group) / n:.6f}",
        })
    return summaries


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_no} must be a JSON object")
            rows.append(evaluate_row(row))
    if not rows:
        raise ValueError(f"No JSONL records found in {path}")
    return rows


def read_manual_reviews(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    """Read manual labels/notes from a previously generated per-example CSV."""
    reviews: dict[tuple[str, str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"case_id", "condition", "strategy", "manual_factuality_label", "manual_review_notes"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Reviewed CSV is missing required columns: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            key = (row["case_id"], row["condition"], row["strategy"])
            if key in reviews:
                raise ValueError(f"Duplicate reviewed row key on line {line_no}: {key}")
            reviews[key] = {
                "manual_factuality_label": row.get("manual_factuality_label", "") or "",
                "manual_review_notes": row.get("manual_review_notes", "") or "",
            }
    return reviews


def merge_manual_reviews(
    rows: list[dict[str, Any]], reviews: dict[tuple[str, str, str], dict[str, str]]
) -> list[dict[str, Any]]:
    """Attach reviews by stable row identity and reject stale/mismatched CSVs."""
    row_keys = {(r["case_id"], r["condition"], r["strategy"]) for r in rows}
    review_keys = set(reviews)
    if row_keys != review_keys:
        missing = sorted(row_keys - review_keys)
        extra = sorted(review_keys - row_keys)
        raise ValueError(
            "Reviewed CSV rows do not match this input; "
            f"missing keys: {missing[:3]}, unexpected keys: {extra[:3]}"
        )
    for row in rows:
        key = (row["case_id"], row["condition"], row["strategy"])
        row.update(reviews[key])
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Model-output JSONL file")
    parser.add_argument("--outdir", required=True, type=Path, help="Output directory for CSV reports")
    parser.add_argument(
        "--reviewed-per-example", type=Path,
        help="Previously reviewed per_example.csv; merges human labels/notes and refreshes summary.csv",
    )
    args = parser.parse_args()
    try:
        rows = read_jsonl(args.input)
        if args.reviewed_per_example:
            rows = merge_manual_reviews(rows, read_manual_reviews(args.reviewed_per_example))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    summary = summarize(rows)
    write_csv(args.outdir / "per_example.csv", rows)
    write_csv(args.outdir / "summary.csv", summary)
    print(f"Evaluated {len(rows)} runs across {len(summary)} condition/strategy groups.")
    print(f"Per-example results: {args.outdir / 'per_example.csv'}")
    print(f"Summary: {args.outdir / 'summary.csv'}")
    print("Reminder: exact match/token F1 are pilot metrics, not sufficient for open-ended factuality claims.")
    print("Alias-mention columns are diagnostics only; manually adjudicate factual correctness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
