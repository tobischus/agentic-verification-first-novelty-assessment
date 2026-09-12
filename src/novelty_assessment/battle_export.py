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
from agent.evidence_map import trim_display_span

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


def _pair_groups(pairs: List[tuple]) -> List[tuple]:
    """Group pairs that share the same (normalised) submission span, in first-seen order.

    One correspondence usually names several prior-work spans against the same sentence of
    the submission -- listing that sentence once per pair repeats it as many times as the
    paper was quoted. Mirrors ReviewWalkthrough.jsx's groupBySubmissionQuote so the exported
    text and the reviewer UI group evidence the same way.

    `pairs` is a list of (original_index, pair) so a group keeps the number each pair had
    when it was sent to check_evidence -- the number its own reasoning refers to.
    """
    groups: List[tuple] = []
    index: dict = {}
    for i, p in pairs:
        key = " ".join((p.get("claim_quote") or "").split())
        if key not in index:
            index[key] = len(groups)
            groups.append((key, []))
        groups[index[key]][1].append((i, p))
    return groups


def _render_pair_groups(pairs: List[tuple], out: List[str]) -> None:
    """`pairs` is a list of (original_index, pair); see `_pair_groups`."""
    for claim_quote, group in _pair_groups(pairs):
        first_i, first = group[0]
        if claim_quote:
            out.append("Submission contribution span")
            out.append(_quote(claim_quote) if first.get("claim_quote_verified") else
                       f"(not confirmed verbatim) {claim_quote}")
            out.append("")
        for i, p in group:
            # Numbered so the evidence check's own reasoning ("pairs 1, 2, 4, 5, 6") stays
            # checkable against what is actually shown here.
            label = f"Pair {i}"
            # Printed after the paper's span it read as a comment on it; printed before, it
            # is the assertion the quote is evidence for -- which is what a pair is.
            if p.get("rationale"):
                out += [f"{label}: {p['rationale'].strip()}", ""]
            else:
                out += [label, ""]
            pq = (p.get("paper_quote") or "").strip()
            if pq:
                out.append("The prior work states:")
                out.append(_quote(pq) if p.get("paper_quote_verified") else
                           f"(not confirmed verbatim) {pq}")
                out.append("")


def _evidence_pairs(c: dict, out: List[str], claim_stop_reason: str = "") -> None:
    """Render the grounded claim/paper quote pairs for one comparison.

    `c["evidence_pairs"]` already passed two gates before it got here: text verification
    (both spans stand in their document, see evidence_map.build_map) and ownership (the
    paper's span is its own contribution, not a citation, see check_ownership). Neither
    gate is enough on its own to call a pair "support" -- PIKE-RAG's pair 1 is verified
    AND owned, and the evidence check still rejects it, because the quoted spans don't
    establish the SPECIFIC relation the pair claims (task-complexity classification is
    not the same thing as GraphRAG-Bench's benchmark task design). That third gate is
    `evidence_check.supporting_pair_indices`, and it is the one enforced below.

    So for `material`, only the pairs the check actually named as supporting appear in
    the main section, and every other grounded-and-owned candidate moves under a
    separate, clearly-labelled header -- so a reader cannot mistake a merely-topical
    correspondence for one the system is standing behind, and so nothing is dropped: a
    rejected candidate stays visible in the audit trail, just not presented as support.

    `nonmaterial` and `insufficient` do NOT clear `main` to empty: an empty
    `supporting_pair_indices` there does not mean "no evidence" -- the checker's
    `reasoning` for those verdicts is often written IN TERMS OF the same pairs, arguing
    why their relation is topical rather than substantive, and a reader needs the pairs
    in front of them to follow that argument. Comparisons from the older, non-agentic
    builder carry no evidence_check at all; those also fall back to showing every
    grounded pair, for the same reason.

    A pair rejected by `material`'s own check (verified, owned, but the relation itself
    didn't hold) is not printed at all here -- printing PIKE-RAG's pair 1 right after the
    reasoning that just rejected it made the same claim read as both accepted and refused
    in the same breath. It is not lost: `evidence_pairs` on the comparison record still
    carries it, unabridged, for anyone auditing the run. Every pair that IS shown keeps
    the number it had when check_evidence was asked about it, so "pairs 1, 2, 4, 5, 6" in
    the reasoning above can be matched against what actually appears below it.
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

    # 1-based, matching what check_evidence was given: the order of `ok` exactly as sent
    # to the evidence-check prompt (see api.py's own enumerate(pairs, 1)).
    numbered = list(enumerate(ok, 1))
    main = [(i, p) for i, p in numbered if i in supporting] if status == "material" and supporting \
        else numbered

    _render_pair_groups(main, out)

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


_EC_PHRASE = {
    "material": "material evidence", "nonmaterial": "nonmaterial",
    "insufficient": "insufficient evidence",
}


def _related_cell(entry) -> str:
    """One cell of the related-work table: what is actually known for this (paper, claim).

    A blank dash collapses three different situations into one mark: the paper was never
    compared for this claim, it was compared and found not to overlap, or it was compared
    and the evidence check could not settle the question. The first is an absent
    measurement; the second and third are results, and different ones -- `superficial`
    with `insufficient` evidence is not the same finding as `superficial` with the check
    actually agreeing there is no substantive relation. Collapsing them let a missing
    comparison read as a confirmed absence of overlap, which is the opposite of what an
    empty result means.
    """
    if entry is None:
        return "not assessed"
    deg, status = entry
    # The qualifier used to be dropped for partial/substantial/same, which made every
    # overlap in the table look unchecked and left the check visible only on the
    # non-overlapping cells -- backwards, since a reader most needs to know whether an
    # OVERLAP is backed by evidence. Every cell with a degree now gets one.
    plain = vd.overlap_label(deg) or deg or "not compared"
    phrase = _EC_PHRASE.get(status, "no evidence check")
    return f"{plain} · {phrase}"


_RELATED_LEGEND = (
    "Legend: Cells show overlap degree and evidence status: material = meaningful shared contribution supported; nonmaterial = examined correspondences do not support meaningful contribution overlap; insufficient = inconclusive evidence; no evidence check = no check recorded. Missing support is not proof of no overlap. Conflicting assessments are identified under Evidence limits."
)


# --------------------------- claim-level conclusion ------------------------- #
# Five fields, assembled from records the comparison step already wrote -- no new model
# call, no new interpretive sentence invented for a specific paper. Where the existing
# per-claim synthesis (Artifact B) has not been run against the CURRENT set of
# comparisons, the fields below are derived by the same deterministic rules verdict.py
# already applies per comparison (challenges(), overlapping(), degree_rank) rather than
# left to read as though a synthesis had produced them. A second, model-generated
# synthesis over these fields is future work, not something to fake here.

def _claim_verdict(comparisons: list, recorded: str):
    """(verdict, is_derived). Prefers Artifact B's own verdict; falls back to the same
    challenges()-over-comparisons rule the per-paper review already uses, so a missing
    synthesis does not silently read as "no assessment" further down the document."""
    if recorded:
        return recorded, False
    derived = "challenged" if any(vd.challenges(c) for c in comparisons or []) else "not_challenged"
    return derived, True


_ASSESSMENT_GLOSS = {
    "not_challenged": (
        "No comparison in the examined candidate set was found to substantially or "
        "equivalently overlap this claim under material evidence. This does not "
        "establish novelty across the wider literature -- only that none was found here."
    ),
    "challenged": (
        "At least one comparison in the examined candidate set is assessed to "
        "substantially or equivalently overlap this claim under material evidence. "
        "This does not by itself determine whether the claim should be rejected."
    ),
    "uncertain": "The available evidence did not permit a confident determination for this claim.",
}


def _claim_assessment(comparisons: list, recorded_verdict: str, recorded_rationale: str) -> str:
    verdict, derived = _claim_verdict(comparisons, recorded_verdict)
    lines = [f"{vd.verdict_label(verdict)}.", _ASSESSMENT_GLOSS.get(verdict, "")]
    if recorded_rationale and not derived:
        lines.append(recorded_rationale.strip())
    elif derived:
        lines.append(
            "(No claim-level synthesis was recorded for this run; the verdict above is "
            "derived from refutation_status across the comparisons below.)"
        )
    return " ".join(x for x in lines if x)


def _main_overlap(comparisons: list) -> str:
    """The decisive prior work and the SPECIFIC component each shares -- `what_is_shared`
    is the comparison step's own text, already written per (claim, paper); this only
    selects and labels it, it does not paraphrase or judge it.

    Cut with `trim_display_span`, the same boundary-respecting cut already used to keep a
    verified quote readable elsewhere in this pipeline (see evidence_map.py) -- one
    sentence here, since this field lists several papers and a full multi-sentence
    `what_is_shared` per paper is what pushed this field past a page.
    """
    rows = sorted(vd.overlapping(comparisons), key=vd.sort_key)
    if not rows:
        return "No prior work in the examined candidate set reached partial overlap or stronger."
    # "The decisive prior work", not a second copy of the related-work table: where a
    # stronger degree is present (substantial/same), the partial-overlap comparisons
    # beneath it are not what decided this claim's assessment, and listing all of them
    # here just repeats the table above at paragraph length instead of pointing at what
    # mattered. Restricting to the strongest tier present is what made 11 comparisons for
    # claim 2 collapse to the 2 (Zhou, Han) that are actually substantial.
    strongest = vd.degree_rank(vd.degree(rows[0]))
    rows = [c for c in rows if vd.degree_rank(vd.degree(c)) == strongest]
    parts = []
    for c in rows:
        shared = trim_display_span((c.get("what_is_shared") or "").strip(),
                                   max_sentences=1, max_chars=220)
        deg = vd.degree(c)
        status = ((c.get("evidence_check") or {}).get("status") or "").strip().lower()
        tag = f"{vd.degree_label(deg)}" + (f" · {status}" if status else "")
        piece = c.get("title", "")
        if shared:
            piece += f" ({shared})"
        parts.append(f"{piece} [{tag}]")
    return "; ".join(parts) + "."


def _eligible_for_remainder(comparisons: list) -> list:
    """Comparisons whose degree is actually carried by the evidence check, not merely
    proposed. `material` plus an overlap degree is the plain reading; the stricter
    `proposed_degree_supported is True` is not required here because the field is
    sometimes left unset for cases the check still considers valid (see EvidenceCheck's
    own docstring: null is a legitimate value, not a rejection)."""
    return [c for c in (comparisons or [])
            if ((c.get("evidence_check") or {}).get("status") or "").lower() == "material"
            and vd.degree(c) in vd.OVERLAP_DEGREES]


def _remaining_contribution(comparisons: list) -> str:
    """The submission_delta of EVERY comparison at the strongest evidence-supported
    degree, verbatim and separately -- not one picked arbitrarily among ties, and not
    merged into a single sentence that would misrepresent two different papers' deltas
    as one synthesis. Each bullet is the comparison step's own text; nothing here is
    written new for this export beyond the selection and the heading.
    """
    eligible = _eligible_for_remainder(comparisons)
    if not eligible:
        return ("**Remaining contribution:** No evidence-supported material comparison "
                "was available from which to derive a residual contribution.")
    strongest = min(vd.degree_rank(vd.degree(c)) for c in eligible)
    rows = [c for c in eligible if vd.degree_rank(vd.degree(c)) == strongest]
    out = ["**Remaining contribution relative to the strongest supported comparison(s):**", ""]
    for c in rows:
        delta = trim_display_span((c.get("submission_delta") or "").strip(),
                                  max_sentences=2, max_chars=380)
        out.append(f"- **{c.get('title', '')}:** "
                   + (delta or "No submission_delta text was recorded for this comparison."))
    out.append("")
    out.append("These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.")
    return "\n".join(out)


def _evidence_limits(comparisons: list) -> str:
    """Three separate limits, not one blended sentence -- `insufficient`, `no evidence
    check ran`, and `assessment and evidence check disagree` are different failures with
    different remedies, and folding them into "did not fully support the proposed
    degree" hid which one applied to a given paper. A prior version of this line named
    PIKE-RAG and "How to Mitigate Information Loss" together under that one phrase, when
    only the second is actually a conflict -- PIKE-RAG's evidence check simply never
    completed for the field this reads, and its `unresolved_question` alone had put it
    in the same bucket as a paper the check flatly disagreed with.

    A conflict is read directly off the two fields that are supposed to agree: the
    assessed degree (does it count as overlap?) and the evidence check's status (did the
    check find a meaningful shared contribution?). `proposed_degree_supported is None`
    is NOT treated as a conflict signal here -- EvidenceCheck returns null for
    none/superficial proposals by design (see its own field description), so null means
    "not applicable", not "unsupported".
    """
    comparisons = comparisons or []
    total = len(comparisons)

    def status_of(c):
        return ((c.get("evidence_check") or {}).get("status") or "").strip().lower()

    insufficient = [c for c in comparisons if status_of(c) == "insufficient"]
    not_checked = [c for c in comparisons if status_of(c) not in ("material", "nonmaterial", "insufficient")]

    def conflict(c):
        s, overlap = status_of(c), vd.degree(c) in vd.OVERLAP_DEGREES
        return (overlap and s == "nonmaterial") or (not overlap and s == "material")

    conflicts = [c for c in comparisons if conflict(c)]

    lines = []
    counted = []
    if insufficient:
        verb = "has" if len(insufficient) == 1 else "have"
        counted.append(f"{len(insufficient)} of {total} comparisons {verb} insufficient evidence")
    if not_checked:
        verb = "has" if len(not_checked) == 1 else "have"
        counted.append(f"{len(not_checked)} {verb} no recorded evidence check")
    if counted:
        lines.append(", and ".join(counted).capitalize() + ".")

    for c in conflicts:
        s, deg = status_of(c), vd.degree(c)
        lines.append(
            f"One comparison shows a conflict between the overlap assessment and evidence "
            f"check: {c.get('title', '')} was assessed as {deg or 'none'} while the evidence "
            f"check found {s} overlap. This conflict remains unresolved."
        )

    if insufficient:
        lines.append(
            "Insufficient evidence means the check could not settle the question, not "
            "that no overlap exists."
        )

    return " ".join(lines) or f"No insufficiency, missing evidence checks, or " \
                              f"assessment/evidence conflicts recorded among the {total} comparisons."


def _coverage(comparisons: list) -> str:
    comparisons = comparisons or []
    counts = {"material": 0, "nonmaterial": 0, "insufficient": 0}
    checked = 0
    for c in comparisons:
        status = ((c.get("evidence_check") or {}).get("status") or "").strip().lower()
        if status in counts:
            counts[status] += 1
            checked += 1
    parts = ", ".join(f"{n} {label}" for label, n in counts.items() if n)
    tail = f": {parts}" if parts else ""
    return (f"{len(comparisons)} comparison{'s' if len(comparisons) != 1 else ''} processed"
            + (f", {checked} with an evidence check{tail}." if checked else "."))


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
    # One row per paper, one column per claim: a paper can be `partial` for one claim and
    # `substantial` for another, and showing only its strongest degree -- as this table
    # used to -- let a reader see "substantial" here and "partial" in the claim's own
    # review section for the SAME paper with no indication that they are different claims.
    by_paper = {}     # pid -> {"title", "cite", cid: (degree, evidence_check_status)}
    best_rank = {}    # pid -> lowest DEGREE_RANK seen, for sorting only
    for cid in order:
        for c in (a_by.get(cid) or {}).get("comparisons", []) or []:
            pid = c.get("paper_id")
            pm = pool.get(pid, {})
            deg = vd.degree(c)
            row = by_paper.setdefault(pid, {
                "title": c.get("title", ""),
                "cite": _cite(c.get("authors") or pm.get("authors", ""),
                              c.get("year") or pm.get("year")),
            })
            status = ((c.get("evidence_check") or {}).get("status") or "").strip().lower()
            row[cid] = (deg, status)
            rank = vd.degree_rank(deg)
            if rank < best_rank.get(pid, vd.UNRANKED):
                best_rank[pid] = rank

    if by_paper:
        cols = [(cid, f"Claim {i + 1}") for i, cid in enumerate(order) if cid in a_by]
        out += ["## Related work examined", "",
                f"{len(by_paper)} papers were compared against the claims above.", ""]
        if len(cols) > 1:
            out.append("| Paper | " + " | ".join(h for _, h in cols) + " |")
            out.append("|" + "---|" * (len(cols) + 1))
            for pid in sorted(by_paper, key=lambda p: (best_rank.get(p, vd.UNRANKED),
                                                        by_paper[p]["title"].lower())):
                row = by_paper[pid]
                name = " — ".join(x for x in (row["title"], row["cite"]) if x)
                cells = [_related_cell(row.get(cid)) for cid, _ in cols]
                out.append(f"| {name} | " + " | ".join(cells) + " |")
        else:
            # One claim: a table with one data column says nothing a list didn't.
            for pid in sorted(by_paper, key=lambda p: (best_rank.get(p, vd.UNRANKED),
                                                        by_paper[p]["title"].lower())):
                row = by_paper[pid]
                cell = _related_cell(row.get(cols[0][0]) if cols else None)
                tail = " — ".join(x for x in (row["cite"], cell) if x and x != "not assessed")
                out.append(f"- {row['title']}" + (f" — {tail}" if tail else ""))
        out.append(_RELATED_LEGEND)
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

        # Five fields, each pulled from records the comparison step already wrote (see
        # the functions above for exactly which field feeds which line, and what is
        # derived by rule versus quoted verbatim). This replaces a plain prior-work list
        # and a count line with something that actually answers "so what, for this
        # claim" -- without adding a second, model-written synthesis on top of Artifact A.
        comparisons = e.get("comparisons") or []
        out += [
            "#### Claim-level conclusion", "",
            f"**Assessment:** {_claim_assessment(comparisons, v.get('verdict'), v.get('rationale'))}", "",
            f"**Main overlap:** {_main_overlap(comparisons)}", "",
            _remaining_contribution(comparisons), "",
            f"**Evidence limits:** {_evidence_limits(comparisons)}", "",
            f"**Coverage:** {_coverage(comparisons)}", "",
        ]

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
