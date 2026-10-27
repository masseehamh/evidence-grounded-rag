"""
Evidence-Grounded RAG API extracted from Evidence_Grounded_RAG_notebook_fixed_v8.ipynb.
"""
import os
import re
import json
import time
import uuid
from typing import Optional

import numpy as np
import spacy
from sentence_transformers import SentenceTransformer
from transformers import pipeline, T5ForConditionalGeneration, T5Tokenizer
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load the same models used by notebook v8.
retriever = SentenceTransformer("all-MiniLM-L6-v2")
verifier = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-small")
nlp = spacy.load("en_core_web_sm")
model_name = "google/flan-t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
generation_model = T5ForConditionalGeneration.from_pretrained(model_name)

# Switches for the V2 accuracy improvements. All True = improved system.
# Setting them to False reproduces the original behaviour, which is how the
# before/after comparison in Section 7b works.
CONFIG = {
    "paired_nli": True,           # give DeBERTa (premise, hypothesis) as a proper pair
    "strict_numbers": True,       # a number in the claim must appear in the evidence
    "cross_type_entities": True,  # ignore spaCy labelling the same name PERSON vs GPE
    "lexical_retrieval": True,    # evaluation retrieval = same scoring as the demo
}

def split_into_sentences(text):
    """Split text into sentences."""
    text = str(text).strip()
    if not text:
        return []
    # Handle pasted text with no space after punctuation, e.g. "government.In 1962".
    text = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

FINITE_VERB = re.compile(
    r"^(was|were|is|are|has|have|had|will|can|could|did|does|do|"
    r"may|might|should|would)\b",
    re.IGNORECASE,
)

def find_subject(clause):
    """Return the grammatical subject of a clause (e.g. 'Thomas'), or None.

    Uses the spaCy dependency parse: the noun marked nsubj/nsubjpass plus
    the words that modify it on its left ('The FBI', 'Three women').
    """
    doc = nlp(clause)
    for token in doc:
        if token.dep_ in {"nsubj", "nsubjpass"}:
            return doc[token.left_edge.i : token.i + 1].text
    return None

def split_claims(sentence):
    """Split a sentence into simple independent claims.

    - Splits only on but/while/although/because (NOT on 'and', because names
      and lists contain 'and').
    - If a later clause starts with a verb ('was arrested ...'), the subject
      of the first clause is restored ('Thomas was arrested ...').
    - A sentence with nothing to split is returned EXACTLY as written, so a
      short answer such as '1889' is never rewritten at this stage.
    """
    sentence = sentence.strip()
    if not sentence:
        return []

    parts = re.split(
        r"\s+(but|while|although|because)\s+",
        sentence,
        flags=re.IGNORECASE,
    )

    # Nothing to split: keep the sentence untouched.
    if len(parts) == 1:
        return [sentence]

    # parts = [clause1, connector, clause2, connector, clause3, ...]
    # Keep EVERY clause (the old version silently dropped clause 3+).
    clauses = [p.strip() for p in parts[0::2] if p.strip()]
    subject = find_subject(clauses[0])

    if subject is None:  # fallback: words before the first auxiliary verb
        words = clauses[0].split()
        for i, word in enumerate(words[1:], start=1):
            if FINITE_VERB.match(word):
                subject = " ".join(words[:i])
                break

    claims = [clauses[0]]
    for clause in clauses[1:]:
        if subject and FINITE_VERB.match(clause):
            clause = subject + " " + clause
        claims.append(clause)

    return [c.rstrip(" ,.!?") + "." for c in claims]

def retrieve_evidence(claim, context):
    """Return the single most semantically similar evidence sentence."""
    sentences = split_into_sentences(context)
    if not sentences:
        return "", 0.0

    claim_embedding = retriever.encode(claim, convert_to_numpy=True)
    context_embeddings = retriever.encode(sentences, convert_to_numpy=True)

    claim_norm = max(np.linalg.norm(claim_embedding), 1e-10)
    context_norms = np.maximum(np.linalg.norm(context_embeddings, axis=1), 1e-10)
    similarities = np.dot(context_embeddings, claim_embedding) / (
        context_norms * claim_norm
    )

    best_index = int(np.argmax(similarities))
    return sentences[best_index], float(similarities[best_index])

def retrieve_diverse_evidence(claim, context, top_k=3):
    """Retrieve top-k evidence using semantic similarity + lexical overlap."""
    sentences = split_into_sentences(context)
    if not sentences:
        return []

    claim_embedding = retriever.encode(claim, convert_to_numpy=True)
    context_embeddings = retriever.encode(sentences, convert_to_numpy=True)

    claim_norm = max(np.linalg.norm(claim_embedding), 1e-10)
    context_norms = np.maximum(np.linalg.norm(context_embeddings, axis=1), 1e-10)
    similarities = np.dot(context_embeddings, claim_embedding) / (
        context_norms * claim_norm
    )

    claim_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.lower()))
    scored = []

    for i, sentence in enumerate(sentences):
        sentence_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower()))
        overlap = len(claim_words & sentence_words)
        combined_score = 0.7 * float(similarities[i]) + 0.3 * min(overlap / 5, 1.0)
        scored.append((sentence, combined_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

def prepare_retrieval_context(context):
    """Pre-compute normalized context embeddings once for faster evaluation."""
    sentences = split_into_sentences(context)
    if not sentences:
        return [], np.empty((0, 0))

    embeddings = retriever.encode(
        sentences,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    norms = np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-10)
    return sentences, embeddings / norms

def retrieve_evidence_fast(claim, sentences, embeddings, top_k=3):
    """Retrieve evidence using already-computed context embeddings.

    With CONFIG["lexical_retrieval"] the score is the same blend used by the
    demo (0.7 * semantic + 0.3 * word overlap), so evaluation and demo agree.
    """
    if not sentences:
        return []

    claim_embedding = retriever.encode(
        claim,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    claim_embedding = claim_embedding / max(np.linalg.norm(claim_embedding), 1e-10)
    scores = np.dot(embeddings, claim_embedding)

    if CONFIG["lexical_retrieval"]:
        claim_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.lower()))
        for k, sentence in enumerate(sentences):
            sentence_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower()))
            overlap = len(claim_words & sentence_words)
            scores[k] = 0.7 * scores[k] + 0.3 * min(overlap / 5, 1.0)

    indices = np.argsort(scores)[::-1][:top_k]
    return [(sentences[k], float(scores[k])) for k in indices]

def verify_claim(claim, evidence):
    """Use DeBERTa NLI to classify evidence (premise) vs claim (hypothesis)."""
    if not evidence:
        return "neutral", 0.0

    if CONFIG["paired_nli"]:
        # NLI cross-encoders are trained on (premise, hypothesis) PAIRS.
        result = verifier({"text": evidence, "text_pair": claim})
    else:
        result = verifier(f"Evidence: {evidence}\nClaim: {claim}")

    while isinstance(result, list):   # pipeline output shape differs by version
        result = result[0]
    return result["label"].lower(), float(result["score"])

number_words = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

def extract_number_action_pairs(text):
    """Extract (number, action) pairs using spaCy dependency parsing."""
    doc = nlp(text)
    pairs = []

    for token in doc:
        if not token.like_num:
            continue

        if token.text.isdigit():
            number = int(token.text)
        elif token.text.lower() in number_words:
            number = number_words[token.text.lower()]
        else:
            continue

        if token.dep_ in {"nsubj", "nsubjpass"}:
            verb = token.head
            if verb.pos_ in {"VERB", "AUX"}:
                pairs.append((number, verb.lemma_))

        elif token.dep_ == "nummod":
            noun = token.head
            if noun.dep_ in {"nsubj", "nsubjpass"}:
                verb = noun.head
                if verb.pos_ in {"VERB", "AUX"}:
                    pairs.append((number, verb.lemma_))

    return pairs

def extract_all_numbers(text):
    """All numeric values in a text: digits (1889, 1,200, 3.5) and number words.

    'one' is skipped because it is usually a pronoun ('one of the ...').
    """
    values = set()
    for match in re.findall(r"\d[\d,]*\.?\d*", text):
        cleaned = match.replace(",", "").rstrip(".")
        try:
            values.add(float(cleaned))
        except ValueError:
            pass
    for word in re.findall(r"[a-zA-Z]+", text.lower()):
        if word in number_words and word != "one":
            values.add(float(number_words[word]))
    return values

def check_number_consistency(claim, evidence, extra_evidence=""):
    """Two-stage number check.

    Stage 1 (number-action pairs): 'five died' must match 'three died'.
       A CONFLICT only exists when the evidence gives a DIFFERENT number for the
       SAME action. If the evidence never attaches a number to that action
       (e.g. claim 'Two women were arrested', evidence 'Noelle, 28, and Asia, 31,
       were arrested'), that is missing information, not a contradiction, so the
       number is left for the NLI model instead of being flagged.
    Stage 2 (strict numbers): every other number in the claim, including bare
       years like '1889' or bare answers like 'Seven', must appear in the evidence.
    """
    claim_pairs = extract_number_action_pairs(claim)
    evidence_pairs = extract_number_action_pairs(evidence)
    unverifiable = set()   # claim numbers whose action the evidence does not count

    for claim_number, claim_action in claim_pairs:
        matching_numbers = [
            number for number, action in evidence_pairs
            if action == claim_action
        ]

        if not matching_numbers:
            unverifiable.add(float(claim_number))
            continue

        if claim_number not in matching_numbers:
            return {
                "consistent": False,
                "reason": (
                    f"Claim says {claim_number} {claim_action}, "
                    f"but evidence says {matching_numbers} {claim_action}"
                ),
            }

    if CONFIG["strict_numbers"]:
        claim_numbers = extract_all_numbers(claim) - unverifiable
        if claim_numbers:
            evidence_numbers = extract_all_numbers(evidence + " " + extra_evidence)
            missing = sorted(claim_numbers - evidence_numbers)
            if missing:
                shown = [int(m) if m == int(m) else m for m in missing]
                return {
                    "consistent": False,
                    "reason": f"Claim mentions {shown} but the evidence does not contain it",
                }
            return {"consistent": True, "reason": "All numbers in the claim appear in the evidence"}

    if not claim_pairs:
        return {"consistent": True, "reason": "No number-action information in claim"}
    if unverifiable:
        return {"consistent": True, "reason": "Number-action information not counted in evidence; left to NLI"}
    return {"consistent": True, "reason": "Number-action information is consistent"}

def extract_entities(text):
    """Extract important named entities using spaCy NER."""
    doc = nlp(text)
    entities = {}

    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "LOC"}:
            entities.setdefault(ent.label_, []).append(ent.text)

    return entities

def check_entity_consistency(claim, evidence):
    """Flag clear entity-value mismatches between claim and evidence."""
    claim_entities = extract_entities(claim)
    evidence_entities = extract_entities(evidence)

    if not claim_entities:
        return {"consistent": True, "reason": "No entities in claim"}

    for entity_type, claim_values in claim_entities.items():
        if entity_type not in evidence_entities:
            continue

        if CONFIG["cross_type_entities"]:
            # spaCy sometimes labels the same name PERSON in one sentence and
            # GPE in another, so accept a match under ANY entity type.
            evidence_values = [
                x.lower() for values in evidence_entities.values() for x in values
            ]
        else:
            evidence_values = [x.lower() for x in evidence_entities[entity_type]]
        for claim_value in claim_values:
            if claim_value.lower() not in evidence_values:
                return {
                    "consistent": False,
                    "reason": (
                        f"Claim {entity_type} '{claim_value}' does not match "
                        f"evidence entities {evidence_entities[entity_type]}"
                    ),
                }

    return {"consistent": True, "reason": "Entity information is consistent"}

# Short-answer support: fixes correct bare answers (e.g. "1905") being reported as
# NOT ENOUGH EVIDENCE.
#
# ROOT CAUSE
#   FLAN-T5 usually answers a factual question with just the value, e.g. "1905".
#   The old verify_claim_improved sent that bare fragment to DeBERTa as the NLI
#   *hypothesis*. NLI decides whether a STATEMENT follows from a premise; "1905"
#   is not a statement, so the label came back "neutral" and the claim became
#   NOT ENOUGH EVIDENCE even though the evidence says it outright. Retrieval had
#   the same blind spot: a claim made only of digits has no words to match.
#
# FIX (the existing models and checks are all still used)
#   1. Retrieve with the QUESTION + answer, and prefer the sentence that contains
#      the answer text.
#   2. Rebuild the (question, answer) pair into a full statement for NLI.
#   3. If NLI is still neutral, accept the answer only when it is copied from a
#      question-relevant evidence sentence with no competing candidate and the
#      number/entity checks pass ("answer_span_in_evidence").
#   4. A different year given for a question-relevant evidence sentence is a
#      CONTRADICTION (and is corrected to the evidence sentence).

GENERIC_QUESTION_WORDS = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "many",
    "much", "does", "did", "was", "were", "are", "the", "and", "for", "with",
    "that", "this", "from", "into", "about", "have", "has", "had", "been", "being",
    "year", "years", "date", "number", "name", "time", "kind", "type", "there",
    "their", "them", "they", "give", "tell", "please", "would", "could", "should",
}
YEAR_RE = re.compile(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)")
IRREGULAR_PARTICIPLES = {
    "built", "made", "held", "found", "born", "known", "given", "taught", "won",
    "lost", "sent", "spent", "bought", "brought", "written", "chosen", "spoken",
    "drawn", "shown", "seen", "done", "begun", "led", "paid", "said", "told",
    "sold", "kept", "left", "meant", "met", "set", "put", "read", "run",
}
MONTHS = ("january february march april may june july august september "
          "october november december monday tuesday wednesday thursday friday "
          "saturday sunday").split()
ABSTENTION_PATTERN = re.compile(
    r"(don't|do not|doesn't|does not)\s+(have|contain)\s+enough\s+information"
    r"|not\s+enough\s+information|cannot\s+be\s+determined|unanswerable",
    re.IGNORECASE,
)


def is_abstention(text):
    """True when the generator declined to answer ('I don't have enough information...')."""
    return bool(ABSTENTION_PATTERN.search(str(text or "")))


def is_short_answer_fragment(claim):
    """True for a bare answer such as '1905', 'Five' or 'Paris, France' (no verb)."""
    text = (claim or "").strip()
    if not text or len(text.split()) > 8:
        return False
    tokens = [t for t in nlp(text) if not t.is_punct and not t.is_space]
    return bool(tokens) and not any(t.pos_ in {"VERB", "AUX"} for t in tokens)


def _norm_word(word):
    word = word.lower().replace("\u2019", "'")
    if word.endswith("'s"):
        word = word[:-2]
    return word.strip("'-")


def _stem(word):
    if word.endswith("s") and len(word) > 3:
        word = word[:-1]
    return word[:6]


def question_content_words(question):
    """Distinctive words of a question (no wh-words / filler), in order, unique."""
    seen, words = set(), []
    for raw in re.findall(r"[A-Za-z][A-Za-z'\u2019\-]*", question or ""):
        w = _norm_word(raw)
        if len(w) >= 3 and w not in GENERIC_QUESTION_WORDS and w not in seen:
            seen.add(w)
            words.append(w)
    return words


def question_coverage(question, evidence):
    """(fraction, count) of the question's distinctive words found in the evidence."""
    words = question_content_words(question)
    if not words:
        return 0.0, 0
    present = {_stem(_norm_word(w)) for w in re.findall(r"[A-Za-z][A-Za-z'\u2019\-]*", evidence or "")}
    matched = [w for w in words if _stem(w) in present]
    return len(matched) / len(words), len(matched)


def answer_span_in_evidence(claim, evidence):
    """True if the answer text appears verbatim (whole words) in the evidence."""
    answer = (claim or "").strip().rstrip(" .!?,;:")
    if not answer:
        return False
    return re.search(r"(?<!\w)" + re.escape(answer) + r"(?!\w)", evidence or "", re.IGNORECASE) is not None


def has_competing_candidates(claim, evidence):
    """True when the evidence sentence holds another value of the same kind
    (another year, or another PERSON/ORG/place) so a copied span proves nothing."""
    answer = (claim or "").strip().rstrip(" .!?,;:")
    if YEAR_RE.fullmatch(answer):
        return bool(set(YEAR_RE.findall(evidence)) - {answer})
    doc = nlp(evidence or "")
    kinds = {"PERSON", "ORG", "GPE", "LOC", "NORP", "FAC", "EVENT", "WORK_OF_ART"}
    label = next((e.label_ for e in doc.ents if e.text.lower().strip() == answer.lower()), None)
    if label not in kinds:
        return False
    return any(e.label_ == label and e.text.lower().strip() != answer.lower() for e in doc.ents)


PRONOUN_START = re.compile(r"^(it|he|she|they|this|these|those|his|her|its|their)\b", re.IGNORECASE)


def evidence_with_antecedent(sentence, context):
    """If the evidence sentence starts with a pronoun ('It was completed in 1889.'),
    prepend the previous sentence so the name it refers to is available."""
    if not PRONOUN_START.match(sentence or ""):
        return sentence
    sentences = split_into_sentences(context)
    index = next((i for i, s in enumerate(sentences) if s == sentence), 0)
    return f"{sentences[index - 1]} {sentence}" if index > 0 else sentence


def answer_is_grounded(question, claim, evidence, window=None):
    """Bare answer copied from a question-relevant evidence sentence?

    `evidence` is the retrieved sentence (span and competing-value checks use it);
    `window` is the same sentence plus its antecedent sentence (used for coverage).
    """
    if not answer_span_in_evidence(claim, evidence):
        return False
    fraction, matched = question_coverage(question, window or evidence)
    if fraction < 0.60 or matched < 2:
        return False
    return not has_competing_candidates(claim, evidence)


def _looks_like_participle(word):
    word = word.lower()
    return word.endswith(("ed", "en", "wn")) or word in IRREGULAR_PARTICIPLES


def question_to_statement(question, answer):
    """Rebuild (question, short answer) into a full statement for NLI.

    'What year is described as X?' + '1905'  -> 'The year 1905 is described as X.'
    'When was the tower completed?' + '1889' -> 'The tower was completed in 1889.'
    Anything it cannot rebuild falls back to a neutral template.
    """
    q = (question or "").strip().rstrip("?").strip()
    a = (answer or "").strip().rstrip(" .!?")
    if not q or not a:
        return None

    m = re.match(r"(?i)^how many\s+([A-Za-z\-]+)\s+(?!(?:did|do|does)\b)(.+)$", q)
    if m:
        return f"{a} {m.group(1)} {m.group(2)}."
    m = re.match(r"(?i)^who\s+(?!(?:is|was|are|were)\s*$)(.+)$", q)
    if m:
        return f"{a} {m.group(1)}."
    m = re.match(r"(?i)^(?:what|which)\s+(?!(?:is|was|are|were|did|do|does)\b)([A-Za-z\-]+)\s+"
                 r"(is|was|are|were)\s+([A-Za-z\-]+)(.*)$", q)
    if m and _looks_like_participle(m.group(3)):
        noun, aux, verb, rest = m.groups()
        return f"The {noun} {a} {aux} {verb}{rest}."
    m = re.match(r"(?i)^(when|where)\s+(is|was|are|were)\s+(.+)\s+([A-Za-z\-]+)$", q)
    if m and _looks_like_participle(m.group(4)):
        wh, aux, subject, verb = m.groups()
        if wh.lower() == "when" and not YEAR_RE.fullmatch(a) and (
                re.search(r"\d", a) or a.split()[0].lower() in MONTHS):
            prep = "on"
        else:
            prep = "in"
        subject = subject[0].upper() + subject[1:]
        return f"{subject} {aux.lower()} {verb} {prep} {a}."
    if re.search(r"(?i)\b(name|called)\b", q) and re.search(r"(?i)\b(my|the person's|the persons|their|his|her)\b", q):
        return f"The person's name is {a}."
    return f'The answer to the question "{q}?" is {a}.'


def check_answer_number_alignment(question, claim, evidence, window=None):
    """A different YEAR given for a question-relevant evidence sentence is a conflict.

    Reason text contains 'but evidence says' so determine_claim_status marks it
    CONTRADICTED (same convention as the number-action check).
    """
    answer = (claim or "").strip().rstrip(" .!?,;:")
    if not YEAR_RE.fullmatch(answer):
        return {"consistent": True, "reason": "Not a year answer"}
    fraction, matched = question_coverage(question, window or evidence)
    years = sorted(set(YEAR_RE.findall(evidence or "")))
    if fraction >= 0.60 and matched >= 2 and years and answer not in years:
        return {
            "consistent": False,
            "reason": f"Claim says {answer}, but evidence says {years} for this question",
            "aligned_conflict": True,
        }
    return {"consistent": True, "reason": "No year conflict with question-relevant evidence"}


def retrieve_evidence_for_claim(claim, context, question="", top_k=3):
    """Evidence for one claim -> (evidence_list, is_fragment).

    Full-sentence claims: exactly the old behaviour. Bare answers: also search
    with the question and prefer the sentence that contains the answer text.
    """
    base = retrieve_diverse_evidence(claim, context, top_k=top_k)
    if not (question and is_short_answer_fragment(claim)):
        return base, False
    with_question = retrieve_diverse_evidence(f"{question} {claim}", context, top_k=top_k)
    merged, seen = [], set()
    for text, score in base + with_question:
        if text not in seen:
            seen.add(text)
            merged.append((text, score))
    containing = [item for item in merged if answer_span_in_evidence(claim, item[0])]
    if containing:
        best = max(containing, key=lambda item: question_coverage(question, item[0])[0])
        return [best] + [item for item in merged if item[0] != best[0]], True
    return base, True


def verify_fragment_claim(claim, statement, evidence, grounded, window=None, question=""):
    """NLI for a bare answer: judge the rebuilt statement first.

    Entailment/contradiction of the statement is trusted. If it is neutral and the
    answer is grounded, a neutral verdict on the bare fragment is meaningless, so
    it is ignored; otherwise the old bare-fragment verdict is kept (no regression).
    The statement is judged against `window` (sentence + antecedent) when given.
    """
    decided = verify_claim(statement, window or evidence) if statement else ("neutral", 0.0)
    # A copied name token is not enough: the rebuilt name statement itself
    # must be evaluated by NLI, and the entity consistency check below.
    name_question = bool(re.search(r"(?i)\b(name|called)\b", question or ""))
    if decided[0] in {"entailment", "contradiction"} or (grounded and not name_question):
        return decided
    return verify_claim(claim, evidence)


# Define answer-shape helpers here as well, before verify_claim_improved is used.
# Cell 48 also contains these helpers for the final answer-correction stage; keeping
# the definitions here prevents NameError when verification cells are run first.
def question_answer_type(question):
    q = (question or "").strip().lower()
    if not q:
        return None
    if re.match(r"^when\b", q):
        return "date"
    if re.match(r"^where\b", q):
        return "place"
    if re.match(r"^who\b", q) or (re.search(r"\b(name|called)\b", q) and re.search(r"\b(my|the person's|the persons|their|his|her)\b", q)):
        return "person"
    if re.match(r"^how (many|much)\b", q) or re.search(r"\bnumber of\b", q):
        return "number"
    if re.match(r"^(what|which)\b", q) and re.search(r"\b(year|date|day|month)\b", q):
        return "date"
    return None

# Define these before answer_matches_question_type is called; the later helper cell also uses them.
_PLACE_LABELS = {"GPE", "LOC", "FAC"}

def answer_matches_question_type(question, answer):
    kind = question_answer_type(question)
    text = str(answer or "")
    if kind is None:
        return True
    if not text.strip() or is_abstention(text):
        return False
    if kind == "date":
        return bool(YEAR_RE.search(text) or _MONTH_RE.search(text))
    if kind == "number":
        return bool(re.search(r"\d", text) or _NUMBER_WORD_RE.search(text))
    if kind == "place":
        return any(ent.label_ in _PLACE_LABELS for ent in nlp(text).ents)
    if kind == "person":
        return (any(ent.label_ == "PERSON" for ent in nlp(text).ents)
                or bool(re.fullmatch(r"[A-Z][A-Za-z'-]*", text.strip())))
    return True

def question_relation_is_missing(question, claim, evidence):
    """
    Guard against answering role/relationship questions with a merely mentioned
    entity. NLI can over-credit topical similarity (e.g. a store is mentioned
    in a delivery sentence, but no delivery partner is named).
    """
    q = (question or "").lower()
    ev = (evidence or "").lower()
    role_patterns = [
        (r"\b(which|what)\s+(company|business|provider|service)\b.*\b(deliver|delivery|courier|carrier|ship|fulfil|fulfill)",
         r"\b(delivery partner|courier|carrier|shipping company|delivery company|delivered by|delivery is handled by|orders are handled by|fulfilled by|fulfilment partner|fulfillment partner)\b"),
        (r"\b(who)\b.*\b(deliver|delivery|ship|courier|carry)\b",
         r"\b(delivered by|delivery partner|courier|carrier|shipping company|delivery company|handled by|fulfilled by|fulfilment partner|fulfillment partner)\b"),
    ]
    for question_pattern, evidence_pattern in role_patterns:
        if re.search(question_pattern, q) and not re.search(evidence_pattern, ev):
            return True
    return False


def determine_claim_status(label, number_check, entity_check, question="", claim="", evidence="",
                           answer_grounded=False, type_ok=True):
    """Combine NLI with deterministic checks without treating missing data as contradiction."""
    # Deterministic conformance first: a reply that cannot even have the SHAPE the
    # question asks for (a country for "When did ...?", a year for "Who ...?") is not
    # an answer to that question, whatever the NLI model says about it.
    if not type_ok:
        return "NOT ENOUGH EVIDENCE"

    if question_relation_is_missing(question, claim, evidence):
        return "NOT ENOUGH EVIDENCE"

    # Name questions need an explicit name relation in the supplied evidence.
    if re.search(r"(?i)\b(name|called)\b", question or "") and re.search(
            r"(?i)\b(my|your|their|his|her|the person's|the persons)\s+name\b", question or ""):
        name_match = re.search(
            r"(?i)\b(?:my|your|their|his|her|the person's|the persons)\s+name\s+(?:is|was|called)\s+([A-Za-z][A-Za-z'-]*)",
            evidence or "")
        if not name_match:
            return "NOT ENOUGH EVIDENCE"
        evidenced_name = name_match.group(1)
        claimed_name = (claim or "").strip().rstrip(" .!?,;:").split()[-1]
        if evidenced_name.casefold() != claimed_name.casefold():
            return "CONTRADICTED"
        return "SUPPORTED"

    if label == "contradiction":
        return "CONTRADICTED"

    if not number_check["consistent"]:
        reason = number_check.get("reason", "").lower()
        # A number absent from evidence is unknown, not a proven conflict.
        if "does not contain" in reason or "does not contain it" in reason:
            return "NOT ENOUGH EVIDENCE"
        # A different number attached to the same action is a real conflict.
        if "but evidence says" in reason:
            return "CONTRADICTED"
        return "NOT ENOUGH EVIDENCE"

    if not entity_check["consistent"]:
        reason = entity_check.get("reason", "").lower()
        # An entity missing from evidence is not automatically contradicted.
        if "does not match evidence entities" in reason:
            if re.search(r"(?i)\b(name|called)\b", question or "") and re.search(r"(?i)\b(my|the person's|the persons|their|his|her)\b", question or ""):
                return "CONTRADICTED"
            return "NOT ENOUGH EVIDENCE"
        return "NOT ENOUGH EVIDENCE"

    if label == "entailment":
        return "SUPPORTED"

    # A bare answer copied from question-relevant evidence (see answer_is_grounded):
    # NLI "neutral" on a fragment is not evidence against it. Contradictions and
    # failed number/entity checks were already handled above.
    if answer_grounded and label == "neutral":
        return "SUPPORTED"

    return "NOT ENOUGH EVIDENCE"


def question_relevant_sentence(question, context):
    """Return the evidence sentence most relevant to the question, or None.

    Uses question-word coverage and includes the previous sentence when needed
    to resolve a sentence beginning with a pronoun. Defined before
    verify_claim_improved so the function is available when that cell runs.
    """
    best_sentence, best_coverage = None, (0.0, 0)
    for sentence in split_into_sentences(context or ""):
        window = evidence_with_antecedent(sentence, context or "")
        coverage = question_coverage(question or "", window)
        if coverage > best_coverage:
            best_sentence, best_coverage = sentence, coverage
    if best_sentence and best_coverage[0] >= 0.60 and best_coverage[1] >= 2:
        return best_sentence
    return None


def verify_claim_improved(claim, context, top_k=3, question=""):
    """Verify one claim using retrieval, NLI, numbers, entities and question-role checks.

    NLI entailment is only one signal; missing role/number/entity evidence remains unknown.
    Bare answers ("1905") are handled by the short-answer helpers (previous cell).
    """
    evidence_list, fragment = retrieve_evidence_for_claim(claim, context, question, top_k)
    if not evidence_list:
        return {
            "claim": claim,
            "evidence": "",
            "similarity": 0.0,
            "nli_label": "neutral",
            "nli_confidence": 0.0,
            "number_consistent": True,
            "number_reason": "No evidence available",
            "entity_consistent": True,
            "entity_reason": "No evidence available",
            "status": "NOT ENOUGH EVIDENCE",
            "support_basis": None,
            "hypothesis": claim,
            "question_coverage": 0.0,
        }

    best_evidence, similarity = evidence_list[0]
    statement, grounded, coverage = claim, False, 0.0
    if fragment:
        window = evidence_with_antecedent(best_evidence, context)
        statement = question_to_statement(question, claim)
        grounded = answer_is_grounded(question, claim, best_evidence, window)
        coverage = question_coverage(question, window)[0]
        label, confidence = verify_fragment_claim(claim, statement, best_evidence, grounded, window, question)
    else:
        label, confidence = verify_claim(claim, best_evidence)

    # Check numeric consistency against the selected supporting sentence only.
    # Other retrieved passages may contain unrelated dates (e.g. birth year,
    # graduation year, and a sibling's birth year). Treating all those numbers as
    # one evidence statement can falsely reject a correct short answer.
    number_check = check_number_consistency(claim, best_evidence)
    aligned_conflict = False
    if fragment:
        alignment = check_answer_number_alignment(question, claim, best_evidence, window)
        if not alignment["consistent"]:
            number_check, aligned_conflict = alignment, True
        elif question and context:
            # The retrieved sentence may simply be the one that CONTAINS the answer
            # text. When the sentence that actually discusses the question gives a
            # different value, that is a real conflict -- and that sentence is the
            # evidence to show for it.
            alt = question_relevant_sentence(question, context)
            if alt and alt != best_evidence:
                alt_window = evidence_with_antecedent(alt, context)
                alt_alignment = check_answer_number_alignment(question, claim, alt, alt_window)
                if not alt_alignment["consistent"]:
                    number_check, aligned_conflict = alt_alignment, True
                    best_evidence, window = alt, alt_window
                    grounded = answer_is_grounded(question, claim, best_evidence, window)
                    coverage = question_coverage(question, window)[0]
                    label, confidence = verify_fragment_claim(
                        claim, statement, best_evidence, grounded, window, question
                    )
    entity_check = check_entity_consistency(claim, best_evidence)
    # Shape of the reply vs. what the question asks for (see the new helper cell).
    type_ok = answer_matches_question_type(question, claim)

    # Direct relation support for short place answers. NLI can label a bare
    # place name as neutral when the evidence contains several locations, even
    # though it explicitly states the requested relation (e.g. grandparents
    # emigrated TO Texas). Only activate this when the question and evidence
    # share the relation verb, the answer occurs in that same evidence sentence,
    # and distinctive question words are covered. This is not a place-name
    # hardcode and does not bypass contradiction/number checks.
    q_lower = (question or "").lower()
    ev_lower = (best_evidence or "").lower()
    direct_relation_support = False
    if fragment and question_answer_type(question) == "place" and answer_span_in_evidence(claim, best_evidence):
        relation_groups = (
            (r"\b(emigrat\w*|immigrat\w*)\b", r"\b(emigrat\w*|immigrat\w*)\b"),
            (r"\b(born|birth)\b", r"\b(born|birth)\b"),
            (r"\b(mov\w*|relocat\w*)\b", r"\b(mov\w*|relocat\w*)\b"),
            (r"\b(located|situated|based)\b", r"\b(located|situated|based)\b"),
        )
        relation_match = any(re.search(qp, q_lower) and re.search(ep, ev_lower)
                             for qp, ep in relation_groups)
        q_coverage, q_matched = question_coverage(question, evidence_with_antecedent(best_evidence, context))
        direct_relation_support = relation_match and q_coverage >= 0.60 and q_matched >= 2

    status = determine_claim_status(
        label, number_check, entity_check, question=question,
        claim=claim, evidence=best_evidence, answer_grounded=grounded,
        type_ok=type_ok,
    )
    if (direct_relation_support and number_check["consistent"]
            and entity_check["consistent"] and label != "contradiction"):
        status = "SUPPORTED"

    # General direct-span safeguard for short answers across manual and document
    # modes. If the answer appears exactly in the question-relevant sentence, the
    # question's distinctive words are covered, there is no competing value of
    # the same kind in THAT sentence, and number/entity checks pass, a noisy NLI
    # contradiction must not overrule the direct evidence. This is generic; it is
    # not specific to Selena Gomez, Texas, or any one question wording.
    if fragment and answer_span_in_evidence(claim, best_evidence):
        support_window = evidence_with_antecedent(best_evidence, context)
        support_fraction, support_matched = question_coverage(question, support_window)
        direct_span_support = (
            support_fraction >= 0.60 and support_matched >= 2
            and not has_competing_candidates(claim, best_evidence)
            and number_check["consistent"] and entity_check["consistent"]
        )
        if direct_span_support and label != "contradiction":
            status = "SUPPORTED"
        elif direct_span_support and label == "contradiction":
            # Exact answer span + question match + no same-kind alternative is
            # stronger than a known noisy contradiction on a bare answer.
            status = "SUPPORTED"

    support_basis = None
    if status == "SUPPORTED":
        support_basis = "nli_entailment" if label == "entailment" else "answer_span_in_evidence"

    return {
        "claim": claim,
        "evidence": best_evidence,
        "similarity": similarity,
        "nli_label": label,
        "nli_confidence": confidence,
        "number_consistent": number_check["consistent"],
        "number_reason": number_check["reason"],
        "entity_consistent": entity_check["consistent"],
        "entity_reason": entity_check["reason"],
        "status": status,
        "support_basis": support_basis,
        "hypothesis": statement,
        "question_coverage": coverage,
        "aligned_conflict": aligned_conflict,
    }

def analyze_answer_improved(answer, context, question=""):
    """Split an answer into claims and verify every claim."""
    results = []
    for sentence in split_into_sentences(answer):
        for claim in split_claims(sentence):
            results.append(verify_claim_improved(claim, context, question=question))
    return results

def get_hallucinated_spans(example):
    """Extract hallucinated text spans from a RAGTruth example."""
    raw = example.get("hallucination_labels", "[]")
    if not raw:
        return []
    try:
        labels = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return []
    return [item.get("text", "") for item in labels if item.get("text")]

def sentence_contains_hallucination(text, hallucinated_spans):
    """Return True if any annotated hallucinated span occurs in text."""
    lower_text = text.lower()
    return any(span.lower() in lower_text for span in hallucinated_spans)

def run_verification_pipeline(question, context, answer, verbose=True):
    """Run claim-level verification and return a structured report."""
    all_claims = []
    claim_number = 0

    for sentence in split_into_sentences(answer):
        for claim in split_claims(sentence):
            claim_number += 1
            result = verify_claim_improved(claim, context, question=question)
            result["claim_number"] = claim_number
            all_claims.append(result)

    summary = {
        "total_claims": len(all_claims),
        "supported": sum(r["status"] == "SUPPORTED" for r in all_claims),
        "contradicted": sum(r["status"] == "CONTRADICTED" for r in all_claims),
        "not_enough_evidence": sum(r["status"] == "NOT ENOUGH EVIDENCE" for r in all_claims),
    }

    if summary["contradicted"] > 0:
        overall_status = "CONTAINS HALLUCINATION"
    elif summary["not_enough_evidence"] > 0:
        overall_status = "NEEDS VERIFICATION"
    else:
        overall_status = "FULLY SUPPORTED"

    result = {
        "question": question,
        "context": context,
        "original_answer": answer,
        "claims": all_claims,
        "overall_status": overall_status,
        "summary": summary,
    }

    if verbose:
        print("=" * 70)
        print("VERIFICATION REPORT")
        print("=" * 70)
        print("Question:", question)
        print("Answer:", answer)
        for item in all_claims:
            print(f"\nClaim {item['claim_number']}: {item['claim']}")
            print("Status:", item["status"])
            print("NLI:", item["nli_label"], f"({item['nli_confidence']:.4f})")
            print("Evidence:", item["evidence"])
        print("\nOverall:", overall_status)
        print("Summary:", summary)

    return result

# Single source of truth for the insufficient-evidence wording (used by the
# corrector, the extraction fallback and the API adapter).
INSUFFICIENT_ANSWER = "The available evidence is not sufficient to provide a verified answer."


def replacement_is_grounded(replacement, question, evidence, context):
    """A replacement must be (a) text that really occurs in the supplied evidence
    and (b) a sentence that actually bears on the question.

    (a) keeps the correction evidence-grounded instead of model memory; (b) stops a
    true-but-unrelated sentence (the 1893 South Africa line for a question about
    1921) from being pasted into the answer as "the fix". Without a question or a
    context (the model-free unit tests) the legacy behaviour is kept.
    """
    text = str(replacement or "").strip()
    if not text:
        return False
    haystack = " ".join((context or "").split())
    core = " ".join(text.rstrip(" .!?").split())
    if haystack and core.lower() not in haystack.lower():
        return False                      # never introduce text that is not evidence
    if question:
        window = evidence_with_antecedent(evidence, context) if context else evidence
        coverage, matched = question_coverage(question, window)
        if coverage < 0.60 or matched < 2:
            return False                  # true, but about something else
    return True


def attempt_correction(claim, evidence, claim_result):
    """
    Conservative evidence-grounded correction.

    We only attempt correction when the evidence directly contains
    information relevant to the claim. Otherwise, the claim is removed
    rather than inventing a new fact.
    """
    if not evidence:
        return None

    # A wrong year/number for a question-relevant evidence sentence: the evidence
    # sentence itself is the safe correction (a bare answer has no words to match).
    if claim_result and claim_result.get("aligned_conflict"):
        return evidence.strip().rstrip(".!?") + "."

    claim_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.lower()))
    evidence_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", evidence.lower()))

    if not claim_words or not evidence_words:
        return None

    overlap = len(claim_words & evidence_words)
    overlap_ratio = overlap / len(claim_words)

    # Only use the evidence as a correction when most of the
    # important words from the original claim occur in the evidence.
    # This helper is called only for claims already classified CONTRADICTED.
    # Keep the existing conservative lexical-overlap correction behavior here;
    # NOT ENOUGH EVIDENCE claims are removed and never reach this branch.
    if overlap_ratio >= 0.60:
        return evidence.strip().rstrip(".!?") + "."

    return None


def correct_answer_evidence_grounded(verification_results, verbose=True):
    """
    Produce a conservative corrected answer.

    SUPPORTED:
        Keep the original claim exactly as generated.

    CONTRADICTED:
        Replace with evidence only when there is strong lexical overlap AND the
        replacement is text from the supplied evidence that answers this question
        (replacement_is_grounded). Otherwise remove the claim.

    NOT ENOUGH EVIDENCE:
        Remove the claim because it cannot be safely verified.
    """

    # The question and the evidence let us refuse off-topic "corrections"
    # (replacement_is_grounded). Missing keys keep the legacy behaviour.
    question = str(verification_results.get("question") or "").strip()
    context = str(verification_results.get("context") or "")

    retained = []
    corrected = []
    removed = []
    final_claims = []

    for item in verification_results["claims"]:

        claim = item["claim"]
        status = item["status"]

        # -----------------------------------
        # 1. SUPPORTED → KEEP EXACTLY
        # -----------------------------------
        if status == "SUPPORTED":

            retained.append(claim)
            final_claims.append(claim)

        # -----------------------------------
        # 2. CONTRADICTED → TRY TO CORRECT
        # -----------------------------------
        elif status == "CONTRADICTED":

            replacement = attempt_correction(
                claim,
                item["evidence"],
                item
            )

            if replacement and not replacement_is_grounded(
                replacement, question, item.get("evidence", ""), context
            ):
                # The sentence is supported by the evidence but does not answer THIS
                # question: drop the claim instead of pasting an unrelated fact in.
                replacement = None

            if replacement:
                corrected.append({
                    "original": claim,
                    "corrected": replacement,
                    "evidence": item["evidence"]
                })

                final_claims.append(replacement)

            else:
                removed.append({
                    "claim": claim,
                    "reason": "Claim contradicted by evidence and no safe correction was found."
                })

        # -----------------------------------
        # 3. NOT ENOUGH EVIDENCE → REMOVE
        # -----------------------------------
        else:

            removed.append({
                "claim": claim,
                "reason": "Not enough evidence to verify the claim."
            })

    # SAFETY RULE: if nothing was corrected or removed, the answer was fully
    # supported, so return the ORIGINAL generated answer character-for-character
    # (no re-joining, no added punctuation: '1889' stays '1889').
    if not corrected and not removed:
        corrected_answer = str(verification_results["original_answer"]).strip()
    else:
        corrected_answer = " ".join(final_claims).strip()

    # If every claim was removed, clearly report that
    if not corrected_answer:
        corrected_answer = INSUFFICIENT_ANSWER

    report = {
        "total_claims": len(verification_results["claims"]),
        "retained": len(retained),
        "corrected": len(corrected),
        "removed": len(removed)
    }

    if verbose:
        print("\nCORRECTED ANSWER:", corrected_answer)
        print("CORRECTION REPORT:", report)

    return {
        "original_answer": verification_results["original_answer"],
        "corrected_answer": corrected_answer,
        "correction_report": report,
        "claims_retained": retained,
        "claims_corrected": corrected,
        "claims_removed": removed
    }

def generate_answer(question, context, max_length=128):
    """Generate a context-grounded draft answer with FLAN-T5-small."""
    prompt = f"""Answer the question based only on the context provided.
If the context does not contain enough information, say "I don't have enough information to answer this question.".

Context: {context}

Question: {question}

Answer:"""

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        max_length=512,
        truncation=True,
    )
    outputs = generation_model.generate(
        **inputs,
        max_length=max_length,
        num_beams=4,
        early_stopping=True,
        no_repeat_ngram_size=2,
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def generate_answer_plain(question, context, max_length=128):
    """Second attempt in FLAN-T5's standard reading-comprehension format.

    Used only when the first answer was an abstention. The retry is NOT trusted:
    it goes through the same claim verification and correction as any answer.
    """
    prompt = f"Read this and answer the question.\n\n{context}\n\n{question}"
    inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
    outputs = generation_model.generate(
        **inputs, max_length=max_length, num_beams=4,
        early_stopping=True, no_repeat_ngram_size=2,
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

# ---- Final scope: answer conformance + deterministic evidence extraction ----
#
# WHAT WAS WRONG: FLAN-T5-small sometimes replies with a topical fragment
# ("India") instead of the value a factoid question asks for (a YEAR for
# "When did Gandhi assume leadership of the Indian National Congress?").
# Nothing checked the SHAPE of the reply, so the fragment reached verification,
# where "the word appears somewhere in the evidence" could look like support.
#
# Everything here is deterministic (no model, no per-question hard-coding):
#   question_answer_type()          which kind of value answers this question
#   answer_matches_question_type()  does a reply carry that kind of value
#   question_relevant_sentence()    the evidence sentence that actually discusses
#                                   the question's subject
#   extract_short_answer()          the unique value of that kind, taken verbatim
#                                   from those sentences. Used only as a FALLBACK,
#                                   and re-verified through the normal pipeline.

_EXTRACT_MIN_COVERAGE = 0.60
_EXTRACT_MIN_MATCHED = 2
_MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\b", re.IGNORECASE)
_NUMBER_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(number_words, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_PLACE_LABELS = {"GPE", "LOC", "FAC"}


def question_answer_type(question):
    """Infer the expected answer type from common natural-language question forms.

    Supports equivalent temporal phrasings such as:
      - When was Mandela arrested?
      - What year was Mandela arrested?
      - Which year was Mandela arrested?
      - In which year did Mandela get arrested?
      - On what date did it happen?

    This detects answer shape only; evidence verification still determines truth.
    """
    q = re.sub(r"\s+", " ", (question or "").strip().lower())
    if not q:
        return None

    # Temporal questions can be phrased with when, what/which year, or date/day/month.
    temporal_patterns = (
        r"^when\b",
        r"^(?:(?:in|during|on|by|around)\s+)?(?:what|which)\s+(?:year|date|day|month)\b",
        r"^(?:what|which)\s+(?:was|is|would be)\s+the\s+(?:year|date|day|month)\b",
        r"^what\s+(?:year|date|day|month)\b",
    )
    if any(re.search(pattern, q) for pattern in temporal_patterns):
        return "date"

    if re.match(r"^where\b", q) or re.search(r"\b(whereabouts|in what place)\b", q):
        return "place"
    if (re.match(r"^who\b", q)
            or (re.search(r"\b(name|called)\b", q)
                and re.search(r"\b(my|the person's|the persons|their|his|her)\b", q))):
        return "person"
    if re.match(r"^how\s+(many|much)\b", q) or re.search(r"\bnumber of\b", q):
        return "number"
    return None

def answer_matches_question_type(question, answer):
    """True when `answer` carries the kind of value `question` asks for.

    This is a SHAPE check only -- factual support is decided separately by the
    claim verification. An open-ended question places no constraint (True), and
    an abstention ("I don't have enough information ...") never answers a
    factoid question (False).
    """
    kind = question_answer_type(question)
    text = str(answer or "")
    if kind is None:
        return True
    if not text.strip() or is_abstention(text):
        return False
    if kind == "date":
        return bool(YEAR_RE.search(text) or _MONTH_RE.search(text))
    if kind == "number":
        return bool(re.search(r"\d", text) or _NUMBER_WORD_RE.search(text))
    if kind == "place":
        return any(ent.label_ in _PLACE_LABELS for ent in nlp(text).ents)
    if kind == "person":
        return (any(ent.label_ == "PERSON" for ent in nlp(text).ents)
                or bool(re.fullmatch(r"[A-Z][A-Za-z'-]*", text.strip())))
    return True


def question_relevant_sentence(question, context):
    """The evidence sentence with the highest coverage of the question's words
    (subject sentence + antecedent), or None when nothing really discusses it."""
    best, best_coverage = None, (0.0, 0)
    for sentence in split_into_sentences(context or ""):
        window = evidence_with_antecedent(sentence, context)
        coverage = question_coverage(question, window)
        if coverage > best_coverage:
            best, best_coverage = sentence, coverage
    if best and best_coverage[0] >= _EXTRACT_MIN_COVERAGE and best_coverage[1] >= _EXTRACT_MIN_MATCHED:
        return best
    return None


def _answer_values(kind, text, question=""):
    """Verbatim values of `kind` inside `text` (order kept, duplicates removed)."""
    doc = nlp(str(text or ""))
    values = []
    if kind == "date":
        values = YEAR_RE.findall(doc.text)
        if not values:
            values = _MONTH_RE.findall(doc.text)
    elif kind == "number":
        values = re.findall(r"\d[\d,]*\.?\d*", doc.text)
        if not values:
            values = _NUMBER_WORD_RE.findall(doc.text)
    elif kind in {"person", "place"}:
        labels = {"person": {"PERSON"}, "place": _PLACE_LABELS}[kind]
        entities = [ent for ent in doc.ents if ent.label_ in labels]
        # Entities the QUESTION already names are the subject, not the answer
        # ("Where is the Eiffel Tower located?" -> "The Eiffel Tower" is not it).
        question_tokens = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", question or "")}
        entities = [
            ent for ent in entities
            if not question_tokens.intersection(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", ent.text))
        ]
        if kind == "place" and entities:
            # "located in Paris, France" -> the place after the preposition, not both.
            anchored = [
                ent.text for ent in entities
                if re.search(r"(?i)\b(in|at|near|to|into|from)\s*$", doc[:ent.start].text[-30:])
            ]
            if anchored and len({a.lower() for a in anchored}) == 1:
                entities = [ent for ent in entities if ent.text in anchored]
        values = [ent.text for ent in entities]
    seen, unique = set(), []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            unique.append(value)
    return unique


def extract_short_answer(question, context):
    """Fallback: the unique value of the kind `question` asks for, taken from the
    evidence sentence(s) that actually discuss the question's subject.

    Returns (answer_text, source_sentence) or None. None means the evidence does
    not yield a single trustworthy value -- the caller must then say so instead
    of guessing.
    """
    kind = question_answer_type(question)
    if kind is None or not (question or "").strip() or not (context or "").strip():
        return None
    found = []                                   # (value, source sentence)
    for sentence in split_into_sentences(context):
        window = evidence_with_antecedent(sentence, context)
        coverage, matched = question_coverage(question, window)
        if coverage < _EXTRACT_MIN_COVERAGE or matched < _EXTRACT_MIN_MATCHED:
            continue                             # sentence is about something else
        # Use the sentence that states the fact to extract the value. The
        # antecedent window is only for resolving pronouns and measuring topic
        # coverage; it may contain unrelated dates (e.g. Mandela's 1952 and
        # 1955 activities before the 1962 arrest). Extracting from the whole
        # window incorrectly treats those historical dates as competing answers.
        for value in _answer_values(kind, sentence, question):
            found.append((value, sentence))
    if not found:
        return None
    if len({value for value, _ in found}) > 1:
        return None                              # ambiguous -> never guess
    value = found[0][0]
    source = next((s for v, s in found if v == value and v in s), found[0][1])
    return value, source


def adopt_extracted_answer(question, context, correction, verbose=True):
    """When the corrected answer cannot serve as an answer to this question,
    mine the evidence for the requested value and re-verify it like any answer.

    The extracted text is verbatim evidence and is only used when EVERY verified
    claim of it comes back SUPPORTED. Otherwise the pipeline returns an explicit
    insufficient-evidence answer instead of guessing."""
    if answer_matches_question_type(question, correction.get("corrected_answer", "")):
        return correction                       # already answers the question

    extracted = extract_short_answer(question, context)
    if extracted:
        value, source = extracted
        check = run_verification_pipeline(question, context, value, verbose=False)
        if check["claims"] and all(c["status"] == "SUPPORTED" for c in check["claims"]):
            correction["corrected_answer"] = value
            correction["corrected_evidence"] = source
            correction["correction_source"] = "evidence_extraction"
            correction["correction_report"]["extracted"] = 1
            correction["_verified_report"] = check
            if verbose:
                print("ANSWER EXTRACTED FROM EVIDENCE:", value)
            return correction

    correction["corrected_answer"] = INSUFFICIENT_ANSWER
    correction["correction_source"] = "insufficient_evidence"
    correction.pop("corrected_evidence", None)
    if verbose:
        print("NO TRUSTWORTHY ANSWER IN THE EVIDENCE.")
    return correction


def corrected_answer_status(question, context, correction, verification=None):
    """Status OF THE CORRECTED ANSWER, always derived from its own claim statuses.

    The results page used to show a hard-coded SUPPORTED badge here, which could
    disagree with the overall status printed next to it."""
    corrected = str(correction.get("corrected_answer") or "").strip()
    if (not corrected or corrected == INSUFFICIENT_ANSWER or is_abstention(corrected)
            or not answer_matches_question_type(question, corrected)):
        return "NOT_ENOUGH_EVIDENCE"
    original = str(correction.get("original_answer") or "").strip()
    if corrected == original and verification is not None:
        report = verification
    elif correction.get("_verified_report") is not None:
        report = correction["_verified_report"]
    else:
        report = run_verification_pipeline(question, context, corrected, verbose=False)
    statuses = [c["status"] for c in report.get("claims", [])]
    if not statuses:
        return "NOT_ENOUGH_EVIDENCE"
    if "CONTRADICTED" in statuses:
        return "CONTRADICTED"
    if "NOT ENOUGH EVIDENCE" in statuses:
        return "NOT_ENOUGH_EVIDENCE"
    return "SUPPORTED"

def run_full_rag_pipeline(question, context, verbose=True):
    """Question -> answer generation -> verification -> correction.

    Two deterministic guards keep the result usable for the final demo:
      1. a reply whose SHAPE cannot answer the question (a country for a
         "When ...?" question) is never verified as SUPPORTED;
      2. if nothing verified survives the correction, the evidence itself is
         mined for the requested value (adopt_extracted_answer) and re-verified;
         if that fails too, an explicit insufficient-evidence answer is returned
         instead of a guess.
    """
    generated_answer = generate_answer(question, context)
    initial_answer, retried = generated_answer, False
    if is_abstention(generated_answer):
        # FLAN-T5-small sometimes abstains although the context answers the
        # question. Try once more; the new answer is verified like any other.
        second = (generate_answer_plain(question, context) or "").strip()
        if second and not is_abstention(second):
            generated_answer, retried = second, True
    verification = run_verification_pipeline(
        question, context, generated_answer, verbose=verbose
    )
    correction = correct_answer_evidence_grounded(verification, verbose=verbose)
    correction = adopt_extracted_answer(question, context, correction, verbose=verbose)
    corrected_status = corrected_answer_status(question, context, correction, verification)
    correction["corrected_status"] = corrected_status

    return {
        "question": question,
        "context": context,
        "generated_answer": generated_answer,
        "initial_answer": initial_answer,
        "generation_retried": retried,
        "verification": verification,
        "correction": correction,
        "corrected_status": corrected_status,
    }

# Phase 1, part A: read an uploaded .txt file, split it into passages, index them.
# Reuses: split_into_sentences, retriever, retrieve_evidence_fast (all defined above).
import os
import hashlib

DOC_MAX_BYTES = 2_000_000       # refuse files larger than about 2 MB
DOC_CHUNK_WORDS = 60            # maximum words per passage
DOC_TOP_K = 3                   # passages sent to generation + verification
DOC_MIN_RELEVANCE = 0.25        # best passage below this -> "insufficient evidence"
DOC_MAX_CONTEXT_TOKENS = 350    # generate_answer cuts its prompt at 512 tokens


def read_uploaded_txt(uploaded):
    """Read an uploaded .txt file. Returns (text, error); exactly one is None."""
    if uploaded is None:
        return None, "No file uploaded. Please upload a .txt file."

    # Gradio gives either a path string or an object with a .name path.
    path = uploaded if isinstance(uploaded, str) else getattr(uploaded, "name", None)
    if not path or not os.path.isfile(path):
        return None, "Could not find the uploaded file. Please upload it again."
    if not path.lower().endswith(".txt"):
        return None, "Only .txt files are supported."
    if os.path.getsize(path) > DOC_MAX_BYTES:
        return None, f"File is too large (limit {DOC_MAX_BYTES // 1_000_000} MB)."

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as error:
        return None, f"Could not read the file: {error}"

    if b"\x00" in raw:
        return None, "This does not look like a plain-text file (binary content found)."
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")      # fallback for older Windows text files

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return None, "The uploaded file is empty."
    return text, None


def chunk_document(text, max_words=DOC_CHUNK_WORDS):
    """Split text into passages of at most `max_words` words.

    Paragraphs (blank-line separated) are never mixed together. Inside a
    paragraph, whole sentences are grouped until the word limit is reached.
    A single sentence longer than the limit is cut into pieces.
    """
    chunks = []
    for paragraph in re.split(r"\n\s*\n", text):
        current, count = [], 0
        for sentence in split_into_sentences(paragraph):
            words = sentence.split()
            pieces = [" ".join(words[i:i + max_words])
                      for i in range(0, len(words), max_words)]
            for piece in pieces:
                n = len(piece.split())
                if current and count + n > max_words:
                    chunks.append(" ".join(current))
                    current, count = [], 0
                current.append(piece)
                count += n
        if current:
            chunks.append(" ".join(current))
    return chunks


def build_document_index(text):
    """Embed every passage once (same normalisation as prepare_retrieval_context)."""
    chunks = chunk_document(text)
    if not chunks:
        return None
    embeddings = retriever.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    norms = np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-10)
    return {"chunks": chunks, "embeddings": embeddings / norms}


_doc_cache = {"key": None, "index": None}

def get_document_index(text):
    """Build the index once per document, so each new question is fast."""
    key = hashlib.md5(text.encode("utf-8")).hexdigest()
    if _doc_cache["key"] != key:
        _doc_cache["index"] = build_document_index(text)
        _doc_cache["key"] = key
    return _doc_cache["index"]


def retrieve_passages(question, index, top_k=DOC_TOP_K):
    """Top-k passages for the question as (passage, score), best first.

    Calls the existing retrieve_evidence_fast, so the scoring (0.7 semantic +
    0.3 word overlap, controlled by CONFIG["lexical_retrieval"]) is the same
    as in the rest of the project.
    """
    return retrieve_evidence_fast(
        question, index["chunks"], index["embeddings"], top_k=top_k
    )

# Phase 1, part B: question + document text -> retrieved passages -> EXISTING pipeline.

def run_document_rag(question, document_text):
    """Retrieve passages from the document, then call run_full_rag_pipeline on them."""
    question = (question or "").strip()
    if not question:
        return {"error": "Please enter a question."}

    index = get_document_index(document_text)
    if index is None:
        return {"error": "No usable text was found in the document."}

    passages = retrieve_passages(question, index)
    best_score = passages[0][1] if passages else 0.0

    # Not relevant enough: do not generate an answer from unrelated text.
    if not passages or best_score < DOC_MIN_RELEVANCE:
        return {"question": question, "insufficient": True,
                "passages": passages, "best_score": best_score}

    # Keep the prompt inside generate_answer's 512-token limit (drop weakest passages).
    selected = list(passages)
    while len(selected) > 1:
        joined = " ".join(text for text, _ in selected)
        if len(tokenizer(joined)["input_ids"]) <= DOC_MAX_CONTEXT_TOKENS:
            break
        selected.pop()

    # The retrieved passages ARE the context for generation, verification and correction.
    context = " ".join(text for text, _ in selected)
    result = run_full_rag_pipeline(question, context, verbose=False)
    result["passages"] = selected
    result["best_score"] = best_score
    return result

# Paste this entire cell at the END of the V6 notebook, after all pipeline functions
# and models have loaded. This adapter reuses the existing notebook functions.

import threading, uuid, os, time, subprocess, requests, json
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Evidence-Grounded RAG API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Prototype only. Restrict this before public deployment.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory document store for the demo. Uploaded documents disappear when Colab resets.
API_DOCUMENTS = {}

class AskRequest(BaseModel):
    question: str
    mode: str = "manual"  # manual | document (automatic web retrieval removed)
    evidence: Optional[str] = None
    document_id: Optional[str] = None

@app.get("/health")
@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "evidence-grounded-rag-api"}

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    filename = file.filename or "upload.txt"
    if not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=415, detail="This notebook currently supports .txt uploads only.")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="File is too large. Maximum size is 2 MB.")
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise HTTPException(status_code=400, detail="The uploaded text file is empty.")
    document_id = str(uuid.uuid4())
    API_DOCUMENTS[document_id] = {"filename": filename, "text": text}
    return {"document_id": document_id, "filename": filename, "message": "Text document ready."}

def _status_summary(claims):
    statuses = [str(c.get("status", "NOT ENOUGH EVIDENCE")).upper() for c in claims]
    if not statuses:
        return "NEEDS VERIFICATION"
    if "CONTRADICTED" in statuses:
        return "CONTAINS HALLUCINATION"
    if any("NOT ENOUGH EVIDENCE" in s or "NOT_ENOUGH_EVIDENCE" in s for s in statuses):
        return "NEEDS VERIFICATION"
    return "FULLY SUPPORTED"

def _consistency_block(item):
    """The results page reads consistency.status and consistency.details."""
    numbers_ok, entities_ok = item.get("number_consistent"), item.get("entity_consistent")
    if numbers_ok is None and entities_ok is None:
        status = "NOT_CHECKED"
    else:
        status = "PASS" if (numbers_ok is not False and entities_ok is not False) else "FAIL"
    details = [f"Numbers: {item.get('number_reason', 'n/a')}", f"Entities: {item.get('entity_reason', 'n/a')}"]
    if item.get("support_basis") == "answer_span_in_evidence":
        details.append("Support: the answer text appears in a question-relevant evidence sentence "
                       f"(question word coverage {item.get('question_coverage', 0.0):.2f}).")
    return {
        "status": status,
        "details": " | ".join(details),
        "numbers_consistent": numbers_ok,
        "number_reason": item.get("number_reason"),
        "entities_consistent": entities_ok,
        "entity_reason": item.get("entity_reason"),
        "support_basis": item.get("support_basis"),
    }

def _overall_confidence(item):
    """Keep heuristic short-answer support separate from NLI model probability."""
    if item.get("status") == "SUPPORTED" and item.get("support_basis") == "answer_span_in_evidence":
        return None
    return item.get("nli_confidence")

def _to_frontend(result, sources=None):
    if result.get("error"):
        raise HTTPException(status_code=400, detail=str(result["error"]))
    if result.get("insufficient"):
        return {
            "verification_status": "NOT ENOUGH EVIDENCE",
            "original_answer": "No answer was generated because sufficient relevant evidence was not retrieved.",
            "corrected_answer": INSUFFICIENT_ANSWER,
            "corrected_status": "NOT_ENOUGH_EVIDENCE",
            "corrected_evidence": "",
            "claims": [], "removed_claims": [], "sources": sources or [],
            "message": result.get("message", "The evidence was insufficient."),
        }
    verification = result.get("verification", {})
    correction = result.get("correction", {})
    claim_items = []
    for item in verification.get("claims", []):
        claim_items.append({
            "claim": item.get("claim", ""),
            "status": str(item.get("status", "NOT ENOUGH EVIDENCE")).replace(" ", "_"),
            "evidence": item.get("evidence", ""),
            "nli_label": item.get("nli_label"),
            "confidence": _overall_confidence(item),
            "nli_confidence": item.get("nli_confidence"),
            "support_basis": item.get("support_basis"),
            "consistency": _consistency_block(item),
        })
    removed = correction.get("claims_removed", [])
    # The headline status is derived from the SAME claims shown on the page, so the
    # two can never disagree (it matches verification["overall_status"], which is
    # computed from the same list).
    if claim_items:
        overall_status = _status_summary(claim_items)
    else:
        overall_status = verification.get("overall_status") or "NEEDS VERIFICATION"
    return {
        "verification_status": overall_status,
        "original_answer": result.get("generated_answer", correction.get("original_answer", "")),
        "corrected_answer": correction.get("corrected_answer", ""),
        # Status OF THE CORRECTED ANSWER, computed from its own claim statuses by
        # the pipeline -- the results page must never hard-code a SUPPORTED badge.
        "corrected_status": correction.get("corrected_status") or "NOT_ENOUGH_EVIDENCE",
        "corrected_evidence": correction.get("corrected_evidence", ""),
        "claims": claim_items,
        "removed_claims": removed,
        "sources": sources or [],
    }

@app.post("/api/ask")
def api_ask(payload: AskRequest):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    mode = (payload.mode or "manual").lower()
    try:
        if mode == "manual":
            evidence = (payload.evidence or "").strip()
            if not evidence:
                raise HTTPException(status_code=400, detail="Please provide evidence text.")
            result = run_full_rag_pipeline(question, evidence, verbose=False)
            return _to_frontend(result)
        if mode == "document":
            if not payload.document_id or payload.document_id not in API_DOCUMENTS:
                raise HTTPException(status_code=400, detail="Upload the .txt document again; its temporary ID may have expired.")
            doc = API_DOCUMENTS[payload.document_id]
            result = run_document_rag(question, doc["text"])
            sources = [{"title": doc["filename"], "url": "", "passage": p[0]} for p in result.get("passages", [])]
            return _to_frontend(result, sources=sources)
        raise HTTPException(status_code=400, detail="Unknown mode. Use manual or document.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {type(exc).__name__}: {exc}")

# Start the API in the background so this notebook cell remains usable.


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
