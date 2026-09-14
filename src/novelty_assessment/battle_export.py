#!/usr/bin/env python3
"""Deterministic reviewer export, layout v3.

Drop-in replacement for src/novelty_assessment/battle_export.py.
Uses existing Artifact A/B and embedded run provenance. Makes no model calls,
changes no verdicts, and never fills historical version metadata from a live pool.
Comparison cells contain the complete recorded text. Quote text is not shortened.
--check-sources diagnoses missing run-bound version metadata without generating a
report, modifying artifacts, downloading documents, or calling a model.
"""
import argparse
import json
import re
from pathlib import Path
from typing import List

import verdict as vd

EXPORT_LAYOUT_VERSION = "reviewer-v3.1"

_LQ, _RQ = "“", "”"

_QUOTE_NOTE = (
    "Block quotations show stored source passages. Unless marked 'Not confirmed verbatim', "
    "they were automatically matched against their attributed document. This checks "
    "the quoted wording, not the correctness of its interpretation."
)

def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

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
        if s.get("kind") == "quote" or "verified" in s:
            _span(content, bool(s.get("kind") == "quote" and s.get("verified")), out)
            continue
        else:
            out.append(content)
        out.append("")

_EC_PHRASE = {
    "material": "material evidence", "nonmaterial": "nonmaterial",
    "insufficient": "insufficient evidence",
}

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

def _eligible_for_remainder(comparisons: list) -> list:
    """Comparisons whose degree is actually carried by the evidence check, not merely
    proposed. `material` plus an overlap degree is the plain reading; the stricter
    `proposed_degree_supported is True` is not required here because the field is
    sometimes left unset for cases the check still considers valid (see EvidenceCheck's
    own docstring: null is a legitimate value, not a rejection)."""
    return [c for c in (comparisons or [])
            if ((c.get("evidence_check") or {}).get("status") or "").lower() == "material"
            and vd.degree(c) in vd.OVERLAP_DEGREES]

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

def main():
    ap = argparse.ArgumentParser(description="Render the final assessment as plain text")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--out", default=None, help="write here instead of stdout")
    ap.add_argument("--variant", default="", help="export the {variant}-suffixed artifacts")
    ap.add_argument("--check-sources", action="store_true",
                    help="diagnose version metadata in existing artifacts; no model calls")
    args = ap.parse_args()
    if args.check_sources:
        print(check_sources(args.data_dir, args.submission_id, args.variant))
        return
    text = build(args.data_dir, args.submission_id, variant=args.variant)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"written: {p}  ({len(text)} chars)")
    else:
        print(text)


def _cite(authors, year=None) -> str:
    if isinstance(authors, list):
        authors = ", ".join(a.get("name", "") if isinstance(a, dict) else str(a)
                            for a in authors)
    names = [n.strip() for n in str(authors or "").split(",") if n.strip()]
    name = (names[0].split()[-1] + " et al." if len(names) > 1 else names[0]) if names else ""
    return " · ".join(str(x) for x in (name, year) if x)


def _status(c: dict) -> str:
    return str((c.get("evidence_check") or {}).get("status") or "").strip().lower()


def _conflict(c: dict) -> bool:
    overlap = vd.degree(c) in vd.OVERLAP_DEGREES
    return (overlap and _status(c) == "nonmaterial") or (not overlap and _status(c) == "material")


def _cell(text: str) -> str:
    """Keep prose in one Markdown table cell without turning source pipes into columns."""
    return " ".join(str(text or "").split()).replace("|", "&#124;")


def _pid(c: dict) -> str:
    return str(c.get("paper_id") or c.get("title") or "unidentified source")


def _ref(c: dict, refs: dict) -> str:
    return refs.get(_pid(c), c.get("title") or "Unidentified source")


def _snapshot(entry: dict, c: dict) -> dict:
    """Only this claim's embedded run record (or inline fields), never a current manifest.

    RunLog.to_dict() exports its comparisons as the prior_work LIST. This is the
    immutable source record associated with the assessment, not the retrieval pool.
    """
    result = {k: c[k] for k in ("pinned_version", "pinned_version_date", "pinned_url",
                               "version_status", "final_state", "unresolved_reason",
                               "unresolved_deficit") if c.get(k) is not None}
    log = entry.get("run_log")
    prior = log.get("prior_work") if isinstance(log, dict) else None
    for p in prior if isinstance(prior, list) else []:
        if not isinstance(p, dict):
            continue
        if _pid(p) == _pid(c):
            result.update(p)
            break
    return result


def _document_label(snapshot: dict) -> str:
    version = str(snapshot.get("pinned_version") or "").strip()
    if version.isdigit():
        version = "v" + version
    date = str(snapshot.get("pinned_version_date") or "").strip()
    # Preserve a recorded ISO calendar day, not just the year. Do not invent a day
    # for old runs that recorded only a year, or infer one from an arXiv identifier.
    match = re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", date)
    day = date[:10] if match else "exact date not recorded"
    label = f"{version or 'version not recorded'} · {day}"
    url = str(snapshot.get("pinned_url") or "").strip()
    if url.startswith(("https://", "http://")) and version:
        label = f"[{label}](<{url}>)"
    return label


def _related_cell(entry) -> str:
    if entry is None:
        return "not assessed"
    degree, status = entry
    return f"{vd.overlap_label(degree) or degree or 'not compared'} · " + _EC_PHRASE.get(status, "no evidence check")


_RELATED_LEGEND = (
    "**Legend:** overlap degree · evidence check. **Material:** meaningful overlap supported; "
    "**nonmaterial:** examined matches do not support it; **insufficient:** inconclusive; "
    "**no evidence check:** not recorded. These are separate assessments; missing support "
    "does not establish absence."
)


def _strongest(rows: list) -> list:
    """Keep every tie, using the original export's degree selection."""
    if not rows:
        return []
    rank = min(vd.degree_rank(vd.degree(c)) for c in rows)
    return [c for c in rows if vd.degree_rank(vd.degree(c)) == rank]


def _comparison_summary(comparisons: list, refs: dict, out: List[str]) -> None:
    # Preserve the original main-overlap selection (refutations sorted first),
    # and the independent evidence-supported selection for the reported delta.
    overlap = sorted(vd.overlapping(comparisons), key=vd.sort_key)
    main = []
    if overlap:
        rank = vd.degree_rank(vd.degree(overlap[0]))
        main = [c for c in overlap if vd.degree_rank(vd.degree(c)) == rank]
    remainder = _strongest(_eligible_for_remainder(comparisons))
    main_ids, delta_ids = {id(c) for c in main}, {id(c) for c in remainder}
    selected = main + [c for c in remainder if id(c) not in main_ids]
    out += ["## Closest comparisons", ""]
    if not selected:
        out += ["No comparison qualified for the strongest-overlap summary.", ""]
        return
    out += ["| Source | Shared contribution | Reported difference | Assessment |",
            "|---|---|---|---|"]
    for c in selected:
        shared = str(c.get("what_is_shared") or "").strip() or "Not recorded."
        # Do not promote an unchecked delta into the strongest supported remainder.
        delta = ((str(c.get("submission_delta") or "").strip() or "Not recorded.") if id(c) in delta_ids
                 else "Not selected as an evidence-supported remainder; see comparison details.")
        tag = _related_cell((vd.degree(c), _status(c)))
        label = _ref(c, refs)
        if id(c) not in main_ids:
            label += " (strongest supported comparison)"
        out.append("| " + " | ".join(_cell(x) for x in (label, shared, delta, tag)) + " |")
    out.append("")


def _missing_check_reason(c: dict, snapshot: dict) -> str:
    if (snapshot.get("final_state") == "dismissed" or c.get("dismissed")
            or (c.get("map_diag") or {}).get("dismissed")):
        return "dismissed before the evidence check"
    if (snapshot.get("final_state") == "technical_error"
            or (c.get("map_diag") or {}).get("call_failed")):
        return "technical error recorded"
    return "reason not recorded"


def _evidence_limits(entry: dict, comparisons: list, refs: dict, out: List[str]) -> None:
    out += ["## Evidence limits", ""]
    insufficient = [c for c in comparisons if _status(c) == "insufficient"]
    unchecked = [c for c in comparisons if _status(c) not in _EC_PHRASE]
    conflicts = [c for c in comparisons if _conflict(c)]
    if insufficient:
        out += [f"- **Inconclusive:** {len(insufficient)}/{len(comparisons)} comparisons "
                f"({', '.join(_ref(c, refs) for c in insufficient)})."]
    if unchecked:
        sources = "; ".join(f"{_ref(c, refs)} — {_missing_check_reason(c, _snapshot(entry, c))}"
                            for c in unchecked)
        out += [f"- **No evidence check:** {len(unchecked)}/{len(comparisons)} ({sources})."]
    if conflicts:
        out.append(f"- **Unresolved assessment conflicts:** {len(conflicts)}.")
        for c in conflicts:
            out.append(f"  - {_ref(c, refs)}: {vd.degree(c) or 'unspecified degree'} · {_status(c)} evidence.")
    if not insufficient and not unchecked and not conflicts:
        out.append("No inconclusive checks, missing checks, or degree/evidence conflicts recorded.")
    out.append("")


def _span(text: str, verified: bool, out: List[str]) -> None:
    if not str(text or "").strip():
        out += ["Not recorded.", ""]
    elif verified:
        out += ["> " + _quote(text), ""]
    else:
        out += ["Not confirmed verbatim:", "", "> " + _quote(str(text)), ""]


def _evidence_pairs(c: dict, out: List[str], snapshot: dict = None) -> None:
    """Keep every original index, including placeholders and non-supporting candidates.

    Show definitions BEFORE the checker reasons about 'Pair 1', 'Pair 2', etc.
    A candidate's rationale is not the checker's endorsement; label both separately.
    Repeated submission spans are cross-referenced to an EARLIER numbered pair.
    """
    pairs = c.get("evidence_pairs") or []
    check = c.get("evidence_check") or {}
    status = _status(c)
    supporting = {int(i) for i in check.get("supporting_pair_indices", []) or []
                  if str(i).isdigit()}
    out += ["#### Evidence pairs", "",
            "Each pair links a submission passage to a prior-work passage. "
            "The label records how the evidence check used it.", ""]
    seen_submission = {}
    for i, p in enumerate(pairs, 1):
        if status == "material":
            use = "supports overlap" if i in supporting else "not used to support overlap"
        elif status == "nonmaterial":
            use = "does not establish material overlap"
        elif status == "insufficient":
            use = "inconclusive candidate"
        else:
            use = "candidate; no evidence check recorded"
        out += [f"**Pair {i} — {use}**", ""]
        cq = str(p.get("claim_quote") or "").strip()
        key = (" ".join(cq.split()), bool(p.get("claim_quote_verified")))
        if cq and key in seen_submission:
            out += [f"**Submission:** same passage as Pair {seen_submission[key]}.", ""]
        else:
            out += ["**Submission passage**", ""]
            _span(cq, bool(p.get("claim_quote_verified")), out)
            if cq:
                seen_submission[key] = i
        out += ["**Prior-work passage**", ""]
        _span(p.get("paper_quote"), bool(p.get("paper_quote_verified")), out)
        if p.get("rationale"):
            out += ["**Proposed correspondence:** " + p["rationale"].strip(), ""]
    if not pairs:
        out += ["No evidence pairs recorded.", ""]
    out += ["#### Evidence-check assessment", "",
            "**Status:** " + _EC_PHRASE.get(status, "no evidence check recorded") + ".", ""]
    if status == "material":
        indices = ", ".join(str(i) for i in sorted(supporting)) or "none recorded"
        out += [f"**Supporting pairs:** {indices}.", ""]
        missing = sorted(supporting - set(range(1, len(pairs) + 1)))
        if missing:
            out += ["**Record inconsistency:** supporting indices without a stored pair: "
                    + ", ".join(map(str, missing)) + ".", ""]
    if check.get("reasoning"):
        out += [check["reasoning"].strip(), ""]
    unresolved = c.get("unresolved_deficit") or (snapshot or {}).get("unresolved_deficit")
    reason = c.get("unresolved_reason") or (snapshot or {}).get("unresolved_reason")
    if unresolved:
        out += ["**Unresolved question:** " + str(unresolved).strip(), ""]
    if reason:
        out += ["**Recorded stopping reason:** " + str(reason).replace("_", " ") + ".", ""]


def _comparison_detail(c: dict, entry: dict, refs: dict, pool: dict,
                       out: List[str]) -> None:
    snapshot = _snapshot(entry, c)
    pm = pool.get(_pid(c), {})
    out += ["---", "", f"### {_ref(c, refs)} — {c.get('title') or 'Untitled prior work'}", "",
            f"**Source used:** {_document_label(snapshot)}", ""]
    cite = _cite(c.get("authors") or pm.get("authors"), c.get("year") or pm.get("year"))
    if cite:
        out += [cite, ""]
    out += [f"**Assessment:** {_related_cell((vd.degree(c), _status(c)))}", "",
            "#### Comparison", ""]
    for label, key in (("Shared contribution", "what_is_shared"),
                       ("Reported difference", "submission_delta")):
        if c.get(key):
            out += [f"**{label}:** {c[key].strip()}", ""]
    note = c.get("assessment") or c.get("brief_note")
    if note:
        out += ["**Novelty argument:** " + note.strip(), ""]
    # Pair-referencing checker reasoning belongs below the pairs. The optional
    # prior-work narrative remains available, but cannot interrupt that sequence.
    _evidence_pairs(c, out, snapshot)
    if c.get("paper_realization"):
        out += ["#### Additional prior-work context", ""]
        _segments(c["paper_realization"], out)


def build(data_dir: str, submission_id: str, variant: str = "") -> str:
    sub = Path(data_dir) / submission_id
    suffix = f"_{variant}" if variant else ""
    a = _load(sub / f"{submission_id}_artifact_a{suffix}.json")
    if a is None:
        raise FileNotFoundError(f"{submission_id}_artifact_a{suffix}.json not found")
    b = _load(sub / f"{submission_id}_artifact_b{suffix}.json") or {}
    meta = _load(sub / f"{submission_id}.json") or {}
    claims_doc = _load(sub / f"{submission_id}_claims.json") or {"claims": []}
    ranked = _load(sub / "related_work_data" / "ranked_papers.json") or []
    # The live pool supplies bibliographic authors/year only, NEVER pinned versions.
    pool = {_pid(p): p for p in ranked}
    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    b_by = {v.get("claim_id"): v for v in b.get("per_claim", [])}
    order = [c["id"] for c in claims] or list(a_by)
    by_paper = {}
    for cid in order:
        entry = a_by.get(cid) or {}
        for c in entry.get("comparisons", []) or []:
            pid = _pid(c)
            pm = pool.get(pid, {})
            row = by_paper.setdefault(pid, {"title": c.get("title") or pid,
                "cite": _cite(c.get("authors") or pm.get("authors"), c.get("year") or pm.get("year")),
                "claims": {}, "versions": {}})
            row["claims"][cid] = (vd.degree(c), _status(c))
            row["versions"][cid] = _document_label(_snapshot(entry, c))
    paper_order = sorted(by_paper, key=lambda p: (by_paper[p]["title"].casefold(), p))
    refs = {pid: f"R{i}" for i, pid in enumerate(paper_order, 1)}
    out: List[str] = ["# Novelty Assessment", ""]
    title = meta.get("title") or claims_doc.get("title")
    if title:
        out += [f"**{title}**", ""]
    authors = _authors_from_tei(sub, submission_id)
    if authors:
        out += [f"Authors: {authors}", ""]
    if meta.get("publication_date"):
        out += [f"Publication date: {meta['publication_date']}", ""]
    if claims:
        out += ["## Extracted claims", ""]
        for i, c in enumerate(claims, 1):
            out += [f"### Claim {i}", "", (c.get("claim_text") or "").strip(), "",
                    "**Claim anchor in the submission**", ""]
            _span(c.get("evidence_quote"), bool(c.get("evidence_verified")), out)
    cols = [(cid, f"Claim {i + 1}") for i, cid in enumerate(order) if cid in a_by]
    if by_paper:
        out += ["## Related work examined", "",
                "Source IDs below identify the same paper throughout the report. "
                "Version dates come from the corresponding run record.", "",
                "| Source | Paper | Version used · date | " + " | ".join(label for _, label in cols) + " |",
                "|" + "---|" * (3 + len(cols))]
        for pid in paper_order:
            row = by_paper[pid]
            documents = list(dict.fromkeys(row["versions"].values()))
            version = documents[0] if len(documents) == 1 else "; ".join(
                f"{label}: {row['versions'][cid]}" for cid, label in cols if cid in row["versions"])
            name = " — ".join(x for x in (row["title"], row["cite"]) if x)
            cells = [refs[pid], name, version] + [_related_cell(row["claims"].get(cid)) for cid, _ in cols]
            out.append("| " + " | ".join(_cell(x) for x in cells) + " |")
        out += ["", _RELATED_LEGEND, ""]
    for i, cid in enumerate(order, 1):
        entry = a_by.get(cid)
        if entry is None:
            continue
        recorded = b_by.get(cid) or {}
        comparisons = entry.get("comparisons") or []
        out += ["---", "", f"# Claim {i} — Review", "",
                (entry.get("claim_text") or entry.get("claim_name") or "").strip(), "",
                "## Claim-level conclusion", "",
                "**Assessment:** " + _claim_assessment(comparisons, recorded.get("verdict"),
                                                      recorded.get("rationale")), ""]
        _comparison_summary(comparisons, refs, out)
        _evidence_limits(entry, comparisons, refs, out)
        out += ["**Coverage:** " + _coverage(comparisons), ""]
        # No claim_realization / 'What the submission does for this claim' section.
        # Keep overlaps plus explicit conflicts, so every unresolved conflict named
        # above is inspectable even if its proposed degree is superficial.
        details = [c for c in comparisons if vd.is_overlap(c) or _conflict(c)]
        details.sort(key=vd.sort_key)
        out += ["## Detailed comparisons", ""]
        if not details:
            out += ["No overlapping comparison or assessment/evidence conflict recorded.", ""]
        for c in details:
            _comparison_detail(c, entry, refs, pool, out)
    out += ["---", "", _QUOTE_NOTE]
    return "\n".join(out).rstrip() + "\n"


def quote_index(data_dir: str, submission_id: str, variant: str = "") -> dict:
    """Every VERIFIED quote this export blockquotes, keyed by its own normalised text.

    Built for the frontend's Summary tab: it renders `build()`'s own text verbatim (so
    the tab's content stays byte-identical to the export by construction) and needs a
    side channel to know, for a given rendered blockquote, which document it can be
    found in and what id to scroll the PDF viewer to. `_quote()` normalises with
    `' '.join(text.split())` before wrapping in curly quotes; this index normalises the
    SAME way, so a rendered blockquote's text (curly quotes stripped) is the exact key
    to look up here -- no fuzzy matching needed.

    Unverified spans are not indexed: `_span()` renders them as "Not confirmed verbatim"
    prose, not a clickable quote, and a search for text that is not actually in the PDF
    would silently fail there anyway.

    Returns {"submission": [{"id","text"}], "papers": {paper_id: {"title", "quotes":
    [{"id","text"}]}}, "refs": {paper_id: "R#"}} -- `refs` lets the frontend resolve the
    "### R7 — Title" headings it walks past back to a paper_id, the same numbering
    `build()` itself assigns.
    """
    sub = Path(data_dir) / submission_id
    suffix = f"_{variant}" if variant else ""
    a = _load(sub / f"{submission_id}_artifact_a{suffix}.json")
    if a is None:
        return {"submission": [], "papers": {}, "refs": {}}
    claims_doc = _load(sub / f"{submission_id}_claims.json") or {"claims": []}
    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]

    sub_list, sub_seen = [], {}

    def add_sub(text) -> None:
        key = " ".join(str(text or "").split())
        if not key or key in sub_seen:
            return
        item = {"id": f"sub#{len(sub_list)}", "text": key}
        sub_list.append(item)
        sub_seen[key] = item["id"]

    for c in claims:
        if c.get("evidence_verified"):
            add_sub(c.get("evidence_quote"))

    papers: dict = {}

    def add_paper(pid: str, title: str, text) -> None:
        key = " ".join(str(text or "").split())
        if not key:
            return
        p = papers.setdefault(pid, {"title": title, "quotes": [], "_seen": {}})
        if key in p["_seen"]:
            return
        item = {"id": f"pap:{pid}#{len(p['quotes'])}", "text": key}
        p["quotes"].append(item)
        p["_seen"][key] = item["id"]

    for entry in a.get("claims", []) or []:
        for c in entry.get("comparisons", []) or []:
            pid, title = _pid(c), c.get("title") or _pid(c)
            for seg in c.get("paper_realization") or []:
                if seg.get("kind") == "quote" and seg.get("verified"):
                    add_paper(pid, title, seg.get("content"))
            for p in c.get("evidence_pairs") or []:
                if p.get("claim_quote_verified"):
                    add_sub(p.get("claim_quote"))
                if p.get("paper_quote_verified"):
                    add_paper(pid, title, p.get("paper_quote"))

    for p in papers.values():
        p.pop("_seen", None)

    # The SAME paper_order/refs assignment build() uses, so "### R7 —" in the rendered
    # text resolves to the paper_id this index filed its quotes under.
    by_paper_titles = {pid: papers[pid]["title"] for pid in papers}
    for entry in a.get("claims", []) or []:
        for c in entry.get("comparisons", []) or []:
            by_paper_titles.setdefault(_pid(c), c.get("title") or _pid(c))
    paper_order = sorted(by_paper_titles, key=lambda p: (by_paper_titles[p].casefold(), p))
    refs = {pid: f"R{i}" for i, pid in enumerate(paper_order, 1)}

    return {"submission": sub_list, "papers": papers, "refs": refs}


def check_sources(data_dir: str, submission_id: str, variant: str = "") -> str:
    """Read-only diagnosis. Current manifest entries are NOT historical provenance.

    The report is deliberately not repaired from the latest manifest or an arbitrary
    log for the same paper. Such a log may belong to another review/run/version.
    """
    sub = Path(data_dir) / submission_id
    suffix = f"_{variant}" if variant else ""
    artifact_path = sub / f"{submission_id}_artifact_a{suffix}.json"
    a = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest_path = sub / "related_work_data" / "versions.json"
    manifest = _load(manifest_path) or {}
    if not isinstance(manifest, dict):
        manifest = {}
    lines = [f"Artifact: {artifact_path}",
             f"Current versions.json: {manifest_path.exists()} ({len(manifest)} entries)",
             "NOTE: current manifest values below are diagnostic only; not evidence of what an old run read.", ""]
    for entry in a.get("claims", []) or []:
        comps = entry.get("comparisons") or []
        log = entry.get("run_log")
        raw_prior = log.get("prior_work") if isinstance(log, dict) else None
        prior = raw_prior if isinstance(raw_prior, list) else []
        prior_by = {_pid(p): p for p in prior if isinstance(p, dict)}
        run_id = log.get("run_id") if isinstance(log, dict) else None
        lines += [f"Claim {entry.get('claim_id')}: {len(comps)} comparisons",
                  f"  run_log type: {type(log).__name__}; run_id: {run_id or 'not recorded'}",
                  f"  prior_work type: {type(raw_prior).__name__}; records: {len(prior)}"]
        matched = complete = current_complete = 0
        incomplete_examples = []
        for c in comps:
            pid = _pid(c)
            p = prior_by.get(pid)
            if p is not None:
                matched += 1
            # Mirror the export's supported format; malformed historical logs are
            # reported above rather than allowed to crash this diagnostic command.
            if isinstance(log, dict) and (raw_prior is None or isinstance(raw_prior, list)):
                snap = _snapshot(entry, c)
            else:
                snap = c
            version, day = snap.get("pinned_version"), snap.get("pinned_version_date")
            valid_day = bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", str(day or "")))
            ready = bool(version and valid_day)
            complete += int(ready)
            current = manifest.get(pid) or {}
            if not isinstance(current, dict):
                current = {}
            current_complete += int(bool(current.get("version") and current.get("version_date")))
            if not ready and len(incomplete_examples) < 9:
                incomplete_examples += [
                    f"    {pid} — {c.get('title') or ''}",
                    f"      run record matched: {p is not None}; pinned_version={version!r}; pinned_version_date={day!r}",
                    f"      current manifest (UNBOUND): version={current.get('version')!r}; version_date={current.get('version_date')!r}",
                ]
        lines += [f"  ID matches in embedded log: {matched}/{len(comps)}",
                  f"  Exportable version + date: {complete}/{len(comps)}",
                  f"  Version + date in current manifest: {current_complete}/{len(comps)}"]
        lines += incomplete_examples
        lines.append("")
    log_dir = sub / "run_logs"
    files = sorted(log_dir.glob("*.json")) if log_dir.is_dir() else []
    lines += [f"Standalone log files: {len(files)} in {log_dir}",
              "Standalone logs are not automatically attached: they must be linked to this exact run.",
              "No files changed. No downloads. No model calls."]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
