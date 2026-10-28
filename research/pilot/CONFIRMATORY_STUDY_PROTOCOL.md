# Confirmatory study protocol: selective correction in evidence-grounded RAG

**Status:** proposed protocol; not preregistered and not yet run
**Basis:** exploratory audited-v1 pilot and AI repeat-pass consistency check

## 1. Research question

When a draft answer and retrieved context disagree, does an explicit selective-correction policy improve the balance among correcting wrong drafts, preserving correct drafts, and abstaining only when evidence is genuinely insufficient or unresolved, compared with generic correction and retrieval-only baselines?

This is a testable follow-up question, not a novelty claim. Prior work already studies RAG noise and counterfactual robustness (RGB), knowledge conflicts (WikiContradict; (D)RAGged Into a Conflict), and hallucination annotations (RAGTruth). The contribution, if any, must be stated as a carefully scoped result about the intervention, data conditions, and trade-offs after direct benchmark and method comparison.

## 2. Preregistered hypotheses

- **H1 — avoid harmful revisions:** On items with a correct initial draft, selective correction has a lower false-correction rate than generic correction.
- **H2 — retain useful correction:** On items with an incorrect initial draft and reliable answer-bearing evidence, selective correction is non-inferior to generic correction in correction success, within a predeclared margin.
- **H3 — calibrate abstention:** On genuinely insufficient or unresolved items, selective correction increases warranted abstention; on answerable items with reliable evidence, it does not increase avoidable abstention beyond a predeclared margin.

Define the minimum practically meaningful difference and H2/H3 non-inferiority margins before the confirmatory data are generated. If the team cannot justify those margins, report descriptive paired estimates and uncertainty instead of significance claims.

## 3. Experimental factors

### Data tracks

1. **Controlled track:** use fictional entities and randomly assigned attributes/values so the answer is specified by the experimental evidence rather than familiar parametric knowledge. Make the true answer, false counterclaim, evidence sufficiency, and source-reliability label explicit in the dataset metadata. Keep metadata hidden from the model unless the condition intentionally supplies it. When source reliability is a treatment, assign its label independently of passage truth; include authoritative-but-false and unverified-but-true examples so the label is not an answer key.
2. **Source-grounded track:** use independently verified real-world questions and authoritative source passages. Keep the current 25 audited-v1 examples as development material only; do not count them as confirmatory test items.

A draft schema and one fictional illustration are in [controlled_dataset.schema.json](controlled_dataset.schema.json) and [controlled_dataset.example.json](controlled_dataset.example.json); the example is not research data. Report the tracks separately. Synthetic results establish behavior in the controlled construction; real-world results test whether the pattern transfers to sourced facts.

### Item states

Balance initial drafts as correct versus incorrect. Cross them with these evidence states:

- reliable evidence supports the truth;
- a misleading/unverified passage asserts a false counterclaim;
- irrelevant or non-answer-bearing evidence;
- genuinely unresolved conflict (two sources disagree, with authority either unequal or explicitly equal).

Record source reliability and whether the conflict is explicit or implicit. Avoid calling a passage “conflicting” when the model sees only one claim and no signal that it is unreliable; that tests trust in an isolated claim, not conflict resolution.

An isolated false passage is not identifiable as false from its wording alone. Treat such cells as stress tests of reliance on retrieved assertions, not as cases where the model should somehow recover hidden truth. If the research claim concerns selective correction under noise, include multi-passage conditions that vary independent corroboration, source dependence, provenance, and agreement/disagreement. Keep the trusted answer key hidden, but make the evidence available to the model sufficient for the intended decision; otherwise the task measures an impossible inference.

### System conditions

Run the same question, draft, evidence, model version, and decoding settings through:

1. **Preserve-draft baseline:** return the initial answer unchanged.
2. **Retrieval-only baseline:** answer directly from the supplied evidence.
3. **Generic correction:** the current correction prompt.
4. **Selective correction:** first classify evidence as supports, contradicts, unresolved, or insufficient; then preserve, revise, or abstain according to a frozen decision rule.

A starting development-only prompt and metadata contract are in [SELECTIVE_CORRECTION_PROMPT_V0.md](SELECTIVE_CORRECTION_PROMPT_V0.md). The selective prompt and decision rule must be frozen before the held-out run. Any iteration on prompts belongs to development data only. Keep all outputs, prompts, evidence order, model identifiers, timestamps, and generation settings.

## 4. Outcomes and annotation

Use two human annotators, blinded to system condition and strategy, to independently rate each answer. Raters may consult the authoritative reference needed to judge factual correctness, but must not see system labels, gold/foil aliases, or previous ratings. Keep the retrieved passage distinct from the trusted truth reference so evidence support and factual correctness are rated separately. For each output, collect:

- factual correctness: correct, correct with caveat, mixed, incorrect, or cannot determine;
- support relation to shown evidence: supported, contradicted, mixed, not addressed, or cannot determine;
- action: preserved, corrected, or abstained;
- abstention appropriateness;
- whether a correct draft was damaged or an incorrect draft repaired.

Use a written rubric, train on a separate calibration subset, preserve both initial ratings, report raw agreement and Cohen's kappa for nominal factuality labels, and adjudicate disagreements. Do not use the previous assistant-generated labels as gold. The AI repeat-pass files are not human labels and must not enter the gold set.

## 5. Primary analysis

Use the question/item as the paired unit; compare system conditions on identical item states. Preselect H1 false-correction rate and H2 correction-success rate as co-primary outcomes, with family-wise error control (for example, Holm adjustment). Report the denominators and paired effect sizes with confidence intervals. Use paired tests appropriate to binary outcomes and preserve item-level clustering when multiple generations per item are run. Treat warranted abstention and evidence-support ratings as secondary outcomes unless the preregistration explicitly promotes them.

Determine sample size before the confirmatory run using a paired-outcome power calculation. Estimate the discordant-pair rate on development data, define the minimum meaningful effect and error rate, and document the calculation. The current 25-case pilot and its AI-coded labels are too small and too dependent on this setup to serve as reliable power estimates by themselves. If generation is stochastic, predeclare the number of repeats and analyze repeated outputs clustered by item.

## 6. Data quality and reproducibility gates

Before spending inference budget:

- two reviewers verify each source, answer key, counterclaim, and evidence-state label;
- resolve or document disagreements and freeze a dataset version/hash;
- ensure aliases cover common paraphrases, but keep semantic human ratings as the outcome;
- test the annotation form on examples that include correct answers with extra wording, false answers supported by misleading evidence, abstentions, and mixed claims;
- freeze prompts, decoding settings, exclusions, primary metrics, margins, and analysis code;
- reserve held-out items that were not used to edit prompts or labels.

The known audited-v1 foil-alias misses (audit_012 and audit_017) should be repaired in a new version, while keeping v1 immutable. Re-running an evaluator on prior outputs with changed aliases must be recorded as a diagnostic re-analysis, not silently relabeled as a new model run.

## 7. Decision gates

- **Gate A — source and annotation readiness:** do not run the confirmatory batch until independent review and the rubric are complete.
- **Gate B — statistical readiness:** do not set a confirmatory sample size until effect margins, paired discordance assumptions, and the power calculation are written down.
- **Gate C — contribution readiness:** do not claim novelty or target a conference until the related-work matrix directly compares task definitions, data, baselines, and outcomes against RGB, WikiContradict, (D)RAGged Into a Conflict, RAGTruth, and any closer selective-correction/abstention work found in the focused search.

## 8. Pilot boundary

The current 25-question pilot is exploratory engineering evidence only. The earlier 125-row labels are provisional assistant annotations; the 123/125 repeat-pass match and kappa 0.974 measure same-assistant consistency after label mapping, not human reliability or evaluator validity. Do not use either statistic as the confirmatory study result.

## References to compare directly

- RGB, AAAI 2024: https://ojs.aaai.org/index.php/AAAI/article/view/29728
- WikiContradict, NeurIPS 2024: https://proceedings.neurips.cc/paper_files/paper/2024/hash/c63819755591ea972f8570beffca6b1b-Abstract-Datasets_and_Benchmarks_Track.html
- (D)RAGged Into a Conflict, 2025: https://research.google/pubs/dragged-into-a-conflict-detecting-and-addressing-conflicting-sources-in-retrieval-augmented-llms/
- RAGTruth, ACL 2024: https://aclanthology.org/2024.acl-long.585/


## 9. Provisional power sensitivity (not a final sample-size decision)

For two-sided McNemar comparisons, a normal-approximation planning formula is:

`n ≈ (z_(1−α/2)√q + z_(1−β)√(q−Δ²))² / Δ²`

where `n` is the number of paired item-state units in the relevant outcome stratum, `q` is the total discordant-pair rate between the two systems, and `Δ` is the minimum absolute difference to detect. The table uses 80% power and a conservative per-outcome α = .025 for two co-primary outcomes (Bonferroni control of family-wise α=.05). It is an approximation; final planning should use an exact/simulated McNemar power calculation with assumptions justified from development data.

| Target absolute paired difference | Assumed discordant-pair rate q | Approximate paired units per eligible outcome stratum | Illustrative n with 15% unusable-item allowance |
|---:|---:|---:|---:|
| 10 percentage points | 0.20 | 188 | 216 |
| 10 percentage points | 0.30 | 283 | 325 |
| 10 percentage points | 0.40 | 378 | 435 |
| 15 percentage points | 0.20 | 82 | 95 |
| 15 percentage points | 0.30 | 125 | 143 |
| 15 percentage points | 0.40 | 167 | 192 |

These values are **sensitivity scenarios**, not chosen margins or a preregistered target. H1 and H2 apply to different eligible item strata (initially correct versus initially incorrect drafts), so each stratum needs its own adequate paired sample. If both draft states are generated from the same base question, the shared-item dependence must be modeled or handled by item-clustered inference; the table does not include a clustering design effect. The 15% allowance only illustrates incomplete/invalid annotations and does not correct for clustering.

Before fixing N, the research team must choose and justify the smallest meaningful effect, estimate or conservatively bound `q` from a development set with human-reviewed outcomes, decide how base questions are allocated across draft/evidence states, and run an exact paired-power simulation. The current AI-coded pilot cannot justify those choices by itself.
