# Multisource-v1 guided review progress: prompt v0.4

**Purpose:** record labels the user confirmed during a guided chat review of the v0.4 outputs. These are assistant-proposed labels confirmed by the user; they are AI-assisted single-reviewer judgments, not independent annotation or inter-rater reliability. The prior v0.3 review is recorded separately in `MULTISOURCE_CHAT_REVIEW_PROGRESS.md`.

## Round 1: evidence and action review

`review_001` was used as a walkthrough and excluded. The user confirmed round-one labels for `review_002` through `review_024` (23 rows), using `MULTISOURCE_HUMAN_REVIEW_RUBRIC.md`.

| Review IDs | Observed action | Evidence relation | Action appropriate? | Source attribution |
|---|---|---|---|---|
| 002, 019 | abstained | not_addressed | appropriate | none_needed |
| 003 | qualified | supported | appropriate | all_correct |
| 004, 005 | qualified | supported | appropriate | all_correct |
| 006, 007, 011, 012, 014, 016 | preserved | supported | appropriate | none_needed |
| 008, 009, 010, 013, 017, 020 | corrected | supported | appropriate | none_needed |
| 015, 023 | corrected | supported | unclear | none_needed |
| 018, 021, 022 | qualified | supported | appropriate | all_correct |
| 024 | qualified | supported | appropriate | unclear |

Notes: The `unclear` action-appropriateness labels for `review_015` and `review_023` reflect that the rubric does not define whether one lower-provenance passage alone justifies overriding a draft. The two passages in `review_011` and `review_020` share an independence group; they were not counted as independent corroboration. `review_024` reports a conflict but does not map its values to S1 and S2.

## Round 2: factuality against the constructed key

After round one was saved, the constructed key was used to judge the answers. Confirmed labels across 23 counted rows:

- **Correct:** 8 (`review_006`, `review_007`, `review_008`, `review_009`, `review_014`, `review_016`, `review_017`, `review_023`)
- **Correct with caveat:** 6 (`review_004`, `review_005`, `review_018`, `review_021`, `review_022`, `review_024`)
- **Incorrect:** 7 (`review_003`, `review_010`, `review_011`, `review_012`, `review_013`, `review_015`, `review_020`)
- **Cannot determine:** 2 (`review_002`, `review_019`)
- **Mixed:** 0

The two abstentions were judged cannot-determine because their passages did not address the requested field and the key marked the evidence as insufficient. The key defines truth only for this fictional dataset.

## Artifacts

- Round-one frozen copy: `serialized/controlled-multisource-v1/stratified-24/human-review-v0.4/review_packet_round1_completed.csv`
- Completed packet: `serialized/controlled-multisource-v1/stratified-24/human-review-v0.4/review_packet_completed.csv`
- Separate key: `serialized/controlled-multisource-v1/stratified-24/human-review-v0.4/reference_key.csv`
- v0.4 outputs: `serialized/controlled-multisource-v1/stratified-24/model_outputs.v0.4.jsonl`
