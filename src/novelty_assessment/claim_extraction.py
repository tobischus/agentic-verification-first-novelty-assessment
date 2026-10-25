"""Claim extraction (Section 4.3) and the claim edits of the claims checkpoint.

One call with the full text of the submission returns the claims, each with a verbatim
anchor. For each claim, a second call explains what the submission delivers for it.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import evidence as ev

load_dotenv()

DEFAULT_EXTRACTION_MODEL = os.getenv("NOVELTY_EXTRACTION_MODEL", "gpt-5.6-luna")


class _ClaimOut(BaseModel):
    claim: str = Field(description="ONE concise sentence stating this contribution, in the authors' own terminology")
    evidence: str = Field(
        description="EXACT contiguous verbatim passage from the paper stating this contribution"
    )
    anchor_index: int = Field(
        default=-1,
        description="0-based index of the authors' contribution statement this claim covers (-1 if none)",
    )


class _Claims(BaseModel):
    claims: List[_ClaimOut] = Field(default_factory=list)


class _Segment(BaseModel):
    kind: str = Field(description='"text" for your own prose, "quote" for a VERBATIM span copied character-for-character')
    content: str = Field(description="the prose, or the verbatim quote (no [Section] tag, no quotation marks)")


class _Realization(BaseModel):
    segments: List[_Segment] = Field(default_factory=list)


def _fill(template: str, **kw) -> str:
    """Placeholder substitution that tolerates literal braces in the values."""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


_PRICES = {
    "gpt-5-mini": (0.00025, 0.0020),
    "gpt-5-nano": (0.00005, 0.0004),
    "gpt-5": (0.00125, 0.0100),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1-nano": (0.0001, 0.0004),
    "gpt-4.1": (0.0020, 0.0080),
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o": (0.0025, 0.0100),
    "o4-mini": (0.0011, 0.0044),
    "o3": (0.0020, 0.0080),
    "gpt-5.6-luna": (0.0002, 0.0012),
    "gpt-5.6-terra": (0.0020, 0.0120),
    "gpt-5.6-sol": (0.0050, 0.0300),
}


def _usage(raw) -> tuple:
    um = getattr(raw, "usage_metadata", None) or {}
    if um:
        return int(um.get("input_tokens", 0) or 0), int(um.get("output_tokens", 0) or 0)
    tu = (getattr(raw, "response_metadata", {}) or {}).get("token_usage", {}) or {}
    return int(tu.get("prompt_tokens", 0) or 0), int(tu.get("completion_tokens", 0) or 0)


def _price_key(model: str):
    m = model or ""
    if m in _PRICES:
        return m
    cands = [k for k in _PRICES if m.startswith(k) and (len(m) == len(k) or m[len(k)] == "-")]
    return max(cands, key=len, default=None)


def _usd(model: str, pt: int, ct: int):
    """List-price cost in USD, or None for an unknown model."""
    key = _price_key(model)
    if key is None:
        return None
    p_in, p_out = _PRICES[key]
    return round(pt / 1000 * p_in + ct / 1000 * p_out, 4)


def _cost_block(model: str, pt: int, ct: int, n_calls: int) -> dict:
    return {"model": model, "prompt_tokens": pt, "completion_tokens": ct,
            "n_calls": n_calls, "usd": _usd(model, pt, ct)}


def _make_llm(model_name: str, temperature: float = 0.0, reasoning_effort: Optional[str] = None):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    if model_name.startswith(("gpt-5", "o1", "o3", "o4")):
        kw = {"reasoning_effort": reasoning_effort
              or os.getenv("NOVELTY_REASONING_EFFORT", "low")}
    else:
        kw = {"temperature": temperature}
    try:
        timeout = float(os.getenv("NOVELTY_LLM_TIMEOUT", "180"))
    except ValueError:
        timeout = 180.0
    try:
        max_retries = int(os.getenv("NOVELTY_LLM_MAX_RETRIES", "6"))
    except ValueError:
        max_retries = 6
    return ChatOpenAI(model_name=model_name, api_key=api_key, max_retries=max_retries,
                      timeout=timeout, **kw)


_REALIZE_FULLTEXT_PROMPT = """Explain what THE PAPER ITSELF does to realize this specific claim, using ONLY the paper text below. Describe the contribution and HOW IT IS BUILT/DESIGNED (e.g. for a benchmark: its tasks, corpora, construction, metrics) -- not a verdict, not the novelty, and not the experimental results unless the claim itself is about a finding.

The paper covers several contributions; describe only what pertains to THIS claim.

Write `segments` as a flowing explanation in reading order, alternating:
- kind="text": your own concise prose.
- kind="quote": a VERBATIM span copied CHARACTER-FOR-CHARACTER from the paper text (no section heading, no quotation marks). Use quotes for the load-bearing specifics (what is built, how). Every quote must be copyable verbatim from the text below.
Keep it to a short paragraph or two.

## Claim
{claim}

## Full text
{content}"""


def build_realization_fulltext(caller, claim_text: str, content: str,
                               source_text: str) -> List[dict]:
    """Explanation of what the submission delivers for one claim, with verified quotes."""
    parsed = caller._struct(_Realization, _fill(
        _REALIZE_FULLTEXT_PROMPT, claim=claim_text[:1200], content=content))
    segments = []
    for s in (getattr(parsed, "segments", None) or []):
        text = (s.content or "").strip()
        if not text:
            continue
        if (s.kind or "text").lower() == "quote":
            verified, repaired = caller._verify(text, source_text)
            segments.append({"kind": "quote", "verified": True, "content": repaired} if verified
                            else {"kind": "text", "verified": False, "content": text})
        else:
            segments.append({"kind": "text", "content": text})
    return segments


def _load(data_dir: str, submission_id: str):
    """Metadata and sections of the parsed submission."""
    sub = Path(data_dir) / submission_id
    meta = json.loads((sub / f"{submission_id}.json").read_text(encoding="utf-8"))
    sections = []
    ft = sub / f"{submission_id}_fulltext.json"
    if ft.exists():
        sections = json.loads(ft.read_text(encoding="utf-8")).get("sections", [])
    return meta, sections


_FREE_PROMPT = """Below is the complete text of a scientific paper.

Identify this paper's NOVELTY CLAIMS: the contributions the AUTHORS THEMSELVES put forward as their own, which together capture what this paper adds to the research literature.

What this is for, so you can judge what belongs in the set: every claim you return will afterwards be checked INDIVIDUALLY against prior work to decide whether that contribution is actually new. A claim therefore earns its place only if it is

- REALLY THE AUTHORS' OWN: something they present as their contribution -- not background, motivation, a problem statement, or work by others;
- SUBSTANTIAL: a contribution whose novelty is worth checking against the literature at all -- not a minor detail, an incidental experiment, or routine practice;
- STANDALONE: it stands on its own, rather than being a component, feature, design choice, implementation detail, intermediate result, or a rephrasing of another claim in your set.

Taken together, the set should represent the paper's contribution completely and without duplication: nothing important left out, nothing padded in, and no two claims that a reader would regard as the same contribution.

Where exactly those lines fall differs from paper to paper -- use your own judgement for THIS one, including how many claims that turns out to be and how to phrase each. Stay faithful to what the authors actually claim; do not strengthen or generalise it.

For each claim give:
- claim: one clear sentence.
- evidence: an exact CONTIGUOUS verbatim passage from the paper text below, copied character-for-character, that states this contribution.

## Paper title
{title}

## Full text
{content}"""


class ClaimExtractor:
    """Claims from the full text in one call, then one explanation call per claim."""

    def __init__(self, model_name: str = DEFAULT_EXTRACTION_MODEL, reasoning_effort: str = "high",
                 max_chars: int = 400000,
                 min_quote_tokens: int = ev.DEFAULT_MIN_QUOTE_TOKENS,
                 fuzzy_threshold: float = ev.DEFAULT_FUZZY_THRESHOLD):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.max_chars = max_chars
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.llm = _make_llm(model_name, reasoning_effort=reasoning_effort)
        self._pt = self._ct = self._calls = 0

    def _struct(self, schema, prompt):
        """Structured call with token accounting; None on failure."""
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    def _verify(self, quote: str, source: str) -> tuple:
        """(verified, quote completed to its sentence) against the submission text."""
        chk = ev.verify_quote(quote, source, self.min_quote_tokens, self.fuzzy_threshold)
        if chk.verified:
            return True, ev.expand_to_sentence(quote, source)
        return False, quote

    def extract(self, data_dir: str, submission_id: str,
                out_name: Optional[str] = None) -> dict:
        self._pt = self._ct = self._calls = 0
        meta, sections = _load(data_dir, submission_id)
        title = meta.get("title", "") or ""
        abstract = (meta.get("abstract", "") or "").strip()

        body = "\n\n".join(
            (f"## {(s.get('section') or '').strip()}\n{(s.get('text') or '').strip()}"
             if (s.get("section") or "").strip() else (s.get("text") or "").strip())
            for s in sections if (s.get("text") or "").strip()
        )
        content = (f"Abstract:\n{abstract}\n\n{body}" if abstract else body)[: self.max_chars]
        source_text = "\n\n".join([s.get("text", "") for s in sections] + [abstract])

        parsed = self._struct(_Claims, _fill(_FREE_PROMPT, title=title, content=content))

        claims = []
        for i, c in enumerate(getattr(parsed, "claims", None) or [], 1):
            claim_text = (getattr(c, "claim", "") or "").strip()
            if not claim_text:
                continue
            quote = (getattr(c, "evidence", "") or "").strip()
            verified, repaired = self._verify(quote, source_text) if quote else (False, quote)
            segments = build_realization_fulltext(self, claim_text, content, source_text)
            claims.append({
                "id": f"claim_{i}",
                "name": " ".join(claim_text.split()[:12]),
                "claim_text": claim_text,
                "evidence_quote": repaired,
                "evidence_verified": verified,
                "contribution_statement": "",
                "contribution_statement_verified": False,
                "anchor_index": -1,
                "realization": segments,
                "description": claim_text,
                "source": "",
                "origin": "llm",
                "status": "pending",
            })

        doc = {
            "submission_id": submission_id,
            "title": title,
            "publication_date": meta.get("publication_date"),
            "year": meta.get("year"),
            "date_source": meta.get("date_source"),
            "extraction_scope": "free_fulltext",
            "extraction": {
                "model": self.model_name,
                "mode": "free_fulltext",
                "reasoning_effort": self.reasoning_effort,
                "content_chars": len(content),
                "truncated": len(content) >= self.max_chars,
                "n_sections": len(sections),
                "realization": True,
                "realization_mode": "fulltext",
                "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls),
            },
            "claims": claims,
        }
        out = Path(data_dir) / submission_id / (out_name or f"{submission_id}_claims.json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc


def _find(doc: dict, claim_id: str) -> dict:
    for c in doc["claims"]:
        if c["id"] == claim_id:
            return c
    raise KeyError(f"claim not found: {claim_id}")


def accept_claim(doc: dict, claim_id: str) -> dict:
    _find(doc, claim_id)["status"] = "accepted"
    return doc


def edit_claim(doc: dict, claim_id: str, **fields) -> dict:
    """Edit a claim. Its anchor is kept and its explanation is cleared."""
    c = _find(doc, claim_id)
    for k, v in fields.items():
        if k in ("name", "claim_text", "description", "source"):
            c[k] = v
    c["status"] = "edited"
    if "claim_text" in fields or "description" in fields:
        c["realization"] = []
    return doc


def delete_claim(doc: dict, claim_id: str) -> dict:
    _find(doc, claim_id)["status"] = "rejected"
    return doc


def add_claim(
    doc: dict, name: str, claim_text: str = "", description: str = "", source: str = "reviewer"
) -> dict:
    """Add a reviewer claim without an anchor."""
    existing = {c["id"] for c in doc["claims"]}
    i = len(doc["claims"]) + 1
    while f"claim_{i}" in existing:
        i += 1
    doc["claims"].append(
        {
            "id": f"claim_{i}",
            "name": name,
            "claim_text": claim_text,
            "evidence_quote": "",
            "evidence_verified": False,
            "contribution_statement": "",
            "contribution_statement_verified": False,
            "anchor_index": -1,
            "realization": [],
            "description": description,
            "source": source,
            "origin": "reviewer",
            "status": "accepted",
        }
    )
    return doc


def main():
    ap = argparse.ArgumentParser(description="Claim extraction")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default=DEFAULT_EXTRACTION_MODEL)
    ap.add_argument("--reasoning-effort", default="high")
    ap.add_argument("--out-name", default=None)
    args = ap.parse_args()

    doc = ClaimExtractor(model_name=args.model, reasoning_effort=args.reasoning_effort).extract(
        args.data_dir, args.submission_id, out_name=args.out_name)
    print(f"Title: {doc.get('title')}  |  date (cutoff): {doc.get('publication_date')}")
    print(f"\nClaims ({len(doc['claims'])}):")
    for c in doc["claims"]:
        print(f"  [{c['id']}] {c['claim_text']}")
        v = "verified" if c.get("evidence_verified") else "UNVERIFIED"
        print(f"        evidence ({v}): {(c.get('evidence_quote') or '')[:160]}")


if __name__ == "__main__":
    main()
