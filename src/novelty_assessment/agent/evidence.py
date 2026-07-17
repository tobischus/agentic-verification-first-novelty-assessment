#!/usr/bin/env python3
"""
Deterministic two-sided quote verification (the evidence-grounding invariant).

A quote counts as VERIFIED only if it is (a) long enough (>= min_quote_tokens
words -- short spans verify trivially and could game the gate) and (b) present in
the source text, either as a normalized substring (exact) or as a fuzzy window
above a threshold (tolerates whitespace/OCR noise).

This runs OUTSIDE the judging LLM (OpenNovelty-style token-level matcher), so the
agent cannot fabricate evidence: every claim_quote is checked against the
submission text, every paper_quote against that prior paper's source text. A
`can_refute` comparison keeps that status only if it has at least one evidence
pair whose BOTH sides verify.

Reused by the read tools (integrity of passages) and by record_comparison
(gating of committed evidence). Pure/deterministic, no model calls.
"""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

# Defaults; overridable from the agent budgets / .env (see claim_agent).
DEFAULT_MIN_QUOTE_TOKENS = 10
DEFAULT_FUZZY_THRESHOLD = 90.0  # 0-100; near-verbatim (passages come from the source)


def normalize(text: str) -> str:
    """Lowercase + collapse all whitespace (same convention as artifact_a._normalize)."""
    return " ".join((text or "").lower().split())


def token_count(text: str) -> int:
    return len((text or "").split())


@dataclass
class QuoteCheck:
    verified: bool
    method: str        # exact | fuzzy | too_short | not_found | empty
    score: float       # 100 for exact, else fuzzy partial ratio (0-100)
    matched_span: str  # best-matching normalized window in the source (audit trail), or ""

    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "method": self.method,
            "score": round(self.score, 1),
            "matched_span": self.matched_span,
        }


def _best_window(needle_norm: str, hay_norm: str) -> str:
    """Return the normalized substring of `hay_norm` that best aligns to `needle_norm`."""
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
    """Check whether `quote` occurs in `source_text` (verbatim or near-verbatim)."""
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


def expand_to_sentence(quote: str, source_text: str, max_extra: int = 400) -> str:
    """Repair a truncated verbatim quote using the true source text.

    The read tools cut passages to a hard character budget, so a quote the model
    copied character-for-character can end mid-word/mid-sentence. After the quote
    verified, locate it in the source and extend it to the end of its sentence
    (bounded by max_extra), completing partial words on both ends. Returns the
    original quote whenever the span cannot be located.
    """
    q = (quote or "").strip()
    # drop a leading "[Section] " tag the model may have copied from the passage header
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
    while s > 0 and not source_text[s - 1].isspace():  # complete a partial leading word
        s -= 1
    tail = source_text[e:min(len(source_text), e + max_extra)]
    sent_end = re.search(r"[.!?](?=\s|$)", tail)
    if sent_end:
        e += sent_end.end()
    else:  # no sentence end nearby: at least finish the current word
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
    """Verify BOTH sides of an evidence pair; returns the enriched pair dict.

    A pair is fully verified only when the claim_quote is found in the submission
    AND the paper_quote is found in the prior paper's source text.
    """
    cq = verify_quote(claim_quote, submission_text, min_quote_tokens, fuzzy_threshold)
    pq = verify_quote(paper_quote, paper_text, min_quote_tokens, fuzzy_threshold)
    return {
        "claim_quote_verified": cq.verified,
        "paper_quote_verified": pq.verified,
        "fully_verified": cq.verified and pq.verified,
        "claim_quote_check": cq.to_dict(),
        "paper_quote_check": pq.to_dict(),
    }
