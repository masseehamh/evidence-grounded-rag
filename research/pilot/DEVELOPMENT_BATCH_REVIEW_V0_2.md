# Controlled-v0 stratified development review (selective prompt v0.2)

**Run date:** 2026-10-28
**Model:** `@cf/zai-org/glm-4.7-flash`
**Inputs:** 12 synthetic item-state combinations, one in each evidence-scenario × draft-state cell
**Calls:** 12; selective-correction strategy only
**Status:** prompt and workflow debugging; not confirmatory evidence

## Descriptive results

| Evidence condition | Draft state | n | Observed answer/action pattern |
|---|---:|---:|---|
| True single passage, higher or lower provenance | Correct | 2 | Preserved the draft; both exact-match answers stayed correct. |
| True single passage, higher or lower provenance | Incorrect | 2 | Corrected to the passage claim; both exact-match answers matched the hidden key. |
| False single passage, higher or lower provenance | Correct | 2 | Changed to the false passage claim in both cases; both correct drafts were damaged. |
| False single passage, higher or lower provenance | Incorrect | 2 | Preserved the draft, which was the false claim in both cases; neither was repaired. |
| Equal-provenance conflict | Correct / incorrect | 2 | Qualified by stating both claims in both cases. Exact match marked both non-exact. |
| Irrelevant-only passage | Correct / incorrect | 2 | Returned “Unverified” and abstained in both cases, without repeating the draft. |

Across the 12 rows, 4 final answers were exact matches. That number is not an overall quality estimate: the two conflict answers and two abstentions are not appropriately judged by exact match alone. In particular, the main stress-test result is that one false passage was followed in every false-evidence cell, regardless of the supplied higher/lower provenance label. With one observation per cell, this is a prompt-debugging signal only; it does not establish a provenance effect or a population rate.

## Output-contract inspection

- All 12 responses were Markdown-fenced JSON; the shared parser extracted the answer field in all 12.
- Every cited ID existed in the input passages, and the support/contradiction arrays were disjoint in all 12.
- On a passage-by-passage check against the draft, 11 of 12 source classifications matched the v0.2 definition. In `dev_0249` (`true_higher`, incorrect draft), the model corrected to the true passage answer but listed that source as supporting the draft, even though it contradicted the draft. The model appears to have classified that source relative to its new answer in this case.
- In both irrelevant-only cases, the answer was just “Unverified”; the draft was omitted. This may be an avoidable loss of useful context under the current instruction to preserve it only as unverified.

## Interpretation and limitations

This balanced 12-row batch contains one item per cell and one generation per item. It is useful for finding failure modes, not for estimating rates, comparing systems, or claiming that v0.2 improves performance over v0.1. The selective-correction behavior follows the single retrieved assertion even when that assertion is false. A model cannot identify an isolated false claim from the claim text alone; provenance labels do not reveal truth. The current fixture therefore exposes a limitation of single-passage evidence and motivates testing corroboration, source dependence, and calibrated uncertainty in future development items.

No human factuality annotations were performed. Exact-match and alias-mention fields remain lexical diagnostics. The evaluator's manual factuality fields are blank.

## Next development decisions

1. Keep these v0.2 outputs immutable and preserve the prompt version in the run record.
2. Clarify whether unsupported but potentially useful draft content should be repeated with an explicit unverified caveat or omitted as an abstention; label those actions separately in future annotation.
3. Expand the controlled design with multi-source cases (agreement, disagreement, and source dependence) so correction decisions can be evaluated with corroboration rather than a single assertion. Do not assume that a “higher” label makes a false passage detectable.
4. Before any confirmatory study, define operational reliability categories, decision thresholds, primary outcomes, and human-review rubric; then freeze prompts and data on a held-out set.

## Artifacts

- Raw outputs: `serialized/controlled-v0/stratified-12-selective-v0.2/model_outputs.jsonl`
- Per-example diagnostics: `serialized/controlled-v0/stratified-12-selective-v0.2/results/per_example.csv`
- Scenario/draft summary: `serialized/controlled-v0/stratified-12-selective-v0.2/results/summary.csv`
- Selection manifest: `serialized/controlled-v0/stratified-12-selective-v0.2/selection_manifest.json`
