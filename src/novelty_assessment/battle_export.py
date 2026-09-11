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


def _pair_groups(pairs: List[dict]) -> List[tuple]:
    """Group pairs that share the same (normalised) submission span, in first-seen order.

    One correspondence usually names several prior-work spans against the same sentence of
    the submission -- listing that sentence once per pair repeats it as many times as the
    paper was quoted. Mirrors ReviewWalkthrough.jsx's groupBySubmissionQuote so the exported
    text and the reviewer UI group evidence the same way.
    """
    groups: List[tuple] = []
    index: dict = {}
    for p in pairs:
        key = " ".join((p.get("claim_quote") or "").split())
        if key not in index:
            index[key] = len(groups)
            groups.append((key, []))
        groups[index[key]][1].append(p)
    return groups


def _render_pair_groups(pairs: List[dict], out: List[str]) -> None:
    for claim_quote, group in _pair_groups(pairs):
        first = group[0]
        if claim_quote:
            out.append("Submission contribution span")
            out.append(_quote(claim_quote) if first.get("claim_quote_verified") else
                       f"(not confirmed verbatim) {claim_quote}")
            out.append("")
        for p in group:
            # Printed after the paper's span it read as a comment on it; printed before, it
            # is the assertion the quote is evidence for -- which is what a pair is.
            if p.get("rationale"):
                out += [p["rationale"].strip(), ""]
            pq = (p.get("paper_quote") or "").strip()
            if pq:
                out.append("The prior work states:")
                out.append(_quote(pq) if p.get("paper_quote_verified") else
                           f"(not confirmed verbatim) {pq}")
                out.append("")


def _evidence_pairs(c: dict, out: List[str], claim_stop_reason: str = "") -> None:
    """Render the grounded claim/paper quote pairs for one comparison.

    Where an evidence check ran (the agentic pipeline's map -> check_evidence gate), its
    verdict decides what the reader is shown: for `material`, only the pairs the check
    actually named as supporting appear in the main section, and every other grounded
    candidate moves under a separate, clearly-labelled header -- so a reader cannot mistake
    a merely-topical correspondence for one the system is standing behind. Comparisons from
    the older, non-agentic builder carry no evidence_check at all; those fall back to
    showing every grounded pair as before.
    """
    pairs = c.get("evidence_pairs") or []
    ok = [p for p in pairs
          if (p.get("claim_quote") or "").strip() or (p.get("paper_quote") or "").strip()]
    if not ok:
        return

    out += ["Grounded evidence for the assessed overlap", ""]

    check = c.get("evidence_check") or {}
    status = (check.get("status") or "").strip().lower()
    supporting = {i for i in (check.get("supporting_pair_indices") or [])}

    if status:
        out.append(f"Evidence check: {status}")
        if status == "material":
            out.append(f"{len(supporting)} of {len(ok)} grounded candidates support the overlap")
        out.append("")
        if check.get("reasoning"):
            out += [check["reasoning"].strip(), ""]

    if status == "material" and supporting:
        # 1-based, matching what check_evidence was given: the order of `ok` exactly as
        # sent to the evidence-check prompt (see api.py's own enumerate(pairs, 1)).
        main = [p for i, p in enumerate(ok, 1) if i in supporting]
        additional = [p for i, p in enumerate(ok, 1) if i not in supporting]
    else:
        main, additional = ok, []

    _render_pair_groups(main, out)

    if additional:
        out += ["Additional grounded candidate correspondences not used as material "
               "support", ""]
        _render_pair_groups(additional, out)

    # `insufficient` is the evidence check unable to settle the question; `c["insufficient"]`
    # is the paper loop's own read/re-entry budget running out with a deficit still standing
    # -- both leave the assessment resting on less than the pipeline normally requires, and
    # a reader comparing systems is entitled to see that rather than a confident-looking
    # verdict that quietly cost less scrutiny than the others.
    if status == "insufficient" or c.get("insufficient"):
        out.append("evidence_sufficient=False")
        if c.get("unresolved_deficit"):
            out.append(f"unresolved_deficit: {c['unresolved_deficit'].strip()}")
        elif claim_stop_reason:
            out.append(f"stop_reason: {claim_stop_reason}")
        out.append("")


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
            _evidence_pairs(c, out, claim_stop_reason=e.get("stop_reason", ""))
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
