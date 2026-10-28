#!/usr/bin/env python3
"""Run selected prompt conditions on controlled-v0 model inputs.

The runner reads model_inputs.jsonl only. It never opens evaluation_key.jsonl.
Inference may incur Cloudflare Workers AI cost; the default is five input rows.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from backend.app import DEFAULT_MODEL, cloudflare_chat, cloudflare_configuration
    from research.pilot.controlled_output_utils import extract_answer
except Exception as exc:
    raise SystemExit(
        "Could not import backend.app. Install backend/requirements.txt first. "
        f"Details: {exc}"
    ) from exc


STRATEGIES = ("preserve_draft", "retrieval_only", "generic_correction", "selective_correction")
DEFAULT_SELECTIVE_PROMPT = Path(__file__).with_name("SELECTIVE_CORRECTION_PROMPT_V0_2.md")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Input line {line_number} must be a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"No model inputs found in {path}")
    required = {"input_id", "question", "draft_answer", "passages"}
    for row in rows:
        if not required.issubset(row):
            raise ValueError(f"Model input {row.get('input_id', '?')} is missing fields")
        if set(row) != required:
            raise ValueError(f"Model input {row['input_id']} contains fields outside the allow-list")
    return rows


def selective_system_prompt(prompt_path: Path) -> str:
    source = prompt_path.read_text(encoding="utf-8")
    match = re.search(r"## Candidate system instruction\s*```text\s*(.*?)\s*```", source, re.S)
    if not match:
        raise ValueError(f"Could not find the candidate prompt in {prompt_path}")
    return match.group(1)


def user_payload(row: dict[str, Any]) -> str:
    return json.dumps({
        "question": row["question"],
        "draft_answer": row["draft_answer"],
        "passages": row["passages"],
    }, ensure_ascii=False)


def messages_for(row: dict[str, Any], strategy: str, selective_prompt: str) -> list[dict[str, str]]:
    payload = user_payload(row)
    if strategy == "retrieval_only":
        system = (
            "Answer the question using only the supplied passages. Give a concise answer. "
            "If they do not answer it or they conflict, state that clearly. Do not guess."
        )
    elif strategy == "generic_correction":
        system = (
            "Review the draft answer against the supplied passages. Correct it only when "
            "the passages support a change. If evidence is insufficient or conflicting, "
            "say so. Return a concise user-facing answer only."
        )
    elif strategy == "selective_correction":
        system = selective_prompt
    else:
        raise ValueError(f"No model prompt is defined for strategy {strategy}")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload},
    ]


def main() -> int:
    default_dir = Path(__file__).resolve().parent / "serialized" / "controlled-v0"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=default_dir / "model_inputs.jsonl")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output JSONL (default: model_outputs.jsonl beside --input)",
    )
    parser.add_argument("--start", type=int, default=1, help="1-based row number; default 1")
    parser.add_argument("--limit", type=int, default=5, help="Input rows to run; default 5")
    parser.add_argument(
        "--strategies", default=",".join(STRATEGIES),
        help="Comma-separated strategies: " + ", ".join(STRATEGIES),
    )
    parser.add_argument("--pause", type=float, default=0.25, help="Pause between API calls")
    parser.add_argument("--seed", type=int, default=20261028, help="Deterministic row shuffle seed")
    parser.add_argument(
        "--prompt-file", type=Path, default=DEFAULT_SELECTIVE_PROMPT,
        help="Selective-correction prompt markdown (default: v0.2)",
    )
    parser.add_argument(
        "--prompt-version", default="selective-correction-v0.2",
        help="Version label stored with each response",
    )
    args = parser.parse_args()
    if args.output is None:
        args.output = args.input.parent / "model_outputs.jsonl"
    if args.start < 1 or args.limit < 1 or args.pause < 0:
        parser.error("--start and --limit must be positive, and --pause cannot be negative")
    strategies = tuple(s.strip() for s in args.strategies.split(",") if s.strip())
    if not strategies or len(set(strategies)) != len(strategies):
        parser.error("Provide one or more distinct strategies")
    unknown = sorted(set(strategies) - set(STRATEGIES))
    if unknown:
        parser.error(f"Unknown strategies: {', '.join(unknown)}")

    try:
        rows = load_jsonl(args.input)
        random.Random(args.seed).shuffle(rows)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    selected = rows[args.start - 1:args.start - 1 + args.limit]
    if not selected:
        print(f"No input rows available starting at {args.start}", file=sys.stderr)
        return 2

    model_name = os.getenv("CLOUDFLARE_MODEL", DEFAULT_MODEL)
    api_calls = len(selected) * sum(s != "preserve_draft" for s in strategies)
    print(f"Model: {model_name}")
    print(f"Selected rows: {len(selected)}; strategies: {', '.join(strategies)}")
    print(f"Estimated model calls: {api_calls}; preserve_draft uses no API call.")
    print("Answer keys are not opened or included in requests.")
    if api_calls and not all(cloudflare_configuration()):
        print(
            "Cloudflare credentials are missing in this Command Prompt session. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in the current "
            "terminal, then rerun. No model calls were made.",
            file=sys.stderr,
        )
        return 2
    try:
        prompt = selective_system_prompt(args.prompt_file) if "selective_correction" in strategies else ""
    except (OSError, ValueError) as exc:
        print(f"Prompt error: {exc}", file=sys.stderr)
        return 2

    if args.output.exists() and args.output.stat().st_size > 0:
        print(f"Output already exists; choose a new --output path: {args.output}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            for index, row in enumerate(selected, start=1):
                for strategy in strategies:
                    if strategy == "preserve_draft":
                        response = row["draft_answer"]
                        final_answer = response
                        parser_status = "not_applicable"
                    else:
                        response = cloudflare_chat(messages_for(row, strategy, prompt), max_tokens=240)
                        final_answer, parser_status = extract_answer(strategy, response)
                        time.sleep(args.pause)
                    record = {
                        "input_id": row["input_id"],
                        "strategy": strategy,
                        "initial_answer": row["draft_answer"],
                        "final_answer": final_answer,
                        "raw_response": response,
                        "parser_status": parser_status,
                        "model": model_name,
                        "prompt_version": args.prompt_version if strategy == "selective_correction" else strategy,
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                print(f"Completed selected row {index}/{len(selected)}")
    except Exception as exc:
        print(f"Run stopped: {exc}", file=sys.stderr)
        if args.output.exists() and args.output.stat().st_size == 0:
            args.output.unlink()
            print("No output file was retained because no results were written.", file=sys.stderr)
        else:
            print(f"Partial raw model outputs, if any, are in {args.output}", file=sys.stderr)
        return 1
    print(f"Wrote model responses to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
