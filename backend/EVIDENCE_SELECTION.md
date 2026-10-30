# Hally evidence selection pipeline

## Purpose

Hally ranks retrieved evidence separately for each extracted claim. It does not equate search-result order, domain allowlisting, or a high ranking score with truth.

## Pipeline

1. Search or receive evidence candidates from the selected input mode.
2. Normalize HTTPS hostnames and assign a coarse authority tier.
3. Score each passage for claim relevance using token coverage, passage precision, phrase and numeric overlap.
4. Add weak metadata-completeness and date signals when publication metadata is available.
5. Group exact or near-identical passages so repeated copies do not count as independent corroboration.
6. Rank candidates and exclude passages with zero lexical relationship to the claim.
7. Supply the selected passages separately for each claim to the instruction-model verifier.
8. Require the verifier to return a verbatim excerpt; discard excerpts not found in the selected context.
9. Re-run the same claim-level selection and verification after correction.
10. Return scores, source tiers, reasons, candidate counts and duplicate-group metadata to the report UI.

## Ranking formula

`selection_score = 0.58 × relevance + 0.27 × authority + 0.10 × metadata_completeness + 0.05 × freshness_signal`

All component scores are bounded between 0 and 1. The result is a deterministic heuristic for ordering candidates, **not** a calibrated probability, confidence score, or guarantee that a source is correct.

### Relevance

- Token coverage: share of claim content words present in the passage.
- Passage precision: share of passage content words that overlap the claim.
- Phrase bonus: small bonus for a matching multiword phrase.
- Numeric bonus: small bonus when a number in the claim also appears in the passage.

This is lexical relevance, not semantic embedding similarity. Different wording can still be missed.

### Authority tiers

- Primary / institutional domains: government, academic and intergovernmental domains, plus selected primary institutions.
- Scholarly publishers.
- Established news publishers.
- Specialist educational publishers.
- Unverified domains.
- Blocked user-generated/social platforms.

A trusted/allowlisted domain is labelled `allowlisted_domain_unverified_page`: Hally has **not** fetched, authenticated, or audited the specific page merely by recognizing its hostname. Domain tiers are broad priors and are imperfect (for example, not every university subdomain is an authoritative source for every topic).

### Metadata and freshness

Publication date and author are used only when supplied by the search provider. Missing dates receive a neutral value; they are not guessed. The date signal is intentionally weak and is not a substitute for topic-specific recency rules.

### Duplicates and corroboration

Exact and highly similar passages are grouped. Only the highest-ranked member of a duplicate group is selected, so syndicated copies or repeated snippets do not inflate the selected-source count. Distinct domains are reported as a simple diversity indicator; they are not proof of editorial independence.

## Verification and correction

The verifier receives claim-specific evidence. It can classify each claim as supported, contradicted, or not enough evidence. Conflicting evidence must remain visible to the verifier; absence of evidence is not treated as contradiction. Correction uses only the retrieved context and is followed by a fresh verification pass.

The verifier is an instruction-following language model, not an independently trained NLI classifier. Its labels can still be wrong. The system therefore exposes exact excerpts and reasons for human review.

## Current limitations

- Web search results provide snippets; this pipeline does not fetch and parse the full page body.
- Domain reputation is a hand-maintained coarse allowlist, not a learned source-quality model.
- Freshness is weak and depends on provider metadata.
- Duplicate detection is passage-text similarity, not full publisher/syndication graph analysis.
- Relevance is lexical; a future semantic retriever can be added behind the same selector interface.
- Source independence is approximated by domains and duplicate grouping, not proven.
- Manual/document evidence is user-provided and is not externally authenticated.

These limitations are returned in the UI rather than hidden behind an authoritative-looking score.
