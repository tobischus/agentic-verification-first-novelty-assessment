"""Verbatim predicate V(q, D) of Equation 3.2.

A quote is verified if it has at least `min_quote_tokens` words and occurs in the source
text after normalization, exactly or with a RapidFuzz partial ratio of at least
`fuzzy_threshold`.
"""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

DEFAULT_MIN_QUOTE_TOKENS = 10
DEFAULT_FUZZY_THRESHOLD = 90.0


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join((text or "").lower().split())


def token_count(text: str) -> int:
    return len((text or "").split())


@dataclass
class QuoteCheck:
    verified: bool
    method: str        # exact | fuzzy | too_short | not_found | empty
    score: float
    matched_span: str

    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "method": self.method,
            "score": round(self.score, 1),
            "matched_span": self.matched_span,
        }


def _best_window(needle_norm: str, hay_norm: str) -> str:
    """The window of `hay_norm` that best aligns with `needle_norm`."""
    try:
        al = fuzz.partial_ratio_alignment(needle_norm, hay_norm)
        if al is not None:
            return hay_norm[al.dest_start:al.dest_end]
    except Exception:
        pass
    return ""


def verify_quote(
    quote: str,
    source_text: str,
    min_quote_tokens: int = DEFAULT_MIN_QUOTE_TOKENS,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> QuoteCheck:
    q = normalize(quote)
    src = normalize(source_text)
    if not q or not src:
        return QuoteCheck(False, "empty", 0.0, "")
    if token_count(quote) < min_quote_tokens:
        return QuoteCheck(False, "too_short", 0.0, "")
    if q in src:
        return QuoteCheck(True, "exact", 100.0, q)
    score = float(fuzz.partial_ratio(q, src))
    if score >= fuzzy_threshold:
        return QuoteCheck(True, "fuzzy", score, _best_window(q, src))
    return QuoteCheck(False, "not_found", score, "")


def verify_contiguous(
    quote: str,
    source_text: str,
    min_quote_tokens: int = DEFAULT_MIN_QUOTE_TOKENS,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
):
    """Verify a quote; if it joins distant parts, keep the longest part that verifies.

    Parts are split at ellipses, otherwise runs of consecutive sentences are tried.
    Returns (QuoteCheck, span).
    """
    q = (quote or "").strip()
    chk = verify_quote(q, source_text, min_quote_tokens, fuzzy_threshold)
    if chk.verified:
        return chk, expand_to_sentence(q, source_text)
    parts = [x.strip() for x in re.split(r"\s*(?:\.\s*){3,}\s*|\s*…\s*", q) if x.strip()]
    if len(parts) > 1:
        for frag in sorted(parts, key=len, reverse=True):
            c2 = verify_quote(frag, source_text, min_quote_tokens, fuzzy_threshold)
            if c2.verified:
                return c2, expand_to_sentence(frag, source_text)
    run = _longest_verified_run(q, source_text, min_quote_tokens, fuzzy_threshold)
    if run is not None:
        return run
    return chk, q


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(•])")
_MAX_SENTENCES = 12


def _longest_verified_run(quote, source_text, min_quote_tokens, fuzzy_threshold):
    """The longest run of consecutive sentences of `quote` that verifies, or None."""
    sents = [x.strip() for x in _SENT_SPLIT.split(" ".join((quote or "").split())) if x.strip()]
    if len(sents) < 2 or len(sents) > _MAX_SENTENCES:
        return None
    for size in range(len(sents) - 1, 0, -1):
        for start in range(0, len(sents) - size + 1):
            cand = " ".join(sents[start:start + size])
            c = verify_quote(cand, source_text, min_quote_tokens, fuzzy_threshold)
            if c.verified:
                return c, expand_to_sentence(cand, source_text)
    return None


def expand_to_sentence(quote: str, source_text: str, max_extra: int = 400) -> str:
    """Extend a verified quote to complete words and the end of its sentence in the source."""
    q = (quote or "").strip()
    q = re.sub(r"^\[[^\]]{1,80}\]\s*", "", q)
    toks = q.split()
    if not toks or not source_text:
        return quote
    pat = r"\s+".join(re.escape(t) for t in toks)
    try:
        m = re.search(pat, source_text, flags=re.IGNORECASE)
    except re.error:
        return quote
    if not m:
        return quote
    s, e = m.start(), m.end()
    while s > 0 and not source_text[s - 1].isspace():
        s -= 1
    tail = source_text[e:min(len(source_text), e + max_extra)]
    sent_end = re.search(r"[.!?](?=\s|$)", tail)
    if sent_end:
        e += sent_end.end()
    else:
        while e < len(source_text) and not source_text[e].isspace():
            e += 1
    return " ".join(source_text[s:e].split())


def verify_pair(
    claim_quote: str,
    paper_quote: str,
    submission_text: str,
    paper_text: str,
    min_quote_tokens: int = DEFAULT_MIN_QUOTE_TOKENS,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> dict:
    """Verify both sides of an evidence pair."""
    cq = verify_quote(claim_quote, submission_text, min_quote_tokens, fuzzy_threshold)
    pq = verify_quote(paper_quote, paper_text, min_quote_tokens, fuzzy_threshold)
    return {
        "claim_quote_verified": cq.verified,
        "paper_quote_verified": pq.verified,
        "fully_verified": cq.verified and pq.verified,
        "claim_quote_check": cq.to_dict(),
        "paper_quote_check": pq.to_dict(),
    }
