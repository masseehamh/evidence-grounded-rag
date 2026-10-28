#!/usr/bin/env python3
"""Generate a deterministic synthetic development set for selective-correction design.

These fictional records are for prompt and pipeline development only. They are not
source-grounded, benchmark, or confirmatory research data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


FAMILIES = [
    {
        "stem": "Vexa",
        "question": "Which signal hue is assigned to {entity}?",
        "attribute": "signal hue",
        "values": ["amber", "teal", "indigo", "coral", "silver", "violet", "ochre", "cyan", "maroon", "mint", "bronze", "lilac"],
    },
    {
        "stem": "Torin",
        "question": "Which channel number is assigned to {entity}?",
        "attribute": "channel number",
        "values": ["143", "271", "389", "457", "523", "641", "719", "853", "967", "1081", "1193", "1327"],
    },
    {
        "stem": "Neral",
        "question": "What maintenance token is assigned to {entity}?",
        "attribute": "maintenance token",
        "values": ["AX-41", "BK-73", "CM-28", "DR-56", "EF-92", "GH-17", "JK-64", "LM-35", "NP-80", "QS-23", "RT-71", "VX-49"],
    },
    {
        "stem": "Quorin",
        "question": "Which route code is assigned to {entity}?",
        "attribute": "route code",
        "values": ["QZ-4", "MN-8", "PL-2", "XB-7", "FT-5", "RY-9", "WC-3", "KD-6", "HJ-1", "SV-0", "UA-2", "BE-5"],
    },
    {
        "stem": "Seln",
        "question": "What shelf code is assigned to {entity}?",
        "attribute": "shelf code",
        "values": ["A17", "C24", "F08", "H31", "K56", "M42", "P19", "R63", "T27", "V84", "X05", "Z38"],
    },
]


def passage(entity: str, attribute: str, value: str) -> str:
    return f"The registry entry for {entity} lists its {attribute} as {value}."


def evidence_variant(
    scenario_id: str,
    answerability: str,
    passages: list[dict[str, str]],
    relations: dict[str, str],
) -> dict:
    return {
        "scenario_id": scenario_id,
        "answerability": answerability,
        "prompt_passages": passages,
        "annotation_key": {"truth_relation_by_source": relations},
    }


def generate() -> list[dict]:
    records = []
    for family_index, family in enumerate(FAMILIES):
        values = family["values"]
        for slot in range(5):
            item_number = family_index * 5 + slot + 1
            entity = f"{family['stem']}-{item_number:02d}"
            # A fixed, transparent permutation makes outputs reproducible while
            # varying the entity-to-answer assignment across items.
            gold = values[(slot * 3 + family_index) % len(values)]
            foil = values[(slot * 3 + family_index + 5) % len(values)]
            question = family["question"].format(entity=entity)
            true_text = passage(entity, family["attribute"], gold)
            false_text = passage(entity, family["attribute"], foil)
            irrelevant_text = f"The registry entry for {entity} lists a maintenance interval of 11 months."

            records.append({
                "schema_version": "controlled-v0",
                "item_id": f"ctrl_{item_number:03d}",
                "question": question,
                "truth_key": {
                    "gold_answer": gold,
                    "false_claim": foil,
                    "review_note": "Fictional deterministic assignment; development data only.",
                },
                "draft_variants": [
                    {"draft_state": "correct", "answer": gold},
                    {"draft_state": "incorrect", "answer": foil},
                ],
                "evidence_variants": [
                    evidence_variant(
                        "true_higher", "answer_present",
                        [{"source_id": "S1", "text": true_text, "provenance_label": "higher"}],
                        {"S1": "supports_truth"},
                    ),
                    evidence_variant(
                        "true_lower", "answer_present",
                        [{"source_id": "S1", "text": true_text, "provenance_label": "lower"}],
                        {"S1": "supports_truth"},
                    ),
                    evidence_variant(
                        "false_higher", "answer_present",
                        [{"source_id": "S1", "text": false_text, "provenance_label": "higher"}],
                        {"S1": "contradicts_truth"},
                    ),
                    evidence_variant(
                        "false_lower", "answer_present",
                        [{"source_id": "S1", "text": false_text, "provenance_label": "lower"}],
                        {"S1": "contradicts_truth"},
                    ),
                    evidence_variant(
                        "equal_conflict", "conflicting",
                        [
                            {"source_id": "S1", "text": true_text, "provenance_label": "higher"},
                            {"source_id": "S2", "text": false_text, "provenance_label": "higher"},
                        ],
                        {"S1": "supports_truth", "S2": "contradicts_truth"},
                    ),
                    evidence_variant(
                        "irrelevant_only", "insufficient",
                        [{"source_id": "S1", "text": irrelevant_text, "provenance_label": "unknown"}],
                        {"S1": "irrelevant"},
                    ),
                ],
            })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).with_name("cases.controlled.dev.v0.jsonl"),
    )
    args = parser.parse_args()
    records = generate()
    if len(records) != 25 or len({row["item_id"] for row in records}) != 25:
        raise ValueError("Generator must produce 25 uniquely identified items")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} synthetic development items to {args.output}")
    print("Each item has 2 draft variants and 6 evidence variants; no model calls were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
