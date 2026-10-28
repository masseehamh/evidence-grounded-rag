# Controlled-v0 development batch review (selective prompt v0.1)

**Run date:** 2026-10-28
**Model:** `@cf/zai-org/glm-4.7-flash`
**Inputs:** 5 of 300 serialized item-state combinations, selected after the runner's fixed-seed shuffle
**Calls:** 5; selective-correction strategy only
**Status:** workflow/prompt debugging only; not a benchmark result

## Observations

- All five responses were JSON wrapped in Markdown fences despite the prompt's JSON-only instruction. The shared parser now extracts the answer from fenced or plain JSON; the saved responses were re-evaluated without additional model calls. The per-example `parser_status` is `valid_json_fenced` for all five.
- The two single-source cases (`true_higher` and `true_lower`) had correct initial drafts. The model chose `preserve`, cited the supplied source, and retained the exact-match answer in both cases.
- All three equal-provenance conflicts produced a qualified answer listing both claims. Exact match therefore counted both initially correct drafts as lost; phrase diagnostics flagged all three conflict answers for review. The incorrect-draft case also remained non-exact, as expected for an answer that states both alternatives rather than choosing one.
- Source attribution was aligned with the draft in two of the three conflict responses. For `ctrl_004` / `dev_0187`, both source IDs appeared in both `supporting_source_ids` and `contradicting_source_ids`, despite the two arrays being intended as distinct classifications. This is an output-contract ambiguity/consistency problem worth debugging, not evidence of general citation quality.
- This batch included no `false_higher`, `false_lower`, or `irrelevant_only` examples. It cannot assess correction from a misleading single passage, abstention under insufficient evidence, or scenario-wide performance.

## Interpretation limits

These are five synthetic development cases chosen by a fixed-seed shuffle, not an independent or representative sample. Exact-match losses on qualified conflict answers do not establish factual error. The phrase flags are diagnostics, not factuality labels. No human annotation was performed, and `manual_factuality_label` remains blank. Do not compute confirmatory claims, infer provenance-label effects, or compare methods from this batch.

## Development change

The next prompt candidate is `SELECTIVE_CORRECTION_PROMPT_V0_2.md`. It defines the source-ID arrays relative to the draft answer, forbids IDs from appearing in both, and prohibits Markdown fences. Keep v0.1 outputs unchanged and version any new run separately. A balanced follow-up should include one case from each of the six evidence scenarios crossed with both draft states (12 rows), then inspect source attribution and decisions manually before considering any larger run.

## Artifacts

- Raw responses: `serialized/controlled-v0/model_outputs.jsonl`
- Joined per-example diagnostics: `serialized/controlled-v0/results/per_example.csv`
- Group summary: `serialized/controlled-v0/results/summary.csv`
- Prompt used: `SELECTIVE_CORRECTION_PROMPT_V0.md`
