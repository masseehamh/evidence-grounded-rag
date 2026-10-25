"""Lightweight stand-ins for the three heavy models, so the notebook's own
logic can be exercised without internet access or a GPU.

IMPORTANT: these are NOT the real MiniLM / DeBERTa / FLAN-T5 models. They let us
test the notebook's decision logic (claim splitting, number/entity checks,
status rules, correction, API). They cannot tell you how the real models behave.
"""
import re
import numpy as np

_WORD = re.compile(r"[A-Za-z]+|\d+")
_STOP = {"the", "and", "for", "with", "that", "this", "from", "was", "were", "are",
         "his", "her", "its", "has", "have", "had", "been", "into", "who", "which"}


def _tokens(text):
    out = []
    for w in _WORD.findall(str(text).lower()):
        if w.isdigit() or (len(w) >= 3 and w not in _STOP):
            out.append(w[:-1] if (w.endswith("s") and len(w) > 4) else w)
    return out


class FakeRetriever:
    """Hashed bag-of-words embeddings (deterministic)."""
    DIM = 512

    def _vec(self, text):
        v = np.zeros(self.DIM, dtype=float)
        for t in _tokens(text):
            v[hash(t) % self.DIM] += 1.0
        return v

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, **_):
        if isinstance(texts, str):
            return self._vec(texts)
        return np.array([self._vec(t) for t in texts])


class FakeNLI:
    """Mimics the one property of NLI cross-encoders that matters here:
    a *statement* can be entailed; a bare fragment ('1905') cannot -> neutral.

      * fewer than 3 content tokens in the hypothesis -> neutral
      * >=70% of hypothesis tokens in premise and no conflicting number -> entailment
      * >=50% overlap but a number in the hypothesis that the premise lacks,
        while the premise has numbers of its own -> contradiction
      * otherwise neutral
    """

    def __call__(self, pair):
        premise, hypothesis = pair["text"], pair["text_pair"]
        h, p = _tokens(hypothesis), set(_tokens(premise))
        if len(h) < 3:
            return {"label": "NEUTRAL", "score": 0.90}
        overlap = sum(t in p for t in h) / len(h)
        h_nums = {t for t in h if t.isdigit()}
        p_nums = {t for t in p if t.isdigit()}
        if h_nums and p_nums and not h_nums <= p_nums and overlap >= 0.5:
            return {"label": "CONTRADICTION", "score": 0.90}
        if overlap >= 0.7:
            return {"label": "ENTAILMENT", "score": 0.95}
        return {"label": "NEUTRAL", "score": 0.85}


class AlwaysNeutralNLI:
    """Worst case: NLI never helps. Tests the deterministic safeguards alone."""

    def __call__(self, pair):
        return {"label": "NEUTRAL", "score": 0.99}
