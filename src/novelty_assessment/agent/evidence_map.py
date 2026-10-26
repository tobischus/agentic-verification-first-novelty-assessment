"""Evidence map and evidence check (Section 4.6).

The map proposes passage pairs between the submission and a prior paper. Both spans are
verified against the full documents, the prior-paper span is checked for ownership, and
the evidence check decides whether the remaining pairs support the proposed overlap.
"""

import re
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from . import evidence as ev

_ABBR = re.compile(r"(?:et al|e\.g|i\.e|cf|vs|Fig|Sec|Tab|Eq|approx|resp|Dr|No|al|[A-Z])\.$")
_STOP = frozenset(
    "a an the of to in for and or is are was were be been with on at by that this "
    "it its as from we our their they can may not but which".split()
)


def _sentences(span: str) -> List[str]:
    """Split a span into sentences, keeping abbreviations and initials intact."""
    out, start = [], 0
    for m in re.finditer(r"[.!?]\s+(?=[A-Z(])", span):
        head = span[start : m.start() + 1]
        if _ABBR.search(head.strip()):
            continue
        out.append(span[start : m.end()].strip())
        start = m.end()
    tail = span[start:].strip()
    if tail:
        out.append(tail)
    return out or [span]


# Section headings and page numbers that the parser left inside a span.
_TAIL_NOISE = re.compile(r"(?:\s*(?:\d+\s*)?##[^.]*|\s+\d{1,4}(?:\s*##.*)?)\s*\.?\s*$")
_HEADING = re.compile(r"\s(?:\d+(?:\.\d+)*\s*)?##\s")


def _strip_structure(span: str) -> str:
    """Remove a section heading inside a span and parser debris at its end."""
    t = " ".join((span or "").split())
    if not t:
        return t
    head = _HEADING.search(t)
    if head and head.start() > 80:
        t = t[: head.start()].strip()
    return _TAIL_NOISE.sub("", t).strip()


def trim_display_span(span: str, max_sentences: int = 3, max_chars: int = 700) -> str:
    """Shorten a verified quote for display, cutting only at sentence boundaries."""
    t = _strip_structure(span)
    if not t:
        return span
    t = _TAIL_NOISE.sub("", t).strip()
    sents = _sentences(t)
    if len(sents) > max_sentences:
        t = " ".join(sents[:max_sentences])
    while len(t) > max_chars and len(_sentences(t)) > 1:
        t = " ".join(_sentences(t)[:-1])
    return t or span


def _clauses(sentence: str, min_words: int = 8) -> List[str]:
    """Split a sentence at ', and' where both sides are clauses of at least `min_words` words."""
    out, last = [], 0
    for mt in re.finditer(r",\s+and\s+", sentence):
        nxt = re.split(r",\s+and\s+", sentence[mt.end() :])[0]
        if len(nxt.split()) >= min_words and len(sentence[last : mt.start()].split()) >= min_words:
            out.append(sentence[last : mt.start()].strip())
            last = mt.end()
    out.append(sentence[last:].strip())
    return [x for x in out if x]


def trim_to_sentence(
    span: str, rationale: str, claim: str, min_tokens: int, counterpart: str = ""
) -> str:
    """Reduce a verified span to the sentence, or clause, that carries the correspondence.

    The sentence is chosen by word overlap with the pair's rationale and the claim. The
    full span is kept when no sentence is long enough to stand as evidence.
    """
    sents = _sentences(_strip_structure(span))
    key = {w for w in re.findall(r"[a-z]{3,}", (rationale or "").lower()) if w not in _STOP}
    anchor = {w for w in re.findall(r"[a-z]{3,}", (claim or "").lower()) if w not in _STOP}
    if not key and not anchor:
        return span
    if len(sents) < 2:
        best = sents[0] if sents else span
        return _pick_clause(best, key, min_tokens, counterpart)
    best, best_score = None, -1.0
    for s in sents:
        if len(s.split()) < min_tokens:
            continue
        words = {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in _STOP}
        score = (len(words & key) + len(words & anchor)) / (len(words) ** 0.5 or 1)
        if score > best_score:
            best, best_score = s, score
    if not best:
        return span
    return _pick_clause(best, key, min_tokens)


def _drop_lead(clause: str) -> str:
    """Remove a leading conjunction left by the clause split."""
    return re.sub(r"^(?:and|or|but|as well as)\s+", "", clause.strip(), flags=re.I)


def _pick_clause(sentence: str, key: set, min_tokens: int, counterpart: str = "") -> str:
    """The clause of a sentence that best matches the rationale and the counterpart span.

    Clauses sharing fewer than two content words with the counterpart are skipped, and the
    whole sentence is kept if no clause qualifies.
    """
    cl = [_drop_lead(c) for c in _clauses(sentence)]
    if len(cl) < 2 or not key:
        return sentence
    other = {x for x in re.findall(r"[a-z]{3,}", (counterpart or "").lower()) if x not in _STOP}
    pick, ps = None, 0.0
    for c in cl:
        if len(c.split()) < min_tokens:
            continue
        w = {x for x in re.findall(r"[a-z]{3,}", c.lower()) if x not in _STOP}
        if other and len(w & other) < 2:
            continue
        sc = (len(w & key) + len(w & other)) / (len(w) ** 0.5 or 1)
        if sc > ps:
            pick, ps = c, sc
    return pick if pick else sentence


class Correspondence(BaseModel):
    submission_quote: str = Field(
        description=(
            "One contiguous verbatim span where the submission states "
            "a substantive component it contributes."
        )
    )

    paper_quote: str = Field(
        description=(
            "One contiguous verbatim span where the prior paper itself "
            "contributes the corresponding component."
        )
    )

    relation: str = Field(
        description=(
            "One concise sentence naming the substantive component instantiated by both spans."
        )
    )

    strength: str = Field(
        description=(
            "same | weaker. `same` means this component is directly delivered; "
            "`weaker` means the prior paper delivers a narrower or partial version."
        )
    )


class EvidenceMap(BaseModel):
    correspondences: List[Correspondence] = Field(
        default_factory=list,
        description=(
            "All substantive component-level correspondences for which both "
            "the submission and this prior paper state something they themselves contribute."
        ),
    )


MAP_PROMPT = """Identify every substantive component-level correspondence between ONE claimed contribution and ONE prior paper.

Your task is evidence extraction, not an overall novelty judgment.
The proposed semantic comparison below is a hypothesis to verify, not a fact.

First identify the specific shared contribution asserted in "What is shared"
and the assessment. Search the provided source texts for evidence of THAT
assertion. Do not substitute a different, easier-to-match contribution.

Keep the current claim as the scope of the comparison. Contributions elsewhere
in the submission are relevant only when you explain their direct bearing on
this claim.

For an empirical claim, distinguish a shared research activity from a shared
finding. "Both conduct experiments" does not by itself establish that both
answer the same scientific question or deliver the same empirical knowledge.
For other claim types, apply the same distinction to their actual contribution.

Use the proposed comparison to direct the search, but do not force agreement.
If the sources establish a different substantive overlap within the current
claim, report that correspondence and explicitly state how it differs from
the proposed rationale. If the proposed overlap has no supporting spans,
do not manufacture a substitute pair.

In each relation, state the concrete shared contribution established by the
two quotes and how it bears on the current claim. Do not merely repeat the
proposed assessment.

## Proposed semantic comparison — unverified
{comparison}
A correspondence exists when:
1. the submission states a substantive component of its claimed contribution;
2. the prior paper itself contributes something that instantiates the same substantive component; and
3. both statements can be supported by verbatim spans from the provided texts.

Judge the matched component, not whether the two papers make the same overall contribution. A prior paper may differ in its overall purpose, framing, scope, or design and still contribute a substantive component of the claim.

Do not report a correspondence when the relationship is only:
- shared topic, terminology, background, motivation, or common technical machinery;
- use, application, evaluation, or discussion of something that the other paper contributes;
- a statement about work cited by the paper rather than the paper's own contribution;
- semantic relatedness without both spans supporting the same substantive claimed component.

For every supported correspondence:
- quote the submission side verbatim;
- quote the prior-paper side verbatim;
- state briefly which substantive component the two spans correspond on;
- mark the relation as `same` when the prior paper directly delivers that component, or `weaker` when it delivers a narrower or partial version.

Report all supported correspondences and no unsupported ones. An empty list is a valid result.

Quote constraints:
- each quote must be ONE contiguous verbatim span;
- each quote must contain at least 10 words;
- each quote must lie within one sentence;
- never join separate spans;
- use the shortest span that still expresses the correspondence;
- each span must state what its own paper contributes, not merely what it discusses.

Do not assign an overall overlap degree in this step.

## Claimed contribution
{claim}

## Submission text
{submission}

## Prior paper: {title}
{paper}"""


class _OwnItem(BaseModel):
    index: int = Field(description="the pair's number, as given")
    own_contribution: bool = Field(
        description="true only if the span states what THIS paper does or delivers"
    )
    why: str = Field(default="", description="one clause")


class _Ownership(BaseModel):
    verdicts: List[_OwnItem] = Field(default_factory=list)


OWNERSHIP_PROMPT = """Below are spans taken from ONE paper, each with the text around it. For each, decide whether the span states what THIS PAPER ITSELF does or delivers.

It does NOT, if the span:

- describes work the paper cites -- another system, dataset, benchmark or finding, however it is worded, and whether or not a citation marker survives in the excerpt
- reports a resource the paper merely USES or evaluates on, rather than one it built
- states background, a problem, or a position the field holds
- appears in a related-work summary, a table of other systems, or a list of prior approaches

It does, if the span states this paper's own construction, artifact, method, property or finding -- what a reader would attribute to these authors.

The surrounding text is what decides it: a sentence naming an artifact can be the paper announcing its own, or the paper describing someone else's, and only the context tells them apart.

## Paper: {title}

{spans}"""


def _norm_span(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _context_of(span: str, document: str, window: int = 320) -> str:
    """The span with about `window` characters of surrounding text on each side."""
    doc = document or ""
    n = _norm_span(span)[:60]
    if not n:
        return span
    flat = _norm_span(doc)
    i = flat.find(n)
    if i < 0:
        return span
    j = int(i / max(len(flat), 1) * len(doc))
    lo, hi = max(0, j - window), min(len(doc), j + len(span) + window)
    return "..." + " ".join(doc[lo:hi].split()) + "..."


def check_ownership(
    struct_call: Callable, pairs: List[dict], title: str, verify_paper: str
) -> List[dict]:
    """Ownership check of the prior-paper spans in one batched call.

    Pairs whose span describes cited work are dropped. If the call fails or a verdict
    is missing, the pair is kept and marked as unchecked.
    """
    if not pairs:
        return pairs
    kept, need = [], list(pairs)
    spans = "\n\n".join(
        f"[{i + 1}] SPAN: {p.get('paper_quote', '')}\n"
        f"    CONTEXT: {_context_of(p.get('paper_quote', ''), verify_paper)}"
        for i, p in enumerate(need)
    )
    parsed = struct_call(_Ownership, OWNERSHIP_PROMPT.format(title=title, spans=spans))
    if parsed is None:
        for p in need:
            p["ownership"] = "unchecked"
        return need
    verdict = {v.index: v for v in (parsed.verdicts or [])}
    for i, p in enumerate(need, start=1):
        v = verdict.get(i)
        if v is None:
            p["ownership"] = "unchecked"
            kept.append(p)
            continue
        if not v.own_contribution:
            p["ownership"] = f"describes_cited_work: {(v.why or '').strip()[:160]}"
            continue
        p["ownership"] = "own_contribution"
        kept.append(p)
    return kept


def build_map(
    struct_call: Callable,
    claim_str: str,
    submission_text: str,
    title: str,
    paper_text: str,
    verify_submission: str,
    verify_paper: str,
    min_quote_tokens: int = 10,
    fuzzy_threshold: float = 90.0,
    comparison: Optional[dict] = None,
) -> dict:
    """Evidence map for one claim-paper pair, with verified and owned pairs only.

    The model quotes from `submission_text` and `paper_text`. Both spans are verified
    against the full documents `verify_submission` and `verify_paper`.
    """
    parsed = struct_call(
        EvidenceMap,
        MAP_PROMPT.format(
            claim=claim_str,
            submission=submission_text,
            title=title,
            paper=paper_text,
            comparison=_fmt_comparison(comparison or {}),
        ),
    )
    if parsed is None:
        return {
            "pairs": [],
            "dropped": 0,
            "returned": 0,
            "not_owned": 0,
            "ownership_unchecked": 0,
            "failed": True,
        }

    pairs, dropped = [], 0
    for c in parsed.correspondences:
        s_chk, s_span = ev.verify_contiguous(
            c.submission_quote, verify_submission, min_quote_tokens, fuzzy_threshold
        )
        p_chk, p_span = ev.verify_contiguous(
            c.paper_quote, verify_paper, min_quote_tokens, fuzzy_threshold
        )
        if not (s_chk.verified and p_chk.verified):
            dropped += 1
            continue
        rel = (c.relation or "").strip()
        pairs.append(
            {
                "claim_quote": trim_to_sentence(s_span, rel, claim_str, min_quote_tokens, p_span),
                "paper_quote": trim_to_sentence(p_span, rel, claim_str, min_quote_tokens, s_span),
                "rationale": rel,
                "strength": (c.strength or "").strip().lower(),
                "claim_quote_verified": True,
                "paper_quote_verified": True,
                "exact": True,
            }
        )
    verified = len(pairs)
    ownership_result = check_ownership(struct_call, pairs, title, verify_paper)
    unchecked = [p for p in ownership_result if p.get("ownership") == "unchecked"]
    owned = [p for p in ownership_result if p.get("ownership") == "own_contribution"]
    return {
        "pairs": owned,
        "dropped": dropped,
        "returned": len(parsed.correspondences),
        "not_owned": verified - len(ownership_result),
        "ownership_unchecked": len(unchecked),
        "failed": False,
    }


def _list_pairs(pairs: List[dict], start: int = 1) -> str:
    return "\n\n".join(
        "[{}] ({}) {}\n    SUBMISSION: “{}”\n    THIS PAPER: “{}”".format(
            i,
            p.get("strength", "?"),
            p.get("rationale", ""),
            " ".join(p["claim_quote"].split()),
            " ".join(p["paper_quote"].split()),
        )
        for i, p in enumerate(pairs, start)
    )


def _fmt_comparison(comparison: dict) -> str:
    """The proposed comparison as text for the prompts."""
    if not comparison:
        return "(not available)"
    lines = [f"Proposed degree: {comparison.get('overlap_degree', '')}"]
    if comparison.get("what_is_shared"):
        lines.append(f"What is shared: {comparison['what_is_shared']}")
    if comparison.get("submission_delta"):
        lines.append(f"Submission delta: {comparison['submission_delta']}")
    if comparison.get("assessment"):
        lines.append(f"Assessment: {comparison['assessment']}")
    return chr(10).join(lines)


class EvidenceCheck(BaseModel):
    status: str = Field(description="material | nonmaterial | insufficient")

    supporting_pair_indices: List[int] = Field(
        default_factory=list,
        description=(
            "1-based indices of grounded pairs that establish substantive "
            "overlap within the CURRENT claim. Include only pairs whose "
            "quoted spans actually support the stated relation."
        ),
    )

    proposed_degree_supported: Optional[bool] = Field(
        default=None,
        description=(
            "For proposed partial/substantial/same: whether the grounded "
            "evidence supports the decision-relevant overlap assertion "
            "at the proposed degree. Do not require every sentence of the "
            "assessment or delta to be established by correspondence pairs. "
            "An unsupported delta assertion makes this false only when "
            "resolving it could change the overlap degree; explain that "
            "dependency in unresolved_question. Otherwise record the "
            "limitation in reasoning. For none/superficial return null. "
            "Do not assign a replacement degree."
        ),
    )

    unresolved_question: str = Field(
        default="",
        description=(
            "Only a question whose resolution could change the overlap "
            "decision or establish its currently missing evidential basis. "
            "Name the contested assertion, relevant pair indices, and why "
            "the answer matters to the decision. Prioritize the conflict "
            "between the proposal and valid evidence, not an irrelevant "
            "rejected pair. Put non-blocking delta limitations in reasoning. "
            "Empty when no decision-relevant conflict remains."
        ),
    )

    reasoning: str = Field(default="")


EVIDENCE_CHECK_PROMPT = """Check whether grounded evidence supports the
specific overlap asserted by a semantic comparison of ONE claim and ONE
prior paper.

The comparison is a hypothesis, not evidence.
The quoted spans have passed source-grounding and ownership checks.
The proposed relation between two spans may still be wrong.

Perform these checks:

1. CLAIM SCOPE
Identify the actual contribution under review.
Do not use a neighboring contribution to establish overlap or preserve novelty
unless its relevance to this claim is explicitly justified.

The submission context below is the same passage selection the comparison was
built from. Use it to establish what the claim's terms MEAN: a construct the
comparison names but never defines, the conditions a result is asserted under,
which component of the work the claim is actually about.

It is context for interpretation, never evidence of overlap. Overlap is
established only by the grounded pairs. A passage here cannot make a relation
supported that the pairs do not carry, and it adds nothing about the prior paper.

If the comparison describes this claim in terms the submission context does not
bear out, say so in reasoning. A description that drifted from the submission is
a reason to doubt the proposed relation, not a reason to repair it.

2. PAIR VALIDITY
For each pair, judge what the quoted spans themselves establish.
A relation is supported only when both spans express the asserted shared
contribution in compatible semantic roles.
Constructing, using, evaluating, and surveying something are not interchangeable.

For empirical claims, distinguish:
- conducting a similar research activity;
- answering the same scientific question;
- establishing the same finding under comparable conditions.

Shared evaluation activity alone is not sufficient evidence of shared findings.
Different conditions may support a narrower overlap; explain the limitation.
Apply equivalent reasoning to methodological, theoretical, resource, and other
contribution types.

3. SUPPORT FOR THE PROPOSED RATIONALE
Check the specific assertion in "What is shared" and the assessment.
Evidence for another component does not automatically support that assertion.
If a different substantive overlap is evidenced within the current claim,
identify it, but do not silently substitute it for the proposed rationale.

4. SUPPORT FOR THE PROPOSED DEGREE
For proposed partial, substantial, or same, assess whether the valid evidence
justifies the proposed rationale at that degree:

partial:
    A meaningful part of the current contribution is already delivered.
    The overlap must be more than a shared topic or generic research activity.

substantial:
    The evidence reaches the central contribution of the current claim.
    A match on a subordinate component alone is not sufficient.

same:
    The evidence supports equivalence of the current claimed contribution
    in its scientifically relevant content and scope.

Use scientific relevance, not the number of pairs or matched phrases.
Do not require every detail to match for partial or substantial overlap.
Do not assign a replacement degree.

A different dataset, implementation, or experimental setting does not by itself
establish a scientifically meaningful residual contribution. Conversely, a
difference can matter when it changes capabilities, assumptions, findings, or
the scope in which a result holds.

5. DISTINGUISH OVERLAP SUPPORT FROM DELTA LIMITATIONS

Correspondence pairs provide positive evidence of overlap.
They are not an exhaustive account of either paper.

Absence of a correspondence does not prove that the prior paper lacks a
component. Do not endorse such an absence claim merely because no pair
demonstrates that component.

However, an unsupported absence claim in the delta does not automatically
invalidate independently supported overlap.

Apply this decision test:
Would resolving the disputed assertion change the proposed overlap degree,
or is the assertion necessary to establish the overlap itself?

If yes:
    Identify the specific dependency in unresolved_question.
    For a material proposal, set proposed_degree_supported=false when
    the available evidence cannot resolve that decision-relevant issue.

If no:
    Do not block the overlap decision because of that assertion.
    Explain in reasoning which delta statement must remain qualified.
    Do not present the unverified difference as established novelty.

For partial overlap, evidence must establish a meaningful shared component.
It need not prove that every other component is absent from the prior paper.
If the evidence leaves a concrete ambiguity about whether the shared
contribution is central rather than partial, explain that ambiguity.
Do not invent such an ambiguity solely because the pairs are non-exhaustive.

For substantial or same, a subordinate match is insufficient to establish
the proposed degree. Missing evidence about centrality or relevant scope
can therefore remain a blocking issue.

When the comparison proposes none/superficial but valid pairs establish
material overlap, the unresolved question must address why that demonstrated
contribution overlap is being treated as nonmaterial.

A rejected pair is not automatically a reason to repeat the comparison.
If other valid pairs independently support the decision, identify the
rejected pair in reasoning without making it the repair target.
It becomes blocking only if the decision depends on its assertion.

Return:

status:
    material: at least one valid pair establishes substantive overlap within
              the current claim.
    nonmaterial: the pairs establish only non-substantive relationships.
    insufficient: available evidence does not permit a reliable determination.

supporting_pair_indices:
    All 1-based indices of valid material pairs.
    Empty for nonmaterial or insufficient.

proposed_degree_supported:
    For proposed partial/substantial/same, true when the valid evidence
    supports the decision-relevant overlap assertion at that degree.
    False when its evidential basis or a decision-relevant scope issue
    remains unresolved.
    Do not set false solely because a nonessential delta statement is
    unsupported or an unused candidate pair is invalid.
    For proposed none/superficial, return null.

unresolved_question:
    State only a decision-relevant conflict.
    Identify the contested assertion and relevant pair indices.
    Explain how resolving it would affect the overlap decision.
    For none/superficial contradicted by material evidence, address that
    contradiction directly.
    Do not request evidence merely to prove all remaining differences absent.
    Do not assume that additional reading is necessary.
    Empty when no decision-relevant conflict remains.

reasoning:
    Explain what the valid pairs establish and what they do not establish.
    Identify rejected pairs and non-blocking limitations separately.
    Explicitly qualify unsupported delta assertions; do not certify residual
    novelty from missing correspondence pairs.

## Current claim
{claim}

## Submission context (the passages this claim and the comparison were drawn from)
{submission_context}

## Proposed semantic comparison
{comparison}

## Grounded pairs
{pairs}
"""

EVIDENCE_CHECK_PROMPT_VERSION = "evidence_check_v2_submission_context"


def check_evidence(
    struct_call: Callable,
    claim_str: str,
    mapping: dict,
    comparison: Optional[dict] = None,
    submission_context: str = "",
) -> dict:
    """Evidence check: do the grounded pairs support the proposed overlap and degree?

    The claim-local submission context is given for interpretation only. Code enforces
    the result: `material` needs supporting pairs, and the proposed degree counts as
    supported only for material evidence.
    """
    comparison = comparison or {}
    pairs = mapping.get("pairs") or []
    proposed_degree = (comparison.get("overlap_degree") or "").lower()
    material_proposal = proposed_degree in {"partial", "substantial", "same"}

    def unresolved(reason):
        return {
            "status": "insufficient",
            "supporting_pair_indices": [],
            "reasoning": reason,
            "proposed_degree_supported": False if material_proposal else None,
            "unresolved_question": reason,
        }

    if not pairs:
        return unresolved(
            "No grounded ownership-verified pair supports the proposed overlap. "
            "Check the specific shared contribution in the comparison against "
            "the source passages; do not substitute a different contribution."
        )

    parsed = struct_call(
        EvidenceCheck,
        EVIDENCE_CHECK_PROMPT.format(
            claim=claim_str,
            submission_context=(submission_context or "").strip()
            or "(no submission context was supplied for this check)",
            comparison=_fmt_comparison(comparison),
            pairs=_list_pairs(pairs),
        ),
    )
    if parsed is None:
        return unresolved("The evidence check did not complete.")

    status = (parsed.status or "").strip().lower()
    if status not in {"material", "nonmaterial", "insufficient"}:
        status = "insufficient"
    indices = sorted(
        {
            i
            for i in (parsed.supporting_pair_indices or [])
            if type(i) is int and 1 <= i <= len(pairs)
        }
    )
    if status == "material" and not indices:
        status = "insufficient"
    if status != "material":
        indices = []

    degree_supported = parsed.proposed_degree_supported
    if material_proposal:
        degree_supported = degree_supported is True and status == "material" and bool(indices)
    else:
        degree_supported = None

    question = (parsed.unresolved_question or "").strip()
    if material_proposal and not degree_supported and not question:
        question = (
            "Which grounded correspondence supports the specific shared "
            "contribution and the proposed overlap degree? Reassess the "
            "comparison if the existing evidence supports only a narrower claim."
        )
    return {
        "status": status,
        "supporting_pair_indices": indices,
        "reasoning": (parsed.reasoning or "").strip(),
        "proposed_degree_supported": degree_supported,
        "unresolved_question": question,
    }
