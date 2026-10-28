# Selective correction policy v0.5 (multisource development only)

**Status:** unvalidated development candidate. It operationalizes a conservative response when only lower-tier or unknown evidence is available. It is not a claim that the draft is true, nor a validated source-reliability policy. Do not use it on held-out or confirmatory data.

## Decision rule under test

Source status is a provenance cue, not a truth label. If every relevant answer-bearing source is lower-tier or unknown, the model must not silently replace the draft with a single unqualified value. It must qualify the answer and distinguish the draft from the source claim:

- If the available lower/unknown source supports the draft, retain the draft as **unverified**, stating that the supplied evidence is limited to lower/unknown provenance.
- If the available lower/unknown source contradicts the draft, state both the draft value and the alternative source claim, attribute the alternative to its source ID or family and status, and say the supplied evidence does not resolve which is true.
- If the source is irrelevant or does not answer the question, say the evidence does not address the requested field; preserve a draft only as unverified, or abstain if repeating it would mislead.

This rule deliberately favors transparency over automatic correction in the lower/unknown-only condition. It does not validate the draft. Higher-tier evidence may still be false; this candidate continues to test how a provenance-weighted policy behaves, not whether source rank guarantees truth.

## Candidate system instruction

```text
Review the draft using only the question and supplied passages. Treat source status as provenance metadata, never as a truth label. Passages with the same independence_group are dependent and count as one evidence group.

Classify each relevant source claim relative to the DRAFT ANSWER. supporting_source_ids and contradicting_source_ids must remain relative to the draft, even if you propose a different answer. Put irrelevant or non-answer-bearing sources in neither array. Use only supplied source IDs; the arrays must be disjoint.

Decision policy:
- If the relevant higher-tier independent groups agree on one answer and no other higher-tier group conflicts, use that answer. If it changes the draft, decision=correct; if the draft matches, decision=preserve. Mention any relevant lower/unknown disagreement and its source. Higher-tier status does not prove truth.
- If every relevant answer-bearing source is lower-tier or unknown, do not replace the draft with a single unqualified value. If the source supports the draft, use decision=preserve and state the draft is unverified because support is only lower-tier/unknown. If a source disagrees with the draft, use decision=qualify: state the draft value and the alternative source claim, attribute the alternative to its source ID or family and status, and say this evidence does not resolve which is true. Do not imply the draft is supported when no passage supports it.
- If equally strong independent sources disagree, use decision=qualify and report both claims with correct source attribution; do not select one as established.
- If higher-tier groups conflict with each other, use decision=qualify and report their competing claims. Do not select one as established.
- If passages are irrelevant or do not answer the question, evidence_status=irrelevant when none answers the question. Preserve a draft only with a clear unverified caveat; otherwise abstain.
- Agreement among dependent copies is one evidence group, not independent corroboration.

Output consistency:
- decision=preserve keeps the draft's answer value, with an optional caveat.
- decision=correct changes the draft's answer value.
- decision=qualify explicitly states uncertainty, conflict, or an evidence limitation; do not present one disputed value as established.
- decision=abstain gives no candidate answer value.
- evidence_status is relative to the draft: supports_draft if relevant claims support it without disagreement; contradicts_draft if relevant claims agree against it; conflicting if relevant answer-bearing claims disagree; insufficient if evidence does not meet the decision policy; irrelevant if no passage answers the question.

Return exactly one JSON object with these fields and no Markdown:
{"decision":"preserve | correct | qualify | abstain","evidence_status":"supports_draft | contradicts_draft | conflicting | insufficient | irrelevant","answer":"concise answer","supporting_source_ids":[],"contradicting_source_ids":[]}
Do not invent facts. Return valid JSON only.
```

## Evaluation notes

Compare v0.5 with v0.4 on development data only. Score factuality separately from whether the action follows the policy, whether the evidence supports the answer, and whether source attribution is accurate. In particular, a qualified statement that a lower-tier source claims an alternative is not itself an assertion that the alternative is true. Review answers with a blinded human rubric before drawing conclusions.
