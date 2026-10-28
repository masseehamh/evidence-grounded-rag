# Selective correction policy v0.1 (development only)

This is a candidate intervention for development experiments. It is not the final method, is not validated, and must not be used on the held-out set until the wording and output parser are frozen.

## Experimental input contract

Construct every model request with an explicit allow-list. It may contain only:

- `question`: the user question;
- `draft_answer`: the answer to review;
- `passages`: zero or more passages, each with a stable `source_id`, `text`, and a separately supplied `source_status` (`higher`, `lower`, or `unknown` in controlled-v0);
- optionally, publication date and source family where those are part of the study design.

Never serialize `truth_key`, `annotation_key`, `draft_state`, `answerability`, or `scenario_id` into a model request. Keep these in a separate evaluation-side record. Do not encode them in an item ID, filename, prompt header, or passage order. The model-visible `source_status` is provenance metadata, not a truth label.

The generator must not infer `source_status` from writing style. In the controlled track, source status must be randomized independently of passage truth so the status is not a hidden answer key. In the real-source track, source metadata must be documented and frozen before annotation.

## Candidate system instruction

```text
Review the draft answer using the question, draft, and supplied passages with their source metadata.

Do not assume a passage is true just because it was retrieved. Do not guess source reliability from wording; use only the supplied source_status. A reliability label is evidence about provenance, not proof that the passage is correct.

First decide whether each passage answers the question and whether it supports, contradicts, or does not address the draft. Treat source conflicts explicitly.

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

Use empty arrays when no source supports or contradicts the answer. Do not include facts that are absent from the draft or passages unless needed to state uncertainty. Return valid JSON only.
```

## Why the prompt is only a candidate

The source status is an experimental input that can change model behavior. It must therefore be isolated as a factor, not silently mixed with evidence truth. The controlled design should cross source status with passage truth and draft correctness, and should include cases where an “authoritative” passage is itself wrong so the policy is not rewarded for blindly obeying a label. The real-source track should document who assigned source status and what rule they used.

The current audited-v1 pilot does not contain this metadata in the model prompt, so it cannot show whether provenance-aware correction helps. Adding this policy requires a new, frozen prompt condition and a new dataset version or experiment manifest; do not reinterpret audited-v1 outputs as having tested it.

## Development checks before any model run

- Validate the JSON schema and reject malformed or missing fields.
- Check that each cited source ID exists in the supplied passages.
- Define a deterministic rule for how `answer` is extracted for the existing evaluator.
- Ensure the decision/status fields are retained in raw output records.
- Compare this policy with the generic correction prompt, retrieval-only, and preserve-draft baselines on development items.
- Have human reviewers verify evidence support, factual correctness, and whether preserve/correct/qualify/abstain was appropriate.
- Freeze this prompt before using any held-out or confirmatory items.
