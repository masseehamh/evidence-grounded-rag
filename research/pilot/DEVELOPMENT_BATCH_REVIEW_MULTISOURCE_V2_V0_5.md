# Controlled multisource-v2 / prompt v0.5 development review

**Run date:** 2026-10-29
**Model:** `@cf/zai-org/glm-4.7-flash`
**Inputs:** 24 synthetic rows, one per scenario × draft-state cell
**Model calls:** 24
**Purpose:** development diagnostics only; not confirmatory evidence

## Results from the offline evaluator

| Diagnostic | Result |
|---|---:|
| Initial exact match | 12/24 (50.0%) |
| Final exact match | 5/24 (20.8%) |
| Exact correction of initially wrong drafts | 0/12 |
| Initially correct drafts preserved as exact match | 5/12 |
| Initially correct drafts no longer exact match | 7/12 |
| Final exact foil answers | 5/24 |
| Responses parseable as JSON | 24/24 |
| Explicit empty-answer abstentions | 2 |
| Source IDs valid | 24/24 |
| Supporting and contradicting ID arrays disjoint | 24/24 |
| Mean per-row draft-relative source classification accuracy | 0.896 |

The exact-match and foil counts are lexical evaluator diagnostics. The seven exact-match losses include qualified outputs and do not by themselves establish factual harm. A guided review has since been completed; its user-confirmed labels and limitations are recorded in `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_5.md` and below.

## Policy and output-contract diagnostics

- The model emitted `decision=correct` eight times. In seven of those rows, the final answer string was exactly the same as the draft, contrary to v0.5's rule that `correct` changes the answer value.
- Both `irrelevant_only` rows abstained with an empty answer. The parser initially treated that valid JSON abstention as malformed and placed the full JSON object in `final_answer`. I fixed extraction to treat an explicit empty answer as a valid abstention and reran the offline evaluator. These rows now have an empty `final_answer` and `valid_json_empty_answer` status; the raw outputs and model responses were not modified.
- Those same two abstentions used `evidence_status=insufficient`, although the prompt defines `irrelevant` when no passage addresses the question.
- In the two cases where a lower-tier source supported the draft (`single_true_lower`/correct draft and `single_false_lower`/incorrect draft), the model preserved the answer but omitted the required unverified caveat. In the two lower-only cases where the passage disagreed with the draft, it qualified both values.
- Draft-relative source classification was below 100% in three rows: `single_false_higher`/correct draft (0.0), `independent_agreement_true`/incorrect draft (0.5), and `independent_agreement_false`/correct draft (0.0). The other 21 rows were exact on this diagnostic.
- The model qualified the single-higher true evidence case with an incorrect draft and the independent-true-agreement case with an incorrect draft instead of making an exact correction. This is consistent with the zero exact-correction count; it is a policy-following issue to inspect, not evidence that qualification was factually wrong.
- A new offline output-contract validator flagged 13/24 rows without consulting the answer key: seven `decision=correct` responses left the draft text unchanged, and six `evidence_status=conflicting` responses did not list both supporting and contradicting source relations. The validator reports issues only; it does not alter responses or establish factual correctness.

## Interpretation limits

This is one generation per synthetic cell. The dataset revision changes only the irrelevant passage wording and version IDs from v1, and the balanced selector may choose different fictional items than the v1 batch. Thus this is not a paired prompt comparison with v0.4. Provenance labels remain experimental metadata and do not guarantee truth. The hidden key defines truth only within this fictional fixture. The source-array and exact-match diagnostics cannot replace human review.

## Guided review

The user confirmed first-round evidence/action/source-attribution labels and second-round key-based factuality labels for 23 rows; `review_001` was a walkthrough and excluded. Round-one action appropriateness was judged appropriate in 13 rows and inappropriate in 10. Round-two labels were 5 correct, 10 correct with caveat, 6 incorrect, 2 cannot determine, and 0 mixed. These are assistant-proposed, user-confirmed single-reviewer labels, not independent blinded annotation or reliability evidence. See `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_5.md` and the completed packet.

## Recommended next step

Before another model run, revise or formally freeze the decision policy and decide how to handle the 13 validator flags. The current v0.5 policy was followed inconsistently, especially in the higher-evidence conditions and lower-only support caveats. The new validator can be rerun locally without model calls. A stronger comparison still needs genuinely new items per condition, repeated generations, baselines, and independent blinded reviewers where feasible.

## Artifacts

- Prompt: `SELECTIVE_CORRECTION_PROMPT_V0_5.md`
- Dataset protocol: `MULTISOURCE_CONTROLLED_V2_PROTOCOL.md`
- Inputs: `serialized/controlled-multisource-v2/stratified-24/model_inputs.jsonl`
- Separate evaluation key: `serialized/controlled-multisource-v2/stratified-24/evaluation_key.jsonl`
- Raw outputs: `serialized/controlled-multisource-v2/stratified-24/model_outputs.v0.5.jsonl`
- Per-example diagnostics: `serialized/controlled-multisource-v2/stratified-24/results-v0.5/per_example.csv`
- Summary: `serialized/controlled-multisource-v2/stratified-24/results-v0.5/summary.csv`
- Output-contract flags: `serialized/controlled-multisource-v2/stratified-24/results-v0.5/output_contract_issues.csv`
- Guided review log: `MULTISOURCE_CHAT_REVIEW_PROGRESS_V0_5.md`
- Completed review packet: `serialized/controlled-multisource-v2/stratified-24/human-review-v0.5/review_packet_completed.csv`
