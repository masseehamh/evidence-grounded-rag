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
    return {
        "case_id": str(row["case_id"]),
        "condition": str(row["condition"]),
        "strategy": str(row["strategy"]),
        "initial_answer": str(row["initial_answer"]),
        "final_answer": str(row["final_answer"]),
        "gold_answers": " || ".join(gold),
        "initial_exact_match": int(initial_correct),
        "final_exact_match": int(final_correct),
        "accuracy_change": int(final_correct) - int(initial_correct),
        "correction_success": int((not initial_correct) and final_correct),
        "harmful_change": int(initial_correct and (not final_correct)),
        "preserved_correct": int(initial_correct and final_correct),
        "foil_adoption": int(matches(row["final_answer"], foil)) if foil else 0,
        # Phrase-presence diagnostics help flag elaborated answers for review;
        # they must not be interpreted as correctness labels.
        "final_gold_alias_mentioned": int(mentions_alias(row["final_answer"], gold)),
        "final_foil_alias_mentioned": int(mentions_alias(row["final_answer"], foil)) if foil else 0,
        "manual_factuality_label": "",
        "manual_review_notes": "",
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
            "harmful_change_count": sum(r["harmful_change"] for r in group),
            "harmful_change_rate_among_initially_correct": rate(
                sum(r["harmful_change"] for r in group), initial_correct
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
    args = parser.parse_args()
    try:
        rows = read_jsonl(args.input)
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
