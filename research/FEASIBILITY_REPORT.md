# Research Feasibility Report: Factual Correction Under Misleading Evidence

**Status:** Pilot design only. No model experiment has been run and no research novelty claim is established.

## Decision

Retain Verity RAG as the application platform. Do not yet claim a new correction algorithm. The most defensible next step is a controlled, paired evaluation of existing correction strategies under clean versus deliberately corrupted evidence.

### Candidate research question

**When the evidence supplied to a post-generation correction system is corrupted, does correction improve or reduce factual accuracy relative to leaving the answer unchanged, and how does this depend on the corruption type?**

This is narrower than a general hallucination-correction system. It focuses on the interaction between *post-generation correction* and *controlled evidence corruption*.

## Literature overlap and implications

| Work | What it already studies | Consequence |
|---|---|---|
| RAC (Findings EMNLP 2025) | Retrieval-augmented factuality correction | Generic retrieval-based correction is not novel. |
| RAGuard (NeurIPS 2025) | Fact-checking under supporting, misleading and unrelated retrieved documents | Misleading retrieval is an established evaluation condition. Its released examples are based on PolitiFact claims and Reddit documents, so it may not be the best primary dataset for general QA correction. |
| RAG-Stress (arXiv:2610.11183, Oct. 2026) | Controlled evidence edits that make a wrong answer appear supported; measures harmful answer overrides conditional on closed-book correctness | The effect of misleading evidence on answers is already directly studied. Its paper does not present itself as a correction method. |
| RAGStress (arXiv:2610.04691, Oct. 2026) | Four knowledge-base corruption types at three severities, with code and corruption-generation scripts | Corruption type/severity as an evaluation variable is already studied. The paper says some benchmark artifacts are pending publication; verify what is downloadable before depending on it. |
| Evidence-Bound Factual Repair (Preprints.org, posted 7 Sep. 2026; not peer reviewed) | Compares deterministic evidence-bound repair with unconstrained regeneration on RAGTruth and ExpertQA under the evidence naturally associated with those datasets | A plain deterministic-vs-generative repair comparison on ordinary evidence would overlap substantially. Our only plausible distinction is to test these correction approaches under controlled corrupted evidence. |
| FactCorrector (ACL 2026) | Structured factuality correction and preservation of useful content | Correction quality and preservation metrics are not new by themselves. |
| RAGTruth (ACL 2024) | Public human-annotated RAG hallucination corpus with span-level labels | Useful for a secondary evaluation on naturally generated responses, but it does not itself provide paired clean/corrupted evidence for every response. |

## Dataset feasibility

### Primary pilot data: controlled, paired QA cases

Start with a small subset of stable, answerable QA items for which we can retain:
- the same question and reference answer across conditions;
- a clean evidence passage;
- a controlled corrupted/misleading passage;
- the intended incorrect foil answer;
- the corruption type and severity.

RAGStress's released code can inform the corruption protocol, but the full benchmark availability must be checked at download time. Do not assume its entire 700-question split or full corrupted knowledge base is currently downloadable. If those files are unavailable, create a small, explicitly documented pilot subset from a publicly licensed QA source and manually audit every evidence edit. Do not represent that pilot subset as the official RAGStress dataset.

### Secondary data: RAGTruth

RAGTruth is publicly available under an MIT license in the ParticleMedia repository. It has QA, summarization and data-to-text tasks and human-annotated hallucination spans. Use only the QA split initially. Its role is secondary: assess whether findings from controlled corruption are consistent with naturally occurring RAG responses. Do not treat RAGTruth as a misleading-evidence benchmark without constructing and validating the paired evidence conditions.

### RAC baseline

The public RAC repository is Apache-2.0 licensed. Its README requires separate generation, breakdown, verification and correction model names, a retrieval file, and environment setup scripts. It is a heavier baseline than a one-prompt correction system. For a student-scale pilot:
1. Implement a transparent same-model generative-correction baseline first.
2. Keep no-correction and retrieval-only controls.
3. Attempt RAC reproduction only after checking dependencies, model access and runtime.
4. Do not claim to reproduce RAC if its original pipeline/configuration was not run.

## Experimental protocol

For each item, keep the question and gold answer fixed. Run the same model configuration under:
1. no retrieval;
2. clean evidence;
3. misleading/factually corrupted evidence;
4. irrelevant evidence;
5. contradictory evidence, if the case has a valid audited version.

Compare:
- no correction (the answer is left unchanged);
- a clearly specified generative correction prompt;
- evidence-bound correction only if it can be implemented without giving it a different evidence advantage.

All methods must receive equivalent evidence and comparable inference budgets. Save raw prompts, raw outputs, model/version identifiers, timestamps, condition IDs and token/cost estimates. Randomize or fix ordering and temperature. Evaluate paired changes rather than comparing unrelated examples.

## Metrics

Primary:
- final answer accuracy;
- harmful correction rate: initially correct answer becomes incorrect after correction;
- correction success rate: initially incorrect answer becomes correct after correction;
- preservation rate: initially correct answer remains correct;
- foil-adoption rate under misleading evidence.

Secondary:
- abstention/insufficient-evidence behavior;
- token-level F1 for short answers;
- inference calls, tokens and estimated cost.

Exact match is only a pilot metric. For open-ended answers, use blinded human review or a validated evaluator and audit a sample manually. Do not rely on an LLM judge alone for headline claims.

## Minimum pilot and go/no-go rules

1. Build and manually audit 50–100 paired QA items before scaling.
2. Run the no-retrieval and clean-evidence conditions first to validate that the model can answer the chosen questions.
3. Run corrupted conditions and the correction baseline on the same eligible items.
4. Report paired counts and confidence intervals; do not report only an aggregate accuracy.
5. If the correction-vs-no-correction comparison under controlled corruption is already present in a directly overlapping paper, stop and revise the research question before expanding.

## Main risks

- **Novelty risk:** The proposed intersection may already be covered by work not yet identified. This report does not certify novelty.
- **Dataset risk:** RAGStress's full artifacts may not all be downloadable yet; RAGuard is domain-specific; RAGTruth is not a corruption benchmark.
- **Evaluation risk:** Exact match can penalize valid paraphrases and cannot reliably assess long-form factual preservation.
- **Cost risk:** Full reproduction of RAC or multi-model experiments may exceed a student-scale budget.
- **Validity risk:** Synthetic evidence edits may be easier to detect than naturally occurring misinformation; report the controlled scope honestly.

## Go/no-go recommendation

**GO for a small feasibility pilot; NO-GO for a novelty claim or a large-scale implementation yet.** First verify the actual downloadable dataset files, produce the paired pilot, and confirm that the exact correction-under-corruption comparison is not already in the closest papers.
