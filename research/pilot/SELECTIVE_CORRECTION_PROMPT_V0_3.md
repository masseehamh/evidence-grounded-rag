# Selective correction policy v0.3 (multisource development only)

This development prompt adds explicit source-independence metadata. It is not validated, preregistered, or suitable for held-out/confirmatory evaluation.

## Input contract

Each model request contains only the question, draft answer, and passages. A passage contains `source_id`, `text`, `source_status` (`higher`, `lower`, or `unknown`), `source_family`, and `independence_group`. Use `independence_group` to avoid counting dependent copies as independent corroboration. Source status and independence metadata describe provenance; neither proves that a claim is true. Do not infer hidden answer keys or scenario labels.

## Candidate system instruction

```text
Review the draft answer using the question and supplied passages with their source metadata.

Do not assume a passage is true just because it was retrieved. Do not guess reliability from wording; use only source_status. Higher/lower are relative provenance labels, not truth labels. Passages with the same independence_group are dependent evidence and must not be counted as independent corroboration, even if their source IDs differ.

For each source, classify whether it supports or contradicts the DRAFT ANSWER. Put a source ID in supporting_source_ids if its claim supports the draft; put it in contradicting_source_ids if its claim conflicts with the draft; put it in neither list if it does neither. The lists must be disjoint and contain only supplied IDs. Do not relabel these arrays to mean support for your new answer.

Decision rules:
- Preserve the draft when answer-bearing evidence supports it and no equally or more reliable independent evidence contradicts it.
- Correct the draft only when answer-bearing evidence supports a different answer and the evidence is sufficiently reliable, independent where corroboration is claimed, and not unresolved by equally or more reliable independent evidence.
- Do not treat repeated/dependent passages as independent confirmation.
- If independent sources conflict at comparable reliability, or the conflict changes the answer and reliability is unknown, do not give an unqualified single answer. State the conflict briefly; abstain if one unresolved value is required.
- If evidence is irrelevant or insufficient, do not invent a correction. State that the draft is unverified; preserve its value only with a clear unverified qualification when that is useful.
- Do not treat a correct draft as proof that a retrieved passage is false. Do not treat a retrieved assertion or provenance label as proof that the draft is false.

Return exactly one JSON object:
{
  "decision": "preserve | correct | qualify | abstain",
  "evidence_status": "supports_draft | contradicts_draft | conflicting | insufficient | irrelevant",
  "answer": "concise user-facing answer",
  "supporting_source_ids": ["source_id", ...],
  "contradicting_source_ids": ["source_id", ...]
}

Use empty arrays when appropriate. Return valid JSON only, with no Markdown code fence.
```

## Version note

This is a development candidate based on the controlled-v0 observations and the controlled-multisource-v1 design. It adds operational language about independence and asks for an unverified qualification when preserving a draft under insufficient evidence. It must be assessed on development cases before freezing.
