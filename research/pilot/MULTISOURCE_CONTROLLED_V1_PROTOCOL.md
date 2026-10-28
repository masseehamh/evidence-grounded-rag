# Multi-source controlled-v1 development design

**Status:** design and synthetic fixture for development only; not preregistered, validated, or confirmatory. No model inference has been run on this dataset.

## Why extend controlled-v0

The controlled-v0 selective prompt followed every false single-passage claim in the 12-row balanced batch, whether the passage was labeled higher or lower provenance. A model cannot identify an isolated false statement from its wording alone. Controlled-v1 makes agreement, disagreement, and source dependence visible so the prompt can be assessed when the input contains usable evidence about corroboration.

## Dataset structure

`cases.controlled.multisource.dev.v1.jsonl` contains 25 fictional items. Every item crosses two draft states (correct/incorrect) with 12 evidence configurations, for 600 item-state combinations. The configurations are:

| Scenario | Visible evidence | Intended diagnostic question |
|---|---|---|
| `single_true_higher`, `single_true_lower` | One true answer-bearing source | Does the draft remain stable when supported? |
| `single_false_higher`, `single_false_lower` | One false answer-bearing source | Does a lone assertion override the draft, and does the provenance label change behavior? |
| `independent_agreement_true` | Two independent sources agree on the truth; one higher and one lower label | Does corroboration increase confidence appropriately? |
| `independent_agreement_false` | Two independent sources agree on the false claim; one higher and one lower label | Does the model avoid treating consensus alone as a guarantee of truth? |
| `independent_conflict_true_higher` | Independent higher source says truth; lower source says false claim | Does the model use provenance while exposing the remaining uncertainty? |
| `independent_conflict_false_higher` | Independent higher source says false claim; lower source says truth | Does it avoid blindly equating higher provenance with truth? |
| `independent_conflict_equal` | Independent, equally labeled sources disagree | Does it qualify or abstain on unresolved conflict? |
| `dependent_agreement_false` | Two passages agree on the false claim but share a source family and independence group | Does the model avoid double-counting dependent evidence? |
| `irrelevant_only` | One non-answer-bearing passage | Does it abstain or preserve the draft only with a clear unverified caveat? |
| `true_plus_irrelevant` | One true answer-bearing source plus an irrelevant passage | Does it separate relevant evidence from distracting context? |

The fixture uses fictional deterministic assignments and fixed scenario templates. Source truth, provenance level, and independence are represented separately in metadata. Scenario labels and answer keys must stay out of model requests. The schema is `controlled_multisource_v1.schema.json`; the generator is `generate_controlled_multisource_v1.py`.

## Development run proposal

First prepare one item per scenario × draft-state cell (24 rows) and run only the current selective policy on that set. This is a failure-mode probe, not a performance estimate. Preserve the exact prompt, model, decoding configuration, output, and selection seed. Inspect source-ID classifications, whether decisions reflect independent corroboration, harmful revisions of correct drafts, useful corrections of incorrect drafts, and abstention/qualification. Then revise only on development material and record a new prompt version.

Do not interpret exact-match loss on a justified qualification or abstention as a factual error. Review output action and factual truth separately. Have a person adjudicate the answers before making factuality claims.

## Limits and gates before confirmation

- Each development stratum has only one selected item and one model generation; results are descriptive.
- `higher` and `lower` are controlled provenance labels, not verified truth labels. Their substantive interpretation must be operationally defined for a real-source study.
- Two different source IDs do not establish real-world independence; v1 supplies an explicit fictional `independence_group` solely to make that experimental signal observable.
- The dependent-agreement condition tests duplicate evidence; it is not equivalent to two genuinely independent sources.
- The false-higher and independent-false-agreement conditions may be impossible for a system to detect without other evidence; treat them as adversarial reliance tests, not evidence of hidden-knowledge capability.
- Before a confirmatory study, independently review and freeze the construction, define reliability and independence for the source-grounded track, write the human annotation rubric, select primary endpoints and margins, and reserve held-out items.
