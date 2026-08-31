#!/usr/bin/env python3
"""
ClaimNoveltyAgent: per-claim novelty assessment as a CODE-CONTROLLED two-phase
pipeline (not a free tool loop -- that let weak models wander and re-list/re-read).

Flow per claim (exactly four phases):
  1. TRIAGE (abstracts only, batched LLM calls): classify EVERY paper in the pool by how
     much it could overlap the claim (none/superficial/partial/substantial/same) +
     what_is_shared + submission_delta. Clearly-distinct papers are done here, cheaply.
  2. DEEP DIVE (full text, ONLY the papers that could overlap): focused single-call
     comparison for `partial`; a small bounded agentic close-read for `substantial`/`same`.
     Produces verified verbatim quote pairs; can_refute without a both-sides-verified
     pair is downgraded (evidence-grounding invariant lives in the toolbox/evidence).
  3. RE-ENTRY (optional, one round): if nothing overlaps, one retrieve_more to probe the
     frontier, then triage + deep-dive any new candidates.
  4. VERDICT from the ledger: challenged (verified refuter) / not_challenged / uncertain.

The control flow is deterministic; the LLM is used only for triage (1 call) and for the
few deep comparisons. Output is the same artifact_a-compatible entry as before.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .tools import ClaimToolbox

load_dotenv()

_MAX_TOOL_CHARS = 1600
_EMBEDDER = None

# USD per 1k tokens (input, output). Longest matching prefix wins, so dated
# variants like "gpt-5-mini-2025-08-07" are priced correctly.
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
    "gpt-3.5-turbo": (0.0005, 0.0015),
    # gpt-5.6 family (short-context tier), per 1k tokens
    "gpt-5.6-luna": (0.0002, 0.0012),
    "gpt-5.6-terra": (0.0020, 0.0120),
    "gpt-5.6-sol": (0.0050, 0.0300),
}


def _get_embedder(name: str = "allenai/specter2_base"):
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(name)
    return _EMBEDDER


def _usage(ai) -> tuple:
    um = getattr(ai, "usage_metadata", None) or {}
    if um:
        return int(um.get("input_tokens", 0) or 0), int(um.get("output_tokens", 0) or 0)
    tu = (getattr(ai, "response_metadata", {}) or {}).get("token_usage", {}) or {}
    return int(tu.get("prompt_tokens", 0) or 0), int(tu.get("completion_tokens", 0) or 0)


def _usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    # Match only at a variant boundary: a bare startswith would price "gpt-5.6-luna"
    # as "gpt-5" (~6x too high). A trailing "-" means a dated/variant suffix; a "."
    # means a different model generation.
    m = model or ""
    cands = [k for k in _PRICES if m.startswith(k) and (len(m) == len(k) or m[len(k)] == "-")]
    key = m if m in _PRICES else max(cands, key=len, default=None)
    p_in, p_out = _PRICES.get(key, (0.0, 0.0))
    return round(prompt_tokens / 1000 * p_in + completion_tokens / 1000 * p_out, 4)


# ------------------------------ schemas ---------------------------------- #


class _TriageItem(BaseModel):
    paper_id: str
    overlap_degree: str = Field(description="none | superficial | partial | substantial | same")
    what_is_shared: str = Field(default="", description="what the paper does that the claim also claims (if any)")
    submission_delta: str = Field(default="", description="what the claim adds beyond this paper")
    brief_note: str = Field(default="", description="1 sentence reason")


class _Triage(BaseModel):
    items: List[_TriageItem]


class _EvidencePairIn(BaseModel):
    claim_quote: str = Field(description="VERBATIM span from the claim/submission passages")
    paper_quote: str = Field(description="VERBATIM span copied character-for-character from the paper passages")
    rationale: str = Field(default="", description="one sentence: why this pair shows overlap")


class _SectionPick(BaseModel):
    """The sections whose FULL text should be loaded (chosen by what each is about)."""
    sections: List[str] = Field(description="exact section titles to read in full, most relevant first")


class _Segment(BaseModel):
    kind: str = Field(description='"text" for your own prose, "quote" for a VERBATIM span copied character-for-character from the source')
    content: str = Field(description="the prose, or the verbatim quote (no [Section] tag, no quotation marks)")


class _Realization(BaseModel):
    """A flowing explanation built from prose + verbatim quote segments, in reading order."""
    segments: List[_Segment] = Field(default_factory=list)


class _SectionComparison(BaseModel):
    # narrative of how THIS paper realizes (or does not) the claimed contribution, with
    # verbatim quote segments from the paper woven in
    paper_realization: List[_Segment] = Field(default_factory=list)
    overlap_degree: str = Field(description="none | superficial | partial | substantial | same (overlap of CONTRIBUTIONS, not topic)")
    refutation_status: str = Field(description="can_refute | cannot_refute | unclear")
    what_is_shared: str = Field(default="", description="what the paper does that the claim also claims (if any)")
    submission_delta: str = Field(default="", description="what the submission adds beyond this paper")
    assessment: str = Field(default="", description="the comparison with the submission and the overlap judgment (2-4 sentences)")
    evidence_pairs: List[_EvidencePairIn] = Field(
        default_factory=list,
        description="ONLY if the paper presents the SAME contribution (can_refute): verbatim claim<->paper pairs")


class _Comparison(BaseModel):
    refutation_status: str = Field(description="can_refute | cannot_refute | unclear")
    overlap_degree: str = Field(description="none | superficial | partial | substantial | same")
    what_is_shared: str = Field(default="")
    submission_delta: str = Field(default="")
    brief_note: str = Field(default="")
    evidence_pairs: List[_EvidencePairIn] = Field(default_factory=list)


class read_more(BaseModel):
    """Read more passages of THIS prior paper (full-text search) if you need other parts before concluding."""
    query: str


class conclude_comparison(BaseModel):
    """Conclude the comparison of this prior paper against the claim."""
    refutation_status: str = Field(description="can_refute | cannot_refute | unclear")
    overlap_degree: str = Field(description="none | superficial | partial | substantial | same")
    what_is_shared: str = Field(default="")
    submission_delta: str = Field(default="")
    brief_note: str = Field(default="")
    evidence_pairs: List[_EvidencePairIn] = Field(default_factory=list)


# ------------------------------ prompts ---------------------------------- #

# How much of each abstract the triage sees. The previous 400-char cut truncated EVERY
# abstract in the corpus (measured: 1270/1270 pool abstracts are longer; median 1461) and
# removed exactly the part that states the contribution, because abstracts open with
# background -- papers were rejected for information the system already had. 2500 keeps all
# but 1 of those 1270 intact; a 30-abstract batch is then ~19k tokens.
_TRIAGE_ABSTRACT_CHARS = 2500

_TRIAGE_PROMPT = """Triage prior-work papers against ONE claimed contribution using ONLY their abstracts, to decide which need a deeper full-text comparison.

overlap_degree measures whether the paper PRESENTS (part of) the SAME CONTRIBUTION as the claim -- NOT whether it is on the same topic or similar to the submission overall. Topical similarity alone is NEVER more than superficial.
- none: nothing of the claimed contribution.
- superficial: same broad topic/field/techniques, but a DIFFERENT KIND of contribution (e.g. the claim proposes a benchmark and the paper proposes a method, a survey, or an application) -> no deeper analysis needed.
- partial: the paper ITSELF delivers part of the claimed contribution (e.g. the claim proposes a benchmark and the paper ALSO introduces a benchmark/evaluation suite for a closely related task or scope) -> needs a closer look.
- substantial / same: the abstract suggests it presents much or all of the SAME contribution -> needs a close look.
Be conservative with substantial/same. Give what_is_shared (what the paper does that the claim also claims, if any) and submission_delta (what the claim adds beyond it). For none/superficial, brief_note must state WHY the paper's contribution does not overlap the claimed one and why no deeper analysis is needed (e.g. "method paper, proposes no benchmark").

## Claim
{claim}

## Papers (paper_id :: title :: abstract)
{papers}

Return one item for EVERY paper_id."""

_COMPARE_PROMPT = """Assess whether a PRIOR-WORK paper challenges the NOVELTY of ONE claimed contribution, using the paper's full-text passages below.
- can_refute: the paper substantially presents the SAME contribution (novelty is challenged) -- REQUIRES a verbatim quote pair.
- cannot_refute: related but does NOT present the same contribution (put the key difference in submission_delta).
- unclear: cannot tell from these passages.
overlap_degree measures overlap of CONTRIBUTIONS (the claim's vs the paper's), NOT topical similarity: a paper merely in the same area / using the same techniques with a different kind of contribution is superficial at most; partial means the paper itself delivers part of the claimed contribution.
Quotes: claim_quote = VERBATIM from the submission passages; paper_quote = COPIED CHARACTER-FOR-CHARACTER from the paper passages below (never paraphrase, never include a leading [Section] tag). Only include evidence_pairs you can copy verbatim.
paper_quote must state what THE PAPER ITSELF does or contributes. NEVER quote text that describes OTHER cited work -- related-work summaries, or descriptions of adopted datasets/methods (patterns like "X [12] is a ... dataset", "we adopt/use the following datasets") describe the CITED paper's contribution, not this paper's, and are NOT evidence. For cannot_refute, include a pair only if it genuinely shows the shared part of the contributions; otherwise return no evidence_pairs.

## Claim
{claim}

## Submission passages (source for claim_quote)
{claim_passages}

## Prior paper: {title}
## Its full-text passages
{passages}

Give refutation_status, overlap_degree (none/superficial/partial/substantial/same), what_is_shared, submission_delta."""

_DEEP_SYSTEM = """You are doing a CLOSE comparison of ONE prior paper against a claimed contribution to decide whether it challenges the claim's novelty. You are given some of the paper's full-text passages. If you need other parts of the paper, call read_more(query) (at most a couple of times). When ready, call conclude_comparison with refutation_status, overlap_degree, what_is_shared, submission_delta, and verbatim evidence_pairs (paper_quote copied CHARACTER-FOR-CHARACTER from passages you saw, without any leading [Section] tag; claim_quote verbatim from the submission passages). paper_quote must state what THE PAPER ITSELF does or contributes -- never quote descriptions of OTHER cited work (related-work summaries, "X [12] is a ... dataset", "we adopt the following datasets"): that is the cited paper's contribution, not this paper's. overlap_degree measures overlap of CONTRIBUTIONS (claim vs paper), not topical similarity: same area + different kind of contribution = superficial at most. Be efficient."""

# --- section-based understanding (V3) ---

_SUBMISSION_SECTION_PICK = """A paper makes ONE specific claimed contribution (below). You will explain what THE SUBMISSION ITSELF does to realize exactly THIS claim -- e.g. if the claim proposes a benchmark, the construction/design of that benchmark, NOT the experimental results or findings.

Choose the section titles whose FULL text you need to explain this. Section titles say what each section is about; pick the ones about the claimed contribution itself (definition, design, construction, method) and skip results/experiments/ablations/limitations unless the claim is about them.

## Claim
{claim}

## Submission sections (title :: preview :: size)
{sections}

Return `sections`: the exact titles to read in full (usually 2-5)."""

_SUBMISSION_REALIZE = """Explain what THE SUBMISSION ITSELF does to realize this specific claim, using ONLY the section text below. Describe the contribution and HOW IT IS BUILT/DESIGNED (e.g. for a benchmark: its tasks, corpora, construction, metrics) -- NOT the experimental results or findings.

Write `segments` as a flowing explanation in reading order, alternating:
- kind="text": your own concise prose.
- kind="quote": a VERBATIM span copied CHARACTER-FOR-CHARACTER from the section text (no [Section] tag, no quotation marks). Use quotes for the load-bearing specifics (what is built, how). Every quote must be copyable verbatim from the text below.
Keep it to a short paragraph or two.

## Claim
{claim}

## Submission sections (full text)
{sections}"""

_PAPER_SECTION_PICK = """You are checking whether ONE prior-work paper challenges the NOVELTY of a specific claimed contribution (below), plus a summary of what the submission itself does for this claim.

Choose the section titles of the PRIOR paper whose FULL text you need to judge whether the paper presents the SAME KIND of contribution as the claim. Section titles say what each section is about; pick the ones about the paper's OWN contribution/method/benchmark/design, and skip unrelated experiments, appendices describing external datasets, or generic related-work sections.

## Claim
{claim}

## What the submission does for this claim
{realization}

## Prior paper: {title}
## Its sections (title :: preview :: size)
{sections}

Return `sections`: the exact titles to read in full (usually 2-5)."""

_PAPER_COMPARE = """Compare ONE prior-work paper against a specific claimed contribution, using the paper's FULL section text below.

First, in `paper_realization`, explain what THE PAPER ITSELF does with respect to the claimed contribution, as `segments` in reading order:
- kind="text": your own concise prose.
- kind="quote": a VERBATIM span copied CHARACTER-FOR-CHARACTER from the section text below (no [Section] tag, no quotation marks). Quote the paper's OWN contribution -- NEVER quote descriptions of other cited work (related-work summaries, "X [12] is a ... dataset", "we adopt the following datasets"): that is a DIFFERENT paper's contribution, not this one's.
If the paper does NOT address the claimed contribution, say so briefly in one text segment (no quotes needed).

Then judge:
- overlap_degree: overlap of CONTRIBUTIONS (claim vs THIS paper), not topical similarity.
  * none / superficial = same area but a DIFFERENT KIND of contribution.
  * partial = the paper itself delivers PART of the claimed contribution.
  * substantial = the SAME KIND of contribution covering much of the same goal, but with a materially different specific design, scope, or data -- so the submission still has a real delta.
  * same = essentially the IDENTICAL contribution/artifact with the same defining design (near-duplication); reserve this for when the submission adds little of substance beyond it.
  Be strict about `same`: if the submission has any clear distinguishing design (e.g. purpose-built datasets/corpora, a different framing or scope), it is at most `substantial`, NOT `same`.
- refutation_status: can_refute only if the paper substantially presents the SAME contribution (overlap_degree substantial or same) (then also give evidence_pairs: verbatim claim_quote from the submission text + verbatim paper_quote of the paper's own contribution). Otherwise cannot_refute.
- what_is_shared / submission_delta / assessment (assessment = the comparison with the submission and your overlap judgment, 2-4 sentences).

## Claim
{claim}

## What the submission does for this claim
{realization}

## Prior paper: {title}
## Its section text (full)
{sections}"""


def _fill(template: str, **kw) -> str:
    """Sequential {key}->value substitution that tolerates literal braces in the values
    (section text may contain { } from math/code) -- str.format would choke on those."""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _fmt_sections_menu(menu: List[dict]) -> str:
    return "\n".join(
        f"- {m['name']} :: {m.get('preview','')[:160]} :: ~{m.get('chars',0)} chars"
        for m in menu) or "(no sections)"


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


def _segments_to_text(segments: List[dict]) -> str:
    """Flatten realization segments to plain prose (for reuse as comparison context)."""
    parts = []
    for s in segments or []:
        c = (s.get("content") or "").strip()
        if not c:
            continue
        parts.append(f'"{c}"' if (s.get("kind") == "quote") else c)
    return " ".join(parts)


def _fmt_passages(hits: List[dict], max_total: int = 1800) -> str:
    out, used = [], 0
    for h in hits or []:
        sec = (h.get("section") or "").strip()
        txt = h.get("text", "")
        line = (f"[{sec}] " if sec else "") + txt
        if used + len(line) > max_total:
            line = line[: max(0, max_total - used)]
        out.append(line)
        used += len(line)
        if used >= max_total:
            break
    return "\n---\n".join(out) if out else "(no passages)"


class ClaimNoveltyAgent:
    def __init__(
        self,
        data_dir: str,
        submission_id: str,
        *,
        model_name: str = "gpt-4.1",
        embedder=None,
        max_steps: int = 24,          # accepted for API compatibility (unused in the pipeline)
        max_retrievals: int = 1,
        closest_n: int = 10,          # coverage-predicate width in the toolbox; triage covers the WHOLE pool
        stalled_k: int = 4,           # accepted for API compatibility (unused)
        hard_stall: int = 6,          # accepted for API compatibility (unused)
        deep_rounds: int = 3,         # max read_more turns in the substantial/same close-read
        min_quote_tokens: int = 10,
        fuzzy_threshold: float = 90.0,
        grobid_server: str = "http://localhost:8070",
        deep_dive_workers: Optional[int] = None,
    ):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.data_dir = data_dir
        self.submission_id = submission_id
        self.model_name = model_name
        self.embedder = embedder or _get_embedder()
        self.max_retrievals = max_retrievals
        self.closest_n = closest_n
        self.deep_rounds = deep_rounds
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.grobid_server = grobid_server
        # Deep dives are independent per-paper comparisons -> run them concurrently.
        # Bounded (default 4) so parallel large-context LLM calls don't trip the model's
        # tokens-per-minute limit. 1 = fully sequential (old behaviour). Env override:
        # NOVELTY_DEEP_DIVE_WORKERS.
        if deep_dive_workers is None:
            try:
                deep_dive_workers = int(os.getenv("NOVELTY_DEEP_DIVE_WORKERS", "4"))
            except ValueError:
                deep_dive_workers = 4
        self.deep_dive_workers = max(1, deep_dive_workers)
        # reasoning models (gpt-5*, o-series) reject any temperature other than the default.
        # For them we also cap the reasoning effort: at the default (medium/high) a single
        # gpt-5-mini call reasons for many minutes, which makes a batch untenable. "low"
        # (env NOVELTY_REASONING_EFFORT) brings calls down to seconds with little quality
        # loss for these structured comparison tasks. Non-reasoning models ignore it.
        is_reasoning = model_name.startswith(("gpt-5", "o1", "o3", "o4"))
        if is_reasoning:
            kw = {"reasoning_effort": os.getenv("NOVELTY_REASONING_EFFORT", "low")}
        else:
            kw = {"temperature": 0.0}
        # A per-request timeout is essential: without it a single stalled HTTP connection
        # (half-open socket behind OpenAI's proxy) hangs the whole run forever -- max_retries
        # never fires because the request never *errors*, it just waits. With a timeout the
        # stalled call aborts and is retried, which reconnects and succeeds in seconds.
        try:
            timeout = float(os.getenv("NOVELTY_LLM_TIMEOUT", "180"))
        except ValueError:
            timeout = 180.0
        try:
            max_retries = int(os.getenv("NOVELTY_LLM_MAX_RETRIES", "6"))
        except ValueError:
            max_retries = 6
        self.llm = ChatOpenAI(
            model_name=model_name, api_key=api_key,
            max_retries=max_retries, timeout=timeout, **kw
        )

    # ------------------------------ helpers ------------------------------ #

    @staticmethod
    def _claim_str(claim: dict) -> str:
        return (f"{claim.get('name','')} — {claim.get('claim_text','')} "
                f"({claim.get('description','')})").strip()

    def _struct(self, model, prompt):
        """Structured LLM call returning (parsed, prompt_tokens, completion_tokens)."""
        res = self.llm.with_structured_output(model, include_raw=True).invoke(prompt)
        parsed, raw = res.get("parsed"), res.get("raw")
        pt, ct = _usage(raw) if raw is not None else (0, 0)
        return parsed, pt, ct

    # ------------------------------ phase 1 ------------------------------ #

    def _triage(self, tb: ClaimToolbox, claim: dict, papers: List[dict]):
        """One batched abstract-triage call; chunked so arbitrarily large pools stay
        within a sane prompt size (30 abstracts per call).

        Abstracts enter the listing essentially in full (_TRIAGE_ABSTRACT_CHARS): this is
        the ONLY evidence the triage gets, and everything it rejects here is never read."""
        by_id, pt, ct = {}, 0, 0
        for i in range(0, len(papers), 30):
            chunk = papers[i:i + 30]
            listing = "\n".join(
                f"{p['paper_id']} :: {p['title']} :: "
                f"{(p.get('abstract') or '(no abstract)')[:_TRIAGE_ABSTRACT_CHARS]}"
                for p in chunk)
            parsed, a, b = self._struct(_Triage, _TRIAGE_PROMPT.format(claim=self._claim_str(claim)[:1500], papers=listing))
            pt += a; ct += b
            if parsed:
                for it in parsed.items:
                    if it.paper_id in tb.pool:
                        by_id[it.paper_id] = it
        tb._log("triage", f"{len(papers)} papers by abstract", progress=True)
        return by_id, pt, ct

    # --------------- phase 0b: section-based submission understanding -------- #

    def _pick_sections(self, tb: ClaimToolbox, pid: str, prompt: str, fallback_k: int = 4):
        """Let the model choose sections from the menu; returns (full_sections, pt, ct).
        Falls back to the largest sections if the paper has no usable section structure."""
        menu = tb.section_menu(pid)
        if not menu:
            return [], 0, 0
        parsed, pt, ct = self._struct(_SectionPick, prompt.replace("{sections}", _fmt_sections_menu(menu)))
        names = [s for s in (getattr(parsed, "sections", None) or []) if s] if parsed else []
        if not names:  # model gave nothing usable -> take the biggest sections
            names = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:fallback_k]]
        got = tb.read_sections(pid, names).get("sections", [])
        return got, pt, ct

    def _understand_submission(self, tb: ClaimToolbox, claim: dict):
        """What the SUBMISSION itself does for this claim (verified-quote realization).

        Normally this is already part of the claim artifact: deep claim extraction
        (Step 2) picks the relevant submission sections, reads them in full and stores
        the realization + section provenance per claim, reviewed at the HITL checkpoint.
        We then just adopt it -- no model call, and the reading the reviewer approved is
        exactly the one used for every comparison.

        Only a claim WITHOUT a stored realization (a reviewer-authored or edited claim)
        is read here on the fly, using the same section-menu -> read-in-full procedure.
        Returns (realization_segments, claim_context_text, pt, ct)."""
        stored = claim.get("realization") or []
        if stored:
            tb.claim_realization = stored
            tb._log("understand_submission",
                    f"from claim artifact: "
                    f"{sum(1 for s in stored if s.get('kind') == 'quote')} verified quotes",
                    progress=True)
            return stored, _segments_to_text(stored), 0, 0

        pt = ct = 0
        pick_prompt = _SUBMISSION_SECTION_PICK.replace("{claim}", self._claim_str(claim)[:1200])
        secs, a, b = self._pick_sections(tb, "submission", pick_prompt); pt += a; ct += b
        if not secs:  # no section structure -> fall back to claim-query passages
            ctx = _fmt_passages(tb.search_submission(self._claim_str(claim), k=4).get("passages"))
            return [], ctx, pt, ct
        parsed, a, b = self._struct(_Realization, _fill(
            _SUBMISSION_REALIZE, claim=self._claim_str(claim)[:1200],
            sections=_fmt_sections_full(secs))); pt += a; ct += b
        raw_segments = [s.model_dump() for s in (getattr(parsed, "segments", None) or [])] if parsed else []
        realization = tb.verify_segments(raw_segments, "submission")
        tb.claim_realization = realization
        tb._log("understand_submission",
                f"{len(secs)} sections -> {sum(1 for s in realization if s['kind']=='quote')} verified quotes",
                progress=True)
        ctx = _segments_to_text(realization) or _fmt_sections_full(secs, max_total=1600)
        return realization, ctx, pt, ct

    # ------------------------------ phase 2 ------------------------------ #

    def _section_compare(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str):
        """Section-based deep dive: the model picks the prior paper's relevant sections,
        reads them in full, and returns a realization (narrative + verified quotes) + the
        overlap judgment."""
        pt = ct = 0
        pick_prompt = (_PAPER_SECTION_PICK
                       .replace("{claim}", self._claim_str(claim)[:1200])
                       .replace("{realization}", claim_ctx[:1600])
                       .replace("{title}", tb.pool[pid]["title"]))
        secs, a, b = self._pick_sections(tb, pid, pick_prompt); pt += a; ct += b
        if not secs:  # no full text -> compare on the abstract passages instead
            hits = tb.read_paper(pid, query=self._claim_str(claim))
            secs = [{"name": "Abstract", "text": _fmt_passages(
                hits.get("passages") or ([{"text": hits.get("abstract", "")}] if hits.get("abstract") else []))}]
        parsed, a, b = self._struct(_SectionComparison, _fill(
            _PAPER_COMPARE, claim=self._claim_str(claim)[:1200], realization=claim_ctx[:1600],
            title=tb.pool[pid]["title"], sections=_fmt_sections_full(secs))); pt += a; ct += b
        return self._to_comp(parsed), pt, ct

    @staticmethod
    def _to_comp(parsed) -> dict:
        """Normalise a _SectionComparison / _Comparison into record_comparison kwargs."""
        if parsed is None:
            return {"refutation_status": "unclear", "overlap_degree": "none", "what_is_shared": "",
                    "submission_delta": "", "brief_note": "", "assessment": "",
                    "paper_realization": [], "evidence_pairs": []}
        if isinstance(parsed, dict):
            g = parsed.get
            pairs = parsed.get("evidence_pairs") or []
            segs = parsed.get("paper_realization") or []
        else:
            g = lambda k, d=None: getattr(parsed, k, d)
            pairs = [p.model_dump() if hasattr(p, "model_dump") else p for p in (getattr(parsed, "evidence_pairs", []) or [])]
            segs = [s.model_dump() if hasattr(s, "model_dump") else s for s in (getattr(parsed, "paper_realization", []) or [])]
        return {
            "refutation_status": g("refutation_status", "unclear"),
            "overlap_degree": g("overlap_degree", "none"),
            "what_is_shared": g("what_is_shared", "") or "",
            "submission_delta": g("submission_delta", "") or "",
            "brief_note": g("brief_note", "") or "",
            "assessment": g("assessment", "") or "",
            "paper_realization": [
                {"kind": (s.get("kind") if isinstance(s, dict) else "text") or "text",
                 "content": (s.get("content", "") if isinstance(s, dict) else "")}
                for s in segs
            ],
            "evidence_pairs": [
                {"claim_quote": (p.get("claim_quote") if isinstance(p, dict) else ""),
                 "paper_quote": (p.get("paper_quote") if isinstance(p, dict) else ""),
                 "rationale": (p.get("rationale", "") if isinstance(p, dict) else "")}
                for p in pairs
            ],
        }

    def _record(self, tb: ClaimToolbox, pid: str, comp: dict, log: bool = True):
        tb.record_comparison(
            paper_id=pid,
            refutation_status=comp["refutation_status"],
            relevance_reason="",
            brief_note=comp["brief_note"],
            overlap_dimensions=[],
            overlap_degree=comp["overlap_degree"],
            what_is_shared=comp["what_is_shared"],
            submission_delta=comp["submission_delta"],
            evidence_pairs=comp["evidence_pairs"],
            paper_realization=comp.get("paper_realization"),
            assessment=comp.get("assessment", ""),
            fulltext_fetch_status=comp.get("fulltext_fetch_status"),
            log=log,
        )

    def _deep_dive(self, tb: ClaimToolbox, claim: dict, pid: str, degree: str, claim_ctx: str):
        tb._log("deep_dive", f"{pid} ({degree})", progress=True)
        # In-process PDF parse NOW, on demand -- only deep-dived papers ever get parsed
        # (most of the pool doesn't reach this point). Timed separately from the LLM
        # comparison so the Review timing breakdown can tell parsing apart from model latency.
        _p0 = time.perf_counter()
        fts = tb.ensure_fulltext(pid)
        parse_s = time.perf_counter() - _p0
        _c0 = time.perf_counter()
        comp, pt, ct = self._section_compare(tb, claim, pid, claim_ctx)
        compare_s = time.perf_counter() - _c0
        comp["fulltext_fetch_status"] = fts
        self._record(tb, pid, comp)
        tinfo = {
            "paper_id": pid,
            "title": (tb.pool.get(pid, {}) or {}).get("title", "")[:90],
            "parse_s": round(parse_s, 1),
            "compare_s": round(compare_s, 1),
            "total_s": round(parse_s + compare_s, 1),
            "fetch_status": fts,
        }
        return pt, ct, tinfo

    # -------------------------------- run -------------------------------- #

    def run(self, claim: dict, progress_cb=None) -> dict:
        tb = ClaimToolbox(
            self.data_dir, self.submission_id, claim, self.embedder,
            closest_n=self.closest_n, min_quote_tokens=self.min_quote_tokens,
            fuzzy_threshold=self.fuzzy_threshold, grobid_server=self.grobid_server,
        )
        pt = ct = 0
        est_total = {"v": 0}  # estimated total steps; 0 until the triage shortlist is known (frontend hides "/max" then)
        # Wall-clock breakdown per phase -- surfaced in the Review UI so the reviewer can
        # see WHAT makes a claim slow (almost always LLM latency: triage over the whole
        # pool + the per-paper deep-dive comparisons; PDF parsing is ~1s since PyMuPDF).
        run_t0 = time.perf_counter()
        timings = {"deep_dive_papers": []}

        def emit(status="running"):
            if not progress_cb:
                return
            # Snapshot the ledger under the toolbox lock: parallel deep dives may be
            # appending to these lists, and serializing them to JSON while a worker
            # mutates them would raise "changed size during iteration".
            with tb._lock:
                traj = list(tb.ledger["trajectory"])
                n_examined = len(tb.ledger["examined"])
                n_comparisons = len(tb.ledger["comparisons"])
                n_retr = tb.retrievals_done()
            try:
                progress_cb({
                    "status": status, "claim_id": claim["id"],
                    "step": len(traj),
                    "max_steps": max(est_total["v"], len(traj)) if est_total["v"] else 0,
                    "last_action": traj[-1]["detail"] if traj else "starting",
                    "trajectory": traj,
                    "examined": n_examined,
                    "comparisons": n_comparisons,
                    "retrieval_rounds": n_retr,
                    "cost": {"prompt_tokens": pt, "completion_tokens": ct,
                             "usd": _usd(self.model_name, pt, ct)},
                })
            except Exception:
                pass

        def dive_all(items):
            """Run deep dives for `items` [(pid, degree)], concurrently when
            deep_dive_workers > 1. Each deep dive is INDEPENDENT (own PDF parse + own
            LLM comparison); the verdict is aggregated from the ledger only after all
            finish, and every shared-ledger write is serialized by the toolbox lock, so
            parallelism changes neither any individual comparison nor the final result --
            only the wall-clock time. Token totals + timing + progress are collected on
            THIS (main) thread as each future completes."""
            lp = lc = 0
            workers = min(self.deep_dive_workers, len(items))
            if workers <= 1:
                for pid, deg in items:
                    a, b, tinfo = self._deep_dive(tb, claim, pid, deg, claim_ctx)
                    lp += a; lc += b
                    timings["deep_dive_papers"].append(tinfo); emit()
                return lp, lc
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(self._deep_dive, tb, claim, pid, deg, claim_ctx)
                        for pid, deg in items]
                for fut in as_completed(futs):
                    a, b, tinfo = fut.result()
                    lp += a; lc += b
                    timings["deep_dive_papers"].append(tinfo); emit()
            return lp, lc

        emit()
        # What the SUBMISSION itself does for THIS claim: normally ADOPTED from the claim
        # artifact (deep claim extraction already read the relevant sections and the
        # reviewer approved it at the checkpoint) -- only derived here for a reviewer-added
        # claim. Reused as context for every prior-work comparison.
        _t = time.perf_counter()
        _real, claim_ctx, a, b = self._understand_submission(tb, claim); pt += a; ct += b
        timings["understand_submission"] = round(time.perf_counter() - _t, 1)
        emit()

        # Phase 1: triage the ENTIRE candidate pool by abstract (no pre-selection --
        # every retrieved related-work paper gets looked at; only possible overlaps go deeper)
        top = tb._ranked()
        _t = time.perf_counter()
        triage, a, b = self._triage(tb, claim, top); pt += a; ct += b
        timings["triage"] = round(time.perf_counter() - _t, 1)
        shortlist = []
        for p in top:
            pid = p["paper_id"]
            it = triage.get(pid)
            deg = (it.overlap_degree if it else "none").lower()
            status = "unclear" if deg in ("partial", "substantial", "same") else "cannot_refute"
            self._record(tb, pid, {
                "refutation_status": status, "overlap_degree": deg,
                "what_is_shared": (it.what_is_shared if it else ""),
                "submission_delta": (it.submission_delta if it else ""),
                "brief_note": (it.brief_note if it else "triaged from abstract"),
                "evidence_pairs": [],
            }, log=False)
            if deg in ("partial", "substantial", "same"):
                shortlist.append((pid, deg))
        tb._log("triage_result",
                f"{len(top) - len(shortlist)} clearly distinct (abstract only); "
                f"{len(shortlist)} need full-text deep dive", progress=True)
        # a deep dive logs ~3 trajectory steps (deep_dive, read_paper, record_comparison)
        est_total["v"] = len(tb.ledger["trajectory"]) + 3 * len(shortlist)
        emit()

        # Phase 2: deep-dive only the papers that could overlap (in parallel)
        _t = time.perf_counter()
        a, b = dive_all(shortlist); pt += a; ct += b
        timings["deep_dive_total"] = round(time.perf_counter() - _t, 1)

        # Phase 3: one re-entry round if nothing overlaps (probe the frontier)
        refuters = [c for c in tb.ledger["comparisons"] if c["refutation_status"] == "can_refute"]
        if not refuters and not shortlist and self.max_retrievals > 0:
            _t = time.perf_counter()
            new = tb.retrieve_more(self._claim_str(claim)).get("papers", [])
            emit()
            if new:
                newp = [tb.pool[x["paper_id"]] for x in new if x["paper_id"] in tb.pool]
                tri2, a, b = self._triage(tb, claim, newp); pt += a; ct += b
                reentry_shortlist = []
                for p in newp:
                    pid = p["paper_id"]; it = tri2.get(pid); deg = (it.overlap_degree if it else "none").lower()
                    status = "unclear" if deg in ("partial", "substantial", "same") else "cannot_refute"
                    self._record(tb, pid, {
                        "refutation_status": status, "overlap_degree": deg,
                        "what_is_shared": (it.what_is_shared if it else ""),
                        "submission_delta": (it.submission_delta if it else ""),
                        "brief_note": (it.brief_note if it else "triaged from abstract"), "evidence_pairs": []}, log=False)
                    if deg in ("partial", "substantial", "same"):
                        reentry_shortlist.append((pid, deg))
                a, b = dive_all(reentry_shortlist); pt += a; ct += b
                emit()
            timings["reentry"] = round(time.perf_counter() - _t, 1)

        # Phase 4: verdict from the ledger
        # any triaged paper still 'unclear' (deep dive didn't resolve) -> leave as cannot_refute
        for c in tb.ledger["comparisons"]:
            if c["refutation_status"] == "unclear":
                c["refutation_status"] = "cannot_refute"
        # A claim is challenged if a prior paper either (a) fully refutes it -- can_refute, with a
        # verified two-sided quote pair -- OR (b) shows substantial/same overlap of CONTRIBUTIONS.
        # Fix A (NOVELTY_CHALLENGE_ON_STRONG_OVERLAP, default on): substantial overlap materially
        # diminishes novelty even when the submission adds a differentiator, so it counts as a
        # challenge. The old rule (can_refute only) required near-identity from a single paper and
        # let substantial-overlap-with-a-wrinkle read as novel -- the "A2 grading miss" the eval
        # found (e.g. CvGqMD5OtX: MCS-SQL substantial overlap yet cannot_refute -> wrongly novel).
        refuters = [c for c in tb.ledger["comparisons"] if c["refutation_status"] == "can_refute"]
        strong_overlap = []
        if os.getenv("NOVELTY_CHALLENGE_ON_STRONG_OVERLAP", "1") != "0":
            strong_overlap = [c for c in tb.ledger["comparisons"]
                              if (c.get("overlap_degree") or "").lower() in ("substantial", "same")]
        if refuters or strong_overlap:
            verdict, suff, stop = "challenged", True, "challenged"
        else:
            verdict, suff, stop = "not_challenged", True, "not_challenged"

        timings["total"] = round(time.perf_counter() - run_t0, 1)
        # "Other" = index building / bookkeeping / verdict not attributed to a named phase.
        _named = sum(v for k, v in timings.items()
                     if k not in ("deep_dive_papers", "total") and isinstance(v, (int, float)))
        timings["other"] = round(max(0.0, timings["total"] - _named), 1)
        entry = tb.artifact_entry()
        entry.update({
            "agent_verdict": verdict,
            "agent_rationale": "",
            "evidence_sufficient": bool(suff),
            "stop_reason": stop,
            "confidence": None,
            "timings": timings,
            "cost": {"prompt_tokens": pt, "completion_tokens": ct, "usd": _usd(self.model_name, pt, ct)},
        })
        # NOT emit("done"): the api worker still assembles the review after this and writes
        # the real "done" payload (with review). A premature done here made the frontend stop
        # polling before the review existed and freeze on the last live state.
        emit()
        return entry
