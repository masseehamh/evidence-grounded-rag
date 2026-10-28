# Development comparison: selective-correction prompt v0.3 vs v0.4

**Run date:** 2026-10-28
**Model:** `@cf/zai-org/glm-4.7-flash`
**Inputs:** the same 24 synthetic rows (12 evidence scenarios × 2 draft states)
**Generations:** one per row and prompt version (48 total)
**Purpose:** prompt and evaluator debugging only; not confirmatory evidence

## Aggregate diagnostics

| Diagnostic | v0.3 | v0.4 |
|---|---:|---:|
| Final exact matches | 8/24 (33.3%) | 8/24 (33.3%) |
| Initially incorrect drafts changed to exact gold | 3/12 | 4/12 |
| Initially correct drafts preserved as exact gold | 5/12 | 4/12 |
| Initially correct drafts no longer exact gold | 7/12 | 8/12 |
| Foil adoption | 8/24 | 6/24 |
| Valid cited source IDs | 24/24 | 24/24 |
| Supporting/contradicting source-ID arrays disjoint | 23/24 | 24/24 |
| Mean draft-relative source classification accuracy | 19/24 (79.2%) | 16/24 (66.7%) |

These are direct descriptive counts from the evaluator's per-example CSV files. “Foil adoption” and exact match are lexical diagnostics, and exact match is especially incomplete for qualified, abstaining, or otherwise valid non-gold-verbatim responses.

## What changed in this small run

v0.4 kept the exact-match total unchanged. It produced one more exact correction among initially incorrect drafts, but also preserved one fewer initially correct draft. It adopted the foil two fewer times and fixed the one support/contradiction source-ID overlap seen in v0.3. At the same time, draft-relative source classification accuracy fell by three rows.

Therefore, these measurements do not support saying v0.4 is broadly better. They show a trade-off in this single run: some output-contract diagnostics improved while source-relation classification was worse. The low and unchanged exact-match totals also leave the main answer-quality question unresolved.

## Interpretation limits

- Each synthetic condition has only one item per draft state and one generation per prompt. A single changed output shifts a condition's rate by 100 percentage points; no uncertainty estimate or causal claim is warranted.
- This comparison changes the prompt version, but model generation can vary. Repeated runs with controlled settings and more items are needed to separate prompt effects from sampling variation.
- The evaluator's gold/foil string matching, decision labels, evidence-status labels, and source-relation fields are not independent evidence of factuality.
- Guided factuality review was completed for 23 counted outputs per version, using assistant-proposed labels confirmed by the user. The label counts were v0.3: 8 correct, 6 correct with caveat, 7 incorrect, 1 cannot determine, 1 mixed; v0.4: 8 correct, 6 correct with caveat, 7 incorrect, 2 cannot determine, 0 mixed. For v0.4, the abstention on an irrelevant-only case was labeled cannot-determine; the conflict report on review_022 was labeled correct-with-caveat. These are AI-assisted single-reviewer labels, not independent or blinded multi-rater annotation, and the distributions should not be read as a comparative performance result.
- The v1 `irrelevant_only` distractor was semantically adjacent to the maintenance-token question. This wording has been revised in immutable controlled-multisource-v2, which keeps the same fictional items and answer assignments; it is a fixture correction, not a new independent sample.

## Recommended next step

The guided v0.4 review is complete and saved. The lower/unknown-only rule was stated in candidate prompt v0.5, and the immutable v2 fixture plus balanced 24-row slice was prepared with the revised distractor. The v0.5 development run is now complete; see `DEVELOPMENT_BATCH_REVIEW_MULTISOURCE_V2_V0_5.md`. Its inputs are not paired to the v0.4 selected rows, and no direct prompt-effect claim is warranted. A guided v0.5 review remains useful before revising the prompt. For a stronger comparison, add genuinely new items per condition, repeated generations, and baselines such as preserve-draft and retrieval-only. Use independently blinded reviewers where feasible, and freeze the prompt, dataset, rubric, and analysis plan before a held-out run.

## Files

- v0.3 per-example: `serialized/controlled-multisource-v1/stratified-24/results/per_example.csv`
- v0.3 summary: `serialized/controlled-multisource-v1/stratified-24/results/summary.csv`
- v0.4 raw responses: `serialized/controlled-multisource-v1/stratified-24/model_outputs.v0.4.jsonl`
- v0.4 per-example: `serialized/controlled-multisource-v1/stratified-24/results-v0.4/per_example.csv`
- v0.4 summary: `serialized/controlled-multisource-v1/stratified-24/results-v0.4/summary.csv`
- v0.4 guided review log: `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_4.md`
- v0.4 completed review packet: `serialized/controlled-multisource-v1/stratified-24/human-review-v0.4/review_packet_completed.csv`
- v0.4 prompt: `SELECTIVE_CORRECTION_PROMPT_V0_4.md`
- v0.5 candidate prompt: `SELECTIVE_CORRECTION_PROMPT_V0_5.md`
- controlled-v2 design: `MULTISOURCE_CONTROLLED_V2_PROTOCOL.md`
- v2 generator and dataset: `generate_controlled_multisource_v2.py`, `cases.controlled.multisource.dev.v2.jsonl`
- v2 stratified inputs: `serialized/controlled-multisource-v2/stratified-24/model_inputs.jsonl`
- v2/v0.5 development review: `DEVELOPMENT_BATCH_REVIEW_MULTISOURCE_V2_V0_5.md`
