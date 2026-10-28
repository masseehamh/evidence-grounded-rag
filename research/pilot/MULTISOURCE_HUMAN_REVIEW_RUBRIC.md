# Human review rubric for multisource controlled-v1

The review packet separates evidence/action judgments from answer-key factuality so the reviewer can first judge what the visible evidence supports.

## Round 1: keep the reference key closed

Use `review_packet.csv`. If possible, have two reviewers independently complete separate copies. Do not open `reference_key.csv`, prior evaluation CSVs, or this run's scenario summary until round-one fields are filled and saved.

- **`observed_action`**: `preserved`, `corrected`, `qualified`, `abstained`, or `unclear`, based on the answer text compared with the draft.
- **`evidence_relation_round1`**: `supported`, `contradicted`, `mixed`, `not_addressed`, or `cannot_determine`, judging the answer against the passages shown. A statement that neutrally reports a conflict can be `supported` by the passages even if it is not a single-value answer.
- **`action_appropriateness_round1`**: `appropriate`, `inappropriate`, or `unclear`, based on whether the answer preserves, changes, qualifies, or abstains in a way justified by the visible passages and metadata. Do not assume a high-status source is true. Passages in the same `independence_group` are dependent; don't count them as independent corroboration.
- **`source_attribution_round1`**: `all_correct`, `one_or_more_wrong`, `none_needed`, or `unclear`, checking any source references in the answer against the visible passage IDs and claims. If the answer gives no source references, use `none_needed` unless attribution was necessary for its qualification.
- **`review_notes_round1`**: brief rationale for difficult or borderline cases.

These labels concern the evidence and behavior visible to the reviewer. Do not use exact-match scores as a substitute for these judgments.

## Round 2: factuality against the constructed key

After saving a copy of the completed round-one packet, open `reference_key.csv` and use the matching `review_id` to fill `factuality_label_round2`:

- `correct`: answer conveys the constructed gold answer without a material caveat/error.
- `correct_with_caveat`: the gold answer is conveyed with a relevant qualification.
- `mixed`: includes both materially correct and incorrect claims.
- `incorrect`: asserts a materially false answer or omits the required answer in a way that is not an appropriate abstention.
- `cannot_determine`: the response does not make a factual claim that can be judged against the key, commonly a justified abstention.

Use `review_notes_round2` for the reason, especially when the answer is a conflict report or abstention. The gold key defines truth only for this fictional dataset; it is not an external factual source.

## Reporting

Preserve original ratings from both reviewers before adjudication. Report agreement separately for round-one and round-two fields, adjudicate disagreements with notes, and do not call one reviewer's labels inter-rater reliability. For any publication-oriented study, use independently reviewed real-source items as well as controlled data and preregister the annotation/analysis plan.
