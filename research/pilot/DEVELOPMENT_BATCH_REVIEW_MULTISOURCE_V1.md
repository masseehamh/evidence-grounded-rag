# Multisource controlled-v1 development batch review (selective prompt v0.3)

**Run date:** 2026-10-28
**Model:** `@cf/zai-org/glm-4.7-flash`
**Inputs:** 24 synthetic rows; one item in each of 12 evidence scenarios × 2 draft states
**Calls:** 24; selective-correction only
**Status:** development prompt/data diagnostics, not confirmatory evidence

## Descriptive observations

- All 24 responses were parseable JSON: 23 were Markdown-fenced and one was plain JSON.
- The evaluator extracted the `answer` field for all rows. Gold/foil lexical exact match was 8/24 (33.3%); this is not an overall quality estimate because qualified conflict and unverified answers are intentionally not exact strings.
- Both true independent-agreement cases ended at the exact gold answer. Both true single-passage scenarios also ended at the exact gold answer for both draft states.
- For single false passages, the model's outcome depended on the label and draft state in this tiny batch: it changed the correct draft to the false claim under the higher label, preserved the correct draft under the lower label, and preserved the incorrect draft under both labels. One output was tagged `decision=correct` despite returning exactly the same text as its draft, so the action field is not fully reliable.
- Both equal-independent-conflict cells were qualified. The provenance-weighted independent conflicts were also qualified, including the condition where the higher-status source supported the false claim. Exact match is not the right measure for those outputs.
- On the false-agreement conditions, the model failed to recover the hidden truth in both draft states. It also marked the correct-draft independent-false-agreement case as `evidence_status=conflicting`, even though both passages made the same claim.
- Both irrelevant-only cases were qualified as unverified, preserving the draft text. With true evidence plus irrelevant context, the correct draft was preserved, but the incorrect draft remained unchanged despite `decision=correct`.

## Output-contract diagnostics

- Every cited source ID was present in the model input (24/24 rows).
- The support and contradiction arrays were disjoint in 23/24 rows; they overlapped for `independent_conflict_true_higher` with a correct draft.
- Source classification relative to the draft matched the synthetic key for 19/24 rows (mean per-row accuracy 0.792). Five rows had source-relation errors, including a single true higher-provenance source wrongly labeled `supports_draft` when the draft was the false claim.
- Decision labels and evidence-status labels should be treated as model outputs requiring review, not trusted evaluator metadata.

## Interpretation limits and design issues

There is one generated item and one model generation per cell, so all patterns are exploratory. The results do not establish method performance, a causal effect of provenance, or a benefit from source independence metadata. The model followed false independent agreement and false higher-provenance evidence in this batch, illustrating that corroboration and provenance are not truth guarantees.

The `irrelevant_only` fixture uses a maintenance-interval statement for every question family. That distractor may be semantically adjacent to the maintenance-token question, so revise it in a new immutable dataset version before any confirmatory use. The source-family and independence groups are synthetic metadata; real-source independence requires an auditable operational definition.

No human factuality labels were entered. Exact match, alias mentions, model decisions, and the source-attribution diagnostic cannot substitute for blinded human judgments.

## Guided chat review update

After the initial report, the user completed a guided, row-by-row review in chat for 23 of the 24 responses; `review_001` was used only as a practice example and excluded. The assistant proposed labels and the user confirmed them. The key-based round-two distribution was: 8 correct, 6 correct with caveat, 7 incorrect, 1 cannot determine, and 1 mixed. This is an AI-assisted single-reviewer pass, not independent human annotation or inter-rater reliability. It is recorded in `MULTISOURCE_CHAT_REVIEW_PROGRESS.md`; the original raw output files and blank CSV packet were left unchanged.

## Recommended next stage

Do not expand to a larger run from this batch alone. First, have a human inspect the 24 outputs using a written rubric for factual correctness, evidence support, action appropriateness, and source-ID attribution. Then revise the development prompt and distractor construction on a new version, add more items and repeated generations per cell, and compare selective correction against preserve-draft, retrieval-only, and generic-correction baselines. Freeze prompt, data, and analysis before a held-out or confirmatory run.

Prompt v0.4 was then run on the same 24 inputs. Its descriptive comparison with v0.3 is documented in `DEVELOPMENT_PROMPT_COMPARISON_V03_V04.md`. The neutral distractor construction and additional item/generation replication remain open before any larger development comparison.

## Artifacts

- Raw model responses: `serialized/controlled-multisource-v1/stratified-24/model_outputs.jsonl`
- Per-example diagnostics: `serialized/controlled-multisource-v1/stratified-24/results/per_example.csv`
- Summary: `serialized/controlled-multisource-v1/stratified-24/results/summary.csv`
- v0.4 per-example diagnostics: `serialized/controlled-multisource-v1/stratified-24/results-v0.4/per_example.csv`
- v0.4 summary: `serialized/controlled-multisource-v1/stratified-24/results-v0.4/summary.csv`
- v0.3/v0.4 comparison: `DEVELOPMENT_PROMPT_COMPARISON_V03_V04.md`
- Design: `MULTISOURCE_CONTROLLED_V1_PROTOCOL.md`
- Prompt candidate: `SELECTIVE_CORRECTION_PROMPT_V0_3.md`
