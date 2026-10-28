# Next-phase research protocol: selective correction under misleading retrieval

**Prepared:** 2026-10-28
**Status:** Design memo after the 25-case exploratory pilot

## What the pilot establishes

The audited-v1 run contains 25 questions and five condition/strategy groups (125 outputs total). All 125 outputs received a provisional label during this assistant-led review; these are **not independent human annotations** and must not be reported as human-evaluation results. In the misleading-evidence groups:

- Retrieval-only adopted a false answer in 23/25 cases and abstained in 2/25.
- Generative correction abstained in 15/25, gave an incorrect answer in 6/25, gave a correct answer in 3/25, and produced one mixed response.
- With clean evidence, generative correction was manually judged correct in 23/25, mixed in 1/25, and incorrect in 1/25.

These are counts from one small run, not estimates of general model performance. The evidence includes deliberately fabricated counterfactual passages, and each case was run once. Exact match and phrase-alias checks are diagnostics, not factuality measures. Two false answers were semantically equivalent to the foil but missed by the exact alias list (audit_012 and audit_017). This is a dataset/diagnostic coverage issue, not evidence that the model avoided those foils.

## Literature positioning

The broad topic is established. RGB evaluates noise robustness, negative rejection, information integration, and counterfactual robustness ([AAAI 2024 paper](https://ojs.aaai.org/index.php/AAAI/article/view/29728)). WikiContradict evaluates real-world knowledge conflicts and reports difficulty representing the conflict rather than choosing one side ([NeurIPS 2024 benchmark](https://proceedings.neurips.cc/paper_files/paper/2024/hash/c63819755591ea972f8570beffca6b1b-Abstract-Datasets_and_Benchmarks_Track.html)). (D)RAGged Into a Conflict develops a conflict taxonomy and realistic benchmark, and reports gains from informing the model about conflict type ([Google Research, 2025](https://research.google/pubs/dragged-into-a-conflict-detecting-and-addressing-conflicting-sources-in-retrieval-augmented-llms/)). RAGTruth supplies manually annotated hallucination spans and responses ([ACL 2024](https://aclanthology.org/2024.acl-long.585/)).


### Related-work comparison

| Work | Conflict/noise setting and evaluation | Relevance to this project | What the pilot still lacks |
|---|---|---|---|
| RGB (AAAI 2024) | Four capabilities: noise robustness, negative rejection, information integration, and counterfactual robustness. | Closest overlap for testing responses to false retrieved passages and insufficient evidence. | The current pilot mainly tests short factoid counterfactuals; it does not isolate these capabilities with balanced testbeds. |
| WikiContradict (NeurIPS 2024) | 253 human-annotated real-world Wikipedia conflict cases; evaluates representing both sides of retrieved conflicts. | Shows that conflict-aware response quality and answer completeness matter beyond choosing the gold answer. | Current pilot uses one deliberately false passage per case, not naturally occurring two-source conflicts or balanced source authority. |
| (D)RAGged Into a Conflict (2025) | Taxonomy of conflict types, expert annotation, realistic search results; studies conflict-type instructions. | Strong prior work for conflict taxonomy and interventions; any prompt-policy contribution must compare directly with its framing and baselines. | Current cases do not label conflict type beyond synthetic counterfactual and do not vary provenance/reliability systematically. |
| RAGTruth (ACL 2024) | Nearly 18,000 RAG responses with case-level and word-level human hallucination annotations. | Useful annotation precedent for claim-level evidence support and human-review procedures. | Current labels are assistant-generated drafts, not independent human annotations, and do not yet provide span-level evidence labels. |

The current pilot is best characterized as a small engineering/behavioral probe at the intersection of counterfactual robustness and answer correction. It is not yet a new benchmark: the set has only 25 hand-built factoids, synthetic misleading passages, one model output per condition, and no independent labels. A stronger follow-up should either (a) use an established dataset and isolate a clearly defined correction/preservation outcome, or (b) justify why a new dataset captures a conflict type existing benchmarks do not. The latter requires a documented benchmark comparison and expert annotation plan before making a novelty claim.
Therefore, “RAG can be misled by bad evidence” is not a defensible novelty claim. A narrower possible contribution is the **trade-off between correcting a wrong draft, preserving a correct draft, and abstaining when retrieved evidence conflicts with it**, measured under controlled evidence provenance and answerability. Novelty remains unproven and requires a systematic related-work review.

## Proposed research question

> When a draft answer conflicts with retrieved evidence, which correction policy best balances (a) fixing wrong drafts, (b) avoiding false changes to correct drafts, and (c) abstaining only when the available evidence is genuinely insufficient or unresolved?

Treat this as a research question, not a claim that a new method already exists.

## Study design before a larger run

### 1. Repair and freeze the evaluation materials

- Preserve audited-v1 unchanged so the completed run remains reproducible.
- Create a versioned follow-up dataset or evaluator mapping that adds the observed foil paraphrases for audit_012 and audit_017; record the change as alias coverage only. Do not silently relabel the old run as a new dataset version.
- Have two human reviewers independently check source support, foil truth status, answer variants, and intended abstention behavior. Resolve disagreements before model runs. Treat the current assistant-generated labels only as a draft annotation aid.
- Separate a **real-fact track** (source-checked, ordinary facts) from a **controlled synthetic track** (randomized facts/entities that reduce the chance the model can answer from parametric memory). Report the tracks separately.
- Include answerable-correct, answerable-incorrect, genuinely insufficient, irrelevant-noise, single misleading-source, and conflicting-source cases. Where conflict is intentional, vary source reliability and whether the conflict is explicit or implicit.

### 2. Compare policies, not just conditions

Use the same questions, initial drafts, retrieved passages, model version, and decoding settings for each paired condition. Compare at least:

1. Retrieval-only answer generation.
2. The current generic correction prompt.
3. A pre-registered selective policy that first classifies support as supported, contradicted, unresolved, or insufficient; then preserves/corrects/abstains according to that classification.
4. A simple source-blind “always follow retrieved evidence” baseline, if not already represented by retrieval-only.

Freeze the prompts before the confirmatory run. Treat any prompt tuning as development data and keep a separate held-out set for final comparison.

### 3. Make outcomes answer-level and evidence-aware

For every answer, two human annotators blinded to the system condition should label:

- factual correctness;
- whether each substantive claim is supported, contradicted, or not established by the supplied evidence;
- whether the system corrected, preserved, or abstained;
- whether an abstention was warranted;
- whether a correct initial answer was damaged or an incorrect initial answer was repaired.

Use two independent annotators and adjudicate disagreements. Report agreement and the adjudication procedure. Keep exact match, token F1, gold-mention, and foil-mention columns as secondary diagnostics. Alias matching should not be counted as semantic adjudication.

Primary outcome candidates should be fixed before running the study: correction success among initially wrong drafts, false-correction rate among initially correct drafts, and warranted-abstention rate on truly insufficient/unresolved cases. Report denominators and paired per-question results; do not collapse these into one score unless a utility function and its weights are justified in advance.

### 4. Plan sample size and analysis

Use a small development set to estimate paired disagreement rates, then run a power calculation for the minimum practically meaningful change in the primary paired outcome. Pre-register the target sample, exclusions, model/version, prompts, decoding settings, and analysis before the confirmatory run. Use paired tests or confidence intervals that respect the per-question pairing; report effect sizes and uncertainty, not only p-values. Replicate runs if generation is stochastic, and retain raw outputs and run metadata.

## Immediate next actions

1. Freeze the current audited-v1 outputs and reviewed CSVs as the pilot artifact.
2. Conduct the focused related-work review around selective correction, conflict-type handling, provenance/source reliability, and abstention calibration; compare task definitions and baselines in a table.
3. Independently re-review the 125 outputs before treating the category counts as findings. Decide whether the main contribution will be a controlled evaluation study or a new correction policy. Do not expand the pilot into a larger model run until the contribution, primary outcome, and held-out design are fixed.
4. PR #9 (case-range support) was merged, as reported by the researcher. The local checkout has not fetched the merge yet: its origin/main still points to 877b42d, while the checked-out PR branch is ac520c1. Sync the checkout before starting another GitHub change.

## Interpretation boundary

The exploratory outputs and provisional assistant labels suggest a failure pattern to investigate: under this setup, generic correction often abstained and sometimes adopted the misleading claim. It does **not** establish that selective correction is generally ineffective, that the proposed selective policy will help, or that this project is novel. Those require a controlled, adequately powered, independently reviewed follow-up.
