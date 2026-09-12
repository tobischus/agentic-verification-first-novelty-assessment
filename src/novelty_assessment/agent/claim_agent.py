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
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional
import hashlib
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from . import evidence_map
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


def _cache_read(ai) -> int:
    """How many of this call's prompt tokens OpenAI served from its own prompt cache.

    Telemetry only -- read-only reporting, never affects what gets sent or how it's
    billed by us. OpenAI's automatic caching hits when a prompt's first 1024+ tokens
    match a recent prior call byte-for-byte; nothing in this pipeline requests or
    controls it. usage_metadata carries it under input_token_details.cache_read
    (langchain_openai >= 0.3); response_metadata is the fallback for older raw usage
    dicts, where OpenAI names it prompt_tokens_details.cached_tokens."""
    um = getattr(ai, "usage_metadata", None) or {}
    if um:
        details = um.get("input_token_details") or {}
        return int(details.get("cache_read", 0) or 0)
    tu = (getattr(ai, "response_metadata", {}) or {}).get("token_usage", {}) or {}
    details = tu.get("prompt_tokens_details") or {}
    return int(details.get("cached_tokens", 0) or 0)


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
    why: str = Field(default="", description="what these sections are expected to show, in one sentence")


class _ReadMore(BaseModel):
    """After a first read: go deeper, or say the paper has no bearing on the claim.

    The second option only exists where nothing screened the pool beforehand. It is what
    keeps looking at every paper affordable -- a paper that turns out to be about
    something else ends here, having been read rather than dismissed from its abstract."""
    bears_on_claim: bool = Field(
        default=True,
        description="false only if what you have read shows this paper does not speak to "
                    "the claimed contribution at all")
    sections: List[str] = Field(
        default_factory=list,
        description="if it does bear on the claim: further section titles you need in "
                    "full, empty if you have enough")
    degree: str = Field(
        default="superficial",
        description="if it does NOT bear on the claim: superficial (same area, different "
                    "contribution) or none (nothing of the claimed contribution)")
    why: str = Field(default="", description="one or two sentences: what you read, and what it showed")


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


class _GateVerdict(BaseModel):
    """A gate's answer: does what has been read carry the decision that was proposed?"""
    sufficient: bool = Field(description="true if what was read supports the proposal")
    missing: str = Field(
        default="",
        description="if not: the ONE thing that would settle it, named concretely enough "
                    "that a section can be chosen for it")
    where: List[str] = Field(
        default_factory=list,
        description="if not: section titles from the unread list likely to contain it")


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

# The abstract screen decides what is ever read, and nothing it rejects can be recovered
# later. It used to be asked for a VERDICT -- "is this the same kind of contribution?" --
# and every rejection on record has the same shape: "method paper, not a benchmark, so no
# deeper analysis needed". The old wording asked for exactly that, defining `superficial`
# as "a DIFFERENT KIND of contribution" and tying "no deeper analysis" to it.
#
# But a paper's headline is not what decides whether its full text bears on a claim. Across
# the runs on disk that cost the screen the two strongest competitors for one claim -- both
# labelled substantial by a reviewer, both dismissed 13 times as "analysis, not a benchmark"
# -- and every partial-overlap paper besides.
#
# Asked instead as a SCREEN, against the claim broken into its parts, recall of the papers a
# reviewer marks substantial or partial went from 73% to 90% over three runs of two claims,
# while 75% of the irrelevant ones stayed out (86% before) and the pool read grew from 47%
# to 57%. Two loosenings that scored higher recall were rejected: both let 97% of the pool
# through, which is not a better screen but no screen at all.
_TRIAGE_PROMPT = """Screen prior-work papers against ONE claimed contribution, using ONLY their abstracts, to decide which ones must be read in full.

This is a SCREEN, not a verdict. The full-text comparison decides overlap; it reads both papers whole and sees everything you do not. Your question is narrower: would reading this paper change what we can say about the claim?

Break the claim into what it actually promises -- the artifacts it builds, the properties it asserts, the questions it answers -- and ask, per paper, whether its full text plausibly holds any ONE of those things.

An abstract reports a headline. A method paper can contain the evaluation, the task structure, or the findings a claim is about, and the abstract will not mention them. So judge what the paper plausibly CONTAINS, never what kind of paper it is.

- Let it through (`partial` or higher) when you can point at a specific part of the claim and say: this paper's full text plausibly speaks to that.
- Keep it out (`superficial` or `none`) when no part of the claim survives that question -- the paper works on a different problem, on different objects, or its connection is the shared field alone.

Both mistakes cost something and they are not symmetric: a paper kept out is never read again, while one let through costs a single comparison. Where the abstract genuinely leaves it open, let it through -- but "open" means you can say which part of the claim is at stake, not that you are simply unsure.

overlap_degree, on the abstract alone: none | superficial | partial | substantial | same. partial and above are read in full; be conservative with substantial/same.

Give what_is_shared (which part of the claim this paper might speak to), submission_delta (what the claim adds beyond it), and for none/superficial a brief_note naming the part of the claim you tested it against and why it fails.

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
Quotes: claim_quote = VERBATIM from the submission passages; paper_quote = ONE CONTIGUOUS span COPIED CHARACTER-FOR-CHARACTER from the paper passages below (never paraphrase, never include a leading [Section] tag, and NEVER join separate parts of the text with "..." -- a stitched quote appears nowhere in the paper and cannot be checked; pick the single most telling span instead). Only include evidence_pairs you can copy verbatim.
paper_quote must state what THE PAPER ITSELF does or contributes. NEVER quote text that describes OTHER cited work -- related-work summaries, or descriptions of adopted datasets/methods (patterns like "X [12] is a ... dataset", "we adopt/use the following datasets") describe the CITED paper's contribution, not this paper's, and are NOT evidence. For cannot_refute, include a pair only if it genuinely shows the shared part of the contributions; otherwise return no evidence_pairs.

## Claim
{claim}

## Submission passages (source for claim_quote)
{claim_passages}

## Prior paper: {title}
## Its full-text passages
{passages}

Give refutation_status, overlap_degree (none/superficial/partial/substantial/same), what_is_shared, submission_delta."""

# Off by one env var so the pipeline can be run both ways for a like-for-like
# comparison, not because the old path is a fallback worth keeping.
_USE_EVIDENCE_MAP = os.getenv("NOVELTY_EVIDENCE_MAP", "1").strip().lower() not in ("0", "false", "no")
# Let the model choose which sections of a prior paper it reads, instead of putting the
# whole paper in.
#
# The previous attempt at choosing lost a real competitor, so this was measured before it
# was turned on: three runs per claim on graphrag_when_to_use, against the reviewer's gold
# labels, whole-paper runs beside it. Choosing scored 13/14/11 of 15 where whole-paper
# scored 10/14/13, and 6/7/6 of 7 where whole-paper scored 5/5/5 -- every choosing run
# ahead of every whole-paper run on that claim -- for 53% and 18% fewer tokens. The paper
# the earlier attempt lost ("RAG vs. GraphRAG") came back `substantial` in all three runs.
# Set to 0 to put whole papers in again.
_AGENTIC_SECTIONS = os.getenv("NOVELTY_AGENTIC_SECTIONS", "1").strip().lower() not in ("0", "false", "no")
# Ceiling on the chosen context. Generous on purpose: the saving should come from the
# model reading less, not from a cap silently truncating it, or the comparison between
# full text and selection would be measuring the cap.
_READ_CAP = 50000          # chars of a paper the model may be shown, per paper
_SUBMISSION_CONTEXT_CAP = 24000
_FALSIFY_SECTIONS = 2      # unread sections a proposed dismissal must survive
# Look at every retrieved paper instead of screening the pool from abstracts first.
#
# The screen is the pipeline's dominant error: measured over three runs of one claim it
# opened 15, 12 and 10 papers of the same 20, and 10 of the 20 were opened in some runs
# and not others -- the run-to-run spread of the whole system comes from there, not from
# the comparison. Without it every paper is read, and depth is earned rather than granted
# in advance: the paper itself is opened at its section level, and one that turns out to
# have no bearing on the claim ends there, before the expensive comparison.
#
# This is affordable precisely because dropping the screen also drops the only sequential
# dependency: with no "which paper next" left to decide, every paper is independent again
# and the existing thread pool runs them side by side.
_NO_TRIAGE = os.getenv("NOVELTY_NO_TRIAGE", "0").strip().lower() not in ("0", "false", "no")
# The floor a dismissal has to stand on. Not a judgement about how much is enough to
# understand a paper -- it is the line below which "this paper has no bearing" is not a
# reading but a glance.
_DISMISS_MIN_SECTIONS = 3
_DISMISS_MIN_CHARS = 8000
# The per-paper loop of point 2: agent policy, a semantic gate on each proposal, and a
# deterministic gate on the evidence that can send the whole thing back to reading.
# Off by default: it costs more calls per paper than the single pick, and what that buys
# has to be measured before it becomes what the pipeline does.
_PAPER_LOOP = os.getenv("NOVELTY_PAPER_LOOP", "0").strip().lower() not in ("0", "false", "no")
_LOOP_MAX_TURNS = 4        # reading turns within one examination
_LOOP_MAX_COMPARES = 2     # times the evidence gate may send it back to read
_FIRST_READ_N = 3          # sections of the mandatory first read -- exactly this many
_DEGREE_RANK = {
    "none": 0,
    "superficial": 1,
    "partial": 2,
    "substantial": 3,
    "same": 4,
}
_DEEP_SYSTEM = """You are doing a CLOSE comparison of ONE prior paper against a claimed contribution to decide whether it challenges the claim's novelty. You are given some of the paper's full-text passages. If you need other parts of the paper, call read_more(query) (at most a couple of times). When ready, call conclude_comparison with refutation_status, overlap_degree, what_is_shared, submission_delta, and verbatim evidence_pairs (paper_quote copied CHARACTER-FOR-CHARACTER from passages you saw, without any leading [Section] tag; claim_quote verbatim from the submission passages). paper_quote must state what THE PAPER ITSELF does or contributes -- never quote descriptions of OTHER cited work (related-work summaries, "X [12] is a ... dataset", "we adopt the following datasets"): that is the cited paper's contribution, not this paper's. overlap_degree measures overlap of CONTRIBUTIONS (claim vs paper), not topical similarity: same area + different kind of contribution = superficial at most. Be efficient."""

# --- section-based understanding (V3) ---

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


_PAPER_READ_MORE = """You have opened part of a prior-work paper in order to judge whether it presents the same kind of contribution as a specific claimed one. Below is what you have read, and the titles of the sections you have not opened.

Decide whether what you have read is enough to say what THIS PAPER ITSELF contributes, and how that stands to the claim.

- If it is enough, return an empty list.
- If something you would need to see is plainly in a section you have not opened, return those titles.

Name only sections you would actually use: each one is then read in full. Do not re-list a section you have already read.

## Claim
{claim}

## What the submission does for this claim
{realization}

## Prior paper: {title}
## What you have read so far
{read}

## Selectable unread sections that fit the remaining read budget
{unread}"""


_PAPER_READ_MORE_OR_DROP = """You have opened part of a prior-work paper in order to judge whether it presents the same kind of contribution as a specific claimed one. Nothing has screened this paper beforehand: it was retrieved for this claim, and what you have read is all that is known about it.

Decide one of two things.

**It has no bearing on the claim.** Set `bears_on_claim` to false, and say in `degree` whether it is `superficial` (same area, a different contribution) or `none` (nothing of the claimed contribution at all). Choose this when what you have read shows the paper is about something else -- not merely that this particular section was unhelpful. Being retrieved for the claim means it shares the vocabulary; that is not a bearing.

**It does bear on the claim.** Leave `bears_on_claim` true. In `sections`, name any further sections you need in full to say what THIS PAPER contributes and how that stands to the claim -- or leave it empty if what you have read is enough. Name only sections you would actually use: each is read in full.

Say in `why`, in one or two sentences, what you read and what it showed. That sentence is what a reviewer sees for a paper that ends here, so it has to state what the paper does, not merely that it differs.

## Claim
{claim}

## What the submission does for this claim
{realization}

## Prior paper: {title}
## What you have read so far
{read}

## Selectable unread sections that fit the remaining read budget
{unread}"""


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


_DISMISS_GATE = """A reading agent proposes to end its examination of one prior-work paper, on the grounds that the paper has no bearing on a claimed contribution. Below is everything it read, and its reason.

Decide whether what was READ carries that conclusion.

It does, if the sections show what the paper is about and that subject is a different contribution.

It does not, if the paper's own contribution is nowhere in what was read -- a method section without the claim it supports, an evaluation without the artifact being evaluated, background only. A paper cannot be shown to lack something by reading pages that would not contain it either way.

If it does not, name in `missing` the ONE thing that would settle it, concretely enough that a section can be chosen for it, and list likely sections in `where`.

## Claim
{claim}

## Prior paper: {title}
## Proposed reason for dismissing it
{why}

## What was read
{read}

## Selectable unread sections that fit the remaining read budget
{unread}"""

_EVIDENCE_REENTRY_MANDATE = """
An earlier evidence check found an unresolved evidence deficit.

Before another comparison can be proposed, inspect additional evidence that could
resolve that specific deficit.

Use `read_more` on this turn and select only unread sections that are relevant to
the outstanding deficit.

`propose_compare` and `propose_dismissal` are not available on this turn.
"""

# The claim is deliberately NOT in this prompt. Given one, the gate asks the prior paper
# to contain the submission's artifact -- it refused a comparison against the strongest
# competitor on the grounds that "an explicit presentation of GraphRAG-Bench" was missing,
# which is the submission's own benchmark and could not be in that paper at any length.
# Twice refused, the agent proposed dismissal instead, and a real overlap was lost.
#
# The question this gate asks does not need the claim: whether these pages state what THIS
# paper contributes is a property of the pages. Removing the claim removes the failure
# rather than discouraging it.
_READ_GATE = """A reading agent proposes to move on to a comparison, having read part of one paper. Below is everything it read.

Decide whether what was READ states what THIS PAPER ITSELF contributes -- what it builds, proposes, measures or finds, in enough detail that someone could set it beside another paper's contribution.

It does, if the sections say what the paper delivers, however far that is from any particular topic. A paper whose contribution is plainly stated is ready to be compared, whatever the comparison then concludes.

It does not, if the pages show only that the paper works in some area: a related-work summary, an experimental setup without the thing being evaluated, a discussion referring to a method described elsewhere in the paper, an introduction that motivates without stating.

Judge the pages, not the paper's importance, and not what it ought to contain. If it does not, name in `missing` the ONE thing that would settle it -- something this paper would state about ITSELF -- and list likely sections in `where`.

## Paper: {title}
## What was read
{read}

## Selectable unread sections that fit the remaining read budget (title :: preview :: size)
{unread}"""


_FIRST_READ_MANDATE = """
This is the first turn.

Use `read_more` and select exactly 3 unread sections with the highest expected information
value for identifying THIS PAPER's own contribution and its relation to the claim.

`propose_compare` and `propose_dismissal` are not available yet.
"""

def _fill(template: str, **kw) -> str:
    """Sequential {key}->value substitution that tolerates literal braces in the values
    (section text may contain { } from math/code) -- str.format would choke on those."""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def rl_sha(text: str) -> str:
    """Short digest of a VERIFICATION corpus, for the record.

    The corpora are the whole documents and never the selected context; recording their
    digests beside the context ids is what shows, afterwards, that a narrowed context did
    not narrow what quotes were checked against.
    """
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def _section_ids(menu: List[dict]) -> dict:
    """{section name: stable handle} for one paper's menu, in menu order."""
    return {m["name"]: f"S{i + 1}" for i, m in enumerate(menu)}


def _resolve_sections(requested, menu: List[dict], ids: dict):
    """Split what the agent named into sections that exist and tokens that do not.

    Returns (names, unresolved). A token resolves by handle first, then by exact title,
    then by unique suffix -- the last because the outline path makes titles long, and a
    model that drops the parent ("3.4 Unified Experimental Settings" for "3 Evaluation
    Framework > 3.4 Unified Experimental Settings") is naming a real section without
    ambiguity. Anything still unmatched is RETURNED, never silently dropped: the caller
    has to be able to tell a request it could not understand from a paper with nothing
    left to read, because those two call for opposite actions.
    """
    by_id = {v.casefold(): k for k, v in ids.items()}
    by_title = {" ".join(m["name"].split()).casefold(): m["name"] for m in menu}
    names, unresolved = [], []
    for raw in (requested or []):
        tok = str(raw or "").strip().strip("[]").strip()
        if not tok:
            continue
        key = " ".join(tok.split()).casefold()
        # The menu prints "[S7] title", and the model echoes the whole line about as often
        # as the bare handle. A leading handle decides on its own -- the title after it is
        # the same section by construction, and reading it as part of the token made the
        # token match nothing at all.
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


def _fmt_sections_menu(menu: List[dict], ids: Optional[dict] = None) -> str:
    """The section menu the agent picks from.

    With `ids`, every line leads with a stable handle -- [S7] -- and the agent is asked for
    handles rather than titles. Titles were the only channel before, matched exactly against
    the outline path, and a model that wrote "3.4 Evaluation Settings" where the menu said
    "3 Evaluation Framework > 3.4 Unified Experimental Settings" resolved to nothing: four
    sections requested, zero loaded, and the controller read that as "no unread sections
    remain" and moved to the comparison with three sections open."""
    if ids is None:
        return "\n".join(
            f"- {m['name']} :: {m.get('preview','')[:160]} :: ~{m.get('chars',0)} chars"
            for m in menu) or "(no sections)"
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

        # One LLM client per ROLE, not per effort level: the per-paper loop's three kinds
        # of call differ in more than how hard to think. Reading/action-selection and the
        # falsification section-pick (same call site) are frequent and cheap to redo, so
        # they can run on a smaller model at low effort. Comparison and the evidence map's
        # semantic judgments are what a reviewer actually reads and what the evidence gate
        # checks everything else against -- worth a stronger model, higher effort, or both.
        #
        # Each role's (model, effort) is independently overridable, so a model change for
        # one role never has to touch the others:
        #   NOVELTY_READING_MODEL / NOVELTY_READING_EFFORT     (default: model_name, low)
        #   NOVELTY_COMPARE_MODEL / NOVELTY_COMPARE_EFFORT     (default: model_name, high)
        #   NOVELTY_EVIDENCE_MODEL / NOVELTY_EVIDENCE_EFFORT   (default: model_name, high)
        # reasoning models (gpt-5*, o-series) reject any temperature other than the default
        # and instead take a reasoning_effort; non-reasoning models ignore effort entirely.
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
            "compare": role_llm("NOVELTY_COMPARE_MODEL", "NOVELTY_COMPARE_EFFORT", "high"),
            "evidence": role_llm("NOVELTY_EVIDENCE_MODEL", "NOVELTY_EVIDENCE_EFFORT", "high"),
        }
        self.llm = self._role_llm["reading"]   # default for call sites that don't specify a role

        # Cache telemetry only -- read-only counters, never consulted by any decision the
        # agent makes. One entry per role, mirroring self._role_llm's keys, plus "other"
        # for anything called without a role.
        self._cache_stats: dict = {}

    # ------------------------------ helpers ------------------------------ #

    @staticmethod
    def _claim_str(claim: dict) -> str:
        return (f"{claim.get('name','')} — {claim.get('claim_text','')} "
                f"({claim.get('description','')})").strip()

    def _new_run_log(self, claim: dict):
        """Everything about this run that is not in the ledger and not in the text.

        Collected at the start rather than the end: a setting read afterwards is the
        setting the process finished with, which is not necessarily the one the calls
        were made under.
        """
        from . import run_log as rl

        log = rl.RunLog(self.submission_id, claim.get("id", ""), self.data_dir)
        repo_root = Path(__file__).resolve().parents[3]

        def role_cfg(role: str, env_model: str, env_effort: str, default_effort: str) -> dict:
            llm = self._role_llm.get(role)
            return {
                "model": os.getenv(env_model, self.model_name),
                "reasoning_effort": os.getenv(env_effort, default_effort),
                # What the client ended up with, in case the env and the object disagree.
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
            gap, pinning = pv.DEFAULT_MIN_GAP_DAYS, pv.enforcement_enabled()
        except Exception:
            gap, pinning = None, None
        try:
            from pdf_sections import _USE_OUTLINE as outline_flag
        except Exception:
            outline_flag = None

        log.config = {
            # With the uncommitted diff saved beside the log, "dirty" stops being a
            # disclaimer and becomes a record: the exact source this run executed.
            "git": rl.git_commit(
                repo_root,
                save_diff_to=(Path(self.data_dir) / self.submission_id / "run_logs"
                              / f"{claim.get('id', 'claim')}_{log.run_id}.diff")),
            "agent_model_default": self.model_name,
            "roles": {
                "reading": role_cfg("reading", "NOVELTY_READING_MODEL",
                                    "NOVELTY_READING_EFFORT", "low"),
                "compare": role_cfg("compare", "NOVELTY_COMPARE_MODEL",
                                    "NOVELTY_COMPARE_EFFORT", "high"),
                "evidence": role_cfg("evidence", "NOVELTY_EVIDENCE_MODEL",
                                     "NOVELTY_EVIDENCE_EFFORT", "high"),
            },
            "flags": {
                "NOVELTY_PDF_OUTLINE": outline_flag,
                "NOVELTY_AGENTIC_SECTIONS": _AGENTIC_SECTIONS,
                "NOVELTY_NO_TRIAGE": _NO_TRIAGE,
                "NOVELTY_PAPER_LOOP": _PAPER_LOOP,
                "NOVELTY_EVIDENCE_MAP": _USE_EVIDENCE_MAP,
                "NOVELTY_VERSION_PINNING": pinning,
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
                "SectionPick": _SectionPick, "ReadMore": _ReadMore,
                "PaperAction": _PaperAction, "GateVerdict": _GateVerdict,
                "SectionComparison": _SectionComparison, "Realization": _Realization,
            }),
        }
        try:
            from . import evidence_map as _em
            log.config["prompts"].update(rl.prompt_hashes(_em))
            log.config["schemas"].update(rl.schema_hashes({
                "EvidenceMap": _em.EvidenceMap, "Correspondence": _em.Correspondence,
                "EvidenceCheck": _em.EvidenceCheck,
            }))
        except Exception:
            pass
        return log

    def _struct(self, model, prompt, role: str = "reading"):
        """Structured LLM call returning (parsed, prompt_tokens, completion_tokens).

        `role` picks which of the per-role clients (reading / compare / evidence) answers
        this call -- each is its own (model, effort) pair, built in __init__."""
        llm = self._role_llm.get(role, self.llm)
        res = llm.with_structured_output(model, include_raw=True).invoke(prompt)
        parsed, raw = res.get("parsed"), res.get("raw")
        pt, ct = _usage(raw) if raw is not None else (0, 0)
        # Telemetry only: does not read into pt/ct and nothing downstream reads it back.
        cached = _cache_read(raw) if raw is not None else 0
        st = self._cache_stats.setdefault(
            role, {"calls": 0, "prompt_tokens": 0, "cached_tokens": 0})
        st["calls"] += 1
        st["prompt_tokens"] += pt
        st["cached_tokens"] += cached
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


    def _build_submission_basis(self, tb: ClaimToolbox, claim: dict):
        """Select original passages once per claim run.

        Comparison, reading policy and evidence mapping reuse this context.
        Complete sections are loaded in selected priority order.
        """
        pt = ct = 0
        cap = _SUBMISSION_CONTEXT_CAP
        menu = tb.section_menu("submission") or []

        blocks, sources, omitted, notes = [], [], [], []
        used = 0
        requested = []
        # What the model asked for, verbatim, before resolution -- kept apart from the
        # titles it resolved to. A handle that matched nothing and a section that was
        # dropped for want of budget are different failures, and only the raw request
        # distinguishes them afterwards.
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
            sources.append({
                "section": name,
                "kind": kind,
                "passage_id": passage_id,
            })
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

            requested, unresolved = _resolve_sections(
                asked_handles,
                menu,
                ids,
            )

            if unresolved:
                notes.append(
                    "Unresolved section requests: " + ", ".join(unresolved)
                )

            if not requested:
                notes.append(
                    "No usable section selection; using source-text fallback."
                )

            for name in requested:
                overhead = len(f"## {name}\n") + (2 if blocks else 0)
                remaining = max(0, cap - used - overhead)

                secs = tb.read_sections(
                    "submission",
                    [name],
                    max_total=remaining,
                    exact=True,
                ).get("sections", []) or []

                sec = next(
                    (s for s in secs if s.get("name") == name),
                    None,
                )

                # Why a requested section is not in the context, not merely that it is
                # absent: "the budget was already spent" and "the section could not be
                # read" leave the same gap and call for different fixes.
                if sec is None:
                    omitted.append({"section": name, "reason": "not returned by read_sections",
                                    "remaining_chars": remaining})
                elif not append_source(name, sec.get("text"), "section"):
                    omitted.append({"section": name,
                                    "reason": "would exceed the context budget",
                                    "section_chars": len(sec.get("text") or ""),
                                    "remaining_chars": remaining})

        if not blocks:
            # Prefer the complete source when it fits.
            if append_source(
                "Submission full text",
                tb._submission_text,
                "full_text",
            ):
                notes.append(
                    "Fallback: full submission fits the context budget."
                )
                omitted = []
            else:
                # Otherwise use explicitly labelled retrieved excerpts.
                hits = tb.search_submission(
                    self._claim_str(claim),
                    k=6,
                ).get("passages") or []

                for i, hit in enumerate(hits, 1):
                    name = hit.get("section") or "Submission"
                    pid = hit.get("passage_id") or f"retrieved-{i}"

                    append_source(
                        f"{name} [retrieved excerpt: {pid}]",
                        hit.get("text"),
                        "excerpt",
                        pid,
                    )

                notes.append(
                    "Fallback: retrieved excerpts; full sections were unavailable."
                )

        text = "\n\n".join(blocks)

        if not text:
            raise ValueError(
                "No original submission passages available for comparison."
            )

        # Two hashes, because they answer different questions. The source hash says which
        # DOCUMENT this came from; the context hash says which SELECTION of it was sent.
        # Only the source hash existed, and it is identical for every selection -- so two
        # runs that read different halves of the submission and reached different verdicts
        # were indistinguishable in the record.
        kinds = sorted({s.get("kind") for s in sources if s.get("kind")})
        basis = {
            "text": text,
            "sources": sources,
            "requested_sections": requested,
            "omitted_sections": omitted,
            "notes": notes,
            "max_chars": cap,
            "chars": len(text),
            "source_sha256": hashlib.sha256(
                tb._submission_text.encode("utf-8")
            ).hexdigest(),
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
            f"{len(omitted)} sections omitted; " + "; ".join(notes),
            progress=True,
        )

        return basis, pt, ct


    def _understand_submission(self, tb: ClaimToolbox, claim: dict):
        """Build the shared source context and explain it once per claim run.

        Claim text stays unchanged. Comparison and mapping consume the
        original passages, not the generated explanation.
        """
        basis, pt, ct = self._build_submission_basis(tb, claim)

        parsed, a, b = self._struct(
            _Realization,
            _fill(
                _SUBMISSION_REALIZE,
                claim=self._claim_str(claim),
                sections=basis["text"],
            ),
        )
        pt += a
        ct += b

        raw = [
            s.model_dump()
            for s in (getattr(parsed, "segments", None) or [])
        ] if parsed else []

        realization = tb.verify_segments(raw, "submission")
        tb.claim_realization = realization

        tb._log(
            "understand_submission",
            "explanation from shared original-source context",
            progress=True,
        )

        return realization, basis["text"], pt, ct

    # ------------------------------ phase 2 ------------------------------ #

    # ------------------ the per-paper loop, with its gates ------------------ #

    def _examine_paper(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str,
                       carry_deficit: str = "", state: Optional[dict] = None):
        """One paper's reading: a mandatory first read, then an action loop.

        The shape is fixed in code, not asked of the model:

          MANDATORY INITIAL READ   turn 0 is a read. The agent picks which sections -- the
                                   three it judges most relevant to the claim -- but it
                                   cannot dismiss or compare from the table of contents,
                                   so no verdict rests on section titles alone.

          ACTION LOOP              read_more / propose_compare / propose_dismissal.

          DISMISSAL FALSIFICATION  the first `propose_dismissal` is never granted and is
                                   never put to a gate. Instead the agent must name the two
                                   UNREAD sections most likely to REFUTE its own dismissal,
                                   and those are read in full. Only then does the flag flip
                                   and the loop continue as before; a dismissal proposed
                                   again after that goes through.

        That last part is the change this method exists for. A gate asking "was enough
        read?" accepted three sections on CG-RAG and lost a paper the gold marks as a real
        partial overlap: the reading was sufficient for the claim the agent made, and the
        claim was wrong. Asking the agent to look for what would refute itself is a
        different question, and it costs two sections rather than a judgement about
        judgement.

        `state`, if given, resumes a PRIOR call on this same paper -- the sections already
        read, the running character total, and whether dismissal falsification has already
        been done. Without it, `_paper_loop`'s re-entry after a failed evidence gate would
        start this method over: `got` and `read` empty again, the mandatory initial read
        fires again, and three sections already on the page get read and billed a second
        time, while `used` resets to 0 so the 50,000-character cap no longer bounds what
        the paper costs across the whole loop -- exactly what the cap exists to prevent.

        Returns (decision, context, sections_read, why, pt, ct, trace, state) -- the last
        item is what a subsequent call should pass back in as `state`.
        """
        pt = ct = 0
        trace: List[str] = []
        claim_s = self._claim_str(claim)[:1200]
        title = (tb.pool.get(pid, {}) or {}).get("title", "")
        menu = tb.section_menu(pid) or []
        if not menu:
            return "compare", "", [], "", pt, ct, ["no section menu"], {}

        def struct(schema, prompt):
            # Reading/action selection AND dismissal falsification's section pick both
            # run on the "reading" role: frequent, cheap-to-redo calls -- which section to
            # read next, which two sections would refute a dismissal -- not the verdict.
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

        # A failed evidence check must cause an actual new read before
        # another comparison may be proposed.
        reentry_requires_read = bool(carry_deficit)

        # Stable handles for the menu. The agent names [S7], not a title it has to
        # reproduce character for character -- see _fmt_sections_menu for what that cost.
        sec_ids = _section_ids(menu)

        def resolve(requested):
            return _resolve_sections(requested, menu, sec_ids)

        def unread():
            return [m for m in menu if m["name"] not in set(read)]
        def fitting_unread():
            remaining = max(0, _READ_CAP - used)
            return [
                m for m in unread()
                if int(m.get("chars") or 0) <= remaining
            ]
        def take(names):
            """Read exactly the sections named -- no more.

            `exact=True` because section names carry their outline path: matched as
            substrings, "3 Evaluation Framework" also pulls in every "3 Evaluation
            Framework > 3.x" beneath it, and an agent that asked for three sections was
            given seven. The budget then went where nothing chose to send it."""
            nonlocal used, last_take
            selectable = {m["name"] for m in fitting_unread()}

            new = [
                n for n in (names or [])
                if n
                and n not in read
                and n in selectable
            ]
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
            # extend, not += : augmented assignment would bind `trace` as a local of this
            # closure and the append above it would raise before anything was written.
            req, loaded, added = last_take
            trace.append(f"turn {turn}: {label} -> {len(names)} sections")
            trace.extend(f"  - {n}" for n in names)
            trace.append(f"  requested: {req}")
            trace.append(f"  loaded: {loaded}")
            trace.append(f"  chars added: {added:,}")
            trace.append(f"  total chars: {used:,}/{_READ_CAP:,}")
            if reason:
                # Stored in full: the trace is the audit record. Shortening for
                # display is the frontend's job.
                trace.append(f"  reason: {' '.join(reason.split())}")

        def deficit_block():
            if not deficits:
                return ""
            return ("\n## Still outstanding -- a check refused an earlier proposal for these\n"
                    + "\n".join(f"- {d}" for d in deficits[-3:]) + "\n")

        def exhausted(turn):
            """Return True when no further COMPLETE section can be read."""
            nonlocal cap_hit

            if used >= _READ_CAP:
                cap_hit = True
                trace.append(
                    f"turn {turn}: read cap exhausted "
                    f"({used:,}/{_READ_CAP:,} chars)"
                )
                return True

            if not unread():
                trace.append(
                    f"turn {turn}: all sections read "
                    f"({len(read)}/{len(menu)})"
                )
                return True

            if not fitting_unread():
                cap_hit = True
                trace.append(
                    f"turn {turn}: no complete unread section fits remaining "
                    f"budget ({_READ_CAP - used:,} chars)"
                )
                return True

            return False

        decision = None
        for turn in range(_LOOP_MAX_TURNS):
            if exhausted(turn):
                if reentry_requires_read:
                    decision = "insufficient"
                    trace.append(
                        f"turn {turn}: evidence deficit remains and no further "
                        "complete section can be read -> INSUFFICIENT"
                    )
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
                read=(
                    _fmt_sections_full(got, max_total=_READ_CAP)
                    if got
                    else "(nothing yet -- this turn must be a read)"
                ),
                unread=_fmt_sections_menu(fitting_unread(), ids=sec_ids),
                deficits=deficit_block(),
                mandate=mandate,
            ))
            if act is None:
                if reentry_requires_read:
                    decision = "insufficient"
                    trace.append(
                        f"turn {turn}: reading action failed during evidence re-entry "
                        "-> INSUFFICIENT"
                    )
                else:
                    decision = "compare"
                    trace.append(f"turn {turn}: no action -> compare")
                break
            tool = (act.tool or "").strip().lower()

            trace.append(
                f"turn {turn}: proposed action={tool}, "
                f"sections={list(act.sections or [])}"
            )

            if reentry_requires_read and tool != "read_more":
                trace.append(
                    f"turn {turn}: {tool or 'invalid action'} rejected -- "
                    "evidence re-entry requires read_more first"
                )
                continue

            if act.suspected_deficit and act.suspected_deficit.strip() not in deficits:
                deficits.append(act.suspected_deficit.strip())

            # ---- turn 0: a read of EXACTLY _FIRST_READ_N sections --------------------
            # Exactly, not at least. The agent orders its picks by relevance, so the first
            # three are the three it considers most relevant; letting it name eight made
            # the mandatory read a way to open half the paper before any decision, which
            # is the opposite of what a first look is for. More is reachable through
            # read_more, where each step is chosen and logged on its own.
            #
            # `resuming` guards this on a re-entry: `got` is non-empty because it came from
            # `state`, not because this call already read something, so testing `got`
            # alone would still treat the first turn of a resumed call as turn 0 and read
            # the same three sections again.
            if not got and not resuming:
                wanted, unresolved = resolve(act.sections)
                names = take(wanted[:_FIRST_READ_N])

                if unresolved:
                    trace.append(f"  unresolved: {', '.join(unresolved[:6])}")

                if len(names) < _FIRST_READ_N:
                    names += take([
                        m["name"]
                        for m in sorted(
                            fitting_unread(),
                            key=lambda m: -m.get("chars", 0)
                        )
                    ][:_FIRST_READ_N - len(names)])

                log_read(
                    turn,
                    f"mandatory initial read ({_FIRST_READ_N} sections)",
                    names,
                    act.why,
                )

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
                    # Nothing was read. WHY decides what happens next, and the two reasons
                    # are not the same: a request the resolver could not match is a bad
                    # action, and the agent gets to choose again; a genuinely empty menu is
                    # the end of reading. Conflating them is what sent "RAG vs. GraphRAG"
                    # into the comparison with three sections open after it had asked for
                    # four more -- the controller read the resolver's failure as the paper
                    # being exhausted.
                    if unread():
                        invalid_note = (
                            "ACTION INVALID: none of "
                            f"{', '.join(unresolved[:6]) or 'the sections named'} matched an "
                            "unread section. Use the [S#] handles exactly as the menu "
                            "prints them."
                        )
                        if invalid_note not in deficits:
                            deficits.append(invalid_note)
                        trace.append(
                            f"turn {turn}: ACTION INVALID -- requested "
                            f"{len(act.sections or [])}, resolved 0, "
                            f"{len(unread())} sections still unread -> choose again"
                        )
                        continue

                    if reentry_requires_read:
                        # The evidence deficit has NOT been resolved by new reading.
                        trace.append(
                            f"turn {turn}: evidence re-entry read loaded nothing; "
                            "deficit remains unresolved"
                        )
                        continue

                    decision = "compare"
                    trace.append(f"turn {turn}: no unread sections remain -> compare")
                    break

                # This is the important transition:
                # actual new evidence was read, so comparison becomes eligible again.
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
                    names += take([
                        m["name"]
                        for m in sorted(fitting_unread(), key=lambda m: -m.get("chars", 0))
                    ][:_FALSIFY_SECTIONS - len(names)])
                trace += [f"  - {n}" for n in names]
                trace.append(f"  requested: {min(_FALSIFY_SECTIONS, len(left))}")
                trace.append(f"  loaded: {len(names)}")
                trace.append(f"  chars added: {last_take[2]:,}")
                trace.append(f"  total chars: {used:,}/{_READ_CAP:,}")
                # The agent's own account of why these sections could refute it is the
                # point of the gate; a fixed sentence here hid that the code had silently
                # substituted its largest-unread fallback for the agent's choice.
                trace.append(f"  reason: {(getattr(pick, 'why', '') or '(none given)')}")
                if len(names) > chosen:
                    trace.append(f"  FALLBACK: agent named {chosen} usable section(s), "
                                 f"{len(names) - chosen} filled in by size")
                required = min(_FALSIFY_SECTIONS, len(left))

                if len(names) >= required:
                    falsification_done = True
                    trace.append(
                        f"turn {turn}: dismissal_falsification_done=True"
                    )
                else:
                    trace.append(
                        f"turn {turn}: dismissal falsification incomplete "
                        f"({len(names)}/{required} complete sections read)"
                    )

                continue

            decision = "compare"
            trace.append(f"turn {turn}: propose_compare -> COMPARE")
            break
        else:
            if reentry_requires_read:
                decision = "insufficient"
                trace.append(
                    f"BUDGET: {_LOOP_MAX_TURNS} turns exhausted while evidence "
                    "re-entry still required an actual new read -> INSUFFICIENT"
                )
            else:
                decision = decision or "compare"
                trace.append(
                    f"BUDGET: {_LOOP_MAX_TURNS} turns exhausted -> compare"
                )
        next_state = {"got": got, "read": read, "used": used,
                      "falsification_done": falsification_done}
        return (decision, _fmt_sections_full(got, max_total=_READ_CAP), read, why,
                pt, ct, trace + ([f"read cap was reached ({used:,}/{_READ_CAP:,} chars)"]
                                 if cap_hit else []), next_state)

    def _paper_loop(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str):
        """One paper, start to finish: the reading loop, the comparison, and the gate that
        can send it back.

        The outer turn exists because the evidence map is where a reading is first tested
        against something other than itself. A comparison can read well and still rest on
        nothing checkable, and the only honest answers to that are to look again or to say
        the claim is not challenged. Looking again is bounded: `_LOOP_MAX_COMPARES` outer
        turns, and the reading budget is shared across them, so a paper cannot absorb the
        run.

        Returns (comp, pt, ct, trace).
        """
        pt = ct = 0
        trace: List[str] = []
        deficit = ""
        comp = self._to_comp(None)
        read_state: Optional[dict] = None
        for turn in range(_LOOP_MAX_COMPARES):
            # `read_state` carries the sections already read, the running character total
            # and the falsification flag from the PRIOR call on this paper. Without it a
            # re-entry after a failed evidence gate re-triggers the mandatory initial
            # read -- re-reading and re-billing the same sections -- and the character cap
            # resets to 0, so it no longer bounds what the paper costs across the whole
            # loop, only within a single call.
            decision, context, names, why, a, b, tr, read_state = self._examine_paper(
                tb, claim, pid, claim_ctx, carry_deficit=deficit, state=read_state)
            pt += a; ct += b
            trace += [f"[read {turn}] {t}" for t in tr]

            if decision == "dismiss":
                comp = self._to_comp(None)
                comp["overlap_degree"] = "superficial"
                # Marked, so the run log can report "dismissed" as its own ending rather
                # than as a superficial comparison that happens to carry no evidence.
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

            # RAW: what the comparison call itself decided, before the evidence map can
            # overwrite overlap_degree/assessment/evidence_pairs. Logging only the final
            # state (after the map) loses this -- a paper whose raw compare said
            # `substantial` and whose map then found nothing checkable reads identically,
            # in the final fields alone, to one the compare call called `none` outright.
            # Those are different failures and want different fixes.
            trace.append(f"[{turn}] RAW COMPARE: degree={comp.get('overlap_degree', '')}")
            trace.append(f"[{turn}] RAW ASSESSMENT: {comp.get('assessment', '')}")
            trace.append(f"[{turn}] RAW SHARED: {comp.get('what_is_shared', '')}")
            trace.append(f"[{turn}] RAW DELTA: {comp.get('submission_delta', '')}")

            if _USE_EVIDENCE_MAP:
                comp, a, b = self._map_evidence(tb, claim, pid, comp, context, turn=turn)
                pt += a
                ct += b

                proposal = comp.get("comparison_proposal") or {}
                check = comp.get("evidence_check") or {}
                pairs = comp.get("evidence_pairs") or []

                raw_degree = (proposal.get("overlap_degree") or "").lower()
                final_degree = (comp.get("overlap_degree") or "").lower()
                evidence_status = (check.get("status") or "").lower()

                trace.append(
                    f"[{turn}] SEMANTIC DEGREE: {raw_degree}"
                )
                trace.append(
                    f"[{turn}] SEMANTIC ASSESSMENT: "
                    f"{proposal.get('assessment', '')}"
                )
                trace.append(
                    f"[{turn}] SEMANTIC SHARED: "
                    f"{proposal.get('what_is_shared', '')}"
                )
                trace.append(
                    f"[{turn}] SEMANTIC DELTA: "
                    f"{proposal.get('submission_delta', '')}"
                )

                trace.append(
                    f"[{turn}] GROUNDED OWNED PAIRS: {len(pairs)}"
                )

                for i, p in enumerate(pairs, 1):
                    relation = " ".join(
                        str(p.get("rationale", "")).split()
                    )

                    submission_quote = " ".join(
                        str(p.get("claim_quote", "")).split()
                    )

                    paper_quote = " ".join(
                        str(p.get("paper_quote", "")).split()
                    )

                    trace.append(
                        f"[{turn}] PAIR {i}: "
                        f"strength={p.get('strength', '')} | "
                        f"relation={relation}"
                    )
                    trace.append(
                        f'[{turn}] PAIR {i} SUBMISSION: "{submission_quote}"'
                    )
                    trace.append(
                        f'[{turn}] PAIR {i} PAPER: "{paper_quote}"'
                    )

                trace.append(
                    f"[{turn}] EVIDENCE CHECK: status={evidence_status}"
                )
                trace.append(
                    f"[{turn}] EVIDENCE SUPPORTING PAIRS: "
                    f"{check.get('supporting_pair_indices', [])}"
                )
                trace.append(
                    f"[{turn}] EVIDENCE REASON: "
                    f"{check.get('reasoning', '')}"
                )
                trace.append(
                    f"[{turn}] PROPOSED DEGREE SUPPORTED: "
                    f"{check.get('proposed_degree_supported')}"
                )

                if check.get("unresolved_question"):
                    trace.append(
                        f"[{turn}] UNRESOLVED QUESTION: "
                        f"{check['unresolved_question']}"
                    )

                semantic_material = raw_degree in {
                    "partial",
                    "substantial",
                    "same",
                }

                if evidence_status == "material":
                    evidence_material = True
                elif evidence_status == "nonmaterial":
                    evidence_material = False
                else:
                    evidence_material = None

                trace.append(
                    f"[{turn}] MATERIAL AGREEMENT: "
                    f"semantic={'material' if semantic_material else 'nonmaterial'} | "
                    f"evidence={evidence_status or 'missing'}"
                )

                trace.append(
                    f"[{turn}] CURRENT SEMANTIC DEGREE: {final_degree}"
                )

            deficit = self._evidence_deficit(comp) or ""
            if not deficit:
                trace.append(f"[{turn}] compared, evidence gate passed")
                return comp, pt, ct, trace
            cap_spent = any("read cap was reached" in t for t in tr)
            if cap_spent or turn + 1 >= _LOOP_MAX_COMPARES:
                # The deficit stands and no further reading is possible -- either the turns
                # or the character cap are spent. The comparison is kept as it is, and the
                # paper is marked INSUFFICIENT rather than closing as a clean verdict: a
                # `none` that means "nothing found" and a `none` that means "the budget ran
                # out while something was still missing" are different findings, and a
                # reviewer is entitled to see which this was.
                comp = dict(comp)

                # Keep the LAST semantic comparison as the best available assessment.
                # Do not overwrite overlap_degree / assessment / what_is_shared / submission_delta.
                comp["unresolved_deficit"] = deficit

                budget_reason = (
                    "read_cap_exhausted"
                    if cap_spent
                    else "comparison_budget_exhausted"
                )

                comp["paper_state"] = "unresolved_budget"
                comp["insufficient"] = True
                comp["unresolved"] = True
                comp["unresolved_reason"] = budget_reason

                # An unresolved paper must never become a verified strong refuter merely
                # because its last semantic proposal was substantial/same.
                comp["refutation_status"] = "cannot_refute"

                why = (
                    "read cap"
                    if cap_spent
                    else f"{_LOOP_MAX_COMPARES} compares"
                )

                trace.append(
                    f"BUDGET: {why} spent -- keeping last semantic assessment "
                    f"({comp.get('overlap_degree', '')}) as best available assessment; "
                    f"UNRESOLVED: {deficit}"
                )

                return comp, pt, ct, trace
            trace.append(f"[{turn}] evidence gate REFUSED -> read again: {deficit}")
        return comp, pt, ct, trace

    @staticmethod
    def _evidence_deficit(comp: dict) -> Optional[str]:
        diag = comp.get("map_diag") or {}

        proposal = comp.get("comparison_proposal") or {}
        proposed_deg = (proposal.get("overlap_degree") or "").lower()

        proposal_material = proposed_deg in {
            "partial",
            "substantial",
            "same",
        }

        # The map itself did not complete.
        if diag.get("call_failed"):
            return (
                "the evidence map did not complete, so the semantic comparison "
                "has not been grounded"
            )

        # Ownership checking failed. This is uncertainty, not negative evidence.
        if proposal_material and diag.get("ownership_unchecked"):
            return (
                "the semantic comparison proposes substantive overlap, but ownership "
                "of the candidate evidence could not be verified"
            )

        # The comparison claims material overlap, but every grounded candidate
        # actually described cited work rather than this paper.
        if (
            proposal_material
            and diag.get("not_owned")
            and not (comp.get("evidence_pairs") or [])
        ):
            return (
                "the semantic comparison proposes substantive overlap, but every "
                "grounded candidate belongs to cited work rather than this paper"
            )

        check = comp.get("evidence_check") or {}
        status = (check.get("status") or "").lower()

        question = (
            check.get("unresolved_question") or ""
        ).strip()

        if (
            proposal_material
            and check.get("proposed_degree_supported") is not True
        ):
            return question or (
                "The grounded evidence does not establish the specific proposed "
                "overlap and its degree. Check the comparison's actual rationale."
            )

        if (
            status == "material"
            and not proposal_material
            and question
        ):
            return question

        # This should normally never be empty after a successful map.
        if not status:
            return "the evidence check produced no usable status"

        # Comparison says non-material, grounded evidence says material:
        # possible comparison false negative -> re-enter.
        if status == "material" and not proposal_material:
            return (
                "grounded evidence supports substantive contribution overlap that "
                "the semantic comparison did not recognize"
            )

        # Comparison says material, evidence says only non-material:
        # possible comparison false positive -> re-enter.
        if status == "nonmaterial" and proposal_material:
            return (
                "the semantic comparison proposes substantive overlap, but the "
                "grounded evidence currently supports only non-substantive overlap"
            )

        # Material semantic claim without sufficient grounded support.
        if status == "insufficient" and proposal_material:
            return (
                "the semantic comparison proposes substantive overlap, but the "
                "available grounded evidence is insufficient to support it"
            )

        return None

    def _read_paper_agentic(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str,
                            may_dismiss: bool = False):
        """The sections the model asks for -- returned as MODEL CONTEXT, nothing else.

        Returns (selected_context, names_read, pt, ct, dismissed). `dismissed` is None
        unless `may_dismiss` and the model, having read part of the paper, says it has no
        bearing on the claim -- then it carries the degree, the reason and the sections
        that were read before saying so, and the caller skips the comparison.

        What this is NOT: it is not the paper. `tb._paper_source_text(pid)` stays the whole
        parsed document and remains the corpus every quote is checked against, so a shorter
        context changes WHERE the model looks and never what counts as verified. Confusing
        the two would let a quote pass because the only text it was compared against was the
        text it came from.

        Two rounds, because one irreversible pick is what failed before: the model chooses
        from the menu, reads those sections in full, then sees what it has and may name more.
        Whether it asks is its decision -- no code gate forces a second look.
        """
        menu = tb.section_menu(pid)
        if not menu:
            return "", [], 0, 0
        pt = ct = 0
        claim_s = self._claim_str(claim)[:1200]
        title = (tb.pool.get(pid, {}) or {}).get("title", "")

        parsed, a, b = self._struct(_SectionPick, _fill(
            _PAPER_SECTION_PICK, claim=claim_s, realization=claim_ctx,
            title=title, sections=_fmt_sections_menu(menu)))
        pt += a; ct += b
        names = [s for s in (getattr(parsed, "sections", None) or []) if s] if parsed else []
        if not names:  # nothing usable came back -> the biggest sections, as elsewhere
            names = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:4]]

        got = tb.read_sections(pid, names, max_total=_READ_CAP).get("sections", []) or []
        if not got:
            # Titles that match no section leave nothing to read, and an empty context
            # silently falls back to the whole paper further down -- the selection would
            # be switched off without anything saying so. Read the biggest sections instead.
            names = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:4]]
            got = tb.read_sections(pid, names, max_total=_READ_CAP).get("sections", []) or []
            tb._log("read_paper", f"{pid}: no section matched the model's titles "
                                  f"-> read the {len(got)} biggest")
        read = [s["name"] for s in got]
        used = sum(len(s.get("text", "")) for s in got)

        unread = [m for m in menu if m["name"] not in set(read)]
        if may_dismiss and unread and (len(got) < _DISMISS_MIN_SECTIONS
                                       or used < _DISMISS_MIN_CHARS):
            # Dismissing a paper has to rest on having read it. Measured over six runs,
            # eight papers with a gold label were dropped this way, and half of them after
            # one or two sections -- the first pick can be narrow, and judging absence from
            # a narrow slice is the same mistake as judging it from an abstract.
            #
            # Topping up costs no model call: read_sections is code. It does put more in
            # the next prompt, which is the point -- the refusal is then informed.
            fill = [m["name"] for m in sorted(unread, key=lambda m: -m.get("chars", 0))]
            extra = tb.read_sections(
                pid, fill[:_DISMISS_MIN_SECTIONS], max_total=max(0, _READ_CAP - used)
            ).get("sections", []) or []
            for s in extra:
                if s["name"] not in read and (len(got) < _DISMISS_MIN_SECTIONS
                                              or used < _DISMISS_MIN_CHARS):
                    got.append(s); read.append(s["name"])
                    used += len(s.get("text", ""))
            unread = [m for m in menu if m["name"] not in set(read)]
        if unread and used < _READ_CAP:
            # Where nothing screened the pool, this turn may also end the paper: the
            # schema carries the extra option, and only then is the prompt that offers it
            # used. In triage mode the papers arriving here were already judged as
            # possible overlaps, so a dismissal would be second-guessing that screen.
            schema = _ReadMore if may_dismiss else _SectionPick
            tmpl = _PAPER_READ_MORE_OR_DROP if may_dismiss else _PAPER_READ_MORE
            parsed2, a, b = self._struct(schema, _fill(
                tmpl, claim=claim_s, realization=claim_ctx, title=title,
                read=_fmt_sections_full(got, max_total=_READ_CAP),
                unread=_fmt_sections_menu(unread)))
            pt += a; ct += b
            if may_dismiss and parsed2 is not None and not getattr(parsed2, "bears_on_claim", True):
                deg = (getattr(parsed2, "degree", "") or "superficial").lower()
                dismissed = {
                    "degree": deg if deg in ("none", "superficial") else "superficial",
                    "why": (getattr(parsed2, "why", "") or "").strip(),
                    "sections": list(read),
                }
                tb._log("read_paper", f"{pid}: no bearing after {len(read)} of "
                                      f"{len(menu)} sections -> {dismissed['degree']}")
                return _fmt_sections_full(got, max_total=_READ_CAP), read, pt, ct, dismissed
            more = [s for s in (getattr(parsed2, "sections", None) or [])
                    if s and s not in read] if parsed2 else []
            if more:
                extra = tb.read_sections(
                    pid, more, max_total=max(0, _READ_CAP - used)).get("sections", []) or []
                for s in extra:
                    if s["name"] not in read:
                        got.append(s); read.append(s["name"])

        tb._log("read_paper", f"{pid}: {len(read)} of {len(menu)} sections, "
                              f"{sum(len(s.get('text','')) for s in got):,} chars")
        return _fmt_sections_full(got, max_total=_READ_CAP), read, pt, ct, None

    def _section_compare(self, tb: ClaimToolbox, claim: dict, pid: str, claim_ctx: str,
                         paper_context: str = "", turn: int = 0):
        """Deep dive on the prior paper's WHOLE text: realization + the overlap judgment.

        The model used to choose sections from a menu and read those -- 13 to 21% of a paper
        across the three deep dives measured. Choosing costs a call, and it misses: on "RAG
        vs. GraphRAG" the selection left out the sentence in which that paper states what it
        contributes ("we present a comprehensive benchmark study comparing RAG and GraphRAG
        on established text-based tasks"), and the comparison came back `none` on one run of
        three -- no overlap found with a paper whose entire subject is the claim.

        Reading everything costs 2.4x per claim and 24% more wall time -- the same number of
        calls, each with more in it -- and over three runs each it never returned `none` for
        either real competitor, where the picking version did once, and it held the same
        verdict for two of three papers against one of three. On this project's scale the
        difference is about a euro across the whole evaluation.
        """
        pt = ct = 0
        # `paper_context` is what the model gets to read. Empty means nobody chose, so the
        # whole document goes in -- the source text is the context in that case, but they
        # are still two different things and only one of them is ever the corpus for a
        # verification.
        paper_text = paper_context or tb._paper_source_text(pid)
        if not paper_text.strip():   # no full text -> compare on the abstract passages
            hits = tb.read_paper(pid, query=self._claim_str(claim))
            paper_text = _fmt_passages(
                hits.get("passages") or ([{"text": hits.get("abstract", "")}]
                                         if hits.get("abstract") else []))
        # The comparison verdict is what a reviewer reads and what the evidence gate
        # judges everything else against -- its own "compare" role, unlike the reading
        # calls that got the model to this point.
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
        # Which text this verdict was actually formed on. "Sections read" says what was
        # available by now; these two ids say what the prompt contained, which is what
        # differs between a first comparison and the one after a re-entry.
        log = getattr(tb, "run_log", None)
        if log is not None:
            prov = tb.paper_provenance(pid)
            log.paper_source(pid, prov)
            # WHAT this text is, not just how it was selected. "whole_document" was
            # ambiguous in the one case where it mattered: with no parsed full text the
            # fallback is the whole of abstract+intro, which is also "whole" -- so a
            # 1.2k-character stand-in and a 60k-character paper were labelled alike.
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
        # What the UI's "sections read" box reports. With a selection the names are already
        # recorded by read_sections; without one the honest answer is that everything went in.
        if not paper_context:
            tb._sections_read.setdefault(pid, [])
            tb._sections_read[pid] = ["(full text)"]
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
        """Record the comparison; returns record_comparison's status summary.

        The comparison as STORED -- with every quote checked against its document -- lands
        in tb.ledger["comparisons"], not in this return value. Reading the model's raw dict
        instead of the ledger entry is how a caller ends up with an assessment whose quotes
        were never verified.
        """
        # Every comparison passes through here, including the ones that never reached a
        # compare call (a dismissed paper is recorded straight from the loop). Writing the
        # run log's per-paper entry at this single funnel is what makes the log's paper
        # count agree with the ledger's: hooking it to the compare call alone left a
        # dismissed paper counted but absent.
        rlog = getattr(tb, "run_log", None)
        if rlog is not None:
            try:
                # sections_used and the fetch status live on the toolbox, not on comp --
                # read them from the same place the ledger entry does.
                rlog.paper_outcome(
                    pid, comp, tb.paper_provenance(pid),
                    sections_used=list(tb._sections_read.get(pid) or []),
                    fulltext_fetch_status=comp.get("fulltext_fetch_status")
                    or (tb._fulltext_status.get(pid) if hasattr(tb, "_fulltext_status") else ""))
            except Exception:
                pass

        return tb.record_comparison(
            paper_id=pid,
            refutation_status=comp["refutation_status"],
            relevance_reason="",
            brief_note=comp["brief_note"],
            overlap_dimensions=[],
            overlap_degree=comp["overlap_degree"],
            what_is_shared=comp["what_is_shared"],
            submission_delta=comp["submission_delta"],
            evidence_pairs=comp["evidence_pairs"],
            extra={
                k: comp[k]
                for k in (
                    "map_diag",
                    "comparison_proposal",
                    "evidence_check",
                    "unresolved_deficit",
                    "paper_state",
                    "insufficient",
                )
                if k in comp
            },
            paper_realization=comp.get("paper_realization"),
            assessment=comp.get("assessment", ""),
            fulltext_fetch_status=comp.get("fulltext_fetch_status"),
            log=log,
        )


    def _map_evidence(self, tb: "ClaimToolbox", claim: dict, pid: str, comp: dict,
                      paper_context: str = "", turn: int = 0):
        """Replace the comparison's own quotes and degree with a verified claim-evidence map.

        The deep-dive call decides the degree and produces the quotes in one breath, and it
        sees only `claim_ctx[:1600]` of the submission -- 2.4% of a 67k-character paper,
        about half of it the extractor's paraphrase rather than the paper's sentences. Asked
        for a verbatim submission quote from that, it quoted the claim back: with the claim
        removed from its own verification corpus, 99 of 199 claim quotes on disk no longer
        verify. The map is given the submission's own sections instead, checks both sides
        against both documents, and decides the degree afterwards from what survived.

        On the four prior papers with a stated gold standard the stored pipeline degree is
        right for three of them -- it calls a medical GraphRAG METHOD a partial overlap of a
        BENCHMARK contribution, in every run -- where the map is right for all four in the
        majority of its runs.
        """
        pt = ct = 0

        def struct(schema, prompt):
            # Passed into evidence_map.build_map/conclude and, through it, into
            # check_ownership -- every semantic judgment the evidence map makes runs on
            # the "evidence" role: which correspondences hold, whether the degree they
            # imply is warranted, whether a span belongs to the paper offering it.
            nonlocal pt, ct
            try:
                parsed, a, b = self._struct(schema, prompt, role="evidence")
            except Exception as e:
                tb._log("evidence_map", f"{pid}: call failed ({type(e).__name__})")
                return None
            pt += a; ct += b
            return parsed

        # The prior paper whole, the submission only where this claim lives.
        #
        # Whole for the paper, because a correspondence can sit anywhere in it: reading only
        # the sections the deep dive picked covers 13-21% of a paper, and two of the seven
        # pairs the full-text version found lie outside that -- including the sentence in
        # which "RAG vs. GraphRAG" states its own contribution.
        #
        # Claim-local for the submission, because the whole of it buys nothing. Measured
        # over three runs of two claims against a stated gold standard, whole-submission
        # scored 19 of 21 and claim-local 20 of 21 -- the same within this sample -- while
        # costing a third more. The submission is also the duplicated half: identical for
        # every paper of a claim, and sent once per paper.
        #
        # Verification runs against the whole of both documents either way, so this changes
        # the search space and the bill, never what counts as verified.
        # Reuse exactly the source context used by the comparison.
        # Do not select or re-read submission sections here.
        basis = getattr(tb, "submission_basis", None) or {}
        submission_text = basis.get("text", "")

        if not submission_text.strip():
            raise ValueError(
                "Build the shared submission basis before evidence mapping."
            )
        # SEARCH SPACE -- what the model reads to propose pairs. May be a selection.
        paper_text = paper_context or tb._paper_source_text(pid)
        if not (submission_text.strip() and paper_text.strip()):
            return comp, pt, ct                      # nothing to map against; leave it alone

        claim_str = self._claim_str(claim)
        # The last two arguments are the VERIFICATION CORPORA and are always the whole
        # documents -- never `paper_text`, however it was narrowed. A pair survives only
        # if both spans are found in the full submission and the full paper, so narrowing
        # the search space can lose a pair but can never manufacture one.
        raw_proposal = {
            "overlap_degree": comp.get("overlap_degree", ""),
            "refutation_status": comp.get("refutation_status", ""),
            "what_is_shared": comp.get("what_is_shared", ""),
            "submission_delta": comp.get("submission_delta", ""),
            "assessment": comp.get("assessment", ""),
        }

        comp = dict(comp)
        comp["comparison_proposal"] = raw_proposal
        # The map gets its own pair of contexts and they are NOT the compare's: the
        # submission side is claim-local here, the paper side may be the whole document.
        # Recording only one pair per paper would attribute the map's pairs to text it
        # never saw.
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
            tb._log(
                "evidence_map",
                f"{pid}: map call failed -- keeping the deep dive's verdict"
            )
            return comp, pt, ct

        check = evidence_map.check_evidence(
            struct,
            claim_str,
            mapping,
            comparison=raw_proposal,
        )

        comp["evidence_check"] = {
            "status": check.get("status", "insufficient"),
            "reasoning": check.get("reasoning", ""),
            "supporting_pair_indices": check.get(
                "supporting_pair_indices", []
            ),
            "grounded_pairs": len(kept),
            "proposed_degree_supported": check.get(
                "proposed_degree_supported"
            ),
            "unresolved_question": check.get(
                "unresolved_question", ""
            ),
        }

        comp["evidence_pairs"] = kept

        # IMPORTANT:
        # overlap_degree, assessment and submission_delta stay exactly as proposed
        # by the semantic comparison.
        comp["overlap_degree"] = raw_proposal["overlap_degree"]
        comp["assessment"] = raw_proposal["assessment"]
        comp["what_is_shared"] = raw_proposal["what_is_shared"]
        comp["submission_delta"] = raw_proposal["submission_delta"]

        # Hard invariant:
        # can_refute is only possible for a strong semantic verdict AND
        # at least one grounded/owned evidence pair.
        raw_degree = (raw_proposal.get("overlap_degree") or "").lower()

        supporting = check.get("supporting_pair_indices") or []

        comp["refutation_status"] = (
            "can_refute"
            if (
                raw_degree in ("substantial", "same")
                and check.get("status") == "material"
                and bool(supporting)
                and check.get("proposed_degree_supported") is True
            )
            else "cannot_refute"
        )

        tb._log(
            "evidence_map",
            f"{pid}: {len(kept)} grounded-owned pairs; "
            f"comparison={raw_degree}, "
            f"evidence_check={check.get('status', 'insufficient')}"
        )

        return comp, pt, ct

    def _deep_dive(self, tb: ClaimToolbox, claim: dict, pid: str, degree: str, claim_ctx: str):
        tb._log("deep_dive", f"{pid} ({degree})", progress=True)
        # In-process PDF parse NOW, on demand -- only deep-dived papers ever get parsed
        # (most of the pool doesn't reach this point). Timed separately from the LLM
        # comparison so the Review timing breakdown can tell parsing apart from model latency.
        _p0 = time.perf_counter()
        fts = tb.ensure_fulltext(pid)
        parse_s = time.perf_counter() - _p0
        _c0 = time.perf_counter()
        # Chosen ONCE and used by both calls. Reading it twice was the old shape: the
        # whole paper went into the comparison and then into the map again.
        pt = ct = 0
        paper_context, dismissed = "", None
        if _PAPER_LOOP:
            comp, a, b, trace = self._paper_loop(tb, claim, pid, claim_ctx)
            pt += a; ct += b
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
        if _AGENTIC_SECTIONS:
            paper_context, _names, a, b, dismissed = self._read_paper_agentic(
                tb, claim, pid, claim_ctx, may_dismiss=_NO_TRIAGE)
            pt += a; ct += b
        if dismissed is not None:
            # Read, and found to be about something else. Recorded as what it is -- a
            # judgement from the paper's own sections, with those sections named -- and
            # not put through the comparison, which is what makes reading every paper
            # affordable at all.
            comp = self._to_comp(None)
            comp["overlap_degree"] = dismissed["degree"]
            comp["dismissed"] = True
            comp["brief_note"] = dismissed["why"]
            comp["assessment"] = dismissed["why"]
        else:
            comp, a, b = self._section_compare(tb, claim, pid, claim_ctx, paper_context)
            pt += a; ct += b
            if _USE_EVIDENCE_MAP:
                comp, a, b = self._map_evidence(tb, claim, pid, comp, paper_context)
                pt += a; ct += b
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
        # Provenance for this claim run: what was configured, which text each call
        # actually received, and how it ended. Attached to the toolbox so every step
        # that sends text to a model can register it where it happens, rather than
        # being reconstructed afterwards from what happened to be logged.
        self.run_log = tb.run_log = self._new_run_log(claim)
        pt = ct = 0
        est_total = {"v": 0}  # estimated total steps; 0 until the triage shortlist is known (frontend hides "/max" then)
        # Wall-clock breakdown per phase -- surfaced in the Review UI so the reviewer can
        # see WHAT makes a claim slow (almost always LLM latency: triage over the whole
        # pool + the per-paper deep-dive comparisons; PDF parsing is ~1s since PyMuPDF).
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
                    "max_steps": (
                        max(est_total["v"], len(traj))
                        if est_total["v"] else 0
                    ),
                    "last_action": traj[-1]["detail"] if traj else "starting",
                    "trajectory": traj,       # raw debug log
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
                    timings["deep_dive_papers"].append(tinfo)
                    emit(extra_pt=lp, extra_ct=lc)
                return lp, lc
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(self._deep_dive, tb, claim, pid, deg, claim_ctx)
                        for pid, deg in items]
                for fut in as_completed(futs):
                    a, b, tinfo = fut.result()
                    lp += a; lc += b
                    timings["deep_dive_papers"].append(tinfo)
                    emit(extra_pt=lp, extra_ct=lc)
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
        if _NO_TRIAGE:
            # Nothing is decided from an abstract: every paper goes to the deep dive, which
            # opens it at its section level and ends there if what it reads shows the paper
            # is about something else. No pre-recorded verdict either -- with no screen,
            # every entry in the ledger comes from having read the paper.
            #
            # The dives remain independent of one another, so they still run side by side.
            # That independence is exactly what a tool loop over the pool gives up: there,
            # each turn's choice depends on the last one's result, which is why it cannot
            # be parallelised however the work is divided.
            shortlist = [(p["paper_id"], "unscreened") for p in top]
            timings["triage"] = 0.0
            tb._log("no_triage",
                    f"{len(shortlist)} papers, none screened from abstracts", progress=True)
        else:
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
        comparisons = tb.ledger["comparisons"]

        # Only verifier-approved strong overlaps challenge novelty.
        refuters = [
            c for c in comparisons
            if c.get("refutation_status") == "can_refute"
        ]

        # Preserve unresolved budget-exhausted paper comparisons for transparency.
        # They do not change the claim-level verdict.
        unresolved = [
            c for c in comparisons
            if c.get("unresolved") or c.get("insufficient")
        ]

        unresolved_papers = [
            {
                "paper_id": c.get("paper_id"),
                "title": c.get("title", ""),
                "semantic_degree": c.get("overlap_degree", ""),
                "semantic_assessment": c.get("assessment", ""),
                "reason": c.get(
                    "unresolved_reason",
                    "budget_exhausted",
                ),
                "deficit": c.get("unresolved_deficit", ""),
            }
            for c in unresolved
        ]

        if refuters:
            verdict = "challenged"
            suff = True
            stop = "challenged"
        else:
            verdict = "not_challenged"
            suff = True
            stop = "not_challenged"

        timings["total"] = round(time.perf_counter() - run_t0, 1)
        # "Other" = index building / bookkeeping / verdict not attributed to a named phase.
        _named = sum(v for k, v in timings.items()
                     if k not in ("deep_dive_papers", "total") and isinstance(v, (int, float)))
        timings["other"] = round(max(0.0, timings["total"] - _named), 1)
        # Cache telemetry only -- summarised here, never consulted above. A zero-cost,
        # zero-behaviour report: whether OpenAI's automatic prompt caching is finding
        # anything to reuse in this pipeline's call shapes, and where.
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

        # How this claim ended, in one place and with the three endings kept apart. The
        # pieces existed -- a verdict here, an `unresolved` flag on one comparison, a
        # failed map call in another's diagnostics -- and a reader had to assemble them
        # to tell "checked, nothing found" from "we stopped while something was missing"
        # from "a call broke".
        outcome = self.run_log.finish(
            verdict, entry.get("comparisons") or [],
            stop_reason=stop, evidence_sufficient=bool(suff))
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
            "evidence_sufficient": bool(suff),
            "review_complete": not bool(unresolved),
            "unresolved_count": len(unresolved),
            "unresolved_papers": unresolved_papers,
            "stop_reason": stop,
            "confidence": None,
            "timings": timings,
            "cost": {"prompt_tokens": pt, "completion_tokens": ct, "usd": _usd(self.model_name, pt, ct),
                     "cache": {"by_role": cache_by_role, "total_prompt_tokens": cache_total_pt,
                               "total_cached_tokens": cache_total_hit,
                               "hit_rate": round(cache_total_hit / cache_total_pt, 3) if cache_total_pt else 0.0}},
        })
        # NOT emit("done"): the api worker still assembles the review after this and writes
        # the real "done" payload (with review). A premature done here made the frontend stop
        # polling before the review existed and freeze on the last live state.
        emit()
        return entry
