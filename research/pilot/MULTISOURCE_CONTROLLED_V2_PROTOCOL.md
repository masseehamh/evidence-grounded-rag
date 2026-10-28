# Multi-source controlled-v2 development design

**Status:** development-only immutable revision; not preregistered, validated, or confirmatory. One 24-call v0.5 development probe has been run; see `DEVELOPMENT_BATCH_REVIEW_MULTISOURCE_V2_V0_5.md`.

## What changed from v1

The v1 fixture's `irrelevant_only` distractor mentioned an 11-month maintenance interval. Because one question family asks about a maintenance token, that distractor could be semantically adjacent to the question. In v2, the distractor says the registry record was reviewed by the records team. It does not state any of the five queried attributes (signal hue, channel number, maintenance token, route code, or shelf code).

The 25 fictional items, gold/foil assignments, scenario structures, and two draft states are inherited from the v1 generator so the distractor is the intended dataset change. IDs and schema version are changed. Therefore v2 is a controlled fixture revision, not a new independent sample of items. The v1 file remains untouched.

## Lower/unknown-only action rule

Prompt v0.5 makes the previously ambiguous case explicit: when all relevant answer-bearing evidence is lower-tier or unknown, do not silently replace the draft with an unqualified single value. If evidence backs the draft, retain it only as unverified. If evidence contradicts the draft, report both the draft and attributed source claim and state that this evidence does not resolve truth. This is a decision-policy convention for the controlled experiment, not a universal epistemic rule. The policy does not treat a higher tier as proof either.

## Files and preparation

- Generator: `generate_controlled_multisource_v2.py`
- Data schema: `controlled_multisource_v2.schema.json`
- Dataset: `cases.controlled.multisource.dev.v2.jsonl`
- Policy candidate: `SELECTIVE_CORRECTION_PROMPT_V0_5.md`

Generate the dataset with `python research/pilot/generate_controlled_multisource_v2.py`. Then use `serialize_controlled_multisource_v1.py` with the v2 dataset path and a new v2 output directory; that serializer separates model inputs from the key and does not change the item schema. Use `prepare_controlled_multisource_batch.py` with explicit v2 inputs/key/output paths only after checking that the generated key covers all 12 scenarios × 2 draft states. Do not send `evaluation_key.jsonl` to the model.

This version's 24-row stratified set would still contain one selected item per cell, so it remains a debugging probe. The v2 wording change addresses one confound but does not increase item diversity or repeated generations. Do not run inference until v2 inputs, the v0.5 prompt, and the review rubric are frozen.
