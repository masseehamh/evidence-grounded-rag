# v0.6 Model-Free Regression Test Plan — Draft

**Status:** Test specification, not yet executable. Field names and enums must be mapped to the actual v0.5 output contract before code is written. The current `main` branch does not contain the reported controlled-multisource-v2 validator or output artifacts, so this file intentionally does not guess their complete schema.

## Test layers

Keep these layers independent:

1. **Parsing and schema:** valid structure, required fields, enum values, empty-answer handling.
2. **Cross-field consistency:** decision/action and evidence-status/source-relation consistency.
3. **Source integrity:** referenced IDs exist and relation arrays obey the schema's overlap rules.
4. **Answer quality:** semantic factuality, which cannot be established by structural validation alone and requires adjudicated examples.

## Required deterministic regression cases

| ID | Input condition | Expected test result | Layer |
|---|---|---|---|
| P01 | Explicit `answer` is an empty string | Parsed answer remains empty; parser must not fall back to raw JSON | Parsing |
| P02 | Missing required answer field | Reject or flag according to the established schema; do not silently invent an answer | Parsing |
| P03 | Unknown decision or evidence-status value | Reject or flag | Schema |
| C01 | Decision is `correct`, but substantive answer is unchanged from draft | Flag inconsistency, unless the actual schema explicitly documents a valid no-op case | Cross-field |
| C02 | Decision is `preserve`, but substantive answer materially changes | Flag inconsistency | Cross-field |
| C03 | Evidence status is `conflicting`, but required support/contradiction relations are absent | Flag contract failure | Cross-field |
| S01 | A cited source ID is not present in the supplied evidence set | Flag invalid source reference | Source integrity |
| S02 | The same source ID appears in mutually exclusive support and contradiction arrays for the same claim | Flag unless claim-level schema explicitly permits it | Source integrity |
| S03 | Conflict relations contain valid IDs but do not actually support/contradict the same claim | Structural validator cannot determine this; route to semantic review | Semantic review |
| A01 | Initially correct draft is supported; irrelevant distractor is added | Expected policy behavior: preserve substantive answer | Policy fixture |
| A02 | Initially wrong draft is contradicted and evidence supports a specific replacement | Expected policy behavior: correct only the contradicted content | Policy fixture |
| A03 | Draft is not verified, but evidence does not contradict it | Expected policy behavior: do not invent a replacement; express uncertainty via the existing schema | Policy fixture |
| A04 | Sources make genuinely incompatible claims | Expected policy behavior: surface the conflict; do not select a winner without grounds | Policy fixture |
| A05 | Final answer includes the gold alias in a longer sentence | Do not label it factually wrong from exact-match failure alone; route to semantic review | Metric guard |

## Implementation notes

- Tests must not call the model, network, or Cloudflare API.
- Use fixed fixtures and deterministic assertions.
- For cross-field checks, test the validator directly rather than testing a prompt's ability to make the model comply.
- Keep lexical metrics separate from human factuality labels.
- Preserve a regression fixture for the observed v0.5 inconsistencies once the exact rows are available.
- Do not hard-code new field names, status enums, or no-op exceptions until the v0.5 schema is inspected.
- After implementation, run the repository's existing offline test suite and report the exact command and results. Do not infer tests passed without executing them.

## Blocking dependency

Before turning this specification into executable tests, retrieve the current local/experiment files that define:
- the v0.5 output schema and prompt;
- the output-contract validator;
- the completed review CSV and the validator's 13 flagged rows.

These files were not found on the committed `main` branch at the expected paths. Do not replace or reconstruct them from memory.
