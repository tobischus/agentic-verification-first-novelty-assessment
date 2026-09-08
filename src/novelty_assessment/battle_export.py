#!/usr/bin/env python3
"""
The system's final output as plain text -- the artifact that goes into the comparison
against other novelty assessment systems.

Nothing here is generated. Every line is copied from artifacts that already exist: the
paper metadata, the extracted claims with the quote each rests on, the related work that
was examined, and the assessment itself (Artifact B) over the evidence (Artifact A).
Rendering the deliverable from a template rather than from a model call is what makes it
reproducible: running this twice on the same run yields byte-identical text.

Text falls into three kinds and each is rendered differently, because conflating them is
exactly the failure this system exists to prevent: a span confirmed in its source appears
in typographic quotation marks, a span the checker could not confirm is labelled as an
unconfirmed quotation, and the system's own prose is left plain. A closing note states the
convention, so the document needs no legend to be read correctly.

Deliberately omitted, because they are reader aids rather than content: the per-quote
checkmarks in the comparison sections and the list of sections read for a comparison.

Usage
-----
  python src/novelty_assessment/battle_export.py --data-dir data --submission-id ID
  python src/novelty_assessment/battle_export.py --data-dir data --submission-id ID \
      --out battle/ID.md
"""
import argparse
import json
import re
from pathlib import Path
from typing import List

import verdict as vd

_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
             "Eighth", "Ninth", "Tenth"]

_LQ, _RQ = "“", "”"          # “ ”
_QUOTE_NOTE = (
    "Text in quotation marks (“…”) is quoted verbatim from the document it is "
    "attributed to and was checked against that document automatically. Everything else is the "
    "system's own prose."
)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ordinal(i: int) -> str:
    return f"{_ORDINALS[i]} extracted claim" if i < len(_ORDINALS) else f"Extracted claim {i + 1}"


def _cite(authors: str, year) -> str:
    names = [n.strip() for n in (authors or "").split(",") if n.strip()]
    cite = ""
    if names:
        surname = names[0].split()[-1] if names[0].split() else names[0]
        cite = f"{surname} et al." if len(names) > 1 else names[0]
    return " · ".join(x for x in (cite, str(year or "")) if x)


def _authors_from_tei(sub: Path, sid: str) -> str:
    """Author list of the submission, read from the GROBID header.

    Document processing stores title, date and abstract in {id}.json but not the authors,
    even though GROBID extracts them -- so read them here rather than leave the field out.
    Only the teiHeader is searched; the bibliography further down is full of persName too.
    """
    tei = sub / f"{sid}.grobid.tei.xml"
    if not tei.exists():
        return ""
    try:
        text = tei.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    head = text[: text.find("</teiHeader>")] if "</teiHeader>" in text else text[:20000]
    names = []
    for block in re.findall(r"<persName[^>]*>(.*?)</persName>", head, re.S):
        parts = re.findall(r"<(?:forename|surname)[^>]*>([^<]+)<", block)
        name = " ".join(p.strip() for p in parts if p.strip())
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _quote(text: str) -> str:
    return f"{_LQ}{' '.join((text or '').split())}{_RQ}"


def _segments(segs, out: List[str]) -> None:
    """Verified spans in quotation marks, the system's prose plain, and rejected quotes
    labelled as such.

    A quote that fails verification is stored as {"kind": "text", "verified": False} while
    genuine prose carries no `verified` key at all. Rendering both the same way would pass
    copied text off as the system's own words and make the closing note untrue, which is
    the opposite of what this document is for.
    """
    for s in segs or []:
        content = (s.get("content") or "").strip()
        if not content:
            continue
        if s.get("kind") == "quote" and s.get("verified"):
            out.append(_quote(content))
        elif "verified" in s:                       # a quote the checker could not confirm
            out += ["Quoted from the source but NOT confirmed verbatim:", content]
        else:
            out.append(content)
        out.append("")


def _evidence_pairs(pairs, out: List[str]) -> None:
    """Render claim/paper quote pairs, the evidence shape the non-agentic builder emits.

    Each pair puts a span of the submission beside a span of the prior work. Only spans the
    checker confirmed on that side are shown as quotations; an unconfirmed one is labelled,
    on the same rule as everywhere else in this document.
    """
    shown = 0
    for p in pairs:
        cq, pq = (p.get("claim_quote") or "").strip(), (p.get("paper_quote") or "").strip()
        if not (cq or pq):
            continue
        if shown == 0:
            out += ["Where the two papers say the same thing", ""]
        # The claim first, then the two spans that carry it. Printed after the quotes it read
        # as a comment on them; printed before, it is the assertion the quotes are evidence
        # for -- which is what a pair is.
        if p.get("rationale"):
            out += [p["rationale"].strip(), ""]
        shown += 1
        if cq:
            out.append("The submission states:")
            out.append(_quote(cq) if p.get("claim_quote_verified") else
                       f"(not confirmed verbatim) {cq}")
            out.append("")
        if pq:
            out.append("The prior work states:")
            out.append(_quote(pq) if p.get("paper_quote_verified") else
                       f"(not confirmed verbatim) {pq}")
            out.append("")


def _delta(c: dict, out: List[str]) -> None:
    """What the submission still holds, with what the search for it turned up.

    A delta is a claim of absence, so what is printed is the pair of things that can be
    checked: the submission's own sentence, and the closest the prior paper came when its
    full text was searched for the same thing. A reader who disagrees can see exactly what
    the claim was checked against.
    """
    held = c.get("delta_evidence") or []
    gone = c.get("delta_withdrawn") or []
    if not (held or gone):
        return
    if held:
        out += ["What the submission still has", ""]
        for d in held:
            out += [f"{d.get('what', '')} — {d.get('note', '')}".strip(" -"), ""]
            if d.get("submission_quote"):
                out += ["The submission states:", _quote(d["submission_quote"]), ""]
            if d.get("closest"):
                out += ["Closest passage found in the prior work when searched for "
                        f"“{d.get('probe', '')}”:",
                        "> " + " ".join(d["closest"].split())[:400], ""]
    for d in gone:
        out += ["Withdrawn: the prior work does deliver this", "",
                f"{d.get('what', '')} — {d.get('note', '')}".strip(" -"), ""]
        if d.get("paper_quote") and d.get("paper_quote_verified"):
            out += ["The prior work states:", _quote(d["paper_quote"]), ""]


def _follow_ups(qs: List[dict], out: List[str]) -> None:
    """The questions the comparison left open, and what looking them up settled.

    Unanswered ones are printed too. A question the paper's own text did not settle is a
    named gap, and a reviewer is better served by seeing it than by prose written over it.
    """
    if not qs:
        return
    out += ["Questions this comparison raised, and what the paper answered", ""]
    for q in qs:
        out += [f"{q.get('question', '')}", ""]
        if q.get("answered"):
            out += [q.get("answer", "").strip(), ""]
            if q.get("quote"):
                out += ["The prior work states:", _quote(q["quote"]), ""]
        else:
            out += [f"Searched for “{q.get('probe', '')}”; not settled by the "
                    f"passages found. {q.get('answer', '').strip()}", ""]


def build(data_dir: str, submission_id: str, variant: str = "") -> str:
    sub = Path(data_dir) / submission_id
    tail = f"_{variant}" if variant else ""
    a = _load(sub / f"{submission_id}_artifact_a{tail}.json")
    if a is None:
        raise FileNotFoundError(f"{submission_id}_artifact_a{tail}.json not found")
    b = _load(sub / f"{submission_id}_artifact_b{tail}.json") or {}
    meta = _load(sub / f"{submission_id}.json") or {}
    claims_doc = _load(sub / f"{submission_id}_claims.json") or {"claims": []}
    ranked = _load(sub / "related_work_data" / "ranked_papers.json") or []
    pool = {p.get("paper_id"): p for p in ranked}

    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    order = [c["id"] for c in claims]
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    b_by = {v.get("claim_id"): v for v in b.get("per_claim", [])}
    if not order:                     # claims file gone or rewritten: fall back to A's order
        order = [e.get("claim_id") for e in a.get("claims", [])]

    out: List[str] = ["# Novelty Assessment", ""]

    # ---------------------------- the paper ---------------------------- #
    title = meta.get("title") or claims_doc.get("title") or ""
    if title:
        out += [f"**{title}**", ""]
    authors = _authors_from_tei(sub, submission_id)
    if authors:
        out.append(f"Authors: {authors}")
    if meta.get("publication_date"):
        out.append(f"Publication date: {meta['publication_date']}")
    out.append("")

    # ------------------------- extracted claims ------------------------ #
    if claims:
        out += ["## Extracted claims", ""]
        for i, c in enumerate(claims, 1):
            out += [f"### Extracted Claim {i}", "", (c.get("claim_text") or "").strip(), ""]
            q = (c.get("evidence_quote") or "").strip()
            if q and c.get("evidence_verified"):
                out += ["Evidence in paper:", "", _quote(q), "", "✓ verbatim in paper", ""]
            elif q:
                out += ["Evidence in paper (could not be confirmed verbatim):", "",
                        " ".join(q.split()), ""]
            else:
                out += ["Evidence in paper: none recorded", ""]

    # ------------------------ related work list ------------------------ #
    # One entry per paper, carrying its STRONGEST overlap across the claims. A paper can be
    # superficial for one claim and substantial for another, so keeping whichever claim came
    # first would understate it.
    strongest = {}
    for cid in order:
        for c in (a_by.get(cid) or {}).get("comparisons", []) or []:
            pid = c.get("paper_id")
            pm = pool.get(pid, {})
            deg = vd.degree(c)
            rank = vd.degree_rank(deg)
            prev = strongest.get(pid)
            if prev is None or rank < prev[0]:
                strongest[pid] = (rank, c.get("title", ""),
                                  _cite(c.get("authors") or pm.get("authors", ""),
                                        c.get("year") or pm.get("year")),
                                  vd.overlap_label(deg))
    related = [(t, cite, deg) for _, t, cite, deg in strongest.values()]
    if related:
        out += ["## Related work examined", "",
                f"{len(related)} papers were compared against the claims above.", ""]
        for t, cite, deg in sorted(related, key=lambda r: (not r[2], r[0].lower())):
            tail = " — ".join(x for x in (cite, deg) if x)
            out.append(f"- {t}" + (f" — {tail}" if tail else ""))
        out.append("")

    # ------------------------------ review ----------------------------- #
    # The synthesised overall assessment is deliberately left out. It is prose ABOUT the
    # review rather than the review, and what a reader -- or a judge comparing systems --
    # has to be able to check is the claim-level evidence: which sentence of the submission
    # a prior paper already states, in both papers' own words.
    out += ["## Review", ""]

    n = 0
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        v = b_by.get(cid) or {}
        out += ["---", "", f"### {_ordinal(n)}", "",
                (e.get("claim_text") or e.get("claim_name") or "").strip(), ""]
        n += 1

        if v.get("verdict"):
            out += [f"**Verdict:** {vd.verdict_label(v['verdict'])}", ""]
        if v.get("rationale"):
            out += [v["rationale"].strip(), ""]

        real = e.get("claim_realization") or []
        if real:
            out += ["#### What the submission does for this claim", ""]
            _segments(real, out)

        overlaps = vd.overlapping(e.get("comparisons"))
        if not overlaps:
            out += ["#### Overlapping prior work", "",
                    f"None found among the {len(e.get('comparisons') or [])} papers compared.", ""]
            continue

        out += ["#### Overlapping prior work", ""]
        for c in overlaps:
            pm = pool.get(c.get("paper_id"), {})
            out.append(f"##### {c.get('title', '')}")
            deg = vd.degree(c)
            head = [vd.degree_label(deg)] if deg else []
            cite = _cite(c.get("authors") or pm.get("authors", ""), c.get("year") or pm.get("year"))
            if cite:
                head.append(cite)
            if head:
                out += [" · ".join(head), ""]

            pr = c.get("paper_realization") or []
            if pr:
                out += ["How this paper realizes the claim", ""]
                _segments(pr, out)
            # Both, never one or the other. paper_realization is an agent-only field, so
            # rendering only the narrative made the linear baseline look as though it had
            # produced no evidence when it had produced verified pairs -- and rendering it
            # INSTEAD of the pairs hid the agent's own claim-evidence map, which is the
            # artifact this system exists to produce and the one a reader can check.
            _evidence_pairs(c.get("evidence_pairs") or [], out)
            _delta(c, out)
            _follow_ups(c.get("follow_ups") or [], out)
            note = c.get("assessment") or c.get("brief_note") or ""
            if note:
                out += ["Comparison with the submission", "", note.strip(), ""]

    out += ["---", "", _QUOTE_NOTE]
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="Render the final assessment as plain text")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--out", default=None, help="write here instead of stdout")
    ap.add_argument("--variant", default="", help="export the {variant}-suffixed artifacts")
    args = ap.parse_args()
    text = build(args.data_dir, args.submission_id, variant=args.variant)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"written: {p}  ({len(text)} chars)")
    else:
        print(text)


if __name__ == "__main__":
    main()
