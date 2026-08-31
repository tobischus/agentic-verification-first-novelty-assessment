#!/usr/bin/env python3
"""
Step 2: Claim & Paper Understanding Extraction.

Produces {id}_claims.json: the CANONICAL claim artifact of the pipeline. It feeds
(a) the per-claim novelty agent, (b) Stage-A evaluation (extraction quality) and
(c) Stage-B "fixed claims" injected into the comparison systems -- so its accuracy
and completeness are load-bearing, not cosmetic.

THE PIPELINE'S EXTRACTOR: `FullTextClaimExtractor` (= `ClaimExtractor`)
----------------------------------------------------------------------
The whole paper goes into ONE unconstrained call to a strong reasoning model, which
decides for itself which contributions are genuinely the authors' own, substantial
and standalone -- no anchor extraction, no section selection, no exclusion rules.
Then, per claim, the whole paper goes in again -- ONE call -- to produce a
verified-quote `realization` of what the submission actually does for that claim
(build_realization_fulltext; `realize=False` for claim-only runs). The provenance a
reviewer needs is the verified quotes themselves -- each one is checked against the
paper text, so it can be looked up directly.

The alternative -- a section menu, a model-picked subset, then reading those in full
(build_realization, `realization_mode="sections"`) -- was inherited from the losing
extractor and measured against this one on 18 claims: full text won the blind
pairwise comparison 8:3 with half the calls, while the section variant kept a
slightly better quote-verification rate (96.8% vs 93.0%).

This deliberately simple design was chosen on evidence, not taste. In the Stage-A
evaluation it beat the engineered anchor-first, section-reading extractor 7:0 in the
blind pairwise comparison at ~1/5 of the cost, and three established inference-time
techniques (self-consistency, chain-of-verification, self-refine -- claim_methods.py)
each failed to beat it in turn. The scaffolding's own guards were what cost recall.

The one invariant kept from the engineered design: every evidence quote and every
realization quote is verified against the real paper text by the SAME deterministic
matcher the agent uses (agent/evidence.py). An unverifiable span is never presented
as verbatim -- realization quotes that cannot be located are demoted to plain prose.

ABLATIONS (kept for the thesis, not used by the pipeline)
--------------------------------------------------------
  DeepClaimExtractor     anchor-first + targeted section reading, four phases
                         (anchor -> claims -> coverage repair -> realize)
  ShallowClaimExtractor  the original one-shot prompt over abstract + introduction
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
from agent.passages import PassageIndex, chunks_from_sections

load_dotenv()

# How much of the paper's leading region counts as "the introduction" (GROBID often
# mis-splits the intro into unnamed sections, so the authors' contribution paragraph
# can land outside the titled section -- take the leading region, not the title match).
_LEAD_CHARS = 20000


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class _AnchorStatement(BaseModel):
    text: str = Field(
        description="EXACT verbatim span from the paper stating ONE contribution, copied character-for-character"
    )
    where: str = Field(default="", description="where it came from, e.g. 'introduction contributions list'")


class _Anchor(BaseModel):
    """The authors' own contribution statements, verbatim."""

    has_explicit_list: bool = Field(
        description="true if the paper has an explicit contributions statement/list (e.g. 'Our contributions are')"
    )
    statements: List[_AnchorStatement] = Field(
        default_factory=list, description="one entry per contribution the authors state"
    )


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


class _SectionPick(BaseModel):
    sections: List[str] = Field(description="exact section titles to read in full, most relevant first")


class _Segment(BaseModel):
    kind: str = Field(description='"text" for your own prose, "quote" for a VERBATIM span copied character-for-character')
    content: str = Field(description="the prose, or the verbatim quote (no [Section] tag, no quotation marks)")


class _Realization(BaseModel):
    segments: List[_Segment] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

_ANCHOR_PROMPT = """You are locating the CONTRIBUTION STATEMENTS of a scientific paper: the sentences in which the AUTHORS THEMSELVES say what their contribution is.

Your ONLY job is to COPY what is already written. Do not summarize, do not rephrase, do not merge, do not add anything the authors did not write.

FIRST look for an EXPLICIT contributions statement in the introduction -- a paragraph or list beginning "Our contributions", "We make the following contributions", "In summary, our contributions are", "In this paper we (1) ... (2) ...", or an enumerated list (1)/(i)/❶/bullets -- usually near the END of the introduction. If it exists, set has_explicit_list=true and return ONE statement per enumerated contribution, each copied VERBATIM (the enumerated item's own text; do not merge two items into one entry, do not split one item into two).

If NO explicit contributions statement exists, set has_explicit_list=false and instead return the authors' individual contribution sentences from the abstract/introduction -- the "we propose / we introduce / we present / we show / we find / we are the first" sentences that state something the authors did.

CRITICAL -- an enumeration is NOT automatically a contribution list. Distinguish:
- A CONTRIBUTION list enumerates DIFFERENT THINGS THE AUTHORS DID ("we propose X; we show Y; we release Z"). Each item gets its own statement.
- A FEATURE list enumerates the PARTS, PROPERTIES or COMPONENTS OF ONE ARTIFACT ("Our benchmark features ❶ diverse corpora, ❷ tasks of increasing difficulty, ❸ evaluation across the pipeline"; "our method consists of (i) ..., (ii) ..."). That is ONE contribution. Return the WHOLE sentence as a SINGLE statement -- never one statement per feature.
  Test: if the items are things the artifact HAS/CONTAINS rather than things the authors DID, it is a feature list.

Each statement MUST:
- be copyable character-for-character from the paper text below (a sentence or a few consecutive sentences from the SAME place); never stitch together text from different places;
- start at a sentence boundary and be self-contained -- do NOT start mid-sentence or mid-enumeration;
- be a SEPARATE, NON-OVERLAPPING span: no statement may contain, or be contained in, another. Never return the same sentence twice cut at different points.

## Paper title
{title}

## Paper text (abstract + leading part of the paper)
{content}"""


_CLAIMS_PROMPT = """You are turning a paper's CONTRIBUTION STATEMENTS into the list of NOVELTY CLAIMS to be assessed against prior work.

The authors' statements below are the ANCHOR: the claims must reflect exactly what the authors say they contribute. Do NOT strengthen, generalize, or "improve" a contribution, and never invent one that is not stated.

A novelty claim is a contribution whose NOVELTY is worth assessing on its own: a new method, model, architecture, algorithm, framework, task, benchmark, dataset, theoretical result, or problem formulation -- OR an empirical finding, analysis, or practical guideline the authors frame as a contribution.

STRICT exclusions -- these are NOT standalone claims, even when a contribution statement mentions them:
- auxiliary evaluation steps or extra measurements that merely support another contribution ("we also measure transferability", "we conduct ablations", "we report additional metrics"): fold them into the claim they support, or drop them.
- releasing code or trained models ("we release our code and models") -- standard practice. EXCEPTION: a released dataset/benchmark the paper presents as a contribution in itself.
- restatements of another claim at a different level of detail, and sub-parts of one artifact (a benchmark and its corpora/tasks/metrics, or a method and its components, is ONE claim).
- descriptions of HOW a proposed method/artifact works (its objectives, components, design choices) -- that detail belongs INSIDE the method claim, never as a separate claim.

ATOMICITY: one contribution per claim. If a SINGLE contribution statement bundles two genuinely different substantive contributions (e.g. "we propose a benchmark AND we show that X"), split it into two claims that BOTH point to that statement's index.
DISTINCTNESS: two claims must not be two phrasings of the same contribution. Building an artifact and using that same artifact for its intended purpose is ONE contribution -- unless the authors present the findings/guidelines obtained with it as a separate contribution of their own.
COVERAGE: every contribution statement below must be covered by at least one claim.

For each claim give:
- claim: ONE concise sentence in the authors' own terminology.
- evidence: an EXACT contiguous verbatim passage from the paper text, copied character-for-character, that states this contribution (prefer the anchor statement itself).
- anchor_index: the 0-based index of the contribution statement it covers.

## Paper title
{title}

## The authors' contribution statements (the ANCHOR; index: text)
{anchors}

## Paper text (for copying verbatim evidence)
{content}"""


_REPAIR_PROMPT = """Some of the authors' contribution statements are NOT yet covered by any claim. Add the MISSING claims -- only for the statements listed below, nothing else.

Apply the same rules: stay faithful to the authors' wording, one contribution per claim, and skip a statement ONLY if it is genuinely not a standalone novelty contribution under the strict exclusions (auxiliary experiments, code release, a restatement or sub-part of another contribution, or a description of how a proposed artifact works). If a statement should be skipped for one of those reasons, simply return no claim for it.

For each added claim give claim, evidence (EXACT verbatim passage from the paper text), and anchor_index.

## Paper title
{title}

## Claims already extracted
{existing}

## UNCOVERED contribution statements (index: text)
{anchors}

## Paper text (for copying verbatim evidence)
{content}"""


_SECTION_PICK_PROMPT = """A paper makes ONE specific claimed contribution (below). You will explain what THE PAPER ITSELF does to realize exactly THIS claim -- e.g. if the claim proposes a benchmark, the construction/design of that benchmark; if it claims an empirical finding, the analysis that produces it.

Choose the section titles whose FULL text you need for that. Section titles say what each section is about; pick the ones about the claimed contribution itself (definition, design, construction, method, or the analysis the claim is about) and skip unrelated experiments, related work, and limitations.

## Claim
{claim}

## Sections (title :: preview :: size)
{sections}

Return `sections`: the exact titles to read in full (usually 2-5)."""


_REALIZE_PROMPT = """Explain what THE PAPER ITSELF does to realize this specific claim, using ONLY the section text below. Describe the contribution and HOW IT IS BUILT/DESIGNED (e.g. for a benchmark: its tasks, corpora, construction, metrics) -- not a verdict, not the novelty, and not the experimental results unless the claim itself is about a finding.

Write `segments` as a flowing explanation in reading order, alternating:
- kind="text": your own concise prose.
- kind="quote": a VERBATIM span copied CHARACTER-FOR-CHARACTER from the section text (no [Section] tag, no quotation marks). Use quotes for the load-bearing specifics (what is built, how). Every quote must be copyable verbatim from the text below.
Keep it to a short paragraph or two.

## Claim
{claim}

## Sections (full text)
{sections}"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _fill(template: str, **kw) -> str:
    """Sequential {key}->value substitution tolerant of literal braces in the values
    (section text can contain { } from math/code, which str.format would choke on)."""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _fmt_sections_menu(menu: List[dict]) -> str:
    return "\n".join(
        f"- {m['name']} :: {m.get('preview', '')[:160]} :: ~{m.get('chars', 0)} chars" for m in menu
    ) or "(no sections)"


def _fmt_sections_full(sections: List[dict], max_total: int = 24000) -> str:
    out, used = [], 0
    for s in sections or []:
        block = f"## {s['name']}\n{s['text']}"
        if used + len(block) > max_total:
            block = block[: max(0, max_total - used)]
        out.append(block)
        used += len(block)
        if used >= max_total:
            break
    return "\n\n".join(out) if out else "(no section text)"


# USD per 1k tokens (input, output); longest matching prefix wins. Models absent here
# report token counts with usd=None rather than a made-up number.
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
    # gpt-5.6 family (short-context tier: our papers are ~17k tokens, far below the
    # long-context threshold). Published per 1M tokens; divided by 1000 here.
    "gpt-5.6-luna": (0.0002, 0.0012),
    "gpt-5.6-terra": (0.0020, 0.0120),
    "gpt-5.6-sol": (0.0050, 0.0300),
}


def _usage(raw) -> tuple:
    """(prompt_tokens, completion_tokens) from a langchain raw response."""
    um = getattr(raw, "usage_metadata", None) or {}
    if um:
        return int(um.get("input_tokens", 0) or 0), int(um.get("output_tokens", 0) or 0)
    tu = (getattr(raw, "response_metadata", {}) or {}).get("token_usage", {}) or {}
    return int(tu.get("prompt_tokens", 0) or 0), int(tu.get("completion_tokens", 0) or 0)


def _price_key(model: str):
    """Longest matching price key, matching only at a VARIANT boundary.

    A bare prefix test is wrong across model generations: "gpt-5.6-luna".startswith("gpt-5")
    is true, so luna would silently be billed at gpt-5 rates. A prefix therefore only counts
    when what follows is a dated/variant suffix ("gpt-5-mini-2025-08-07" -> "gpt-5-mini"),
    never a different version number ("gpt-5.6-..." is NOT "gpt-5").
    """
    m = model or ""
    if m in _PRICES:
        return m
    cands = [k for k in _PRICES if m.startswith(k) and (len(m) == len(k) or m[len(k)] == "-")]
    return max(cands, key=len, default=None)


def _usd(model: str, pt: int, ct: int):
    """Cost in USD, or None when the model's price is not known to this table."""
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
    # Reasoning models (gpt-5*, o-series) reject a custom temperature; cap their effort
    # so extraction stays fast (same convention as the per-claim agent).
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
    """Same output as build_realization, but the model sees the WHOLE paper and picks the
    relevant parts itself -- no section menu, no pre-selection, ONE call instead of two.

    Consistent with how the claims themselves are extracted."""
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


def build_realization(caller, claim_text: str, index: PassageIndex, source_text: str,
                      fallback_k: int = 4) -> List[dict]:
    """What the SUBMISSION itself does for ONE claim: pick the sections that describe this
    contribution, read them IN FULL, and return (segments, section_names).

    `segments` alternate the model's own prose with VERBATIM quotes from those sections;
    a quote that cannot be located in the paper is demoted to prose, so nothing is ever
    presented as verbatim without being verified (same rule as the agent's
    `verify_segments`). Two model calls: section pick + realization.

    Shared by both extractors -- `caller` only has to provide `_struct(schema, prompt)`
    and `_verify(quote, source_text)`. Computing this at EXTRACTION time (rather than in
    the per-claim agent) means it is produced once, reviewable at the HITL checkpoint, and
    reused unchanged by every prior-work comparison.
    """
    menu = index.section_previews()
    if not menu:
        return []
    picked = caller._struct(_SectionPick, _fill(
        _SECTION_PICK_PROMPT, claim=claim_text[:1200], sections=_fmt_sections_menu(menu)))
    names = [s for s in (getattr(picked, "sections", None) or []) if s]
    if not names:  # model gave nothing usable -> take the biggest sections
        names = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:fallback_k]]
    secs = index.get_sections(names)
    if not secs:
        return []
    parsed = caller._struct(_Realization, _fill(
        _REALIZE_PROMPT, claim=claim_text[:1200], sections=_fmt_sections_full(secs)))
    segments = []
    for s in (getattr(parsed, "segments", None) or []):
        content = (s.content or "").strip()
        if not content:
            continue
        if (s.kind or "text").lower() == "quote":
            verified, repaired = caller._verify(content, source_text)
            segments.append({"kind": "quote", "verified": True, "content": repaired} if verified
                            else {"kind": "text", "verified": False, "content": content})
        else:
            segments.append({"kind": "text", "content": content})
    return segments


# --------------------------------------------------------------------------- #
# Deep extractor
# --------------------------------------------------------------------------- #


class DeepClaimExtractor:
    """Anchor-first, section-reading claim extraction (Step 2)."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0,
                 min_quote_tokens: int = ev.DEFAULT_MIN_QUOTE_TOKENS,
                 fuzzy_threshold: float = ev.DEFAULT_FUZZY_THRESHOLD):
        self.model_name = model_name
        self.llm = _make_llm(model_name, temperature)
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self._pt = self._ct = self._calls = 0   # token accounting across all phases

    # ------------------------------ plumbing ------------------------------ #

    def _struct(self, schema, prompt):
        """Structured call; returns None instead of raising on a parse failure."""
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    @staticmethod
    def _load(data_dir: str, submission_id: str):
        """Load metadata + the submission's section structure (Step-1 outputs)."""
        sub = Path(data_dir) / submission_id
        meta = json.loads((sub / f"{submission_id}.json").read_text(encoding="utf-8"))
        sections = []
        ft = sub / f"{submission_id}_fulltext.json"
        if ft.exists():
            sections = json.loads(ft.read_text(encoding="utf-8")).get("sections", [])
        return meta, sections

    @staticmethod
    def _lead_text(sections: List[dict], limit: int = _LEAD_CHARS) -> str:
        """The LEADING region of the body in document order (the 'introduction').

        Matching only the section TITLED 'Introduction' is not enough: GROBID often
        mis-splits the intro into unnamed sections, so the authors' contributions
        paragraph at the end of the intro can land OUTSIDE the titled section."""
        lead, used = [], 0
        for s in sections:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            head = (s.get("section") or "").strip()
            block = f"[{head}]\n{text}" if head else text
            lead.append(block)
            used += len(block)
            if used >= limit:
                break
        return "\n\n".join(lead)

    def _verify(self, quote: str, source: str) -> tuple:
        """(verified, repaired_quote) against the real paper text."""
        chk = ev.verify_quote(quote, source, self.min_quote_tokens, self.fuzzy_threshold)
        if chk.verified:
            return True, ev.expand_to_sentence(quote, source)
        return False, quote

    # ------------------------------- phases ------------------------------- #

    @staticmethod
    def _span(text: str, src_norm: str):
        """(start, end) of `text` inside the normalized source, or None."""
        n = ev.normalize(text)
        if not n:
            return None
        pos = src_norm.find(n)
        return (pos, pos + len(n)) if pos >= 0 else None

    @classmethod
    def _map_to_anchors(cls, claims: List[dict], statements: List[dict], source_text: str) -> List[dict]:
        """Assign each claim the anchor statement it actually covers, by SPAN OVERLAP.

        The model fills `anchor_index` unreliably (it returns -1 even for a claim quoting
        the anchor sentence verbatim), which would make the coverage metric lie. Since
        both the claim's evidence quote and the anchor statements are verbatim spans of
        the same paper, the covered statement is simply the one whose span overlaps the
        evidence quote the most -- deterministic and model-independent. The model's own
        index is kept only as a fallback when the quote cannot be located."""
        src = ev.normalize(source_text)
        spans = [cls._span(s["text"], src) for s in statements]
        for c in claims:
            got = cls._span(c.get("evidence_quote", ""), src)
            if got is None:
                continue  # unverifiable quote -> keep whatever the model said
            best, best_ov = -1, 0
            for i, sp in enumerate(spans):
                if sp is None:
                    continue
                ov = min(got[1], sp[1]) - max(got[0], sp[0])
                if ov > best_ov:
                    best, best_ov = i, ov
            if best >= 0:
                c["anchor_index"] = best
        return claims

    @staticmethod
    def _dedupe_anchors(statements: List[dict], source_text: str) -> List[dict]:
        """Drop anchor statements that are fragments of one another.

        Models reliably fail on ONE pattern: an enumeration of an artifact's FEATURES
        ("X features 1 ..., 2 ..., 3 ...") gets returned as several 'contributions',
        each a suffix of the same sentence -- nested, overlapping spans. Locating every
        statement in the source and keeping only non-overlapping spans (longest first)
        removes those deterministically, whatever the model did."""
        src = ev.normalize(source_text)
        located, unlocated = [], []
        for s in statements:
            pos = src.find(ev.normalize(s["text"]))
            if pos < 0:
                unlocated.append(s)  # not findable (unverified) -> keep, cannot compare
            else:
                located.append((pos, pos + len(ev.normalize(s["text"])), s))
        kept: List[tuple] = []
        for start, end, s in sorted(located, key=lambda t: -(t[1] - t[0])):  # longest first
            if any(start < k_end and k_start < end for k_start, k_end, _ in kept):
                continue  # overlaps an already-kept statement -> same statement, cut differently
            kept.append((start, end, s))
        return [s for _, _, s in sorted(kept, key=lambda t: t[0])] + unlocated  # document order

    def _anchor(self, title: str, content: str, source_text: str) -> dict:
        """Phase A: the authors' own contribution statements, verbatim + verified."""
        parsed = self._struct(_Anchor, _fill(_ANCHOR_PROMPT, title=title, content=content))
        statements = []
        for s in (getattr(parsed, "statements", None) or []):
            text = (s.text or "").strip()
            if not text:
                continue
            verified, repaired = self._verify(text, source_text)
            statements.append({
                "text": repaired if verified else text,
                "where": (s.where or "").strip(),
                "verified": verified,
            })
        n_raw = len(statements)
        statements = self._dedupe_anchors(statements, source_text)
        return {
            "has_explicit_list": bool(getattr(parsed, "has_explicit_list", False)),
            "statements": statements,
            "n_dropped_as_fragments": n_raw - len(statements),
        }

    def _claims(self, title: str, anchor: dict, content: str) -> List[dict]:
        """Phase B: atomic claims derived from the anchor statements."""
        anchors = "\n".join(f"{i}: {s['text']}" for i, s in enumerate(anchor["statements"])) or "(none found)"
        parsed = self._struct(_Claims, _fill(_CLAIMS_PROMPT, title=title, anchors=anchors, content=content))
        return self._normalize_claims(getattr(parsed, "claims", None) or [], len(anchor["statements"]))

    @staticmethod
    def _normalize_claims(raw, n_anchors: int) -> List[dict]:
        out = []
        for c in raw:
            claim_text = (getattr(c, "claim", "") or "").strip()
            if not claim_text:
                continue
            idx = int(getattr(c, "anchor_index", -1) or -1)
            out.append({
                "claim_text": claim_text,
                "evidence_quote": (getattr(c, "evidence", "") or "").strip(),
                "anchor_index": idx if 0 <= idx < n_anchors else -1,
            })
        return out

    def _coverage_repair(self, title: str, anchor: dict, content: str, claims: List[dict]) -> List[dict]:
        """Phase C: one repair pass for anchor statements no claim covers."""
        covered = {c["anchor_index"] for c in claims if c["anchor_index"] >= 0}
        missing = [i for i in range(len(anchor["statements"])) if i not in covered]
        if not missing:
            return claims
        parsed = self._struct(_Claims, _fill(
            _REPAIR_PROMPT, title=title,
            existing="\n".join(f"- {c['claim_text']}" for c in claims) or "(none)",
            anchors="\n".join(f"{i}: {anchor['statements'][i]['text']}" for i in missing),
            content=content,
        ))
        added = self._normalize_claims(getattr(parsed, "claims", None) or [], len(anchor["statements"]))
        # only accept additions that actually target a missing statement
        return claims + [c for c in added if c["anchor_index"] in missing]

    def _realize(self, claim_text: str, index: PassageIndex, source_text: str) -> List[dict]:
        """Phase D -- see build_realization()."""
        return build_realization(self, claim_text, index, source_text)

    # -------------------------------- run --------------------------------- #

    def extract(self, data_dir: str, submission_id: str, realize: bool = True,
                out_name: Optional[str] = None) -> dict:
        """Run the four phases and write {id}_claims.json (or `out_name`, for eval runs)."""
        self._pt = self._ct = self._calls = 0
        meta, sections = self._load(data_dir, submission_id)
        title = meta.get("title", "") or ""
        abstract = (meta.get("abstract", "") or "").strip()
        lead = self._lead_text(sections)

        index = PassageIndex(chunks_from_sections(sections, "submission"), embedder=None)
        # everything a quote may be verified against (whole body + abstract)
        source_text = "\n\n".join([s.get("text", "") for s in sections] + [abstract])

        content = "\n\n".join(p for p in (
            f"Abstract:\n{abstract}" if abstract else "",
            f"Introduction (leading part of the paper):\n{lead}" if lead else "",
        ) if p)

        # A. anchor -> B. claims -> C. coverage repair
        # (the claim->statement mapping is recomputed from spans after each step, so the
        # repair pass and the coverage metric both work off the true mapping)
        anchor = self._anchor(title, content, source_text)
        claims = self._map_to_anchors(self._claims(title, anchor, content),
                                      anchor["statements"], source_text)
        if anchor["statements"]:
            claims = self._map_to_anchors(
                self._coverage_repair(title, anchor, content, claims),
                anchor["statements"], source_text)

        covered = {c["anchor_index"] for c in claims if c["anchor_index"] >= 0}
        uncovered = [i for i in range(len(anchor["statements"])) if i not in covered]

        # D. per-claim targeted reading (the submission understanding the agent used to
        #    re-derive per claim); skipped with realize=False for a cheap claims-only run
        out_claims = []
        for i, c in enumerate(claims, 1):
            quote = c["evidence_quote"]
            q_verified, q_repaired = self._verify(quote, source_text) if quote else (False, quote)
            ai = c["anchor_index"]
            stmt = anchor["statements"][ai] if ai >= 0 else None
            segments = self._realize(c["claim_text"], index, source_text) if realize else []
            out_claims.append({
                "id": f"claim_{i}",
                # name/description stay derived from the claim: downstream (agent,
                # retrieval, report) reads them and must keep working unchanged
                "name": " ".join(c["claim_text"].split()[:12]),
                "claim_text": c["claim_text"],
                "evidence_quote": q_repaired,
                "evidence_verified": q_verified,
                # the authors' OWN statement this claim is anchored in -- the Stage-A
                # reference, and the guard against inflated/invented claims
                "contribution_statement": (stmt or {}).get("text", ""),
                "contribution_statement_verified": bool((stmt or {}).get("verified", False)),
                "anchor_index": ai,
                # what the submission itself does for this claim (verified-quote segments)
                # + which sections were read in full to establish it
                "realization": segments,
                "description": c["claim_text"],
                "source": "",
                "origin": "llm",
                "status": "pending",  # HITL: pending -> accepted/edited/rejected
            })

        doc = {
            "submission_id": submission_id,
            "title": title,
            "publication_date": meta.get("publication_date"),
            "year": meta.get("year"),
            "date_source": meta.get("date_source"),
            "extraction_scope": "deep_anchored_sections",
            "extraction": {
                "model": self.model_name,
                "has_explicit_contribution_list": anchor["has_explicit_list"],
                "anchor_statements": anchor["statements"],
                # nested/overlapping spans the model returned as separate "contributions"
                # (usually one artifact's feature list), removed deterministically
                "n_anchors_dropped_as_fragments": anchor.get("n_dropped_as_fragments", 0),
                "coverage": {
                    "n_anchor_statements": len(anchor["statements"]),
                    "n_covered": len(covered),
                    # statements deliberately or accidentally left without a claim --
                    # surfaced, never silently dropped
                    "uncovered_indices": uncovered,
                },
                "sections_available": index.section_names(),
                "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls),
            },
            "claims": out_claims,
        }
        out_path = Path(data_dir) / submission_id / (out_name or f"{submission_id}_claims.json")
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc


# --------------------------------------------------------------------------- #
# Free full-text extractor
#
# The opposite design bet to DeepClaimExtractor: instead of decomposing the task
# (anchor -> claims -> coverage repair -> per-claim section reading), give a strong
# reasoning model the WHOLE paper and ONE goal -- the set of claims that together best
# capture what the paper contributes -- and let it decide everything else.
#
# Deliberately unconstrained: no anchor, no section selection, no exclusion rules, no
# atomicity/coverage machinery. The only requirement kept is the verbatim evidence quote,
# because the verification-first invariant (and the groundedness metric) depend on it.
#
# It stores no `realization`, so the per-claim agent derives the submission understanding
# on the fly for these claims (the reviewer-added-claim fallback path).
# --------------------------------------------------------------------------- #

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


def load_paper_for_extraction(data_dir: str, submission_id: str, max_chars: int = 400000):
    """(meta, title, content, source_text) for whole-paper extraction.

    `content` is the paper in document order (abstract + body with section headings);
    `source_text` is what a verbatim quote is verified against. Shared by every
    whole-paper method so they all see EXACTLY the same input -- a prerequisite for
    comparing the methods rather than their preprocessing."""
    meta, sections = DeepClaimExtractor._load(data_dir, submission_id)
    title = meta.get("title", "") or ""
    abstract = (meta.get("abstract", "") or "").strip()
    body = "\n\n".join(
        (f"## {(sec.get('section') or '').strip()}\n{(sec.get('text') or '').strip()}"
         if (sec.get("section") or "").strip() else (sec.get("text") or "").strip())
        for sec in sections if (sec.get("text") or "").strip()
    )
    content = (f"Abstract:\n{abstract}\n\n{body}" if abstract else body)[:max_chars]
    source_text = "\n\n".join([sec.get("text", "") for sec in sections] + [abstract])
    return meta, title, content, source_text


def claims_to_doc(submission_id: str, meta: dict, title: str, raw_claims, source_text: str,
                  mode: str, extra: Optional[dict] = None) -> dict:
    """Normalise (claim, evidence) pairs into the canonical claim-artifact shape,
    verifying every evidence quote against the paper (verification-first invariant)."""
    claims = []
    for i, c in enumerate(raw_claims or [], 1):
        claim_text = ((c.get("claim") if isinstance(c, dict) else getattr(c, "claim", "")) or "").strip()
        if not claim_text:
            continue
        quote = ((c.get("evidence") if isinstance(c, dict) else getattr(c, "evidence", "")) or "").strip()
        verified = bool(quote) and ev.verify_quote(quote, source_text).verified
        claims.append({
            "id": f"claim_{i}",
            "name": " ".join(claim_text.split()[:12]),
            "claim_text": claim_text,
            "evidence_quote": ev.expand_to_sentence(quote, source_text) if verified else quote,
            "evidence_verified": verified,
            "contribution_statement": "", "contribution_statement_verified": False,
            "anchor_index": -1, "realization": [],
            "description": claim_text, "source": "", "origin": "llm", "status": "pending",
        })
    return {
        "submission_id": submission_id,
        "title": title,
        "publication_date": meta.get("publication_date"),
        "year": meta.get("year"),
        "date_source": meta.get("date_source"),
        "extraction_scope": mode,
        "extraction": {"mode": mode, **(extra or {})},
        "claims": claims,
    }


class FullTextClaimExtractor:
    """Whole paper in, claim set out -- one free call to a strong reasoning model."""

    def __init__(self, model_name: str = "gpt-5", reasoning_effort: str = "high",
                 max_chars: int = 400000, realize: bool = True,
                 realization_mode: str = "fulltext",
                 min_quote_tokens: int = ev.DEFAULT_MIN_QUOTE_TOKENS,
                 fuzzy_threshold: float = ev.DEFAULT_FUZZY_THRESHOLD):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.max_chars = max_chars
        # Also read, per claim, what the submission itself does for it (build_realization).
        # On by default: it is what every prior-work comparison is given as context, and
        # producing it here makes it reviewable at the HITL checkpoint and reused across
        # runs instead of re-derived by the agent on every claim computation.
        # Stage-A evaluation runs turn it off -- they compare claim TEXT only.
        self.realize = realize
        # "fulltext": one call, whole paper (consistent with how the claims are extracted).
        # "sections": section menu -> pick -> read in full, two calls (the older variant,
        # inherited from DeepClaimExtractor; kept so the two can be compared).
        self.realization_mode = realization_mode
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.llm = _make_llm(model_name, reasoning_effort=reasoning_effort)
        self._pt = self._ct = self._calls = 0

    def _struct(self, schema, prompt):
        """Structured call with token accounting; None instead of raising on failure."""
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    def _verify(self, quote: str, source: str) -> tuple:
        """(verified, repaired_quote) against the real paper text."""
        chk = ev.verify_quote(quote, source, self.min_quote_tokens, self.fuzzy_threshold)
        if chk.verified:
            return True, ev.expand_to_sentence(quote, source)
        return False, quote

    def extract(self, data_dir: str, submission_id: str,
                out_name: Optional[str] = None) -> dict:
        self._pt = self._ct = self._calls = 0
        meta, sections = DeepClaimExtractor._load(data_dir, submission_id)
        title = meta.get("title", "") or ""
        abstract = (meta.get("abstract", "") or "").strip()

        # the WHOLE paper, in document order, section headings kept for readability
        body = "\n\n".join(
            (f"## {(s.get('section') or '').strip()}\n{(s.get('text') or '').strip()}"
             if (s.get("section") or "").strip() else (s.get("text") or "").strip())
            for s in sections if (s.get("text") or "").strip()
        )
        content = (f"Abstract:\n{abstract}\n\n{body}" if abstract else body)[: self.max_chars]
        source_text = "\n\n".join([s.get("text", "") for s in sections] + [abstract])

        parsed = self._struct(_Claims, _fill(_FREE_PROMPT, title=title, content=content))

        # section index over the submission, for the per-claim realization (BM25 only --
        # get_sections() never needs embeddings, so no SPECTER2 load here)
        index = PassageIndex(chunks_from_sections(sections, "submission"), embedder=None)

        claims = []
        for i, c in enumerate(getattr(parsed, "claims", None) or [], 1):
            claim_text = (getattr(c, "claim", "") or "").strip()
            if not claim_text:
                continue
            quote = (getattr(c, "evidence", "") or "").strip()
            verified, repaired = self._verify(quote, source_text) if quote else (False, quote)
            if not self.realize:
                segments = []
            elif self.realization_mode == "sections":
                segments = build_realization(self, claim_text, index, source_text)
            else:
                segments = build_realization_fulltext(self, claim_text, content, source_text)
            claims.append({
                "id": f"claim_{i}",
                "name": " ".join(claim_text.split()[:12]),
                "claim_text": claim_text,
                "evidence_quote": repaired,
                "evidence_verified": verified,
                # this extractor is anchor-free by design (that scaffolding lost in the
                # Stage-A evaluation); the fields stay for schema compatibility
                "contribution_statement": "",
                "contribution_statement_verified": False,
                "anchor_index": -1,
                # what the submission itself does for this claim + the sections read for it
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
                "realization": self.realize,
                "realization_mode": self.realization_mode if self.realize else None,
                "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls),
            },
            "claims": claims,
        }
        out = Path(data_dir) / submission_id / (out_name or f"{submission_id}_claims.json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc


# --------------------------------------------------------------------------- #
# One-shot baseline (ablation for the Stage-A evaluation)
# --------------------------------------------------------------------------- #

_SHALLOW_PROMPT = """You are extracting the CLAIMED NOVELTY CONTRIBUTIONS of a scientific paper, for peer-review novelty assessment.

A novelty claim is anything the authors explicitly present as their OWN new contribution: a method, model, architecture, algorithm, framework, task, benchmark, dataset, theoretical result, or problem formulation -- OR an empirical finding, analysis, or practical guideline they frame as a contribution. Cues: "we propose", "we introduce", "our contribution", "we are the first", "we show that", "we find that", "we provide guidelines".

Do NOT include background, motivation, related work, or isolated performance numbers.

Capture the DISTINCT SUBSTANTIVE contributions the authors present. A claim must be a contribution whose NOVELTY is worth assessing on its own.

STRICT exclusions -- these are NOT standalone claims:
- auxiliary evaluation steps or extra measurements that merely support another contribution.
- releasing code or trained models. Exception: a released dataset/benchmark presented as a contribution in itself.
- restatements of another claim at a different level of detail, and sub-parts of a single artifact.
- descriptions of HOW a proposed method/artifact works.

Stay faithful: use the authors' own terminology and do not invent contributions. A paper typically has 2-4 real novelty claims.

FIRST look for the paper's EXPLICIT contribution statement in the introduction. If it exists, base the claims on the contributions enumerated THERE. Only if NO such statement exists, extract from the authors' individual "we propose / we show" statements instead.

For each distinct claim provide exactly two fields:
- claim: one concise sentence stating the contribution, in the authors' terminology.
- evidence: ONE exact, CONTIGUOUS verbatim passage from the paper text below that states this contribution.

Paper title: {title}

{content}
"""


class ShallowClaimExtractor:
    """The previous ONE-SHOT extractor, kept as the Stage-A ablation baseline.

    Writes to a configurable filename so it can be produced next to the deep
    extraction for comparison instead of overwriting the canonical artifact."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        self.model_name = model_name
        self.llm = _make_llm(model_name, temperature)

    def extract(self, data_dir: str, submission_id: str, out_name: Optional[str] = None) -> dict:
        meta, sections = DeepClaimExtractor._load(data_dir, submission_id)
        abstract = (meta.get("abstract", "") or "").strip()
        intro = DeepClaimExtractor._lead_text(sections)
        conclusion = "\n".join(
            s.get("text", "").strip() for s in sections
            if any(k in (s.get("section") or "").lower() for k in ("conclusion", "discussion"))
        )

        acc = {"pt": 0, "ct": 0, "calls": 0}

        def _run(content: str):
            res = self.llm.with_structured_output(_Claims, include_raw=True).invoke(
                _fill(_SHALLOW_PROMPT, title=meta.get("title", ""), content=content))
            pt, ct = _usage(res.get("raw"))
            acc["pt"] += pt; acc["ct"] += ct; acc["calls"] += 1
            return res.get("parsed")

        result, scope = None, ""
        if intro:
            result = _run("Introduction (leading part of the paper):\n" + intro)
            scope = "introduction"
        if not (result and result.claims):
            content = "\n\n".join(p for p in (
                f"Abstract:\n{abstract}" if abstract else "",
                f"Introduction:\n{intro}" if intro else "",
                f"Conclusion / Discussion:\n{conclusion[:6000]}" if conclusion.strip() else "",
            ) if p)
            result = _run(content)
            scope = "abstract+introduction+conclusion"

        source_text = "\n\n".join([abstract, intro, conclusion])
        claims = []
        for i, c in enumerate(result.claims if result else [], 1):
            claim_text = (c.claim or "").strip()
            quote = (c.evidence or "").strip()
            verified = ev.verify_quote(quote, source_text).verified if quote else False
            claims.append({
                "id": f"claim_{i}",
                "name": " ".join(claim_text.split()[:12]),
                "claim_text": claim_text,
                "evidence_quote": quote,
                "evidence_verified": verified,
                "description": claim_text,
                "source": "",
                "origin": "llm",
                "status": "pending",
            })
        doc = {
            "submission_id": submission_id,
            "title": meta.get("title", ""),
            "publication_date": meta.get("publication_date"),
            "year": meta.get("year"),
            "date_source": meta.get("date_source"),
            "extraction_scope": scope,
            "extraction": {"model": self.model_name, "mode": "one_shot_baseline",
                           "cost": _cost_block(self.model_name, acc["pt"], acc["ct"], acc["calls"])},
            "claims": claims,
        }
        out = Path(data_dir) / submission_id / (out_name or f"{submission_id}_claims.json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc


# The orchestrator/API entry point for Step 2.
#
# The FREE FULL-TEXT extractor is the pipeline's extractor, chosen on evidence: in the
# Stage-A evaluation it beat the anchor-first section-reading extractor 7:0 in the blind
# pairwise comparison at ~1/5 of the cost, and three established inference-time techniques
# (self-consistency, chain-of-verification, self-refine) failed to beat it in turn. The
# other extractors are kept as documented ablations, not as candidates:
#   DeepClaimExtractor     -- anchor + targeted section reading (loses; see TODO task 1)
#   ShallowClaimExtractor  -- the original one-shot prompt (the previous default)
#   claim_methods.py       -- the three rejected inference-time techniques
ClaimExtractor = FullTextClaimExtractor

# Default model for claim extraction. Deliberately independent of the pipeline-wide model:
# extraction quality depends strongly on the model (gpt-5-mini fragments contributions into
# sub-claims where gpt-5.6-luna does not), so a cheaper pipeline model must not silently
# downgrade it. Override with NOVELTY_EXTRACTION_MODEL.
DEFAULT_EXTRACTION_MODEL = os.getenv("NOVELTY_EXTRACTION_MODEL", "gpt-5.6-luna")


# --------------------------------------------------------------------------- #
# Human-in-the-loop operations on the claims document.
# The orchestrator loads {id}_claims.json, applies these, and saves it back.
# Soft-delete (status='rejected') is used to keep a full audit trail.
# --------------------------------------------------------------------------- #


def _find(doc: dict, claim_id: str) -> dict:
    for c in doc["claims"]:
        if c["id"] == claim_id:
            return c
    raise KeyError(f"claim not found: {claim_id}")


def accept_claim(doc: dict, claim_id: str) -> dict:
    _find(doc, claim_id)["status"] = "accepted"
    return doc


def edit_claim(doc: dict, claim_id: str, **fields) -> dict:
    c = _find(doc, claim_id)
    for k, v in fields.items():
        if k in ("name", "claim_text", "description", "source"):
            c[k] = v
    c["status"] = "edited"
    # The stored realization describes the claim as it was BEFORE the edit; drop it so
    # the agent re-derives it for the edited wording instead of reusing a stale reading.
    if "claim_text" in fields or "description" in fields:
        c["realization"] = []
    return doc


def delete_claim(doc: dict, claim_id: str) -> dict:
    # Soft-delete: keep the entry for auditability (verification-first).
    _find(doc, claim_id)["status"] = "rejected"
    return doc


def add_claim(
    doc: dict, name: str, claim_text: str = "", description: str = "", source: str = "reviewer"
) -> dict:
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
            # no stored reading for a reviewer-authored claim -> the agent derives it
            "realization": [],
            "description": description,
            "source": source,
            "origin": "reviewer",
            "status": "accepted",
        }
    )
    return doc


def validated_claims(doc: dict) -> List[dict]:
    """Claims that proceed to later stages (everything the reviewer did not reject)."""
    return [c for c in doc["claims"] if c["status"] != "rejected"]


def main():
    ap = argparse.ArgumentParser(description="Step 2: deep claim & paper understanding extraction")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--shallow", action="store_true",
                    help="run the one-shot baseline extractor instead (Stage-A ablation)")
    ap.add_argument("--free", action="store_true",
                    help="run the free full-text extractor (whole paper, one unconstrained call)")
    ap.add_argument("--reasoning-effort", default="high", help="for --free reasoning models")
    ap.add_argument("--out-name", default=None, help="output filename (baseline runs only)")
    ap.add_argument("--no-realize", action="store_true",
                    help="skip the per-claim section reading (claims only, cheaper)")
    args = ap.parse_args()

    if args.free:
        doc = FullTextClaimExtractor(model_name=args.model,
                                     reasoning_effort=args.reasoning_effort,
                                     realize=not args.no_realize).extract(
            args.data_dir, args.submission_id, out_name=args.out_name)
    elif args.shallow:
        doc = ShallowClaimExtractor(model_name=args.model).extract(
            args.data_dir, args.submission_id, out_name=args.out_name)
    else:
        doc = ClaimExtractor(model_name=args.model).extract(
            args.data_dir, args.submission_id, realize=not args.no_realize,
            out_name=args.out_name)

    print(f"Title: {doc.get('title')}  |  date (cutoff): {doc.get('publication_date')}")
    ex = doc.get("extraction", {})
    if ex.get("anchor_statements") is not None:
        cov = ex.get("coverage", {})
        print(f"Anchor: {cov.get('n_anchor_statements', 0)} author contribution statement(s), "
              f"explicit list: {ex.get('has_explicit_contribution_list')}, "
              f"covered: {cov.get('n_covered', 0)}"
              + (f", UNCOVERED: {cov['uncovered_indices']}" if cov.get("uncovered_indices") else ""))
    print(f"\nClaimed novelty contributions ({len(doc['claims'])}):")
    for c in doc["claims"]:
        print(f"  [{c['id']}] {c['claim_text']}")
        v = "verified" if c.get("evidence_verified") else "UNVERIFIED"
        print(f"        evidence ({v}): {(c.get('evidence_quote') or '')[:160]}")
        nq = sum(1 for s in (c.get("realization") or []) if s.get("kind") == "quote")
        if c.get("realization"):
            print(f"        realization: {len(c['realization'])} segments ({nq} verified quotes)")


if __name__ == "__main__":
    main()
