# Dataset Access Check — 28 October 2026

## Decision

Do **not** make the full RAGStress benchmark the immediate dependency for the pilot. Its paper says the source questions and generation scripts are publicly available, but the fixed 700-question evaluation split, metadata schema, 1,000 corrupted-document sample, and full 182,546-document knowledge base are listed as becoming available upon publication / DOI-archived release. That means we should not assume the full benchmark artifacts are downloadable today.

Paper: https://arxiv.org/html/2610.04691
Author code: https://github.com/Salliberg/CorruptRAG-Code

## What is available

The linked code repository currently exposes:
- source code for generating documents and running experiments;
- a data/mmlu directory;
- experiment/configuration and evaluation code.

The public artifact list in the paper explicitly distinguishes these available components from the evaluation split and full KB promised for later release. Check the repository again before starting a larger reproduction, because the release status may change.

## Implication for our correction experiment

RAGStress evaluates RAG under knowledge-base corruption; it is not itself a benchmark of post-generation correction methods. Even if its artifacts are available, our study must add correction-specific arms and metrics. We must not describe the original benchmark as if it already contains our correction outputs.

The distinct RAG-Stress paper (arXiv:2610.11183) studies evidence edits that support a designated incorrect answer and measures harmful overrides. Its methodology and audit requirements are informative, but we have not verified a public official dataset/code repository from its paper page in this check. Do not assume its saved generations or full paired data are available.

## Recommended next action

1. Check whether the needed evaluation split and corrupted passages have since been released.
2. If not, use a clearly labeled *pilot subset* constructed from a publicly accessible English QA dataset, with paired clean and misleading evidence and manual review of every edit.
3. Keep the initial pilot small (50–100 questions) and treat it as feasibility work, not a benchmark or publishable result by itself.
4. Before scaling, compare the exact correction-under-corruption protocol against the latest versions of RAC, FactCorrector, RAGuard, RAG-Stress, and related work. The research gap remains unconfirmed.

## Validity guardrails

- Never call a locally constructed subset the official RAGStress dataset.
- Never report toy examples as experimental results.
- Keep the gold answer, foil answer, evidence variants, prompts, model identifiers, decoding settings, and failures/retries in a reproducible record.
- Use human review for evidence-edit validity and audit semantic correctness; exact-match scoring alone is inadequate for long-form answers.
- Do not make a novelty claim until the closest experiments have been checked in detail.
