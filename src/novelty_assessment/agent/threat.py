#!/usr/bin/env python3
"""
Examine prior work in order of how much it threatens the claim, and stop when the question
is answered.

The pipeline today triages the whole pool in one call, deep-dives whatever that call
shortlisted, and lists everything it touched with equal weight. Two measurements say this
is where the assessment is lost and where the reviewer is lost:

  * 703 of 1021 paper decisions across every run on disk -- 69% -- are settled by that one
    triage call and never revisited. Deep-diving the papers it dismissed flips 48% of them
    to a real overlap (eval/triage_ablation.py).
  * On one claim the reviewer is shown 11 overlapping papers and 57 quotes. Two of the 11
    carry the challenge; the other nine include a soccer case study.

So the ordering changes from "whatever the triage kept" to "most threatening first", and
the stopping changes from "everything shortlisted" to a check made in code after each
paper: is the claim's novelty settled yet? A paper is examined because the question is
still open, not because a label said so an hour ago -- and the reason for stopping is
recorded, which is what Section 2.4 of the thesis asks for and what none of the systems it
reviews provides.

Two properties follow that the linear baseline cannot have by construction. Budget goes
where the answer is still missing rather than being spread evenly, and the run can say why
it stopped. Neither is reachable by changing a constant in a one-pass pipeline.
"""
from typing import Callable, List, Optional

from pydantic import BaseModel, Field


class ThreatItem(BaseModel):
    paper_id: str
    threat: int = Field(description="0-10: how likely THIS paper already delivers what the "
                                    "claim promises. 0 = different kind of contribution "
                                    "entirely, 10 = looks like the same contribution.")
    reason: str = Field(description="one clause: what in the abstract drives that score")


class ThreatRanking(BaseModel):
    items: List[ThreatItem] = Field(description="one entry for EVERY paper id given")


RANK_PROMPT = """Rank prior-work papers by how much each THREATENS the novelty of ONE claimed contribution, from their abstracts.

The question is not "is this related" -- almost everything retrieved is related. The question is: could THIS paper already have delivered what the claim promises?

  8-10  the abstract suggests this paper presents the same contribution
  5-7   it presents part of it, or the same thing in a narrower setting
  2-4   same area and same machinery, but a different kind of contribution
        (the claim proposes a benchmark, this is a method; or a survey; or an application)
  0-1   nothing of the claimed contribution

Be willing to use the whole range. A pool where everything scores 5 is a ranking that
decides nothing, and a paper you score low is one nobody will read again -- so if the
abstract leaves you unsure whether it delivers the contribution, that uncertainty belongs
in the score, not in a confident dismissal.

## The claim
{claim}

## Papers (paper_id :: title :: abstract)
{papers}

Return one item for EVERY paper_id."""


# ------------------------------ the gate ---------------------------------- #

SERIOUS = 6          # below this a paper is a different kind of contribution


def settled(comparisons: List[dict], next_threat: Optional[int],
            miscalibrated_run: int = 0) -> Optional[str]:
    """Is the claim's novelty settled? Returns the stopping reason, or None to continue.

    Deliberately code, not a model call. The difference from DeepReviewer that Section 2.4
    names is that looking further is triggered by a check rather than chosen by the model,
    so the model must never be able to declare itself finished.

    Two earlier versions were wrong in opposite directions, and the reviews they produced
    showed it. Requiring a GROUNDED challenge never stopped at all: `substantial`
    comparisons carry an evidence pair in 0 of 18 cases on disk, so the gate waited for
    something the comparison stage cannot produce and spent the budget on ever weaker
    papers. Stopping at the first challenge stopped too early: it settled on the paper
    ranked 9 and never opened the one ranked 8, which the previous pipeline had found to
    be a substantial overlap too. A reviewer needs every serious challenge, not the
    strongest one.

    So: read everything that could plausibly challenge the claim, and stop when what is
    left cannot. Two conditions cut it short, and both depend on what was actually found
    rather than on a fixed schedule -- which is what a one-pass pipeline cannot do.
    """
    if any((c.get("overlap_degree") or "").lower() == "same" for c in comparisons):
        # The claim is anticipated outright. Further papers cannot change that finding,
        # and a reviewer holding a `same` does not need a fourth runner-up.
        return "anticipated"
    if miscalibrated_run >= 2:
        # Two straight papers came back below `partial` despite high threat scores: the
        # ranking is overestimating for this claim, so the queue behind them is not worth
        # the budget. This is the loop reacting to its own results.
        return "ranking_miscalibrated"
    if next_threat is None:
        return "candidates_exhausted"
    if next_threat < SERIOUS:
        return "remaining_candidates_below_threshold"
    return None


def ungrounded(comparisons: List[dict],
               degrees=("same", "substantial", "partial")) -> List[dict]:
    """Overlaps asserted without a verified quote pair -- what re-entry should repair.

    This is the deficit the evidence gate measures: a paper put in front of the reviewer as
    overlapping, with nothing they can check. `partial` is included because a blind rating
    marked verifiability down for exactly the papers it excluded -- an overlap the reviewer
    is shown is an overlap they should be able to check, whatever its strength.
    """
    out = []
    for c in comparisons:
        if (c.get("overlap_degree") or "").lower() not in degrees:
            continue
        if any(p.get("claim_quote_verified") and p.get("paper_quote_verified")
               for p in (c.get("evidence_pairs") or [])):
            continue
        out.append(c)
    return out


def rank(struct_call: Callable, claim_str: str, papers: List[dict],
         abstract_chars: int = 2500) -> List[dict]:
    """Threat score per paper, highest first.

    Papers the ranking omits are not dropped: an omission is the model failing to answer,
    not a judgement that the paper is harmless, and treating the two the same is how a
    pool silently shrinks.
    """
    listing = "\n\n".join(
        f"{p['paper_id']} :: {p.get('title', '')} :: {(p.get('abstract') or '')[:abstract_chars]}"
        for p in papers)
    parsed = struct_call(ThreatRanking, RANK_PROMPT.format(claim=claim_str[:1500], papers=listing))
    scores = {}
    if parsed is not None:
        for it in parsed.items:
            scores[it.paper_id] = (max(0, min(10, int(it.threat or 0))), (it.reason or "").strip())
    out = []
    for p in papers:
        threat, reason = scores.get(p["paper_id"], (5, "not scored by the ranking call"))
        out.append({**p, "threat": threat, "threat_reason": reason})
    out.sort(key=lambda p: (-p["threat"], -(p.get("sim") or 0.0)))
    return out


# --------------------------- grounding a challenge -------------------------- #

class GroundedPair(BaseModel):
    claim_quote: str = Field(default="", description="VERBATIM span of the SUBMISSION stating "
                                                     "the part of the claim this paper takes")
    paper_quote: str = Field(default="", description="VERBATIM span of THE PRIOR PAPER showing "
                                                     "it does that. One contiguous span.")
    rationale: str = Field(default="", description="one sentence: why these two say the same thing")
    withdraw: bool = Field(default=False, description="true if no honest pair can be produced")
    withdraw_reason: str = Field(default="", description="if withdrawing: what the overlap "
                                                         "actually amounts to")


GROUND_PROMPT = """A prior paper has been judged to overlap SUBSTANTIALLY with a claimed contribution. Produce the evidence for that judgement, or withdraw it.

Give ONE pair: a verbatim span of the submission stating the part of the claim this paper takes, and a contiguous verbatim span of the prior paper showing that it does that. Both copied character for character, at least 10 words, neither stitched from separate places.

If no honest pair exists -- the two are close in aim but nothing in the paper takes a stated part of this claim -- set `withdraw` and say what the overlap actually amounts to. Withdrawing is the right answer whenever the pair would have to be assembled or stretched to fit: a judgement the reviewer cannot check is worse than one that was retracted.

## The claim
{claim}

## What the submission itself says about it
{realization}

## The prior paper: {title}
{sections}

## The judgement to support or withdraw
{assessment}"""
