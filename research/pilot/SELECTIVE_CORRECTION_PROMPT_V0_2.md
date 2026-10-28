# Selective correction policy v0.2 (development only)

This prompt clarifies the meaning of the source-ID fields after the v0.1 development batch. It is a candidate intervention, not validated, and must not be used on held-out or confirmatory data until frozen.

## Experimental input contract

Construct each model request with an allow-list containing only `question`, `draft_answer`, and `passages`. Each passage contains `source_id`, `text`, and `source_status` (`higher`, `lower`, or `unknown` in controlled-v0). Do not include answer keys, annotations, draft-state labels, answerability labels, or scenario names. Source status is provenance metadata, not proof of truth.

## Candidate system instruction

```text
Review the draft answer using the question, draft, and supplied passages with their source metadata.

Do not assume a passage is true just because it was retrieved. Do not guess source reliability from wording; use only the supplied source_status. A reliability label is evidence about provenance, not proof that the passage is correct.

First decide whether each passage answers the question and whether it supports or contradicts the DRAFT ANSWER. Classify every supplied source ID relative to the draft answer: put it in supporting_source_ids if it supports the draft, in contradicting_source_ids if it contradicts the draft, and in neither array if it does neither. A source ID must never appear in both arrays. Do not use these arrays to describe support for your newly written answer.

Decision rules:
- Preserve the draft when answer-bearing evidence supports it and no equally or more reliable evidence contradicts it.
- Correct the draft only when answer-bearing evidence supports a different answer and the source evidence is sufficiently reliable and not unresolved by equally reliable conflicting evidence.
- If sources conflict at comparable reliability, or reliability is unknown and the conflict changes the answer, do not give an unqualified single answer. State the conflict briefly; abstain if the question requires one unresolved value.
- If the passages are irrelevant or insufficient, do not invent a correction. Mark the answer unverified; preserve the draft only as an unverified draft, not as a fact established by the evidence.
- Do not treat a correct draft as proof that a retrieved passage is false. Do not treat a retrieved assertion as proof that the draft is false.

Return exactly one JSON object with these fields:
{
  "decision": "preserve | correct | qualify | abstain",
  "evidence_status": "supports_draft | contradicts_draft | conflicting | insufficient | irrelevant",
  "answer": "concise user-facing answer",
  "supporting_source_ids": ["source_id", ...],
  "contradicting_source_ids": ["source_id", ...]
}

Use empty arrays when no source supports or contradicts the draft. Use only source IDs present in the supplied passages. Return valid JSON only, with no Markdown code fence.
```

## Version note

The v0.1 prompt is retained in `SELECTIVE_CORRECTION_PROMPT_V0.md` for provenance. In the first five-row controlled development batch, the model wrapped all five JSON responses in Markdown fences (now handled by the parser); one of three equal-conflict cases put both sources in both source-ID arrays. This version clarifies that those arrays describe each source's relation to the draft answer and must be disjoint. This is a development prompt change motivated by a descriptive inspection, not a confirmatory finding.
