# AI annotation repeat-pass check

**Date:** 2026-10-28  
**Pilot:** audited-v1, 25 cases × 5 output groups = 125 answers

## What was compared

A fresh answer-by-answer annotation pass used the reviewer packet fields: question, shown retrieval passage, final answer, trusted-source link, and (only where a correction draft existed) that draft. Condition labels, gold/foil answer lists, metric columns, and the earlier rating CSV were not used while assigning the fresh ratings.

Afterward, the fresh labels were matched to the earlier assistant-generated provisional labels by review ID and case metadata. For comparison, `incorrect_foil` was mapped to `incorrect`, abstention/unsupported labels to `cannot_determine`, and mixed-label variants to `mixed`.

## Repeat-pass results

- Matched answers: 125/125.
- Same factuality category: 123/125 (98.4%).
- Cohen's kappa after the label mapping: 0.974.
- Fresh factuality labels: 67 correct, 7 correct with caveat, 2 mixed, 32 incorrect, and 17 cannot determine.
- Fresh evidence-relation labels: 83 supported, 3 contradicted, 2 mixed, and 37 not addressed.
- The fresh pass marked abstention as warranted in 18 rows (including one qualified answer that also says the exact duration is not verified); 15 rows were classified as abstentions in the draft-comparison field.

## The two factuality disagreements

1. **audit_006, clean correction:** prior label `mixed`; fresh label `correct_with_caveat`. The answer gives approximately 24 hours 39 minutes, which is consistent with the source's approximately 24.6-hour rotation, while correctly qualifying that the exact sol duration is not explicitly confirmed.
2. **audit_010, misleading correction:** prior label `correct`; fresh label `mixed`. The final answer gives the source-correct year (1990), but also says the evidence contradicts the draft even though the draft already says 1990 and the shown evidence supports it. This is a material explanation error alongside a correct answer.

Both cases merit human adjudication before the pilot labels are used as research findings.

## Important interpretation limit

This is **AI repeat-pass consistency**, not independent inter-rater reliability. The same assistant produced both sets, and the earlier labels were present in conversation history even though the fresh pass was based on the unlabeled packet and the earlier ratings file was not consulted during labeling. The passes can share the same factual assumptions and blind spots. The source URLs were available in the packet, but I did not reopen all 25 source pages during this pass; factuality labels are AI judgments based on the case facts and supplied context, not a fresh source audit. The high agreement therefore does not validate factual correctness and must not be described as human agreement, independent annotation, or evidence that the evaluator is valid.

The two known foil-alias misses (audit_012's speed-of-light wording and audit_017's solid-ice wording) remain diagnostic coverage gaps; semantic decisions here were made from the answer and passage, not from exact alias matching.

