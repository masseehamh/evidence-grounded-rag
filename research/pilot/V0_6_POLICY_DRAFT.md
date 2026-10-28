# v0.6 Correction Policy — Draft

**Status:** Proposal only. Not a frozen policy and not an evaluated model configuration.

## Why this draft exists

The reported v0.5 development batch exposed three separate problems that must not be conflated:

- correction performance was poor on initially wrong drafts;
- initially correct drafts were sometimes changed;
- some outputs were internally inconsistent with their declared decision or evidence status.

The reported batch contained 24 outputs from a small synthetic fixture. Its v2 wording variation reuses v1's 25 fictional items and answer assignments, so it is not an independent sample. Human review was a single guided review, not blinded or independent adjudication. These observations motivate targeted tests; they do not establish generalization.

## Proposed policy

The policy is about the relationship between the draft, the evidence, and the final answer. It does not replace the existing output schema.

### 1. Preserve when the evidence supports the draft

- If the available evidence supports the draft and does not materially contradict the claim being checked, retain the draft's substantive answer.
- Do not rewrite a supported answer solely for style, verbosity, or superficial variation.
- Do not infer that an answer is wrong merely because retrieved text is irrelevant or does not repeat it.
- If the contract distinguishes a verified answer from an unverified answer, use the appropriate status without inventing evidence.

### 2. Correct only when there is a supported reason to change

- Make a correction when evidence materially contradicts the draft and provides adequate support for the replacement.
- Change only the unsupported or contradicted portion; preserve other supported content.
- Do not treat a lexical mismatch, a different phrasing, or the presence of a distractor as evidence that a correction is needed.
- Do not claim correction success merely because the final answer differs from the draft.

### 3. Handle insufficient evidence explicitly

- If evidence neither verifies nor adequately contradicts the draft, do not guess a replacement.
- Represent uncertainty using the existing schema's supported mechanism.
- Do not silently convert “not verified by these sources” into “false.”
- Preserve the distinction between an answer that is contradicted, one that is unsupported, and one that cannot be determined.

### 4. Handle genuine source conflict

- Declare a conflict only when the supplied evidence contains material, incompatible claims relevant to the same question.
- Identify the source relations using valid source IDs from the supplied evidence.
- Do not resolve a conflict by choosing whichever source appears last, sounds more confident, or agrees with the draft.
- If the schema requires support and contradiction relations for a conflict, both must be present and refer to relevant sources. A validator can check structural presence and IDs, but cannot by itself establish that the sources semantically conflict.

## Output-contract principle

The declared decision and evidence status must agree with the actual output. Contract validation is a separate deterministic layer:

- A correction decision paired with an unchanged substantive answer is a consistency warning unless the schema explicitly allows a no-op correction.
- A preservation decision paired with a material change is a consistency warning.
- A conflict status missing required source relations is a contract failure.
- Every source ID must exist in the supplied evidence set.
- Mutually exclusive relations must not overlap for the same claim unless the schema explicitly supports claim-level distinctions.
- An explicit empty answer must remain empty during parsing; do not substitute raw JSON or a serialized object as the answer.

These are draft invariants. Exact enum values, field names, and allowed exceptions must be mapped to the actual v0.5 schema before implementing or enforcing them.

## Evaluation principles

Report these outcomes separately:

1. Human-adjudicated correction success among initially wrong drafts.
2. Human-adjudicated preservation among initially correct drafts.
3. Harmful or unsupported changes.
4. Handling of insufficient and conflicting evidence.
5. Output-contract validity.
6. Exact match and token F1 as secondary lexical diagnostics.

Do not collapse these into a single score. An output can be schema-valid but factually wrong; a correct answer can fail exact match due to harmless elaboration; an abstention is not automatically a successful correction.

## Freeze and promotion rule

Keep v0.5 artifacts immutable as a historical baseline. Treat v0.6 as a candidate until:

- the exact output schema and validator are reviewed;
- offline regression tests are added and pass;
- failures are reviewed by category;
- any new model run is explicitly approved and its call budget recorded;
- results are reported with the fixture's dependence and review limitations.

No model calls are part of this draft.
