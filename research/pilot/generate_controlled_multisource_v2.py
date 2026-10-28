#!/usr/bin/env python3
"""Create multisource-v2 by correcting v1's semantically adjacent distractor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_controlled_multisource_v1 import generate as generate_v1


def generate() -> list[dict]:
    """Keep v1's controlled cases fixed; change only version IDs and distractor text."""
    records = generate_v1()
    for index, item in enumerate(records, start=1):
        item["schema_version"] = "controlled-multisource-v2"
        item["item_id"] = f"msctrl2_{index:03d}"
        for variant in item["evidence_variants"]:
            if variant["scenario_id"] in {"irrelevant_only", "true_plus_irrelevant"}:
                for passage in variant["prompt_passages"]:
                    if passage["source_family"] == "Archive-C":
                        passage["text"] = (
                            f"The registry record for {item['question'].split(' assigned to ')[-1].rstrip('?')} "
                            "was reviewed by the records team."
                        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("cases.controlled.multisource.dev.v2.jsonl"),
    )
    args = parser.parse_args()
    records = generate()
    if len(records) != 25 or len({row["item_id"] for row in records}) != 25:
        raise ValueError("Expected 25 uniquely identified development items")
    if any(row["schema_version"] != "controlled-multisource-v2" for row in records):
        raise ValueError("Unexpected schema version")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} fictional v2 items and {len(records)*12*2} item-state/evidence combinations.")
    print("v2 changes only version identifiers and the irrelevant-passage wording; no model calls were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
