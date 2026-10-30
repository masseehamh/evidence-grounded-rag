"""Deterministic, explainable evidence selection for Hally.

Scores are ranking signals, not probabilities or proof of truth. Domain authority
is a coarse prior; it never verifies an individual page.
"""
from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlparse


PRIMARY_DOMAINS = {
    "who.int", "un.org", "europa.eu", "nasa.gov", "nih.gov", "cdc.gov",
    "pubmed.ncbi.nlm.nih.gov", "worldbank.org", "imf.org", "oecd.org",
    "ourworldindata.org", "india.gov.in", "data.gov",
}
SCHOLARLY_DOMAINS = {
    "nature.com", "science.org", "sciencedirect.com", "springer.com",
    "wiley.com", "arxiv.org", "jstor.org",
}
NEWS_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "theguardian.com", "nytimes.com", "washingtonpost.com",
}
EDUCATION_DOMAINS = {
    "health.harvard.edu", "mayoclinic.org", "clevelandclinic.org",
    "medlineplus.gov", "nhs.uk", "betterhealth.vic.gov.au",
    "acefitness.org", "nasm.org", "exrx.net", "verywellfit.com",
    "healthline.com", "strengthlog.com",
}
BLOCKED_DOMAINS = {
    "reddit.com", "quora.com", "medium.com", "facebook.com", "instagram.com",
    "tiktok.com", "x.com", "twitter.com", "pinterest.com", "youtube.com",
}
STOP = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "many", "much", "does", "did", "was", "were", "are", "the", "and", "for",
    "with", "that", "this", "from", "into", "about", "have", "has", "had",
    "been", "being", "year", "years", "date", "number", "name", "time", "kind",
    "type", "there", "their", "them", "they", "give", "tell", "please", "would",
    "could", "should", "can", "is", "in", "on", "of", "to", "a", "an", "it",
    "its", "as", "by", "at", "or", "not", "be", "do",
}


def domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return ""
        host = parsed.hostname.lower().rstrip(".")
        return host[4:] if host.startswith("www.") else host
    except (TypeError, ValueError):
        return ""


def _matches(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def assess_source_authority(source: dict) -> dict:
    url = str(source.get("url") or "")
    host = domain_from_url(url)
    if not url and source.get("source_type") == "uploaded_document":
        return {"authority_score": 0.60, "authority_tier": "user-provided document",
                "trust_level": "user_provided_unverified", "domain": ""}
    if not host:
        return {"authority_score": 0.0, "authority_tier": "invalid or non-HTTPS URL",
                "trust_level": "unverified_domain", "domain": ""}
    if _matches(host, BLOCKED_DOMAINS):
        return {"authority_score": 0.0, "authority_tier": "blocked user-generated platform",
                "trust_level": "blocked_domain", "domain": host}
    if host.endswith((".gov", ".gov.in", ".edu", ".edu.in", ".ac.in", ".ac.uk", ".edu.au", ".int")) or _matches(host, PRIMARY_DOMAINS):
        return {"authority_score": 1.0, "authority_tier": "primary / institutional domain",
                "trust_level": "allowlisted_domain_unverified_page", "domain": host}
    if _matches(host, SCHOLARLY_DOMAINS):
        return {"authority_score": 0.90, "authority_tier": "scholarly publisher",
                "trust_level": "allowlisted_domain_unverified_page", "domain": host}
    if _matches(host, NEWS_DOMAINS):
        return {"authority_score": 0.78, "authority_tier": "established news publisher",
                "trust_level": "allowlisted_domain_unverified_page", "domain": host}
    if _matches(host, EDUCATION_DOMAINS):
        return {"authority_score": 0.72, "authority_tier": "specialist educational publisher",
                "trust_level": "allowlisted_domain_unverified_page", "domain": host}
    return {"authority_score": 0.35, "authority_tier": "unverified domain",
            "trust_level": "unverified_domain", "domain": host}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9'-]{2,}", str(text or "").lower())
    return {word for word in words if word not in STOP}


def relevance_score(claim: str, passage: str) -> float:
    query = _tokens(claim)
    body = _tokens(passage)
    if not query or not body:
        return 0.0
    overlap = query & body
    coverage = len(overlap) / len(query)
    precision = len(overlap) / len(body)
    phrase = " ".join(sorted(query))
    body_phrase = " ".join(sorted(body))
    phrase_bonus = 0.08 if len(query) >= 2 and phrase in body_phrase else 0.0
    numbers_q = set(re.findall(r"\b\d[\d,.]*%?\b", claim or ""))
    numbers_p = set(re.findall(r"\b\d[\d,.]*%?\b", passage or ""))
    number_bonus = 0.08 if numbers_q and numbers_q & numbers_p else 0.0
    return min(1.0, 0.70 * coverage + 0.22 * precision + phrase_bonus + number_bonus)


def _normalise_passage(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _duplicate_groups(records: list[dict]) -> list[list[int]]:
    groups: list[list[int]] = []
    token_sets = [_tokens(item.get("passage", "")) for item in records]
    normalized = [_normalise_passage(item.get("passage", "")) for item in records]
    used: set[int] = set()
    for i in range(len(records)):
        if i in used or not normalized[i]:
            continue
        group = [i]
        for j in range(i + 1, len(records)):
            if j in used or not normalized[j]:
                continue
            if normalized[i] == normalized[j]:
                group.append(j)
                continue
            union = token_sets[i] | token_sets[j]
            similarity = len(token_sets[i] & token_sets[j]) / len(union) if union else 0.0
            if similarity >= 0.92 and len(union) >= 8:
                group.append(j)
        if len(group) > 1:
            groups.append(group)
            used.update(group)
    return groups


def select_evidence(claim: str, sources: list[dict], top_k: int = 8) -> dict:
    """Rank sources for one claim and return selected records plus audit metadata."""
    candidates = []
    for index, raw in enumerate(sources or []):
        source = dict(raw)
        passage = str(source.get("passage") or source.get("snippet") or "").strip()
        if not passage:
            continue
        authority = assess_source_authority(source)
        relevance = relevance_score(claim, passage)
        title = str(source.get("title") or source.get("filename") or "Untitled source")
        url = str(source.get("url") or "")
        metadata_score = sum(bool(value) for value in (
            title, url, source.get("published_date"), source.get("author"),
        )) / 4.0
        # A publication date is a weak freshness signal only; unknown dates are neutral.
        freshness = 0.5
        date = str(source.get("published_date") or "")
        if date:
            freshness = 0.8 if re.match(r"^20(2[4-9]|3[0-9])", date) else 0.45
        score = (
            0.58 * relevance
            + 0.27 * authority["authority_score"]
            + 0.10 * metadata_score
            + 0.05 * freshness
        )
        reasons = []
        if relevance >= 0.45:
            reasons.append("strong claim-to-passage relevance")
        elif relevance >= 0.20:
            reasons.append("partial claim-to-passage relevance")
        else:
            reasons.append("weak lexical relevance")
        reasons.append(authority["authority_tier"])
        if not url:
            reasons.append("uploaded evidence; publisher not independently assessed")
        elif authority["trust_level"] == "allowlisted_domain_unverified_page":
            reasons.append("domain is allowlisted; this page itself was not verified")
        else:
            reasons.append("publisher/page is unverified")
        candidates.append({
            **source,
            "source_id": str(source.get("source_id") or f"source-{index + 1}"),
            "title": title,
            "passage": passage,
            "domain": authority["domain"],
            "trust_level": authority["trust_level"],
            "authority_tier": authority["authority_tier"],
            "authority_score": round(authority["authority_score"], 3),
            "relevance_score": round(relevance, 3),
            "metadata_completeness": round(metadata_score, 3),
            "freshness_signal": round(freshness, 3),
            "selection_score": round(score, 3),
            "selection_reasons": reasons,
        })

    duplicate_groups = _duplicate_groups(candidates)
    duplicate_index = {}
    for group_no, group in enumerate(duplicate_groups, 1):
        for idx in group:
            duplicate_index[idx] = group_no

    # Keep the strongest member of a near-identical passage cluster for ranking;
    # retain the other records in the audit output and mark them as duplicates.
    for idx, item in enumerate(candidates):
        group_no = duplicate_index.get(idx)
        if group_no:
            item["duplicate_group"] = f"dup-{group_no}"
            item["independent_corroboration"] = False
            item["selection_reasons"].append("near-duplicate passage; not counted as independent corroboration")
        else:
            item["duplicate_group"] = None
            item["independent_corroboration"] = True

    ranked = sorted(
        candidates,
        key=lambda item: (
            item["selection_score"],
            item["relevance_score"],
            item["authority_score"],
        ),
        reverse=True,
    )
    selected = []
    seen_groups = set()
    for item in ranked:
        group = item.get("duplicate_group")
        if group and group in seen_groups:
            continue
        selected.append(item)
        if group:
            seen_groups.add(group)
        if len(selected) >= max(1, int(top_k)):
            break

    distinct_domains = {item["domain"] for item in selected if item.get("domain")}
    return {
        "claim": claim,
        "selected_sources": selected,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "independent_domain_count": len(distinct_domains),
        "duplicate_groups": [
            {"group_id": f"dup-{i + 1}", "candidate_indices": [idx + 1 for idx in group]}
            for i, group in enumerate(duplicate_groups)
        ],
        "selection_method": "weighted_heuristic_v1",
        "score_disclaimer": "Ranking score is a heuristic, not a probability of truth or a guarantee of source accuracy.",
    }


def build_evidence_context(selection: dict, max_chars: int = 18000) -> str:
    parts = []
    for item in selection.get("selected_sources", []):
        parts.append(f"[{item['source_id']}] {item['title']} ({item.get('url') or 'uploaded document'})\n{item['passage']}")
    return "\n\n".join(parts)[:max_chars]
