# Public dataset setup: RAGTruth

## Why this dataset

Use **RAGTruth** as an external benchmark for the hallucination-detection / evidence-grounding part of Evidence-Grounded RAG. The upstream corpus contains 17,790 responses across 2,965 source instances, including question answering (QA), summarisation, and data-to-text tasks. It includes source context and manually annotated hallucination spans.

- Official dataset repository: https://github.com/ParticleMedia/RAGTruth
- Research paper: https://aclanthology.org/2024.acl-long.585/
- Upstream licence: see the official repository's LICENSE file. The source data may have separate terms; check the upstream README and underlying corpus terms before redistributing any raw data.

## Download locally

From the project root, run:

```bash
python research/pilot/download_ragtruth.py
```

The script clones the official repository to `data/external/RAGTruth`. To choose another location:

```bash
python research/pilot/download_ragtruth.py --destination data/RAGTruth
```

Requirements: Git installed and internet access. The downloader refuses to overwrite an existing destination.

## How to use it in this project

1. Start with **QA examples** for the closest fit to question answering grounded in retrieved passages.
2. Join the upstream response records to source-information records using `source_id`; consult the upstream README for the exact fields and file layout.
3. Preserve the official train/test split. Do not tune thresholds or correction prompts on the held-out test split.
4. Evaluate hallucination detection against the annotated spans (for example, whether a response contains an annotated unsupported span). Report the task subset, filtering, and metrics clearly.
5. Treat correction as a separate experiment. RAGTruth labels hallucination spans; it does **not** provide a gold corrected answer for every example. If testing correction, define a transparent protocol and separately judge whether the corrected answer is supported by the supplied context and whether it changes correct claims.
6. Keep the existing 25-case controlled pilot as a small diagnostic set, not as a replacement for the public benchmark.

## Why the raw dataset is not committed here

The downloader fetches the data from its official source when needed, instead of copying a large external corpus into the project Git history. This keeps the repository lighter and preserves the upstream source and version history. Record the downloaded commit/revision in experiment notes so runs can be reproduced.

## Required reporting caveat

A benchmark score on RAGTruth measures performance on its dataset and annotation scheme. It does not, by itself, prove that the full system reliably detects and corrects hallucinations in every domain. Report detection and correction results separately.

## Citation

Niu, C. et al. (2024). *RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models*. ACL 2024. https://aclanthology.org/2024.acl-long.585/
