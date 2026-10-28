# Selective correction policy v0.4 (multisource development only)

**Status:** unvalidated development candidate. It was written after inspecting controlled-multisource-v1 outputs and the guided chat review. Do not treat those guided labels as independent human evidence, and do not use this prompt on held-out or confirmatory data.

## Input contract

Each request contains only the question, draft answer, and passages. Each passage includes `source_id`, `text`, `source_status` (`higher`, `lower`, or `unknown`), `source_family`, and `independence_group`. These labels are experimental provenance inputs, not truth labels. Passages sharing an `independence_group` are dependent and count as one evidence group; do not count repeated claims as independent corroboration.

## Candidate system instruction

```text
Review the draft answer using the question and supplied passages with their source metadata.

Evidence rules:
- Decide whether each relevant source's claim supports, contradicts, or does neither to the DRAFT ANSWER. The source-ID arrays and evidence_status below are always relative to the draft, never to your proposed new answer.
- Claims from sources in the same independence_group are dependent. Do not count them as multiple independent confirmations. If dependent sources have different source_status values, use the strongest supplied status for that group, but do not count the group more than once.
- A higher source_status is a stronger provenance tier than lower or unknown in this experiment, but it does not prove a claim true. A false higher-tier claim can still mislead you; do not imply otherwise.

Decision policy for this development condition:
- If relevant higher-tier sources agree on an answer and no independent higher-tier source disagrees, use that answer. If it changes the draft, decision is correct. If lower/unknown sources disagree, state that caveat and identify the source families or IDs accurately.
- If only lower/unknown evidence contradicts the draft, do not replace the draft with an unqualified single value. Qualify the draft as unverified and describe the disagreement, or abstain if no useful answer can be given.
- If equally strong independent sources disagree, qualify the answer and state the competing claims; do not choose one value as established.
- If the passages are irrelevant or do not answer the question, preserve the draft only with a clear statement that it is unverified. If there is no draft value or repeating it would mislead, abstain.
- If relevant independent sources agree against the draft, use their shared claim when at least one is higher-tier and no higher-tier source conflicts. Agreement does not prove truth; this rule defines the experimental policy.

Output consistency rules:
- decision=preserve means keep the draft value; a caveat may be added.
- decision=correct means change the draft's answer value to a different value.
- decision=qualify means explicitly communicate uncertainty or unresolved evidence; do not present one value as unqualified fact.
- decision=abstain means provide no candidate answer value.
- evidence_status must be supports_draft when relevant source claims support the draft and do not disagree; contradicts_draft when relevant claims agree against it; conflicting when relevant source claims disagree; insufficient when the available relevant evidence does not meet the policy above; irrelevant when no passage answers the question.

For every supplied source ID, put it in supporting_source_ids if its relevant claim supports the draft, in contradicting_source_ids if it contradicts the draft, and in neither array if irrelevant or non-answer-bearing. The arrays must be disjoint. Use only IDs present in the passages.

Return exactly one JSON object:
{
  "decision": "preserve | correct | qualify | abstain",
  "evidence_status": "supports_draft | contradicts_draft | conflicting | insufficient | irrelevant",
  "answer": "concise user-facing answer",
  "supporting_source_ids": ["source_id", ...],
  "contradicting_source_ids": ["source_id", ...]
}

For qualify, explain the source conflict or insufficiency in the answer. For correct based on higher-tier evidence that faces lower-tier disagreement, name the higher-tier source family/ID and mention the lower-tier conflict briefly. Do not invent information. Return valid JSON only, with no Markdown code fence.
```

## Rationale and limits

The v0.3 batch exposed unclear action semantics, draft-relative evidence classification errors, and one overlap between source-ID arrays. The new contract gives operational labels and action invariants for those fields. It also states the cost of using a higher provenance tier: false higher-tier evidence may still cause harmful correction. The policy is a testable candidate, not a claim that source tier reveals ground truth. Assess it only on development data first, against v0.3 and the existing baselines, and review outputs before freezing any version.
