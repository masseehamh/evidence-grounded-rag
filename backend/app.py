"""
Lightweight Evidence-Grounded RAG API.

Hosted inference is performed through Cloudflare Workers AI. No local ML models
are downloaded or loaded by this application.
"""
import hmac
import json
import os
import re
import time
import uuid
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from ddgs import DDGS

APP_VERSION = "2.0.0"
DEFAULT_MODEL = "@cf/zai-org/glm-4.7-flash"
MAX_UPLOAD_BYTES = 2_000_000
MAX_EVIDENCE_CHARS = 60_000
MAX_QUESTION_CHARS = 2_000
MAX_CONTEXT_CHARS = 18_000
MAX_COMPLETION_TOKENS = 700
API_DOCUMENTS: dict[str, dict[str, str]] = {}

app = FastAPI(title="Evidence-Grounded RAG API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    mode: str = "manual"
    evidence: Optional[str] = None
    document_id: Optional[str] = None


def cloudflare_configuration() -> tuple[Optional[str], Optional[str]]:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        return None, None
    return account_id, api_token


def cloudflare_chat(messages: list[dict[str, str]], max_tokens: int = MAX_COMPLETION_TOKENS) -> str:
    """Call the documented OpenAI-compatible Workers AI chat-completions endpoint."""
    account_id, api_token = cloudflare_configuration()
    if not account_id or not api_token:
        raise RuntimeError(
            "Cloudflare is not configured. Set CLOUDFLARE_ACCOUNT_ID and "
            "CLOUDFLARE_API_TOKEN in the Render backend environment."
        )

    model = os.getenv("CLOUDFLARE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/v1/chat/completions"
    )
    body = json.dumps({
    "model": model,
    "messages": messages,
    "temperature": 0.1,
    "max_completion_tokens": max_tokens,
    "chat_template_kwargs": {
        "enable_thinking": False
    },
    "stream": False,
}).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=75) as response:
            raw = response.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
    except HTTPError as exc:
        # Do not include request headers or credentials in error messages.
        try:
            raw_error = exc.read().decode("utf-8", errors="replace")
            error_data = json.loads(raw_error)
            errors = error_data.get("errors") or []
            detail = "; ".join(
                str(item.get("message", "Cloudflare API error"))
                for item in errors[:2] if isinstance(item, dict)
            )
            if not detail:
                detail = str(error_data.get("message") or "Cloudflare API error")
        except Exception:
            detail = "Cloudflare returned an unreadable error response."
        if exc.code == 401:
            detail = "Cloudflare rejected the API token (HTTP 401). Check its permissions."
        elif exc.code == 403:
            detail = (
                "Cloudflare denied this model request (HTTP 403). Check model access, "
                "account plan requirements, and Workers AI permissions."
            )
        elif exc.code == 429:
            detail = (
                "Cloudflare rate-limited this request or the daily free Neurons "
                "allowance may be exhausted (HTTP 429). Try later and check the "
                "Workers AI usage dashboard."
            )
        elif exc.code >= 500:
            detail = "Cloudflare's inference service returned a server error. Try again later."
        else:
            detail = f"Cloudflare API request failed (HTTP {exc.code}): {detail[:350]}"
        raise RuntimeError(detail) from None
    except URLError as exc:
        raise RuntimeError(
            "Could not reach Cloudflare Workers AI. Check network access and try again."
        ) from None
    except TimeoutError:
        raise RuntimeError("Cloudflare inference timed out. Try again with shorter evidence.") from None
    except json.JSONDecodeError:
        raise RuntimeError("Cloudflare returned a response that was not valid JSON.") from None

    # The OpenAI-compatible response is choices[0].message.content.
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Cloudflare returned an unexpected chat-completions response format.") from None
    if isinstance(content, list):
        # Some compatible APIs return content parts rather than a plain string.
        content = " ".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Cloudflare returned an empty model response.")
    return content.strip()


def split_into_sentences(text: str) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    text = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", text)
    # Preserve common ranking abbreviation "No. 1"; otherwise the period in
    # "No. 1 singer" is mistaken for a sentence boundary and splits one claim.
    text = re.sub(r"\bNo\.\s+(?=\d)", "No<NO_ABBREVIATION_DOT> ", text, flags=re.I)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [
        part.replace("No<NO_ABBREVIATION_DOT>", "No.").strip()
        for part in parts if part.strip()
    ]


def split_claims(answer: str) -> list[str]:
    """Split generated text into sentence-sized claims, keeping clauses conservative."""
    claims: list[str] = []
    for sentence in split_into_sentences(answer):
        clauses = re.split(r"\s+(?:but|although|however)\s+", sentence, flags=re.I)
        for clause in clauses:
            cleaned = clause.strip(" \t\r\n.;")
            if cleaned:
                claims.append(cleaned + ("" if cleaned.endswith((".", "?", "!")) else "."))
    return claims[:20]


STOP_WORDS = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "many", "much", "does", "did", "was", "were", "are", "the", "and", "for",
    "with", "that", "this", "from", "into", "about", "have", "has", "had",
    "been", "being", "year", "years", "date", "number", "name", "time", "kind",
    "type", "there", "their", "them", "they", "give", "tell", "please", "would",
    "could", "should", "can", "is", "in", "on", "of", "to", "a", "an", "it",
    "its", "as", "by", "at", "or", "not", "be", "do", "did",
}


def content_words(text: str) -> set[str]:
    return {
        token.lower().strip("'-")
        for token in re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")
        if len(token) > 2 and token.lower() not in STOP_WORDS
    }


def retrieval_score(question: str, passage: str) -> float:
    """Small dependency-free lexical retrieval score in the range 0..1."""
    q_words = content_words(question)
    p_words = content_words(passage)
    if not q_words or not p_words:
        return 0.0
    overlap = len(q_words & p_words)
    coverage = overlap / max(len(q_words), 1)
    jaccard = overlap / max(len(q_words | p_words), 1)
    # A matching year, percentage or count is useful for factoid questions.
    q_numbers = set(re.findall(r"\b\d[\d,]*(?:\.\d+)?%?\b", question))
    p_numbers = set(re.findall(r"\b\d[\d,]*(?:\.\d+)?%?\b", passage))
    number_bonus = 0.12 if q_numbers and q_numbers & p_numbers else 0.0
    return min(1.0, 0.75 * coverage + 0.25 * jaccard + number_bonus)


def retrieve_passages(question: str, text: str, top_k: int = 3) -> list[tuple[str, float]]:
    sentences = split_into_sentences(text)
    if not sentences:
        return []
    scored = [(sentence, retrieval_score(question, sentence)) for sentence in sentences]
    scored.sort(key=lambda item: item[1], reverse=True)
    # Keep at least the best sentence if any lexical relationship exists.
    return [item for item in scored[:top_k] if item[1] > 0.0]


def extract_numbers(text: str) -> set[str]:
    return {
        value.replace(",", "").rstrip("%").rstrip(".")
        for value in re.findall(r"\b\d[\d,]*(?:\.\d+)?%?\b", text or "")
    }


def numeric_consistency(claim: str, evidence: str) -> tuple[Optional[bool], str]:
    """Conservative numeric guard; missing numbers are uncertainty, not automatic contradiction."""
    claim_numbers = extract_numbers(claim)
    if not claim_numbers:
        return True, "No numeric values in the claim."
    evidence_numbers = extract_numbers(evidence)
    if not evidence_numbers:
        return None, "Evidence contains no numeric values to compare."
    missing = claim_numbers - evidence_numbers
    if not missing:
        return True, "Claim numeric values appear in the supplied evidence."
    # If evidence contains a numeric value and the claim's numeric values differ,
    # flag for review. The instruction-model verifier must still consider context.
    return False, (
        "Numeric value(s) in the claim are absent from the retrieved evidence: "
        + ", ".join(sorted(missing))
    )


def parse_json_object(text: str) -> dict[str, Any]:
    """Accept strict JSON or JSON surrounded by a Markdown code fence/preamble."""
    text = (text or "").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise ValueError("The model did not return a valid JSON object.")


def generate_answer(question: str, evidence: str) -> str:
    response = cloudflare_chat([
        {
            "role": "system",
            "content": (
                "Answer questions using only the supplied evidence. Do not use outside "
                "knowledge. If the evidence does not answer the question, say that the "
                "evidence is insufficient. Be concise. Do not invent names, dates, "
                "percentages, counts, causes, or conclusions."
            ),
        },
        {
            "role": "user",
            "content": (
                f"QUESTION:\n{question}\n\nEVIDENCE:\n{evidence[:MAX_CONTEXT_CHARS]}\n\n"
                "Give a concise answer grounded only in the evidence."
            ),
        },
    ], max_tokens=350)
    return response.strip()


def verify_claims(question: str, answer: str, evidence: str) -> list[dict[str, Any]]:
    claims = split_claims(answer)
    if not claims:
        return []
    prompt = {
        "question": question,
        "answer_claims": claims,
        "evidence": evidence[:MAX_CONTEXT_CHARS],
        "task": (
            "For each claim, decide whether the evidence directly supports it, "
            "contradicts it, or does not provide enough information. Use only the "
            "provided evidence. Do not treat absence alone as contradiction. "
            "Check names, dates, quantities, percentages, and causal claims. "
            "Return only JSON with shape: "
            '{"claims":[{"claim":"exact claim text","status":"SUPPORTED|CONTRADICTED|NOT_ENOUGH_EVIDENCE",'
            '"evidence":"short exact supporting or conflicting excerpt","reason":"short explanation"}]}'
        ),
    }
    raw = cloudflare_chat([
        {
            "role": "system",
            "content": (
                "You are an evidence verification assistant, not a general knowledge assistant. "
                "Treat the evidence as the only source of truth. Return valid JSON only."
            ),
        },
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ], max_tokens=650)
    parsed = parse_json_object(raw)
    model_claims = parsed.get("claims")
    if not isinstance(model_claims, list):
        raise RuntimeError("The verifier response did not contain a claims list.")

    results: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        match = model_claims[index] if index < len(model_claims) and isinstance(model_claims[index], dict) else {}
        status = str(match.get("status", "NOT_ENOUGH_EVIDENCE")).upper().replace(" ", "_")
        if status not in {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}:
            status = "NOT_ENOUGH_EVIDENCE"
        evidence_excerpt = str(match.get("evidence", "") or "").strip()
        reason = str(match.get("reason", "") or "").strip()
        number_ok, number_reason = numeric_consistency(claim, evidence)
        # Numeric checks can prevent an unsupported number being shown as supported.
        # They do not claim to be a replacement for a trained NLI classifier.
        if number_ok is False and status == "SUPPORTED":
            status = "CONTRADICTED"
            reason = (reason + " " + number_reason).strip()
        elif number_ok is False and status == "NOT_ENOUGH_EVIDENCE":
            # Keep model-declared contradiction if present; otherwise mark uncertainty
            # as contradicted only when the verifier independently says so.
            reason = (reason + " " + number_reason).strip()
        if not evidence_excerpt:
            evidence_excerpt = best_evidence_for_claim(claim, evidence)
        results.append({
            "claim": claim,
            "status": status,
            "evidence": evidence_excerpt,
            "reason": reason or "Instruction-model evidence assessment.",
            "nli_label": "instruction_model_verifier",
            "confidence": None,
            "nli_confidence": None,
            "support_basis": "instruction_model_verifier",
            "consistency": {
                "status": "PASS" if number_ok is True else ("FAIL" if number_ok is False else "NOT_CHECKED"),
                "details": number_reason,
                "numbers_consistent": number_ok,
                "number_reason": number_reason,
                "entities_consistent": None,
                "entity_reason": "Named-entity consistency is assessed by the instruction-model verifier.",
                "support_basis": "instruction_model_verifier",
            },
        })
    return results



def looks_like_claim_check(text: str) -> bool:
    """Recognize explicit claim-check requests and declarative assertions.

    Questions beginning with interrogatives remain answer-generation requests;
    imperative verification prompts and common first-person assertions are checked
    as written instead of being rewritten into a subject-search question.
    """
    value = (text or "").strip()
    low = value.lower()
    explicit = re.match(
        r"^(?:verify|fact[- ]?check|check|assess|evaluate)\s+(?:this\s+)?(?:claim|statement|assertion)\s*[:\-]?\s*",
        low,
    )
    if explicit:
        return True
    if re.match(r"^(?:i am|i'm|i can|i have|i was|i will|i always|i never)\b", low):
        return True
    # Declarative first-person claims should not be transformed into a biography
    # or a general subject question. Ordinary interrogative questions are excluded.
    return False


def extract_user_claims(text: str) -> list[str]:
    """Return the user's own assertion clauses without generating substitute claims."""
    value = re.sub(
        r"^(?:verify|fact[- ]?check|check|assess|evaluate)\s+(?:this\s+)?(?:claim|statement|assertion)\s*[:\-]?\s*",
        "", (text or "").strip(), flags=re.I,
    )
    return split_claims(value)


def verify_user_claims(question: str, evidence: str) -> list[dict[str, Any]]:
    """Verify the exact user-provided assertions, rather than claims from a generated answer."""
    claims = extract_user_claims(question)
    if not claims:
        return []
    prompt = {
        "user_input": question,
        "claims_to_check": claims,
        "evidence": evidence[:MAX_CONTEXT_CHARS],
        "task": (
            "Evaluate ONLY the supplied user claims against the evidence. Preserve each claim's "
            "meaning and subject. Do not rewrite claims into facts about a related person, character, "
            "place, or topic. Topical relevance is not support. A passage about a fictional character "
            "does not establish that the user is that character or shares fictional abilities. "
            "SUPPORTED requires direct evidence for the exact proposition. CONTRADICTED requires "
            "direct conflicting evidence. Otherwise use NOT_ENOUGH_EVIDENCE. Return JSON only: "
            '{"claims":[{"claim":"exact claim text","status":"SUPPORTED|CONTRADICTED|NOT_ENOUGH_EVIDENCE",'
            '"evidence":"exact relevant excerpt or empty string","reason":"concise reason"}]}'
        ),
    }
    raw = cloudflare_chat([
        {"role": "system", "content": (
            "You are a conservative claim verifier. Do not answer the user's question or search for "
            "related facts. Assess the exact propositions supplied. Evidence must directly bear on "
            "the proposition; subject-name overlap is insufficient. Never infer personal identity, "
            "capabilities, health status, or private facts from unrelated web pages. Return valid JSON only."
        )},
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ], max_tokens=650)
    parsed = parse_json_object(raw)
    model_claims = parsed.get("claims")
    if not isinstance(model_claims, list):
        raise RuntimeError("The claim verifier did not return a claims list.")
    results: list[dict[str, Any]] = []
    for i, claim in enumerate(claims):
        item = model_claims[i] if i < len(model_claims) and isinstance(model_claims[i], dict) else {}
        status = str(item.get("status", "NOT_ENOUGH_EVIDENCE")).upper().replace(" ", "_")
        if status not in {"SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"}:
            status = "NOT_ENOUGH_EVIDENCE"
        excerpt = str(item.get("evidence") or "").strip()
        # Do not attach a merely similar passage as if it were evidence.
        if excerpt and excerpt not in evidence:
            excerpt = ""
        reason = str(item.get("reason") or "").strip()
        if status == "SUPPORTED" and not excerpt:
            status = "NOT_ENOUGH_EVIDENCE"
            reason = "No exact evidence passage was returned to substantiate this claim."
        # A generic passage about a named character/person cannot establish the user's
        # first-person identity or abilities. Keep such personal assertions unresolved
        # unless the verifier can cite the exact proposition itself (not merely a related topic).
        first_person_assertion = bool(re.match(
            r"^\\s*(?:verify this claim:\\s*)?(?:i\\s+(?:am|\u2019m|'m|can|could|have|had|will|was|were|do|did)\\b)",
            claim, re.IGNORECASE
        ))
        if first_person_assertion and status == "SUPPORTED" and claim.strip() not in evidence:
            status = "NOT_ENOUGH_EVIDENCE"
            reason = "The evidence does not directly establish this first-person assertion about the user; related-topic evidence is insufficient."
            excerpt = ""
        results.append({
            "claim": claim, "status": status, "evidence": excerpt,
            "reason": reason or "The available evidence does not establish this claim directly.",
            "nli_label": "instruction_model_verifier", "confidence": None,
            "nli_confidence": None, "support_basis": "instruction_model_verifier",
            "consistency": {"status": "NOT_CHECKED", "details": "No independent NLI classifier is configured.",
                            "numbers_consistent": None, "number_reason": "Not independently checked.",
                            "entities_consistent": None, "entity_reason": "Assessed by instruction model only.",
                            "support_basis": "instruction_model_verifier"},
        })
    return results


def best_evidence_for_claim(claim: str, evidence: str) -> str:
    ranked = retrieve_passages(claim, evidence, top_k=1)
    return ranked[0][0] if ranked else ""


def summarize_status(claims: list[dict[str, Any]]) -> str:
    statuses = [item.get("status") for item in claims]
    if not statuses:
        return "NEEDS VERIFICATION"
    if "CONTRADICTED" in statuses:
        return "CONTAINS HALLUCINATION"
    if "NOT_ENOUGH_EVIDENCE" in statuses:
        return "NEEDS VERIFICATION"
    return "FULLY SUPPORTED"


INSUFFICIENT_ANSWER = "The provided evidence does not contain enough information to answer this question."

def correct_answer(question: str, original_answer: str, evidence: str,
                   removed_claims: list[dict[str, Any]]) -> str:
    """Rewrite an answer using evidence when verification finds problems."""
    issues = [
        {
            "claim": item["claim"],
            "status": item["status"],
            "reason": item.get("reason", ""),
        }
        for item in removed_claims
    ]

    return cloudflare_chat([
        {
            "role": "system",
            "content": (
                "You are an evidence-grounded answer correction assistant. "
                "Use only the supplied evidence. Correct contradicted claims, "
                "remove unsupported claims, and preserve claims that the evidence "
                "supports. Never invent replacement facts. If the evidence cannot "
                "answer the question, say that the evidence is insufficient. "
                "Return only the corrected answer, without commentary."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({
                "question": question,
                "original_answer": original_answer,
                "claims_requiring_correction": issues,
                "evidence": evidence[:MAX_CONTEXT_CHARS],
            }, ensure_ascii=False),
        },
    ], max_tokens=350).strip()



def run_rag(
    question: str,
    evidence: str,
    initial_answer_override: Optional[str] = None,
) -> dict[str, Any]:
    # The override is used only by the fixed, token-protected demonstration route.
    # Normal /api/ask requests never accept a caller-supplied initial answer.
    claim_check_mode = initial_answer_override is None and looks_like_claim_check(question)
    if initial_answer_override is not None:
        original_answer = initial_answer_override
        claims = verify_claims(question, original_answer, evidence)
    elif claim_check_mode:
        # Preserve the user's actual assertion as the thing being evaluated.
        original_answer = question
        claims = verify_user_claims(question, evidence)
    else:
        original_answer = generate_answer(question, evidence)
        claims = verify_claims(question, original_answer, evidence)

    if claim_check_mode:
        statuses = {item["status"] for item in claims}
        if statuses == {"SUPPORTED"}:
            corrected_answer = "The supplied evidence directly supports the claim(s) checked."
            corrected_status = "SUPPORTED"
        elif "CONTRADICTED" in statuses:
            corrected_answer = "At least one claim conflicts with the supplied evidence. Review the claim-level findings below."
            corrected_status = "CONTRADICTED"
        else:
            corrected_answer = "The supplied evidence does not establish at least one claim. Treat it as unverified, not as proven false."
            corrected_status = "NOT_ENOUGH_EVIDENCE"
        return {
            "verification_status": summarize_status(claims),
            "original_answer": question,
            "corrected_answer": corrected_answer,
            "corrected_status": corrected_status,
            "corrected_evidence": " ".join(dict.fromkeys(item["evidence"] for item in claims if item.get("evidence"))),
            "claims": claims,
            "removed_claims": [
                {"claim": item["claim"], "status": item["status"], "reason": item.get("reason", ""), "evidence": item.get("evidence", "")}
                for item in claims if item["status"] != "SUPPORTED"
            ],
            "correction_attempted": False,
            "sources": [],
            "verification_mode": "user_claims",
        }

    supported = [
        item for item in claims
        if item["status"] == "SUPPORTED"
    ]
    removed = [
        item for item in claims
        if item["status"] != "SUPPORTED"
    ]

    correction_attempted = bool(removed)

    if not claims:
        corrected_answer = INSUFFICIENT_ANSWER
        corrected_evidence = ""
        corrected_status = "NOT_ENOUGH_EVIDENCE"

    elif not removed:
        # A correct, evidence-supported answer should remain unchanged.
        corrected_answer = original_answer
        corrected_evidence = " ".join(
            dict.fromkeys(
                item["evidence"]
                for item in supported
                if item.get("evidence")
            )
        )
        corrected_status = "SUPPORTED"

    else:
        # Ask the model to correct the answer, then verify it again.
        revised_answer = correct_answer(
            question, original_answer, evidence, removed
        )
        revised_claims = verify_claims(
            question, revised_answer, evidence
        )

        revised_supported = [
            item for item in revised_claims
            if item["status"] == "SUPPORTED"
        ]

        # Never trust the correction without checking its claims.
        if revised_supported:
            corrected_answer = " ".join(
                item["claim"] for item in revised_supported
            )
            corrected_evidence = " ".join(
                dict.fromkeys(
                    item["evidence"]
                    for item in revised_supported
                    if item.get("evidence")
                )
            )
            corrected_status = "SUPPORTED"

        elif supported:
            # Safe fallback: retain only claims supported in the
            # original answer's verification.
            corrected_answer = " ".join(
                item["claim"] for item in supported
            )
            corrected_evidence = " ".join(
                dict.fromkeys(
                    item["evidence"]
                    for item in supported
                    if item.get("evidence")
                )
            )
            corrected_status = "SUPPORTED"

        else:
            corrected_answer = INSUFFICIENT_ANSWER
            corrected_evidence = ""
            corrected_status = "NOT_ENOUGH_EVIDENCE"

    return {
        "verification_status": summarize_status(claims),
        "original_answer": original_answer,
        "corrected_answer": corrected_answer,
        "corrected_status": corrected_status,
        "corrected_evidence": corrected_evidence,
        "claims": claims,
        "removed_claims": [
            {
                "claim": item["claim"],
                "status": item["status"],
                "reason": item.get("reason", ""),
                "evidence": item.get("evidence", ""),
            }
            for item in removed
        ],
        "correction_attempted": correction_attempted,
        "sources": [],
    }

def make_insufficient_response(sources: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    return {
        "verification_status": "NOT ENOUGH EVIDENCE",
        "original_answer": "No answer was generated because sufficient relevant evidence was not retrieved.",
        "corrected_answer": INSUFFICIENT_ANSWER,
        "corrected_status": "NOT_ENOUGH_EVIDENCE",
        "corrected_evidence": "",
        "claims": [],
        "removed_claims": [],
        "sources": sources or [],
        "message": "The provided evidence did not contain enough relevant information.",
    }


def validate_text_file(filename: str, raw: bytes) -> str:
    if not (filename or "").lower().endswith(".txt"):
        raise HTTPException(status_code=415, detail="Only plain-text .txt uploads are supported.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Maximum size is 2 MB.")
    if b"\x00" in raw:
        raise HTTPException(status_code=400, detail="This does not look like a plain-text file.")
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise HTTPException(status_code=400, detail="The uploaded text file is empty.")
    return text


def build_document_chunks(text: str, max_words: int = 90) -> list[str]:
    chunks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        words = paragraph.split()
        for start in range(0, len(words), max_words):
            piece = " ".join(words[start:start + max_words]).strip()
            if piece:
                chunks.append(piece)
    return chunks


def retrieve_document_context(question: str, document_text: str, top_k: int = 3) -> list[tuple[str, float]]:
    chunks = build_document_chunks(document_text)
    ranked = [(chunk, retrieval_score(question, chunk)) for chunk in chunks]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [item for item in ranked[:top_k] if item[1] > 0.0]



def search_web_evidence(question: str, max_results: int = 5) -> list[dict[str, str]]:
    """Retrieve short web passages for evidence-grounded answering."""
    try:
        results = DDGS().text(question, max_results=max_results)
    except Exception:
        raise RuntimeError("Web search is temporarily unavailable. Please try again later.") from None

    sources: list[dict[str, str]] = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Web result").strip()
        url = str(item.get("href") or item.get("url") or "").strip()
        passage = str(item.get("body") or item.get("snippet") or "").strip()
        if passage:
            sources.append({"title": title, "url": url, "passage": passage})
    return sources


@app.get("/health")
@app.get("/api/health")
def api_health() -> dict[str, Any]:
    account_id, token = cloudflare_configuration()
    return {
        "status": "ok",
        "service": "evidence-grounded-rag-api",
        "version": APP_VERSION,
        "cloudflare_configured": bool(account_id and token),
        "model": os.getenv("CLOUDFLARE_MODEL", DEFAULT_MODEL),
    }


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> dict[str, str]:
    filename = file.filename or "upload.txt"
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    text = validate_text_file(filename, raw)
    document_id = str(uuid.uuid4())
    API_DOCUMENTS[document_id] = {"filename": filename, "text": text}
    return {
        "document_id": document_id,
        "filename": filename,
        "message": "Text document ready.",
    }


@app.post("/api/ask")
def api_ask(payload: AskRequest) -> dict[str, Any]:
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    mode = (payload.mode or "manual").lower().strip()
    sources: list[dict[str, str]] = []

    if mode == "manual":
        evidence = (payload.evidence or "").strip()
        if not evidence:
            raise HTTPException(status_code=400, detail="Please provide evidence text.")
        if len(evidence) > MAX_EVIDENCE_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Evidence is too long. Maximum is {MAX_EVIDENCE_CHARS} characters.",
            )
    elif mode == "document":
        if not payload.document_id or payload.document_id not in API_DOCUMENTS:
            raise HTTPException(
                status_code=400,
                detail="Upload the .txt document again; its temporary ID may have expired.",
            )
        document = API_DOCUMENTS[payload.document_id]
        passages = retrieve_document_context(question, document["text"])
        if not passages or passages[0][1] < 0.08:
            return make_insufficient_response()
        evidence = "\n".join(item[0] for item in passages)
        sources = [
            {"title": document["filename"], "url": "", "passage": passage}
            for passage, _score in passages
        ]
    elif mode == "web":
        sources = search_web_evidence(question)
        evidence = "\n".join(
            f"{source['title']}: {source['passage']}" for source in sources
        )
        if not evidence.strip():
            return make_insufficient_response(sources)
        evidence = evidence[:MAX_EVIDENCE_CHARS]
    else:
        raise HTTPException(status_code=400, detail="Unknown mode. Use manual, document, or web.")

    try:
        result = run_rag(question, evidence)
        result["sources"] = sources
        return result
    except RuntimeError as exc:
        # Keep actionable API messages, without leaking secrets or request headers.
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not interpret the model response safely: {exc}",
        ) from None


# Fixed, allowlisted scenarios for demonstrating the correction pipeline.
# Each seeded initial answer is deliberately flawed; every scenario still uses the
# normal verification, correction, and re-verification pipeline.
DEMO_SCENARIOS: dict[str, dict[str, str]] = {
    "eiffel_tower": {
        "title": "Contradicted fact",
        "description": "The initial answer puts the Eiffel Tower in London instead of Paris.",
        "question": "Where is the Eiffel Tower, and when was it completed?",
        "evidence": "The Eiffel Tower is in Paris, France. It was completed in 1889.",
        "initial_answer": "The Eiffel Tower is in London and was completed in 1889.",
        "expected_behavior": "Correct the contradicted location while retaining the supported completion year.",
    },
    "wrong_count": {
        "title": "Incorrect number",
        "description": "The initial answer gives the library the wrong number of floors.",
        "question": "How many floors does the library have, and when did it open?",
        "evidence": "The library opened in 2012. It has three floors.",
        "initial_answer": "The library opened in 2012. It has five floors.",
        "expected_behavior": "Keep the supported opening year and correct the unsupported floor count.",
    },
    "unsupported_cause": {
        "title": "Unsupported explanation",
        "description": "The initial answer adds a cause that the report does not establish.",
        "question": "How did test scores change, and what caused the change?",
        "evidence": "After the training program, average test scores rose from 68 to 81.",
        "initial_answer": "After training, average test scores rose from 68 to 81 because the program increased motivation.",
        "expected_behavior": "Retain the reported score change but remove the unproven causal explanation.",
    },
    "insufficient_evidence": {
        "title": "Insufficient evidence",
        "description": "The initial answer invents a construction cost that is absent from the evidence.",
        "question": "How much did the community center cost to build?",
        "evidence": "The community center opened in 2021 and hosts weekly workshops.",
        "initial_answer": "The community center cost $2 million to build.",
        "expected_behavior": "Withhold the invented cost and state that the evidence is insufficient.",
    },
    "mixed_claims": {
        "title": "Mixed claim statuses",
        "description": "The initial answer mixes one supported fact, one wrong number, and one unverified detail.",
        "question": "When did the library open, how many floors does it have, and how many visitors does it serve daily?",
        "evidence": "The library opened in 2012. It has three floors.",
        "initial_answer": "The library opened in 2012. It has five floors. It serves 800 visitors daily.",
        "expected_behavior": "Preserve supported information, correct the contradicted count, and remove the unverified visitor figure.",
    },
}

# Backwards-compatible aliases used by existing regression tests.
DEMO_QUESTION = DEMO_SCENARIOS["eiffel_tower"]["question"]
DEMO_EVIDENCE = DEMO_SCENARIOS["eiffel_tower"]["evidence"]
DEMO_INITIAL_ANSWER = DEMO_SCENARIOS["eiffel_tower"]["initial_answer"]
DEMO_NOTICE = (
    "Controlled demonstration: the initial answer is deliberately seeded as incorrect. "
    "The backend then runs its normal verification, correction, and re-verification steps."
)


@app.post("/api/demo/correction")
def api_demo_correction(
    x_demo_token: str = Header(default="", alias="X-Demo-Token"),
    scenario_id: str = "eiffel_tower",
) -> dict[str, Any]:
    configured_token = os.getenv("DEMO_ACCESS_TOKEN", "").strip()
    # Return the same not-found response when disabled and when the token is wrong,
    # so the endpoint does not reveal whether demo mode has been configured.
    if not configured_token or not hmac.compare_digest(x_demo_token, configured_token):
        raise HTTPException(status_code=404, detail="Demo endpoint is unavailable.")

    scenario = DEMO_SCENARIOS.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown demonstration scenario.")

    try:
        result = run_rag(
            scenario["question"],
            scenario["evidence"],
            initial_answer_override=scenario["initial_answer"],
        )
        result["demo_mode"] = True
        result["demo_scenario"] = {
            "id": scenario_id,
            "title": scenario["title"],
            "description": scenario["description"],
            "expected_behavior": scenario["expected_behavior"],
        }
        result["demo_notice"] = DEMO_NOTICE
        result["sources"] = []
        return result
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not interpret the model response safely: {exc}",
        ) from None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
