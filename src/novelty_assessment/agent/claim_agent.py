"""Agentic comparison of one claim against every paper in the prior-work pool.

For each paper, an agent loop reads sections, compares, and passes the result through the
evidence gate (evidence map, verbatim and ownership checks, evidence check). A failed
check sends the paper back to reading once. The claim verdict follows from the settled
assessments (Section 3.5).
"""
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from . import evidence_map
from .tools import ClaimToolbox

load_dotenv()

_EMBEDDER = None

# USD per 1k tokens (input, output).
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


def _cache_read(ai) -> int:
    """Prompt tokens of this call that the provider served from its prompt cache."""
    um = getattr(ai, "usage_metadata", None) or {}
    if um:
        details = um.get("input_token_details") or {}
        return int(details.get("cache_read", 0) or 0)
    tu = (getattr(ai, "response_metadata", {}) or {}).get("token_usage", {}) or {}
    details = tu.get("prompt_tokens_details") or {}
    return int(details.get("cached_tokens", 0) or 0)


def _usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """List-price cost; a price key matches the model name exactly or up to a '-' suffix."""
    m = model or ""
    cands = [k for k in _PRICES if m.startswith(k) and (len(m) == len(k) or m[len(k)] == "-")]
    key = m if m in _PRICES else max(cands, key=len, default=None)
    p_in, p_out = _PRICES.get(key, (0.0, 0.0))
    return round(prompt_tokens / 1000 * p_in + completion_tokens / 1000 * p_out, 4)


class _SectionPick(BaseModel):
    """The sections whose FULL text should be loaded (chosen by what each is about)."""
    sections: List[str] = Field(description="exact section titles to read in full, most relevant first")
    why: str = Field(default="", description="what these sections are expected to show, in one sentence")


class _PaperAction(BaseModel):
    """One adaptive reading action proposed by the per-paper agent."""

    tool: str = Field(
        description="read_more | propose_dismissal | propose_compare"
    )
    sections: List[str] = Field(
        default_factory=list,
        description="for read_more: the [S#] handles of unread sections to open, exactly "
                    "as the menu prints them (e.g. S4). A title is accepted only if it "
                    "matches the menu exactly."
    )
    suspected_deficit: str = Field(
        default="",
        description="the specific unresolved question or refinement objective, if any"
    )
    why: str = Field(
        default="",
        description="one or two sentences explaining why this is the best next action"
    )


class _Segment(BaseModel):
    kind: str = Field(description='"text" for your own prose, "quote" for a VERBATIM span copied character-for-character from the source')
    content: str = Field(description="the prose, or ONE contiguous verbatim quote -- never spans joined by an ellipsis (no [Section] tag, no quotation marks)")


class _Realization(BaseModel):
    """A flowing explanation built from prose + verbatim quote segments, in reading order."""
    segments: List[_Segment] = Field(default_factory=list)


class _SectionComparison(BaseModel):
    """Semantic comparison only. Evidence is produced and verified later."""

    paper_realization: List[_Segment] = Field(
        default_factory=list
    )

    overlap_degree: str = Field(
        description=(
            "none | superficial | partial | substantial | same "
            "(overlap of CONTRIBUTIONS, not topic)"
        )
    )

    what_is_shared: str = Field(
        default="",
        description="what this paper itself contributes that the submission also claims",
    )

    submission_delta: str = Field(
        default="",
        description="what substantive contribution remains in the submission beyond this paper",
    )

    assessment: str = Field(
        default="",
        description="the semantic comparison and overlap judgment in 2-4 sentences",
    )


_READ_CAP = 50000
_SUBMISSION_CONTEXT_CAP = 24000
_FALSIFY_SECTIONS = 2
_LOOP_MAX_TURNS = 4
_LOOP_MAX_COMPARES = 2
_FIRST_READ_N = 3

_SUBMISSION_SECTION_PICK = """Select the original SUBMISSION sections needed to compare ONE claimed contribution against prior work.

Choose where the paper actually delivers or substantiates the claim, including its
conditions and scope. For an empirical investigation or guideline claim, include the
actual findings and their conditions, not only the experimental design. For a theoretical
claim, include the result and assumptions; for a method or resource, include the
mechanism or construction and the properties relevant to the claim. These are examples,
not a required taxonomy. Do not exclude results or limitations by section type.

Select only sections relevant to this claim, in descending order of importance. They
will be reused, unchanged, by both the comparison and the evidence mapper. The source
context budget is {budget} characters; prefer a focused set that fits, using the sizes
shown below. An over-budget section will be reported as unavailable in full.

## Claim
{claim}

## Submission sections (title :: preview :: size)
{sections}

Return `sections`: the [S#] handles copied exactly from the menu, most important first.
Return `why`: what these sections establish about the claim."""

_SUBMISSION_REALIZE = """Explain what THE SUBMISSION ITSELF delivers for this specific claim, using ONLY the original source passages below. Describe the concrete contribution and its conditions or scope. For claims about an empirical investigation or practical guidelines, state the actual findings and the conditions studied, not just the setup. For other claims, explain the claimed result, mechanism or resource and the relevant assumptions. Do not introduce a novelty verdict, or infer missing properties from silence.

Write `segments` as a flowing explanation in reading order, alternating:
- kind="text": your own concise prose.
- kind="quote": a VERBATIM span copied CHARACTER-FOR-CHARACTER from the source text (no [Section] tag, no quotation marks). Quote the load-bearing specifics, including findings or assumptions when relevant. Every quote must be copyable verbatim from the text below.
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
- kind="quote": ONE CONTIGUOUS VERBATIM span copied CHARACTER-FOR-CHARACTER from the section text below (no [Section] tag, no quotation marks, and NEVER two passages joined by "..." -- a stitched span appears nowhere in the paper and fails the check; use a second quote segment instead). Quote the paper's OWN contribution -- NEVER quote descriptions of other cited work (related-work summaries, "X [12] is a ... dataset", "we adopt the following datasets"): that is a DIFFERENT paper's contribution, not this one's.
If the paper does NOT address the claimed contribution, say so briefly in one text segment (no quotes needed).

Then judge:
- overlap_degree: overlap of CONTRIBUTIONS, not topical similarity.

  * none =
    The prior paper does not itself deliver any meaningful part of the
    claimed contribution.

  * superficial =
    A real relationship exists, but it concerns topic, supporting machinery,
    evaluation context, or another relationship that does not itself constitute
    substantive contribution overlap.

  * partial =
    The prior paper itself delivers a meaningful substantive part of the claimed
    contribution, but the submission still retains a distinct central contribution.
    After subtracting what the prior paper already delivers, important novelty remains.

  * substantial =
    The prior paper already delivers the central contribution, or most of what makes
    the claimed contribution substantive. After subtracting that overlap, what remains
    is mainly a different design, scope, data choice, realization, or extension rather
    than a distinct central contribution.

  * same =
    The prior paper already delivers essentially the claimed contribution itself.
    The submission adds little substantive novelty beyond it.

Decide in this order:
1. What does THIS prior paper itself contribute?
2. What substantive contribution is genuinely shared?
3. What substantive contribution remains in the submission?
4. Assign the degree from the definitions above.

Do not determine the degree from the number of shared details.
## Claim
{claim}

## What the submission itself does for this claim
{realization}

## Prior paper
{title}

## Sections read from this paper
{sections}
"""

_PAPER_ACTION = """You are adaptively examining ONE prior-work paper against ONE claimed contribution.

Choose exactly ONE next action:

- `read_more`: read additional sections when they could resolve an important uncertainty
  or materially sharpen a plausible overlap.
- `propose_dismissal`: use when you understand THIS PAPER's own contribution and the
  evidence supports that it does not plausibly instantiate any substantive component
  of the claimed contribution.
- `propose_compare`: use when the paper's own contribution and its relation to the claim
  are clear enough for a meaningful comparison.

Use reading effort selectively.

If overlap appears weak and the paper's own contribution is already clear, do not keep
reading merely to prove absence.

If substantive overlap appears plausible, use `read_more` when additional sections could
make the comparison materially more precise.

Do not require exhaustive certainty before `propose_compare`.

Judge only what THIS PAPER itself contributes. Topical similarity and descriptions of
other cited work are not contribution overlap.

When using `read_more`, select only unread sections that serve a specific unresolved
question or refinement objective, and state that objective in `suspected_deficit`.

Name sections by their [S#] handle, copied exactly from the list below. A handle that is
not on that list opens nothing.

{mandate}

{deficits}

## Claim
{claim}

## What the submission itself does to realize this claim
{realization}

## Prior paper
{title}

## Full text of sections already read
{read}

## Selectable unread sections that fit the remaining read budget
{unread}
"""

_FALSIFY_DISMISSAL = """A reading agent proposes to set one prior-work paper aside as having no bearing on a claimed contribution. Before that can stand, the proposal has to survive a look at what would contradict it.

Name the {n} sections, from the UNREAD list below, most likely to contain something that would REFUTE the dismissal -- a contribution of this paper that does bear on the claim after all.

Look for where a paper states what it delivers and what it was measured on: what it built, the artifact or resource it releases, what its evaluation covers. Do not pick sections that would merely confirm the dismissal, and do not pick by size.

## Claim
{claim}

## Prior paper: {title}
## The reason given for dismissing it
{why}

## What has been read
{read}

## Selectable unread sections that fit the remaining read budget (handle :: title :: preview :: size)
{unread}

Return `sections`: the [S#] handles to open, copied exactly from the list above.
Return `why`: in one sentence, what each of those sections could contain that would refute the dismissal."""

_EVIDENCE_REENTRY_MANDATE = """
An earlier evidence check found an unresolved evidence deficit.

Before another comparison can be proposed, inspect additional evidence that could
resolve that specific deficit.

Use `read_more` on this turn and select only unread sections that are relevant to
the outstanding deficit.

`propose_compare` and `propose_dismissal` are not available on this turn.
"""

_FIRST_READ_MANDATE = """
This is the first turn.

Use `read_more` and select exactly 3 unread sections with the highest expected information
value for identifying THIS PAPER's own contribution and its relation to the claim.

`propose_compare` and `propose_dismissal` are not available yet.
"""


def _fill(template: str, **kw) -> str:
    """Placeholder substitution that tolerates literal braces in the values."""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def rl_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def _section_ids(menu: List[dict]) -> dict:
    """{section name: handle S1, S2, ...} in menu order."""
    return {m["name"]: f"S{i + 1}" for i, m in enumerate(menu)}


def _resolve_sections(requested, menu: List[dict], ids: dict):
    """Map requested handles or titles to section names.

    A token resolves by handle, then by exact title, then by a unique title suffix.
    Returns (names, unresolved tokens).
    """
    by_id = {v.casefold(): k for k, v in ids.items()}
    by_title = {" ".join(m["name"].split()).casefold(): m["name"] for m in menu}
    names, unresolved = [], []
    for raw in (requested or []):
        tok = str(raw or "").strip().strip("[]").strip()
        if not tok:
            continue
        key = " ".join(tok.split()).casefold()
        lead = re.match(r"^\[?\s*(s\d+)\s*\]?(?:\s|$)", key)
        hit = by_id.get(lead.group(1)) if lead else None
        hit = hit or by_id.get(key) or by_title.get(key)
        if hit is None:
            tail = [n for t, n in by_title.items()
                    if t.endswith("> " + key) or t.endswith(key)]
            hit = tail[0] if len(tail) == 1 else None
        if hit is None:
            unresolved.append(tok)
        elif hit not in names:
            names.append(hit)
    return names, unresolved


def _fmt_sections_menu(menu: List[dict], ids: dict) -> str:
    """Section menu with handle, title, preview and size per line."""
    return "\n".join(
        f"- [{ids[m['name']]}] {m['name']} :: {m.get('preview','')[:160]} "
        f":: ~{m.get('chars',0)} chars"
        for m in menu if m["name"] in ids) or "(no sections)"


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
        model_name: str = "gpt-5.6-luna",
        embedder=None,
        max_retrievals: int = 1,
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
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.grobid_server = grobid_server
        if deep_dive_workers is None:
            try:
                deep_dive_workers = int(os.getenv("NOVELTY_DEEP_DIVE_WORKERS", "4"))
            except ValueError:
                deep_dive_workers = 4
        self.deep_dive_workers = max(1, deep_dive_workers)
        try:
            timeout = float(os.getenv("NOVELTY_LLM_TIMEOUT", "180"))
        except ValueError:
            timeout = 180.0
        try:
            max_retries = int(os.getenv("NOVELTY_LLM_MAX_RETRIES", "6"))
        except ValueError:
            max_retries = 6

        # One client per role (reading, compare, evidence), each with its own model and
        # reasoning effort, overridable via NOVELTY_<ROLE>_MODEL / NOVELTY_<ROLE>_EFFORT.
        _llm_cache: dict = {}

        def get_llm(model: str, effort: str) -> ChatOpenAI:
            key = (model, effort)
            if key not in _llm_cache:
                is_reasoning = model.startswith(("gpt-5", "o1", "o3", "o4"))
                kw = ({"reasoning_effort": effort} if is_reasoning else {"temperature": 0.0})
                _llm_cache[key] = ChatOpenAI(model_name=model, api_key=api_key,
                                             max_retries=max_retries, timeout=timeout, **kw)
            return _llm_cache[key]

        def role_llm(env_model: str, env_effort: str, default_effort: str) -> ChatOpenAI:
            model = os.getenv(env_model, model_name)
            effort = os.getenv(env_effort, default_effort)
            return get_llm(model, effort)

        self._role_llm = {
            "reading": role_llm("NOVELTY_READING_MODEL", "NOVELTY_READING_EFFORT", "low"),
            "compare": role_llm("NOVELTY_COMPARE_MODEL", "NOVELTY_COMPARE_EFFORT", "low"),
            "evidence": role_llm("NOVELTY_EVIDENCE_MODEL", "NOVELTY_EVIDENCE_EFFORT", "low"),
        }
        self.llm = self._role_llm["reading"]
        self._cache_stats: dict = {}

    @staticmethod
    def _claim_str(claim: dict) -> str:
        return (f"{claim.get('name','')} — {claim.get('claim_text','')} "
                f"({claim.get('description','')})").strip()

    def _new_run_log(self, claim: dict):
        """Run log with the configuration this claim run is started under."""
        from . import run_log as rl

        log = rl.RunLog(self.submission_id, claim.get("id", ""), self.data_dir)
        repo_root = Path(__file__).resolve().parents[3]

        def role_cfg(role: str, env_model: str, env_effort: str, default_effort: str) -> dict:
            llm = self._role_llm.get(role)
            return {
                "model": os.getenv(env_model, self.model_name),
                "reasoning_effort": os.getenv(env_effort, default_effort),
                "client_model": getattr(llm, "model_name", "") or getattr(llm, "model", ""),
            }

        try:
            sub_meta = json.loads(
                (Path(self.data_dir) / self.submission_id /
                 f"{self.submission_id}.json").read_text(encoding="utf-8"))
        except Exception:
            sub_meta = {}

        import sys as _sys
        _sys.path.insert(0, str(repo_root / "src" / "retrieval"))
        try:
            import paper_versions as pv
            gap = pv.DEFAULT_MIN_GAP_DAYS
        except Exception:
            gap = None

        log.config = {
            "git": rl.git_commit(
                repo_root,
                save_diff_to=(Path(self.data_dir) / self.submission_id / "run_logs"
                              / f"{claim.get('id', 'claim')}_{log.run_id}.diff")),
            "agent_model_default": self.model_name,
            "roles": {
                "reading": role_cfg("reading", "NOVELTY_READING_MODEL",
                                    "NOVELTY_READING_EFFORT", "low"),
                "compare": role_cfg("compare", "NOVELTY_COMPARE_MODEL",
                                    "NOVELTY_COMPARE_EFFORT", "low"),
                "evidence": role_cfg("evidence", "NOVELTY_EVIDENCE_MODEL",
                                     "NOVELTY_EVIDENCE_EFFORT", "low"),
            },
            "budgets": {
                "read_cap_chars": _READ_CAP,
                "loop_max_turns": _LOOP_MAX_TURNS,
                "loop_max_compares": _LOOP_MAX_COMPARES,
                "first_read_sections": _FIRST_READ_N,
                "falsify_sections": _FALSIFY_SECTIONS,
                "submission_context_cap": _SUBMISSION_CONTEXT_CAP,
                "deep_dive_workers": self.deep_dive_workers,
                "min_quote_tokens": self.min_quote_tokens,
                "fuzzy_threshold": self.fuzzy_threshold,
            },
            "cutoff": {
                "submission_date": str(sub_meta.get("publication_date")
                                       or sub_meta.get("year") or ""),
                "min_gap_days": gap,
            },
            "prompts": rl.prompt_hashes(_sys.modules[__name__]),
            "schemas": rl.schema_hashes({
                "SectionPick": _SectionPick, "PaperAction": _PaperAction,
                "SectionComparison": _SectionComparison, "Realization": _Realization,
            }),
        }
        log.config["prompts"].update(rl.prompt_hashes(evidence_map))
        log.config["schemas"].update(rl.schema_hashes({
            "EvidenceMap": evidence_map.EvidenceMap,
            "Correspondence": evidence_map.Correspondence,
            "EvidenceCheck": evidence_map.EvidenceCheck,
        }))
        return log

    def _struct(self, model, prompt, role: str = "reading"):
        """Structured call on the client of `role`; returns (parsed, prompt_tokens, completion_tokens)."""
        llm = self._role_llm.get(role, self.llm)
        res = llm.with_structured_output(model, include_raw=True).invoke(prompt)
        parsed, raw = res.get("parsed"), res.get("raw")
        pt, ct = _usage(raw) if raw is not None else (0, 0)
        cached = _cache_read(raw) if raw is not None else 0
        st = self._cache_stats.setdefault(
            role, {"calls": 0, "prompt_tokens": 0, "cached_tokens": 0})
        st["calls"] += 1
        st["prompt_tokens"] += pt
        st["cached_tokens"] += cached
        return parsed, pt, ct

    def _build_submission_basis(self, tb: ClaimToolbox, claim: dict):
        """Claim-local context of the submission, selected once per claim.

        Complete sections are loaded in the selected order up to the context budget. If none
        can be loaded, the full text is used when it fits, otherwise retrieved excerpts.
        """
        pt = ct = 0
        cap = _SUBMISSION_CONTEXT_CAP
        menu = tb.section_menu("submission") or []

        blocks, sources, omitted, notes = [], [], [], []
        used = 0
        requested = []
        asked_handles, why = [], ""

        def append_source(name, text, kind, passage_id=None):
            nonlocal used
            text = (text or "").strip()
            if not text:
                return False
            block = f"## {name}\n{text}"
            cost = len(block) + (2 if blocks else 0)
            if used + cost > cap:
                return False
            blocks.append(block)
            sources.append({"section": name, "kind": kind, "passage_id": passage_id})
            used += cost
            return True

        if menu:
            ids = _section_ids(menu)
            parsed, a, b = self._struct(
                _SectionPick,
                _fill(
                    _SUBMISSION_SECTION_PICK,
                    claim=self._claim_str(claim),
                    sections=_fmt_sections_menu(menu, ids=ids),
                    budget=cap,
                ),
            )
            pt += a
            ct += b

            asked_handles = list(getattr(parsed, "sections", None) or [])
            why = (getattr(parsed, "why", "") or "").strip()
            requested, unresolved = _resolve_sections(asked_handles, menu, ids)
            if unresolved:
                notes.append("Unresolved section requests: " + ", ".join(unresolved))
            if not requested:
                notes.append("No usable section selection; using source-text fallback.")

            for name in requested:
                overhead = len(f"## {name}\n") + (2 if blocks else 0)
                remaining = max(0, cap - used - overhead)
                secs = tb.read_sections(
                    "submission", [name], max_total=remaining, exact=True,
                ).get("sections", []) or []
                sec = next((s for s in secs if s.get("name") == name), None)
                if sec is None:
                    omitted.append({"section": name, "reason": "not returned by read_sections",
                                    "remaining_chars": remaining})
                elif not append_source(name, sec.get("text"), "section"):
                    omitted.append({"section": name,
                                    "reason": "would exceed the context budget",
                                    "section_chars": len(sec.get("text") or ""),
                                    "remaining_chars": remaining})

        if not blocks:
            if append_source("Submission full text", tb._submission_text, "full_text"):
                notes.append("Fallback: full submission fits the context budget.")
                omitted = []
            else:
                hits = tb.search_submission(self._claim_str(claim), k=6).get("passages") or []
                for i, hit in enumerate(hits, 1):
                    name = hit.get("section") or "Submission"
                    pid = hit.get("passage_id") or f"retrieved-{i}"
                    append_source(f"{name} [retrieved excerpt: {pid}]", hit.get("text"),
                                  "excerpt", pid)
                notes.append("Fallback: retrieved excerpts; full sections were unavailable.")

        text = "\n\n".join(blocks)
        if not text:
            raise ValueError("No original submission passages available for comparison.")

        kinds = sorted({s.get("kind") for s in sources if s.get("kind")})
        basis = {
            "text": text,
            "sources": sources,
            "requested_sections": requested,
            "omitted_sections": omitted,
            "notes": notes,
            "max_chars": cap,
            "chars": len(text),
            "source_sha256": hashlib.sha256(tb._submission_text.encode("utf-8")).hexdigest(),
            "context_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "content_kinds": kinds,
        }

        log = getattr(tb, "run_log", None)
        if log is not None:
            basis["context_id"] = log.register_context(
                "submission", text,
                claim_id=claim.get("id", ""),
                sections=[s.get("section") for s in sources],
                content_kinds=kinds,
                budget_chars=cap,
            )
            log.submission_selection = {
                "requested_handles": asked_handles,
                "resolved_sections": requested,
                "loaded_sections": [s.get("section") for s in sources],
                "why": why,
                "omitted_sections": omitted,
                "notes": notes,
                "context_id": basis["context_id"],
                "context_sha256": basis["context_sha256"],
                "chars": len(text),
                "budget_chars": cap,
                "content_kinds": kinds,
                "source_sha256": basis["source_sha256"],
            }

        tb.submission_basis = basis
        tb._log(
            "submission_basis",
            f"{len(sources)} source blocks, {len(text):,}/{cap:,} chars "
            f"[{basis.get('context_id', 'ctx?')}], kinds={','.join(kinds) or '-'}; "
            f"{len(omitted)} sections omitted; " + "; ".join(notes)
        )
        return basis, pt, ct

    def _understand_submission(self, tb: ClaimToolbox, claim: dict):
        """Build the claim-local context and explain what the submission delivers for the claim."""
        basis, pt, ct = self._build_submission_basis(tb, claim)
        parsed, a, b = self._struct(
            _Realization,
            _fill(_SUBMISSION_REALIZE, claim=self._claim_str(claim), sections=basis["text"]),
        )
        pt += a
        ct += b
        raw = [s.model_dump() for s in (getattr(parsed, "segments", None) or [])] if parsed else []
        realization = tb.verify_segments(raw, "submission")
        tb.claim_realization = realization
        tb._log("understand_submission", "explanation from shared original-source context")
        return realization, basis["text"], pt, ct

    def _examine_paper(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str,
                       carry_deficit: str = "", state: Optional[dict] = None):
        """Reading loop for one paper until the agent compares or sets the paper aside.

        Turn 0 reads exactly three sections. The first proposal to set the paper aside
        triggers reading of the unread sections most likely to refute it. With
        `carry_deficit` (re-entry after a failed evidence check), at least one new
        section must be read before comparing again. `state` carries the sections read
        and the budget across calls for the same paper.

        Returns (decision, context, sections_read, why, pt, ct, trace, state), where
        decision is "compare", "dismiss" or "insufficient".
        """
        pt = ct = 0
        trace: List[str] = []
        claim_s = self._claim_str(claim)[:1200]
        title = (tb.pool.get(pid, {}) or {}).get("title", "")
        menu = tb.section_menu(pid) or []
        if not menu:
            return "compare", "", [], "", pt, ct, ["no section menu"], {}

        def struct(schema, prompt):
            nonlocal pt, ct
            try:
                parsed, a, b = self._struct(schema, prompt, role="reading")
            except Exception as e:
                trace.append(f"call failed ({type(e).__name__})")
                return None
            pt += a; ct += b
            return parsed

        state = state or {}
        got: List[dict] = list(state.get("got") or [])
        read: List[str] = list(state.get("read") or [])
        used = int(state.get("used") or 0)
        falsification_done = bool(state.get("falsification_done"))
        resuming = bool(got or read)
        deficits: List[str] = []
        why = ""
        cap_hit = False
        last_take = (0, 0, 0)

        if carry_deficit:
            deficits.append(carry_deficit)
        reentry_requires_read = bool(carry_deficit)
        sec_ids = _section_ids(menu)

        def resolve(requested):
            return _resolve_sections(requested, menu, sec_ids)

        def unread():
            return [m for m in menu if m["name"] not in set(read)]

        def fitting_unread():
            remaining = max(0, _READ_CAP - used)
            return [m for m in unread() if int(m.get("chars") or 0) <= remaining]

        def take(names):
            """Read exactly the named sections that are unread and fit the budget."""
            nonlocal used, last_take
            selectable = {m["name"] for m in fitting_unread()}
            new = [n for n in (names or []) if n and n not in read and n in selectable]
            if not new:
                last_take = (len(names or []), 0, 0)
                return []
            secs = tb.read_sections(pid, new, max_total=max(0, _READ_CAP - used),
                                    exact=True).get("sections", []) or []
            done, added = [], 0
            for s in secs:
                if s["name"] not in read:
                    got.append(s); read.append(s["name"])
                    n = len(s.get("text", ""))
                    used += n; added += n; done.append(s["name"])
            last_take = (len(names or []), len(done), added)
            return done

        def log_read(turn, label, names, reason):
            req, loaded, added = last_take
            trace.append(f"turn {turn}: {label} -> {len(names)} sections")
            trace.extend(f"  - {n}" for n in names)
            trace.append(f"  requested: {req}")
            trace.append(f"  loaded: {loaded}")
            trace.append(f"  chars added: {added:,}")
            trace.append(f"  total chars: {used:,}/{_READ_CAP:,}")
            if reason:
                trace.append(f"  reason: {' '.join(reason.split())}")

        def deficit_block():
            if not deficits:
                return ""
            return ("\n## Still outstanding -- a check refused an earlier proposal for these\n"
                    + "\n".join(f"- {d}" for d in deficits[-3:]) + "\n")

        def exhausted(turn):
            """True when no further complete section can be read."""
            nonlocal cap_hit
            if used >= _READ_CAP:
                cap_hit = True
                trace.append(f"turn {turn}: read cap exhausted ({used:,}/{_READ_CAP:,} chars)")
                return True
            if not unread():
                trace.append(f"turn {turn}: all sections read ({len(read)}/{len(menu)})")
                return True
            if not fitting_unread():
                cap_hit = True
                trace.append(f"turn {turn}: no complete unread section fits remaining "
                             f"budget ({_READ_CAP - used:,} chars)")
                return True
            return False

        decision = None
        for turn in range(_LOOP_MAX_TURNS):
            if exhausted(turn):
                if reentry_requires_read:
                    decision = "insufficient"
                    trace.append(f"turn {turn}: evidence deficit remains and no further "
                                 "complete section can be read -> INSUFFICIENT")
                else:
                    decision = "compare"
                break

            if not got and not resuming:
                mandate = _FIRST_READ_MANDATE
            elif reentry_requires_read:
                mandate = _EVIDENCE_REENTRY_MANDATE
            else:
                mandate = ""
            act = struct(_PaperAction, _fill(
                _PAPER_ACTION,
                claim=claim_s,
                realization=claim_ctx,
                title=title,
                read=(_fmt_sections_full(got, max_total=_READ_CAP) if got
                      else "(nothing yet -- this turn must be a read)"),
                unread=_fmt_sections_menu(fitting_unread(), ids=sec_ids),
                deficits=deficit_block(),
                mandate=mandate,
            ))
            if act is None:
                if reentry_requires_read:
                    decision = "insufficient"
                    trace.append(f"turn {turn}: reading action failed during evidence re-entry "
                                 "-> INSUFFICIENT")
                else:
                    decision = "compare"
                    trace.append(f"turn {turn}: no action -> compare")
                break
            tool = (act.tool or "").strip().lower()
            trace.append(f"turn {turn}: proposed action={tool}, sections={list(act.sections or [])}")

            if reentry_requires_read and tool != "read_more":
                trace.append(f"turn {turn}: {tool or 'invalid action'} rejected -- "
                             "evidence re-entry requires read_more first")
                continue

            if act.suspected_deficit and act.suspected_deficit.strip() not in deficits:
                deficits.append(act.suspected_deficit.strip())

            if not got and not resuming:
                wanted, unresolved = resolve(act.sections)
                names = take(wanted[:_FIRST_READ_N])
                if unresolved:
                    trace.append(f"  unresolved: {', '.join(unresolved[:6])}")
                if len(names) < _FIRST_READ_N:
                    names += take([m["name"] for m in sorted(
                        fitting_unread(), key=lambda m: -m.get("chars", 0)
                    )][:_FIRST_READ_N - len(names)])
                log_read(turn, f"mandatory initial read ({_FIRST_READ_N} sections)",
                         names, act.why)
                if not names:
                    decision = "compare"
                    trace.append(f"turn {turn}: nothing readable -> compare")
                    break
                continue

            if tool == "read_more":
                wanted, unresolved = resolve(act.sections)
                names = take(wanted)
                log_read(turn, "read_more", names, act.why)
                if unresolved:
                    trace.append(f"  unresolved: {', '.join(unresolved[:6])}")

                if not names:
                    if unread():
                        # Unmatched request: the agent chooses again.
                        invalid_note = (
                            "ACTION INVALID: none of "
                            f"{', '.join(unresolved[:6]) or 'the sections named'} matched an "
                            "unread section. Use the [S#] handles exactly as the menu "
                            "prints them."
                        )
                        if invalid_note not in deficits:
                            deficits.append(invalid_note)
                        trace.append(f"turn {turn}: ACTION INVALID -- requested "
                                     f"{len(act.sections or [])}, resolved 0, "
                                     f"{len(unread())} sections still unread -> choose again")
                        continue
                    if reentry_requires_read:
                        trace.append(f"turn {turn}: evidence re-entry read loaded nothing; "
                                     "deficit remains unresolved")
                        continue
                    decision = "compare"
                    trace.append(f"turn {turn}: no unread sections remain -> compare")
                    break

                if reentry_requires_read:
                    reentry_requires_read = False
                    trace.append("evidence re-entry satisfied by new reading -> compare")
                    decision = "compare"
                    break

            if tool in ("dismiss", "propose_dismissal"):
                if falsification_done:
                    decision, why = "dismiss", (act.why or "").strip()
                    trace.append(f"turn {turn}: propose_dismissal (falsification done) -> DISMISSED")
                    trace.append(f"  reason: {' '.join(why.split())}")
                    break
                trace.append(f"turn {turn}: propose_dismissal")
                left = fitting_unread()
                if not left:
                    falsification_done = True
                    trace.append(f"turn {turn}: dismissal falsification exhausted "
                                 f"(no unread sections left)")
                    continue
                trace.append(f"turn {turn}: dismissal falsification required")
                pick = struct(_SectionPick, _fill(
                    _FALSIFY_DISMISSAL, claim=claim_s, title=title,
                    why=(act.why or "")[:600],
                    read=_fmt_sections_full(got, max_total=_READ_CAP),
                    unread=_fmt_sections_menu(left, ids=sec_ids), n=_FALSIFY_SECTIONS))
                asked = (getattr(pick, "sections", None) or []) if pick else []
                wanted, unresolved = resolve(asked)
                names = take(wanted[:_FALSIFY_SECTIONS])
                if unresolved:
                    trace.append(f"  unresolved: {', '.join(unresolved[:6])}")
                chosen = len(names)
                if len(names) < min(_FALSIFY_SECTIONS, len(left)):
                    names += take([m["name"] for m in sorted(
                        fitting_unread(), key=lambda m: -m.get("chars", 0)
                    )][:_FALSIFY_SECTIONS - len(names)])
                trace += [f"  - {n}" for n in names]
                trace.append(f"  requested: {min(_FALSIFY_SECTIONS, len(left))}")
                trace.append(f"  loaded: {len(names)}")
                trace.append(f"  chars added: {last_take[2]:,}")
                trace.append(f"  total chars: {used:,}/{_READ_CAP:,}")
                trace.append(f"  reason: {(getattr(pick, 'why', '') or '(none given)')}")
                if len(names) > chosen:
                    trace.append(f"  FALLBACK: agent named {chosen} usable section(s), "
                                 f"{len(names) - chosen} filled in by size")
                required = min(_FALSIFY_SECTIONS, len(left))
                if len(names) >= required:
                    falsification_done = True
                    trace.append(f"turn {turn}: dismissal_falsification_done=True")
                else:
                    trace.append(f"turn {turn}: dismissal falsification incomplete "
                                 f"({len(names)}/{required} complete sections read)")
                continue

            decision = "compare"
            trace.append(f"turn {turn}: propose_compare -> COMPARE")
            break
        else:
            if reentry_requires_read:
                decision = "insufficient"
                trace.append(f"BUDGET: {_LOOP_MAX_TURNS} turns exhausted while evidence "
                             "re-entry still required an actual new read -> INSUFFICIENT")
            else:
                decision = decision or "compare"
                trace.append(f"BUDGET: {_LOOP_MAX_TURNS} turns exhausted -> compare")
        next_state = {"got": got, "read": read, "used": used,
                      "falsification_done": falsification_done}
        return (decision, _fmt_sections_full(got, max_total=_READ_CAP), read, why,
                pt, ct, trace + ([f"read cap was reached ({used:,}/{_READ_CAP:,} chars)"]
                                 if cap_hit else []), next_state)

    def _paper_loop(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str):
        """Read, compare and check one paper; re-enter reading after a failed check.

        After `_LOOP_MAX_COMPARES` comparisons, or when nothing more can be read, an open
        assessment is kept and marked unresolved. Returns (comp, pt, ct, trace).
        """
        pt = ct = 0
        trace: List[str] = []
        deficit = ""
        comp = self._to_comp(None)
        read_state: Optional[dict] = None
        for turn in range(_LOOP_MAX_COMPARES):
            decision, context, names, why, a, b, tr, read_state = self._examine_paper(
                tb, claim, pid, claim_ctx, carry_deficit=deficit, state=read_state)
            pt += a; ct += b
            trace += [f"[read {turn}] {t}" for t in tr]

            if decision == "dismiss":
                comp = self._to_comp(None)
                comp["overlap_degree"] = "superficial"
                comp["dismissed"] = True
                comp["brief_note"] = comp["assessment"] = why or (
                    "Read at section level; the paper's subject is a different contribution.")
                trace.append(f"[{turn}] dismissed after {len(names)} sections")
                return comp, pt, ct, trace
            if decision == "insufficient":
                comp = dict(comp)
                comp["unresolved_deficit"] = deficit or (
                    "Evidence re-entry required additional reading, "
                    "but no new readable section was obtained."
                )
                comp["paper_state"] = "unresolved_budget"
                comp["insufficient"] = True
                comp["unresolved"] = True
                comp["unresolved_reason"] = "reading_budget_exhausted"
                comp["refutation_status"] = "cannot_refute"
                trace.append(
                    f"[{turn}] BUDGET: no further readable evidence available -- "
                    f"keeping last semantic assessment "
                    f"({comp.get('overlap_degree', '')}) as best available assessment; "
                    f"UNRESOLVED"
                )
                return comp, pt, ct, trace
            comp, a, b = self._section_compare(tb, claim, pid, claim_ctx, context, turn=turn)
            pt += a; ct += b
            self._trace_raw(trace, turn, comp)

            comp, a, b = self._map_evidence(tb, claim, pid, comp, context, turn=turn)
            pt += a; ct += b
            self._trace_grounding(trace, turn, comp)

            deficit = self._evidence_deficit(comp) or ""
            if not deficit:
                trace.append(f"[{turn}] compared, evidence gate passed")
                return comp, pt, ct, trace
            cap_spent = any("read cap was reached" in t for t in tr)
            if cap_spent or turn + 1 >= _LOOP_MAX_COMPARES:
                # The last comparison is kept, but an unresolved pair can never challenge the claim.
                comp = dict(comp)
                comp["unresolved_deficit"] = deficit
                comp["paper_state"] = "unresolved_budget"
                comp["insufficient"] = True
                comp["unresolved"] = True
                comp["unresolved_reason"] = ("read_cap_exhausted" if cap_spent
                                             else "comparison_budget_exhausted")
                comp["refutation_status"] = "cannot_refute"
                why = "read cap" if cap_spent else f"{_LOOP_MAX_COMPARES} compares"
                trace.append(
                    f"BUDGET: {why} spent -- keeping last semantic assessment "
                    f"({comp.get('overlap_degree', '')}) as best available assessment; "
                    f"UNRESOLVED: {deficit}"
                )
                return comp, pt, ct, trace
            trace.append(f"[{turn}] evidence gate REFUSED -> read again: {deficit}")
        return comp, pt, ct, trace

    @staticmethod
    def _trace_raw(trace: List[str], turn: int, comp: dict) -> None:
        trace.append(f"[{turn}] RAW COMPARE: degree={comp.get('overlap_degree', '')}")
        trace.append(f"[{turn}] RAW ASSESSMENT: {comp.get('assessment', '')}")
        trace.append(f"[{turn}] RAW SHARED: {comp.get('what_is_shared', '')}")
        trace.append(f"[{turn}] RAW DELTA: {comp.get('submission_delta', '')}")

    @staticmethod
    def _trace_grounding(trace: List[str], turn: int, comp: dict) -> None:
        proposal = comp.get("comparison_proposal") or {}
        check = comp.get("evidence_check") or {}
        pairs = comp.get("evidence_pairs") or []
        raw_degree = (proposal.get("overlap_degree") or "").lower()
        final_degree = (comp.get("overlap_degree") or "").lower()
        evidence_status = (check.get("status") or "").lower()

        trace.append(f"[{turn}] SEMANTIC DEGREE: {raw_degree}")
        trace.append(f"[{turn}] SEMANTIC ASSESSMENT: {proposal.get('assessment', '')}")
        trace.append(f"[{turn}] SEMANTIC SHARED: {proposal.get('what_is_shared', '')}")
        trace.append(f"[{turn}] SEMANTIC DELTA: {proposal.get('submission_delta', '')}")
        trace.append(f"[{turn}] GROUNDED OWNED PAIRS: {len(pairs)}")
        for i, p in enumerate(pairs, 1):
            relation = " ".join(str(p.get("rationale", "")).split())
            submission_quote = " ".join(str(p.get("claim_quote", "")).split())
            paper_quote = " ".join(str(p.get("paper_quote", "")).split())
            trace.append(f"[{turn}] PAIR {i}: strength={p.get('strength', '')} | "
                         f"relation={relation}")
            trace.append(f'[{turn}] PAIR {i} SUBMISSION: "{submission_quote}"')
            trace.append(f'[{turn}] PAIR {i} PAPER: "{paper_quote}"')
        trace.append(f"[{turn}] EVIDENCE CHECK: status={evidence_status}")
        trace.append(f"[{turn}] EVIDENCE SUPPORTING PAIRS: "
                     f"{check.get('supporting_pair_indices', [])}")
        trace.append(f"[{turn}] EVIDENCE REASON: {check.get('reasoning', '')}")
        trace.append(f"[{turn}] PROPOSED DEGREE SUPPORTED: "
                     f"{check.get('proposed_degree_supported')}")
        if check.get("unresolved_question"):
            trace.append(f"[{turn}] UNRESOLVED QUESTION: {check['unresolved_question']}")
        semantic_material = raw_degree in {"partial", "substantial", "same"}
        trace.append(
            f"[{turn}] MATERIAL AGREEMENT: "
            f"semantic={'material' if semantic_material else 'nonmaterial'} | "
            f"evidence={evidence_status or 'missing'}"
        )
        trace.append(f"[{turn}] CURRENT SEMANTIC DEGREE: {final_degree}")

    @staticmethod
    def _evidence_deficit(comp: dict) -> Optional[str]:
        """Why the assessment is not settled (Equation 3.4), or None if it is."""
        diag = comp.get("map_diag") or {}
        proposal = comp.get("comparison_proposal") or {}
        proposed_deg = (proposal.get("overlap_degree") or "").lower()
        proposal_material = proposed_deg in {"partial", "substantial", "same"}

        if diag.get("call_failed"):
            return ("the evidence map did not complete, so the semantic comparison "
                    "has not been grounded")
        if proposal_material and diag.get("ownership_unchecked"):
            return ("the semantic comparison proposes substantive overlap, but ownership "
                    "of the candidate evidence could not be verified")
        if proposal_material and diag.get("not_owned") and not (comp.get("evidence_pairs") or []):
            return ("the semantic comparison proposes substantive overlap, but every "
                    "grounded candidate belongs to cited work rather than this paper")

        check = comp.get("evidence_check") or {}
        status = (check.get("status") or "").lower()
        question = (check.get("unresolved_question") or "").strip()

        if proposal_material and check.get("proposed_degree_supported") is not True:
            return question or (
                "The grounded evidence does not establish the specific proposed "
                "overlap and its degree. Check the comparison's actual rationale."
            )
        if status == "material" and not proposal_material and question:
            return question
        if not status:
            return "the evidence check produced no usable status"
        if status == "material" and not proposal_material:
            return ("grounded evidence supports substantive contribution overlap that "
                    "the semantic comparison did not recognize")
        if status == "nonmaterial" and proposal_material:
            return ("the semantic comparison proposes substantive overlap, but the "
                    "grounded evidence currently supports only non-substantive overlap")
        if status == "insufficient" and proposal_material:
            return ("the semantic comparison proposes substantive overlap, but the "
                    "available grounded evidence is insufficient to support it")
        return None

    def _section_compare(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str,
                         paper_context: str = "", turn: int = 0):
        """Semantic comparison of one paper with the claim on the sections read.

        Without a selected context the whole parsed paper is used, and without a parsed
        text the abstract passages.
        """
        pt = ct = 0
        paper_text = paper_context or tb._paper_source_text(pid)
        if not paper_text.strip():
            hits = tb.read_paper(pid, query=self._claim_str(claim))
            paper_text = _fmt_passages(
                hits.get("passages") or ([{"text": hits.get("abstract", "")}]
                                         if hits.get("abstract") else []))
        parsed, a, b = self._struct(
            _SectionComparison,
            _fill(
                _PAPER_COMPARE,
                claim=self._claim_str(claim)[:1200],
                realization=claim_ctx,
                title=tb.pool[pid]["title"],
                sections=paper_text,
            ),
            role="compare",
        ); pt += a; ct += b
        log = getattr(tb, "run_log", None)
        if log is not None:
            prov = tb.paper_provenance(pid)
            log.paper_source(pid, prov)
            has_ft = bool((tb.pool.get(pid) or {}).get("fulltext"))
            if paper_context:
                content_source = "agent_sections"
            elif has_ft:
                content_source = "fulltext"
            elif (tb.pool.get(pid) or {}).get("intro"):
                content_source = "abstract_and_intro"
            else:
                content_source = "abstract"
            ft_status = (getattr(tb, "_fulltext_status", {}) or {}).get(pid, "")
            fallback_reason = ""
            if content_source in ("abstract", "abstract_and_intro"):
                fallback_reason = (ft_status or prov.get("version_status", "")
                                   or "no parsed full text available")
            log.round_contexts(
                pid, turn, call="semantic_compare",
                submission_context=(tb.submission_basis or {}).get("context_id", ""),
                paper_context=log.register_context(
                    "paper", paper_text, paper_id=pid,
                    content_source=content_source,
                    fulltext_status=ft_status,
                    fallback_reason=fallback_reason,
                    sections=list(tb._sections_read.get(pid) or [])),
            )
        if not paper_context:
            tb._sections_read.setdefault(pid, [])
            tb._sections_read[pid] = ["(full text)"]
        return self._to_comp(parsed), pt, ct

    @staticmethod
    def _to_comp(parsed) -> dict:
        """A _SectionComparison (or None) as the comparison record."""
        if parsed is None:
            return {"refutation_status": "unclear", "overlap_degree": "none", "what_is_shared": "",
                    "submission_delta": "", "brief_note": "", "assessment": "",
                    "paper_realization": [], "evidence_pairs": []}
        return {
            "refutation_status": "unclear",
            "overlap_degree": parsed.overlap_degree,
            "what_is_shared": parsed.what_is_shared or "",
            "submission_delta": parsed.submission_delta or "",
            "brief_note": "",
            "assessment": parsed.assessment or "",
            "paper_realization": [{"kind": s.kind or "text", "content": s.content}
                                  for s in (parsed.paper_realization or [])],
            "evidence_pairs": [],
        }

    def _record(self, tb: ClaimToolbox, pid: str, comp: dict):
        """Record the comparison in the ledger, where its quotes are verified."""
        rlog = getattr(tb, "run_log", None)
        if rlog is not None:
            try:
                rlog.paper_outcome(
                    pid, comp, tb.paper_provenance(pid),
                    sections_used=list(tb._sections_read.get(pid) or []),
                    fulltext_fetch_status=comp.get("fulltext_fetch_status")
                    or (tb._fulltext_status.get(pid) if hasattr(tb, "_fulltext_status") else ""))
            except Exception:
                pass

        tb.record_comparison(
            paper_id=pid,
            refutation_status=comp["refutation_status"],
            brief_note=comp["brief_note"],
            overlap_degree=comp["overlap_degree"],
            what_is_shared=comp["what_is_shared"],
            submission_delta=comp["submission_delta"],
            evidence_pairs=comp["evidence_pairs"],
            extra={
                k: comp[k]
                for k in ("map_diag", "comparison_proposal", "evidence_check",
                          "unresolved_deficit", "paper_state", "insufficient")
                if k in comp
            },
            paper_realization=comp.get("paper_realization"),
            assessment=comp.get("assessment", ""),
            fulltext_fetch_status=comp.get("fulltext_fetch_status"),
        )

    def _map_evidence(self, tb: "ClaimToolbox", claim: dict, pid: str, comp: dict,
                      paper_context: str = "", turn: int = 0):
        """Evidence gate: evidence map, verbatim and ownership checks, evidence check.

        The model searches the claim-local context and the sections read. Quotes are
        verified against the full texts of both documents. The proposed degree is kept;
        the comparison can refute the claim only if the check supports it.
        """
        pt = ct = 0

        def struct(schema, prompt):
            nonlocal pt, ct
            try:
                parsed, a, b = self._struct(schema, prompt, role="evidence")
            except Exception as e:
                tb._log("evidence_map", f"{pid}: call failed ({type(e).__name__})")
                return None
            pt += a; ct += b
            return parsed

        basis = getattr(tb, "submission_basis", None) or {}
        submission_text = basis.get("text", "")
        if not submission_text.strip():
            raise ValueError("Build the shared submission basis before evidence mapping.")
        paper_text = paper_context or tb._paper_source_text(pid)
        if not (submission_text.strip() and paper_text.strip()):
            return comp, pt, ct

        claim_str = self._claim_str(claim)
        raw_proposal = {
            "overlap_degree": comp.get("overlap_degree", ""),
            "refutation_status": comp.get("refutation_status", ""),
            "what_is_shared": comp.get("what_is_shared", ""),
            "submission_delta": comp.get("submission_delta", ""),
            "assessment": comp.get("assessment", ""),
        }
        comp = dict(comp)
        comp["comparison_proposal"] = raw_proposal

        log = getattr(tb, "run_log", None)
        if log is not None:
            log.paper_source(pid, tb.paper_provenance(pid))
            log.round_contexts(
                pid, turn, call="evidence_map",
                submission_context=log.register_context(
                    "submission", submission_text, paper_id=pid, role="evidence_map"),
                paper_context=log.register_context(
                    "paper", paper_text, paper_id=pid, role="evidence_map"),
                verification_submission_sha256=rl_sha(tb._submission_text),
                verification_paper_sha256=rl_sha(tb._paper_source_text(pid)),
            )
        mapping = evidence_map.build_map(
            struct,
            claim_str,
            submission_text,
            tb.pool.get(pid, {}).get("title", ""),
            paper_text,
            tb._submission_text,
            tb._paper_source_text(pid),
            self.min_quote_tokens,
            self.fuzzy_threshold,
            comparison=raw_proposal,
        )
        kept = mapping["pairs"]
        comp["map_diag"] = {
            "submission_chars": len(submission_text),
            "paper_chars": len(paper_text),
            "returned": mapping.get("returned", 0),
            "unverified": mapping.get("dropped", 0),
            "not_owned": mapping.get("not_owned", 0),
            "ownership_unchecked": mapping.get("ownership_unchecked", 0),
            "kept": len(kept),
            "call_failed": bool(mapping.get("failed")),
        }
        if mapping.get("failed"):
            tb._log("evidence_map", f"{pid}: map call failed -- keeping the deep dive's verdict")
            return comp, pt, ct

        check = evidence_map.check_evidence(
            struct,
            claim_str,
            mapping,
            comparison=raw_proposal,
            submission_context=submission_text,
        )
        comp["evidence_check"] = {
            "status": check.get("status", "insufficient"),
            "prompt_version": evidence_map.EVIDENCE_CHECK_PROMPT_VERSION,
            "reasoning": check.get("reasoning", ""),
            "supporting_pair_indices": check.get("supporting_pair_indices", []),
            "grounded_pairs": len(kept),
            "proposed_degree_supported": check.get("proposed_degree_supported"),
            "unresolved_question": check.get("unresolved_question", ""),
        }
        comp["evidence_pairs"] = kept
        comp["overlap_degree"] = raw_proposal["overlap_degree"]
        comp["assessment"] = raw_proposal["assessment"]
        comp["what_is_shared"] = raw_proposal["what_is_shared"]
        comp["submission_delta"] = raw_proposal["submission_delta"]

        raw_degree = (raw_proposal.get("overlap_degree") or "").lower()
        supporting = check.get("supporting_pair_indices") or []
        comp["refutation_status"] = (
            "can_refute"
            if (raw_degree in ("substantial", "same")
                and check.get("status") == "material"
                and bool(supporting)
                and check.get("proposed_degree_supported") is True)
            else "cannot_refute"
        )
        tb._log(
            "evidence_map",
            f"{pid}: {len(kept)} grounded-owned pairs; "
            f"comparison={raw_degree}, "
            f"evidence_check={check.get('status', 'insufficient')}"
        )
        return comp, pt, ct

    def _deep_dive(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str):
        """Parse one paper, run its loop and record the result."""
        tb._log("deep_dive", pid)
        _p0 = time.perf_counter()
        fts = tb.ensure_fulltext(pid)
        parse_s = time.perf_counter() - _p0
        _c0 = time.perf_counter()
        comp, pt, ct, trace = self._paper_loop(tb, claim, pid, claim_ctx)
        comp.setdefault("map_diag", {})["loop"] = trace
        compare_s = time.perf_counter() - _c0
        comp["fulltext_fetch_status"] = fts
        self._record(tb, pid, comp)
        return pt, ct, {"paper_id": pid,
                        "title": (tb.pool.get(pid, {}) or {}).get("title", "")[:90],
                        "parse_s": round(parse_s, 1),
                        "compare_s": round(compare_s, 1),
                        "total_s": round(parse_s + compare_s, 1),
                        "fetch_status": fts}

    def run(self, claim: dict, progress_cb=None) -> dict:
        """Assess one claim against the whole pool; returns the artifact entry."""
        tb = ClaimToolbox(
            self.data_dir, self.submission_id, claim, self.embedder,
            min_quote_tokens=self.min_quote_tokens,
            fuzzy_threshold=self.fuzzy_threshold, grobid_server=self.grobid_server,
        )
        self.run_log = tb.run_log = self._new_run_log(claim)
        pt = ct = 0
        est_total = {"v": 0}
        run_t0 = time.perf_counter()
        timings = {"deep_dive_papers": []}

        def emit(status="running", extra_pt=0, extra_ct=0):
            if not progress_cb:
                return
            with tb._lock:
                traj = list(tb.ledger["trajectory"])
                comps = list(tb.ledger["comparisons"])
                n_examined = len(tb.ledger["examined"])
                n_comparisons = len(comps)
                n_retr = tb.retrievals_done()
                paper_traces = []
                for c in comps:
                    check = c.get("evidence_check") or {}
                    diag = c.get("map_diag") or {}
                    paper_traces.append({
                        "paper_id": c.get("paper_id"),
                        "title": c.get("title", ""),
                        "overlap_degree": c.get("overlap_degree"),
                        "refutation_status": c.get("refutation_status"),
                        "evidence_status": check.get("status"),
                        "grounded_pairs": len(c.get("evidence_pairs") or []),
                        "insufficient": bool(c.get("insufficient")),
                        "trace": list(diag.get("loop") or []),
                    })
            cur_pt = pt + extra_pt
            cur_ct = ct + extra_ct
            try:
                progress_cb({
                    "status": status,
                    "claim_id": claim["id"],
                    "step": len(traj),
                    "max_steps": max(est_total["v"], len(traj)) if est_total["v"] else 0,
                    "last_action": traj[-1]["detail"] if traj else "starting",
                    "trajectory": traj,
                    "paper_traces": paper_traces,
                    "examined": n_examined,
                    "comparisons": n_comparisons,
                    "retrieval_rounds": n_retr,
                    "cost": {
                        "prompt_tokens": cur_pt,
                        "completion_tokens": cur_ct,
                        "usd": _usd(self.model_name, cur_pt, cur_ct),
                    },
                })
            except Exception:
                pass

        def dive_all(pids):
            """Run the papers' loops, in parallel up to `deep_dive_workers`."""
            lp = lc = 0
            workers = min(self.deep_dive_workers, len(pids))
            if workers <= 1:
                for pid in pids:
                    a, b, tinfo = self._deep_dive(tb, claim, pid, claim_ctx)
                    lp += a; lc += b
                    timings["deep_dive_papers"].append(tinfo)
                    emit(extra_pt=lp, extra_ct=lc)
                return lp, lc
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(self._deep_dive, tb, claim, pid, claim_ctx) for pid in pids]
                for fut in as_completed(futs):
                    a, b, tinfo = fut.result()
                    lp += a; lc += b
                    timings["deep_dive_papers"].append(tinfo)
                    emit(extra_pt=lp, extra_ct=lc)
            return lp, lc

        emit()
        _t = time.perf_counter()
        _real, claim_ctx, a, b = self._understand_submission(tb, claim); pt += a; ct += b
        timings["understand_submission"] = round(time.perf_counter() - _t, 1)
        emit()

        pool = [p["paper_id"] for p in tb._ranked()]
        tb._log("no_triage", f"{len(pool)} papers, none screened from abstracts")
        est_total["v"] = len(tb.ledger["trajectory"]) + 3 * len(pool)
        emit()

        _t = time.perf_counter()
        a, b = dive_all(pool); pt += a; ct += b
        timings["deep_dive_total"] = round(time.perf_counter() - _t, 1)

        # A new search only when the pool is empty.
        if not pool and self.max_retrievals > 0:
            _t = time.perf_counter()
            new = tb.retrieve_more(self._claim_str(claim)).get("papers", [])
            emit()
            if new:
                a, b = dive_all([x["paper_id"] for x in new if x["paper_id"] in tb.pool])
                pt += a; ct += b
                emit()
            timings["reentry"] = round(time.perf_counter() - _t, 1)

        for c in tb.ledger["comparisons"]:
            if c["refutation_status"] == "unclear":
                c["refutation_status"] = "cannot_refute"
        comparisons = tb.ledger["comparisons"]
        refuters = [c for c in comparisons if c.get("refutation_status") == "can_refute"]
        unresolved = [c for c in comparisons if c.get("unresolved") or c.get("insufficient")]
        unresolved_papers = [
            {
                "paper_id": c.get("paper_id"),
                "title": c.get("title", ""),
                "semantic_degree": c.get("overlap_degree", ""),
                "semantic_assessment": c.get("assessment", ""),
                "reason": c.get("unresolved_reason", "budget_exhausted"),
                "deficit": c.get("unresolved_deficit", ""),
            }
            for c in unresolved
        ]
        verdict = "challenged" if refuters else "not_challenged"

        timings["total"] = round(time.perf_counter() - run_t0, 1)
        _named = sum(v for k, v in timings.items()
                     if k not in ("deep_dive_papers", "total") and isinstance(v, (int, float)))
        timings["other"] = round(max(0.0, timings["total"] - _named), 1)
        cache_by_role = {
            role: dict(st) | {
                "hit_rate": round(st["cached_tokens"] / st["prompt_tokens"], 3)
                            if st["prompt_tokens"] else 0.0,
            }
            for role, st in self._cache_stats.items()
        }
        cache_total_pt = sum(st["prompt_tokens"] for st in self._cache_stats.values())
        cache_total_hit = sum(st["cached_tokens"] for st in self._cache_stats.values())
        cache_by_role_str = ", ".join(
            f"{r}={s['cached_tokens']:,}/{s['prompt_tokens']:,}"
            for r, s in self._cache_stats.items())
        cache_rate = round(cache_total_hit / cache_total_pt, 3) if cache_total_pt else 0.0
        tb._log("cache", f"{cache_total_hit:,}/{cache_total_pt:,} prompt tokens served "
                         f"from cache ({cache_rate:.1%}) by role: {cache_by_role_str}")

        entry = tb.artifact_entry()
        outcome = self.run_log.finish(
            verdict, entry.get("comparisons") or [],
            stop_reason=verdict, evidence_sufficient=True)
        self.run_log.config["cost"] = {
            "prompt_tokens": pt, "completion_tokens": ct,
            "usd": _usd(self.model_name, pt, ct),
        }
        log_path = self.run_log.write()
        tb._log("run_log",
                f"{self.run_log.run_id}: {outcome['n_compared']} compared, "
                f"review_complete={outcome['review_complete']}, "
                f"{len(outcome['open_papers'])} open"
                + (f" -> {log_path.name}" if log_path else ""))

        entry.update({
            "submission_basis": tb.submission_basis,
            "run_log": self.run_log.to_dict(),
            "agent_verdict": verdict,
            "agent_rationale": "",
            "evidence_sufficient": True,
            "review_complete": not bool(unresolved),
            "unresolved_count": len(unresolved),
            "unresolved_papers": unresolved_papers,
            "stop_reason": verdict,
            "confidence": None,
            "timings": timings,
            "cost": {"prompt_tokens": pt, "completion_tokens": ct, "usd": _usd(self.model_name, pt, ct),
                     "cache": {"by_role": cache_by_role, "total_prompt_tokens": cache_total_pt,
                               "total_cached_tokens": cache_total_hit,
                               "hit_rate": round(cache_total_hit / cache_total_pt, 3) if cache_total_pt else 0.0}},
        })
        emit()
        return entry
