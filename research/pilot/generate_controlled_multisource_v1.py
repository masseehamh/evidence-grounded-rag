#!/usr/bin/env python3
"""Generate fictional multi-source controlled-v1 development items."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FAMILIES = [
    ("Vexa", "signal hue", ["amber", "teal", "indigo", "coral", "silver", "violet", "ochre", "cyan", "maroon", "mint", "bronze", "lilac"]),
    ("Torin", "channel number", ["143", "271", "389", "457", "523", "641", "719", "853", "967", "1081", "1193", "1327"]),
    ("Neral", "maintenance token", ["AX-41", "BK-73", "CM-28", "DR-56", "EF-92", "GH-17", "JK-64", "LM-35", "NP-80", "QS-23", "RT-71", "VX-49"]),
    ("Quorin", "route code", ["QZ-4", "MN-8", "PL-2", "XB-7", "FT-5", "RY-9", "WC-3", "KD-6", "HJ-1", "SV-0", "UA-2", "BE-5"]),
    ("Seln", "shelf code", ["A17", "C24", "F08", "H31", "K56", "M42", "P19", "R63", "T27", "V84", "X05", "Z38"]),
]

SCENARIOS = (
    "single_true_higher", "single_true_lower", "single_false_higher", "single_false_lower",
    "independent_agreement_true", "independent_agreement_false",
    "independent_conflict_true_higher", "independent_conflict_false_higher",
    "independent_conflict_equal", "dependent_agreement_false",
    "irrelevant_only", "true_plus_irrelevant",
)


def record_passage(
    source_id: str, entity: str, attribute: str, value: str, provenance: str,
    family: str, independence: str,
) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_family": family,
        "independence_group": independence,
        "text": f"The registry entry for {entity} lists its {attribute} as {value}.",
        "provenance_label": provenance,
    }


def evidence(scenario: str, passages: list[dict[str, str]], relations: dict[str, str], answerability: str | None = None) -> dict[str, Any]:
    if answerability is None:
        answerability = "conflicting" if "conflict" in scenario else (
            "insufficient" if scenario == "irrelevant_only" else "answer_present"
        )
    return {
        "scenario_id": scenario,
        "answerability": answerability,
        "prompt_passages": passages,
        "annotation_key": {"truth_relation_by_source": relations},
    }


def generate() -> list[dict[str, Any]]:
    records = []
    for family_index, (stem, attribute, values) in enumerate(FAMILIES):
        for slot in range(5):
            number = family_index * 5 + slot + 1
            entity = f"{stem}-{number:02d}"
            gold = values[(slot * 3 + family_index) % len(values)]
            foil = values[(slot * 3 + family_index + 5) % len(values)]

            def passage(source_id: str, claim: str, status: str, family: str, group: str):
                return record_passage(source_id, entity, attribute, claim, status, family, group)

            one_gold_high = passage("S1", gold, "higher", "Archive-A", "independent-A")
            one_gold_low = passage("S1", gold, "lower", "Archive-A", "independent-A")
            one_foil_high = passage("S1", foil, "higher", "Archive-A", "independent-A")
            one_foil_low = passage("S1", foil, "lower", "Archive-A", "independent-A")
            gold_high_a = passage("S1", gold, "higher", "Archive-A", "independent-A")
            gold_low_b = passage("S2", gold, "lower", "Archive-B", "independent-B")
            foil_high_a = passage("S1", foil, "higher", "Archive-A", "independent-A")
            foil_low_b = passage("S2", foil, "lower", "Archive-B", "independent-B")
            gold_low_b2 = passage("S2", gold, "lower", "Archive-B", "independent-B")
            foil_high_a2 = passage("S1", foil, "higher", "Archive-A", "independent-A")
            foil_high_b = passage("S2", foil, "higher", "Archive-B", "independent-B")
            foil_low_a = passage("S2", foil, "lower", "Archive-A", "independent-A")
            irrelevant = {
                "source_id": "S1", "source_family": "Archive-C",
                "independence_group": "independent-C",
                "text": f"The registry entry for {entity} lists a maintenance interval of 11 months.",
                "provenance_label": "unknown",
            }

            variants = [
                evidence("single_true_higher", [one_gold_high], {"S1": "supports_truth"}),
                evidence("single_true_lower", [one_gold_low], {"S1": "supports_truth"}),
                evidence("single_false_higher", [one_foil_high], {"S1": "contradicts_truth"}),
                evidence("single_false_lower", [one_foil_low], {"S1": "contradicts_truth"}),
                evidence("independent_agreement_true", [gold_high_a, gold_low_b], {"S1": "supports_truth", "S2": "supports_truth"}),
                evidence("independent_agreement_false", [foil_high_a, foil_low_b], {"S1": "contradicts_truth", "S2": "contradicts_truth"}),
                evidence("independent_conflict_true_higher", [gold_high_a, foil_low_b], {"S1": "supports_truth", "S2": "contradicts_truth"}),
                evidence("independent_conflict_false_higher", [foil_high_a2, gold_low_b2], {"S1": "contradicts_truth", "S2": "supports_truth"}),
                evidence("independent_conflict_equal", [gold_high_a, foil_high_b], {"S1": "supports_truth", "S2": "contradicts_truth"}),
                evidence("dependent_agreement_false", [foil_high_a, foil_low_a], {"S1": "contradicts_truth", "S2": "contradicts_truth"}),
                evidence("irrelevant_only", [irrelevant], {"S1": "irrelevant"}, "insufficient"),
                evidence("true_plus_irrelevant", [gold_high_a, irrelevant | {"source_id": "S2"}], {"S1": "supports_truth", "S2": "irrelevant"}),
            ]
            records.append({
                "schema_version": "controlled-multisource-v1",
                "item_id": f"msctrl_{number:03d}",
                "question": f"What {attribute} is assigned to {entity}?",
                "truth_key": {
                    "gold_answer": gold,
                    "false_claim": foil,
                    "review_note": "Fictional deterministic assignment; development data only.",
                },
                "draft_variants": [
                    {"draft_state": "correct", "answer": gold},
                    {"draft_state": "incorrect", "answer": foil},
                ],
                "evidence_variants": variants,
            })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("cases.controlled.multisource.dev.v1.jsonl"))
    args = parser.parse_args()
    records = generate()
    if len(records) != 25 or len({row["item_id"] for row in records}) != 25:
        raise ValueError("Expected 25 unique development items")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} fictional items, 12 evidence variants and 2 draft states each ({len(records)*12*2} combinations).")
    print("Development data only; no inference was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
