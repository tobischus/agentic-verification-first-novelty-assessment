#!/usr/bin/env python3
"""
Every paper is looked at; the agent decides which ones are worth looking at properly.

The triage this replaces asked one model call to label a pool from abstracts, and that
label was final: 726 of 1059 paper decisions across every run on disk -- 69% -- were
settled there and never revisited, and reading the dismissed ones with the pipeline's own
machinery flipped 48% of them to a real overlap. A threat ranking, tried next, moved the
error rather than removing it: it too decided from abstracts, and it too dropped the tail
unread.

So nothing is decided from an abstract here, and nothing is dropped.

  1. EVERY paper is scanned first, with retrieval and no model call at all: the claim is
     put to the paper's own full text and the passages that come back are the evidence
     that this paper has something to say about it. A cheap pass over everything beats an
     expensive judgement over a shortlist, and it costs nothing per paper.

  2. The agent then works a tool loop. It sees the whole pool -- every paper, its best
     matching passage, what has been done to it so far -- and chooses ONE action per turn.
     Depth goes where the evidence so far says it is needed, and a paper skipped in turn
     three can still be opened in turn nine, because nothing was thrown away.

  3. It may not declare itself finished. `finish` is a request; a gate in code grants it,
     and refuses while a paper the scan ranked high has never been compared, or while an
     overlap it asserted has no verified quote pair. That gate is the difference from
     DeepReviewer, which Section 2.4 of the thesis names: there, further work is chosen by
     the model; here it is triggered by a check the model does not control.
"""
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field

SCAN_K = 3                 # passages retrieved per paper in the free pass
OVERLAP = ("same", "substantial", "partial")
CHALLENGE = ("same", "substantial")


class Action(BaseModel):
    tool: str = Field(description="read | compare | ground | finish")
    paper_id: str = Field(default="", description="which paper; empty for finish")
    query: str = Field(default="", description="for read: what to look for in that paper")
    why: str = Field(default="", description="one clause: why this action, now")


ACT_PROMPT = """You are assessing whether ONE claimed contribution is novel, by examining the prior work retrieved for it.

Every paper below has already been scanned: the claim was put to its full text and the best-matching passage is shown with a retrieval score. That score says the passage exists, not that the paper overlaps -- reading it is what decides that.

Choose ONE action:

- read(paper_id, query)   pull further passages from that paper. Use it when the scan hints at something but you cannot tell from the snippet whether the paper delivers the claim, and a full comparison would be premature.
- compare(paper_id)       read the paper's relevant sections in full and judge the overlap. This is the expensive action; spend it where the evidence so far says it belongs.
- ground(paper_id)        demand a verbatim quote pair for an overlap you have already asserted, or withdraw it.
- finish()                you believe the claim's novelty is settled.

Spend depth where it is warranted and not evenly: a paper whose scan passage plainly restates the claim deserves a comparison before one that merely shares vocabulary. A paper you pass over now is not lost -- it stays in the list and you may open it later.

## The claim
{claim}

## What the submission itself does for this claim
{realization}

## The pool -- every retrieved paper, with its scan
{pool}

## What has happened so far
{history}

{gate}"""


def scan(tb, claim_str: str, papers: List[dict], ensure_fulltext: bool = True) -> List[dict]:
    """Put the claim to every paper's own text. No model call.

    The score is the cosine between the claim and the paper's best-matching passage, in the
    shared embedding space -- deliberately computed here rather than taken from
    PassageIndex.search, whose score is normalised WITHIN a paper (`bm / bm.max()`) and so
    hands every paper's best passage a value near 1.0. On the first run every one of twenty
    papers scored 0.97 or 0.98, which ranks nothing.

    What this measures is still weak on purpose: that a passage of this paper answers to the
    claim's wording. Far short of "this paper overlaps" -- it decides only where to look.
    """
    import numpy as np
    emb = tb.embedder
    q = None
    if emb is not None:
        try:
            q = emb.encode([claim_str], convert_to_numpy=True)[0]
            q = q / (np.linalg.norm(q) + 1e-9)
        except Exception:
            q = None

    out = []
    for p in papers:
        pid = p["paper_id"]
        if ensure_fulltext:
            try:
                tb.ensure_fulltext(pid)
            except Exception:
                pass
        best, snippet, section = 0.0, "", ""
        try:
            idx = tb._index_for(pid)
            idx._ensure_emb()
            if q is not None and idx._emb is not None and len(idx.chunks):
                sims = idx._emb @ q
                j = int(np.argmax(sims))
                best = float(sims[j])
                snippet = idx.chunks[j]["text"][:300]
                section = idx.chunks[j].get("section", "")
            else:                                   # no embedder: fall back to retrieval
                hits = idx.search(claim_str, k=1)
                if hits:
                    best = hits[0]["score"]
                    snippet, section = hits[0]["text"][:300], hits[0].get("section", "")
        except Exception:
            pass
        out.append({**p, "scan": round(best, 3), "snippet": snippet, "snippet_section": section})
    out.sort(key=lambda x: -x["scan"])

    # A fixed cut-off cannot work across embedding spaces and claim wordings; "high" means
    # high FOR THIS POOL. The gate below uses it, so it has to come from the data.
    scores = [x["scan"] for x in out]
    if scores:
        hi = sorted(scores)[int(len(scores) * 0.75)] if len(scores) > 3 else max(scores)
        for x in out:
            x["scan_high"] = x["scan"] >= hi
    return out


def deficits(scanned: List[dict], state: Dict[str, dict]) -> List[str]:
    """What still stands in the way of finishing. Empty means the gate opens.

    Written as sentences because they are shown to the agent: a gate that only says "no"
    makes the next turn a guess, and the point of checking in code is to name the work that
    is left, not merely to withhold permission.
    """
    out = []
    for p in scanned:
        st = state.get(p["paper_id"], {})
        if p.get("scan_high") and not st.get("compared"):
            out.append(f"{p['paper_id']} is in the top quarter of the pool by scan "
                       f"({p['scan']:.2f}) and has never been compared")
    for pid, st in state.items():
        if st.get("degree") in CHALLENGE and not st.get("grounded"):
            out.append(f"{pid} was called {st['degree']} without a verified quote pair")
    return out


def pool_table(scanned: List[dict], state: Dict[str, dict], limit: int = 30) -> str:
    rows = []
    for p in scanned[:limit]:
        st = state.get(p["paper_id"], {})
        done = st.get("degree") or ("read" if st.get("read") else "-")
        rows.append(
            f"{p['paper_id']} | scan {p['scan']:.2f} | {done:12} | {p.get('title', '')[:64]}\n"
            f"    best passage [{p.get('snippet_section', '')}]: {p.get('snippet', '')[:220]}")
    return "\n".join(rows)


def gate_text(defs: List[str]) -> str:
    if not defs:
        return ("## The gate\nNothing outstanding. finish() will be granted.")
    lines = "\n".join(f"- {d}" for d in defs[:8])
    return ("## The gate -- finish() will be REFUSED while these stand\n" + lines +
            "\nThese are checked in code after every action. Clear them, or spend the "
            "budget deciding they cannot be cleared.")
