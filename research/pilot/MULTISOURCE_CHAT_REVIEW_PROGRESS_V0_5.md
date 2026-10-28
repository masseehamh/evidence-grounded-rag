# Multisource-v2 guided review progress: prompt v0.5

**Purpose:** record labels confirmed by the user during a guided review. The assistant proposed each label and the user confirmed or could correct it. This is AI-assisted single-reviewer annotation, not independent or blinded multi-rater review, and not inter-rater reliability. The answer key defines correctness only for this fictional controlled dataset.

`review_001` was a walkthrough and is excluded. Round 1 was completed and saved before the separate key was opened for Round 2. The rubric is `MULTISOURCE_HUMAN_REVIEW_RUBRIC.md`.

## Round 1: visible-evidence and action review (23 rows)

| Review IDs | Observed action | Evidence relation | Action appropriate? | Source attribution |
|---|---|---|---|---|
| 002, 007, 009, 011, 014, 015, 019, 020, 024 | preserved | supported, except 024 contradicted | appropriate for 002, 007, 009, 011, 014, 015; inappropriate for 019, 020, 024 | none_needed |
| 003, 023 | abstained | not_addressed | appropriate | none_needed |
| 004, 005, 006, 008, 010, 013, 016, 017, 018, 021, 022 | qualified | supported for 004, 005, 008, 010, 013, 017, 022; mixed for 006, 016, 018, 021 | appropriate for 008, 013, 018, 022; inappropriate for the other seven qualified rows | all_correct: 006, 008, 017, 018, 022; unclear: 004, 005, 010, 013, 016, 021 |
| 012 | corrected | supported | appropriate | none_needed |

Round-one totals: observed action—9 preserved, 11 qualified, 2 abstained, 1 corrected; evidence relation—16 supported, 4 mixed, 2 not addressed, 1 contradicted; action appropriateness—13 appropriate, 10 inappropriate; attribution—12 none needed, 6 unclear, 5 all correct.

The most frequent appropriateness issue was not following the v0.5 decision rule when higher-provenance answer-bearing evidence was uncontested. In the lower-only support cases (review_019 and review_020), the answers preserved the draft but omitted the required unverified caveat. Lower-only contradiction cases (review_013 and review_018) were qualified by reporting both values.

## Round 2: constructed-key factuality review (23 rows)

- **Correct:** 5 (`review_007`, `review_014`, `review_015`, `review_020`, `review_024`)
- **Correct with caveat:** 10 (`review_004`, `review_006`, `review_008`, `review_010`, `review_013`, `review_016`, `review_017`, `review_018`, `review_021`, `review_022`)
- **Incorrect:** 6 (`review_002`, `review_005`, `review_009`, `review_011`, `review_012`, `review_019`)
- **Cannot determine:** 2 (`review_003`, `review_023`)
- **Mixed:** 0

These are guided, AI-assisted labels against the fictional key. They are not independent human annotations and should not be described as factuality evidence for real-world RAG.

## Artifacts

- Blinded original packet: `serialized/controlled-multisource-v2/stratified-24/human-review-v0.5/review_packet.csv`
- Frozen first-round packet: `serialized/controlled-multisource-v2/stratified-24/human-review-v0.5/review_packet_round1_completed.csv`
- Completed packet: `serialized/controlled-multisource-v2/stratified-24/human-review-v0.5/review_packet_completed.csv`
- Separate constructed key: `serialized/controlled-multisource-v2/stratified-24/human-review-v0.5/reference_key.csv`
