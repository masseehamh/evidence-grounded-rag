# Source audit: audited-v1

## Scope

`cases.audited.v1.jsonl` contains 25 short factoid cases for a larger engineering pilot of evidence-based answer correction. It is a **first-pass source audit**, not a validated benchmark. Each item has a linked authoritative source, a source title and publisher, an access date, concise paraphrased clean evidence, gold aliases, foil aliases, and a deliberately false synthetic passage for the misleading condition.

The clean passages are paraphrases rather than copied source text. The false passages were written for this experiment and are not claims made by the linked publishers. The `evidence_misleading_type` and `evidence_misleading_note` fields record that distinction; keep them in any exported copy. The runner passes only the passage text to the model, so the synthetic status does not tip off the model during the misleading condition.

## Coverage and provenance

| Source publisher | Cases | Topics |
| --- | ---: | --- |
| NASA / NASA Science | 11 | Solar-system facts, the Moon, Apollo 11, Hubble |
| NIST | 3 | Speed of light, SI second, mole |
| U.S. Geological Survey | 5 | Water composition and water-cycle processes |
| NOAA | 5 | Ocean coverage, ocean water, ocean basins, dry-air composition |
| Smithsonian National Air and Space Museum | 1 | Wright Flyer |

All source pages were checked on 2026-10-28. The source links and the fact-specific supporting paraphrases are stored on each case row. The dataset has repeated publishers and some related subject matter, so cases should not be treated as 25 fully independent source domains.

## Use and limitations

- A full run makes about 125 model calls (five per case). Check the configured model and inference budget before launching it.
- This is a small, hand-curated, single-reviewer set. A second reviewer should verify each question, answer aliases, clean evidence, foil, and counterfactual before using it for research claims.
- Some answers involve units, numbers, and aliases. Exact match and token F1 can still mis-score elaborated answers or equivalent formats; use the manual-review fields and report these outcomes separately.
- The synthetic passages test responses to controlled false statements. They do not model the prevalence, distribution, or style of misinformation in real retrieval systems.
- Check source terms, data reuse requirements, and whether the cases suit the intended population and research question before publication or external distribution.
- Record the model identifier, prompt version, run timestamp, and any changed case file when running a study. Do not append repeated runs to a file unless the repeated records are intentional.

## Validation checks

The JSONL file should contain 25 unique `audit_###` records, all with HTTPS source links, non-empty gold and foil aliases, and `evidence_misleading_type` set to `synthetic_counterfactual`. The runner rejects source-checked records that omit provenance fields or use a non-HTTPS source URL.
