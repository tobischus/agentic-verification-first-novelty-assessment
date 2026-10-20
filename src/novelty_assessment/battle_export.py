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

import source_refs
import verdict as vd

# v3.2 reorders and links what v3.1 already printed; it adds no field and removes no
# recorded text. Changes: every assessment in the two overview tables is a link to the
# comparison it names (anchor scheme in _anchor); "Closest comparisons" drops the two
# prose columns that were repeated verbatim in each section below and names the source
# with its title; a comparison section leads with its metadata and assessment, then the
# prior paper's own realization (renamed "Prior work summary" and moved above the
# comparison), then the comparison, then the evidence pairs the check accepted, with the
# rest under "Pairs not used to support overlap". Any renderer keyed to v3.1's order
# needs updating; the two in this repository are.
#
# v3.3 opens the document with "## Novelty summary" when Artifact B carries one, before
# "## Extracted claims". It is rendered, never generated here -- paper_synthesis.py writes
# it -- and a summary whose claim results have since changed is printed with that stated.
#
# v4.0 reorders for reading, not for completeness -- the SAME recorded text, all of it.
# A reviewer reads the paper-level summary first and then one claim at a time, so each
# claim is now one top-level section ("# Claim N — Review") that opens with the facts its
# collapsed row shows (claim text, verdict, number of detailed comparisons, open points)
# and carries everything else underneath: the claim-level assessment, its submission
# passage (formerly under "## Extracted claims"), coverage and evidence limits, then its
# detailed comparisons. "Closest comparisons" is gone: every row it listed is a detailed
# comparison below, with the same source id and assessment. Each comparison shows its
# source, version, assessment, novelty argument and open points directly, then two blocks
# the renderers fold -- "Evidence check and limitations" and "Full comparison and quoted
# passages". Metadata and the related-work matrix move to their own sections at the end.
# Open points are derived from stored fields only (see _open_points); nothing is judged
# here. The renderers recognise this layout by its "# Metadata" section and keep
# rendering older frozen reports (the pilot's) by their old rules.
#
# v4.1 (requested by the study author after reading v4.0):
#   - "# How to read the assessments" (a legend of the overlap levels and evidence-check
#     statuses, worded after the definitions the comparisons were made under) and
#     "# Related work examined" now come right after the novelty summary, before the claims.
#   - the claim row names the overlap levels of its detailed comparisons ("13 (partial
#     overlap)") and no longer carries an "Open points" count; each comparison still
#     states its own open points.
#   - "## Coverage and limitations" is dropped. Its counts and lists are the claim's
#     column of the related-work table, now directly above; the per-comparison stopping
#     reasons and unresolved questions stay in each comparison's evidence check.
#   - in a comparison, "Full comparison and quoted passages" comes before "Evidence check
#     and limitations", so the pairs the check refers to by number are read first.
#   - the labels "Main novelty concern", "Remaining contribution" and the claim-level
#     "Assessment" stand on their own line; the text follows as its own paragraph.
#
# v4.2: authors and publication date stand under the title; the "# Metadata" section is
# gone. The renderers recognise v4.x by "# How to read the assessments" (or "# Metadata").
#
# v4.3: the claim-level assessment carries a claim-specific explanation of its verdict
# (claim_assessment.py, stored in Artifact B as per_claim[i].claim_assessment), between the
# verdict line and the general sentence on what the verdict means; a stored explanation
# whose comparisons have since changed is printed marked out of date.
#
# v4.4: the general sentence on what a verdict means (formerly _ASSESSMENT_GLOSS) and the
# per-claim "## Submission passages" section (the claim's single anchor quote) are removed.
# quote_index() gives each claim's anchor as "claim_anchors"; the renderers make the claim
# text itself the link to that passage in the submission PDF.
EXPORT_LAYOUT_VERSION = "reviewer-v4.4"

_LQ, _RQ = "“", "”"

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

def _claim_assessment(comparisons: list, recorded_verdict: str, recorded_rationale: str,
                      stored: dict = None, stale: bool = False) -> List[str]:
    """The claim-level assessment as paragraphs: the verdict on the label's own line, then
    why this claim got it (claim_assessment.py, stored in Artifact B). Without a stored
    assessment: the older recorded rationale, if any."""
    verdict, derived = _claim_verdict(comparisons, recorded_verdict)
    paragraphs = [f"**Assessment:** {vd.verdict_label(verdict)}."]
    text = str((stored or {}).get("text") or "").strip()
    if text and not derived:
        if stale:
            paragraphs.append("**Out of date:** the comparisons below have changed since this "
                              "assessment was written. It has not been regenerated.")
        paragraphs.append(text)
    elif recorded_rationale and not derived:
        paragraphs.append(recorded_rationale.strip())
    elif derived:
        paragraphs.append(
            "(No claim-level synthesis was recorded for this run; the verdict above is "
            "derived from refutation_status across the comparisons below.)"
        )
    return [p for p in paragraphs if p]


def _degree_counts(details: list) -> str:
    """"13 (partial overlap)" or "13 (12 partial overlap, 1 superficial)": the claim
    row's count of detailed comparisons with the overlap levels behind it, strongest
    first, levels that do not occur left out."""
    counts: dict = {}
    for c in details:
        d = vd.degree(c) or "not compared"
        counts[d] = counts.get(d, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: vd.degree_rank(kv[0]))
    label = lambda d: vd.overlap_label(d) or d
    if len(ordered) == 1:
        return f"{len(details)} ({label(ordered[0][0])})"
    return f"{len(details)} (" + ", ".join(f"{n} {label(d)}" for d, n in ordered) + ")"

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


# The same predicate the paper-level synthesis uses to find decision-relevant conflicts.
# It lives in verdict.py because it IS a rule about what a comparison means, and two
# modules acting on it had to be unable to drift apart.
_conflict = vd.conflicts


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
    """Degree and evidence status in one cell -- plus, when they part company, the fact
    that the check did not confirm the degree. Without that third piece "partial ·
    material evidence" reads as an established partial overlap even where the check said
    the opposite."""
    if entry is None:
        return "not assessed"
    degree, status = entry[0], entry[1]
    confirmed = entry[2] if len(entry) > 2 else None
    cell = (f"{vd.overlap_label(degree) or degree or 'not compared'} · "
            + _EC_PHRASE.get(status, "no evidence check"))
    # Only where a degree was actually proposed. `none`/`superficial` propose no overlap,
    # so the check leaves proposed_degree_supported null for them and there is nothing to
    # confirm -- annotating those said "not confirmed" about a claim nobody made.
    if (status == "material" and confirmed is False
            and (degree or "").lower() in vd.OVERLAP_DEGREES):
        cell += "; proposed degree not confirmed"
    return cell


def _has_detail(c: dict) -> bool:
    """Whether this comparison gets its own section under "Detailed comparisons".

    Mirrors build()'s own filter exactly. An assessment cell is only ever linked when
    this is true -- a link to a section that was never written is worse than plain text,
    and silently linking every cell would produce dead jumps for the majority of them
    (most comparisons are superficial and carry no detail section).
    """
    return bool(vd.is_overlap(c) or _conflict(c))


def _anchor(claim_index: int, ref: str) -> str:
    """The jump target for one (claim, source) detail section.

    Deliberately NOT written into the text as an HTML anchor: this file's output is also
    the plain-text artifact used in the system comparison, and embedding `<a id=…>` in it
    would put markup into the thing being compared. The two renderers
    (frontend/src/components/ReviewSummary.jsx and
    final_evaluation/dashboard/.../ReportRenderer.jsx) derive the SAME id from the
    "# Claim N — Review" heading they last passed plus the "### R# — …" heading they are
    rendering, so the link resolves in the UI and degrades to readable label text
    anywhere else.
    """
    return f"cmp-{claim_index}-{ref}"


def _linked(label: str, claim_index: int, ref: str, linkable: bool) -> str:
    return f"[{label}](#{_anchor(claim_index, ref)})" if linkable else label


# The overlap levels are explained in the wording of the definitions the comparisons were
# made under (agent/claim_agent.py, the close-comparison prompt), shortened, not changed.
# The labels are the ones the report prints (verdict.DEGREE_LABEL for overlaps).
_LEGEND = [
    "# How to read the assessments", "",
    "Each comparison carries two separate assessments: the overlap level proposed by the "
    "comparison, and the evidence check of the quoted passages.", "",
    "**Overlap level**", "",
    "- **same contribution:** the prior work already delivers essentially the claimed "
    "contribution.",
    "- **substantial overlap:** the prior work already delivers the central contribution or "
    "most of it; what remains is mainly a different design, scope, data or extension.",
    "- **partial overlap:** the prior work delivers a meaningful part of the claimed "
    "contribution; the submission keeps a distinct central contribution.",
    "- **superficial:** a real relationship -- topic, tools, evaluation setting or similar -- "
    "but no substantive part of the contribution is shared.",
    "- **none:** the prior work does not deliver any meaningful part of the claimed "
    "contribution.", "",
    "**Evidence check**", "",
    "- **material evidence:** the passages establish a meaningful shared element. Whether "
    "they also support the proposed overlap level is stated separately (\"proposed degree "
    "not confirmed\" in the table below, an open point in the comparison).",
    "- **nonmaterial:** the examined passages do not establish a meaningful shared element.",
    "- **insufficient evidence:** the check was inconclusive.",
    "- **no evidence check:** none was recorded.", "",
    "Missing support does not establish that there is no overlap.", "",
]

# Open points, one sentence each, keyed by the stored field they come from. Nothing here
# judges a comparison: each is a restatement of a recorded status, so the same record
# always yields the same sentences, for agent and linear alike.
_HINT = {
    "insufficient": "The available evidence did not resolve this comparison.",
    "nocheck": "No evidence check was recorded for this comparison.",
    "notsupported": "The evidence check does not support this overlap level.",
    "conflict": "The comparison and evidence check disagree.",
}


def _open_points(c: dict) -> list:
    """Which open-point sentences apply to one comparison, from stored fields only.

    `proposed_degree_supported` is read as a three-valued field: False is a recorded
    rejection of the proposed level, None means the check was never asked (none /
    superficial proposals, or no check at all) and says nothing. The rejection is only
    named where it is not already implied by another point -- for an inconclusive check,
    or for a nonmaterial one that contradicts an overlap degree (a conflict), the
    rejection is what those already say, and repeating it would count one fact twice.
    """
    status = _status(c)
    keys = []
    if status not in _EC_PHRASE:
        keys.append("nocheck")
    elif status == "insufficient":
        keys.append("insufficient")
    if _conflict(c):
        keys.append("conflict")
    elif (status == "material" and vd.degree(c) in vd.OVERLAP_DEGREES
          and (c.get("evidence_check") or {}).get("proposed_degree_supported") is False):
        keys.append("notsupported")
    return keys


def _missing_check_reason(c: dict, snapshot: dict) -> str:
    if (snapshot.get("final_state") == "dismissed" or c.get("dismissed")
            or (c.get("map_diag") or {}).get("dismissed")):
        return "dismissed before the evidence check"
    if (snapshot.get("final_state") == "technical_error"
            or (c.get("map_diag") or {}).get("call_failed")):
        return "technical error recorded"
    return "reason not recorded"


def _span(text: str, verified: bool, out: List[str]) -> None:
    if not str(text or "").strip():
        out += ["Not recorded.", ""]
    elif verified:
        out += ["> " + _quote(text), ""]
    else:
        out += ["Not confirmed verbatim:", "", "> " + _quote(str(text)), ""]


def _pair_use_label(status: str, index: int, supporting: set) -> str:
    if status == "material":
        return "supports overlap" if index in supporting else "not used to support overlap"
    if status == "nonmaterial":
        return "does not establish material overlap"
    if status == "insufficient":
        return "inconclusive candidate"
    return "candidate; no evidence check recorded"


def _evidence_check_block(c: dict, out: List[str], snapshot: dict = None) -> None:
    """Everything the evidence check recorded about one comparison, in one place.

    Folded by the renderers: it is where a reader goes to find out WHY a comparison carries
    the open points shown above it, not what they read first. Nothing is shortened. Both
    open questions are printed -- the check's own `unresolved_question` and the run's
    `unresolved_deficit` -- because they differ in a minority of comparisons and the first
    was never printed at all before v4.0; identical ones are printed once.
    """
    snapshot = snapshot or {}
    pairs = c.get("evidence_pairs") or []
    check = c.get("evidence_check") or {}
    status = _status(c)
    supporting = {int(i) for i in check.get("supporting_pair_indices", []) or []
                  if str(i).isdigit()}
    out += ["**Status:** " + _EC_PHRASE.get(status, "no evidence check recorded") + ".", ""]
    if status == "material":
        indices = ", ".join(str(i) for i in sorted(supporting)) or "none recorded"
        out += [f"**Supporting pairs:** {indices}.", ""]
        missing = sorted(supporting - set(range(1, len(pairs) + 1)))
        if missing:
            out += ["**Record inconsistency:** supporting indices without a stored pair: "
                    + ", ".join(map(str, missing)) + ".", ""]
    elif status in ("nonmaterial", "insufficient") and pairs:
        out += ["**Supporting pairs:** none.", ""]
    pds = check.get("proposed_degree_supported")
    if pds is not None:
        out += [f"**Proposed overlap level supported:** {'yes' if pds else 'no'}.", ""]
    if check.get("reasoning"):
        out += [check["reasoning"].strip(), ""]
    questions = []
    for q in (check.get("unresolved_question"),
              c.get("unresolved_deficit") or snapshot.get("unresolved_deficit")):
        q = " ".join(str(q or "").split())
        if q and q not in questions:
            questions.append(q)
    for q in questions:
        out += ["**Unresolved question:** " + q, ""]
    reason = c.get("unresolved_reason") or snapshot.get("unresolved_reason")
    if reason:
        out += ["**Recorded stopping reason:** " + str(reason).replace("_", " ") + ".", ""]
    if status not in _EC_PHRASE:
        out += ["**Why no check was recorded:** " + _missing_check_reason(c, snapshot) + ".", ""]


def _evidence_pair_list(c: dict, out: List[str]) -> None:
    """Every pair, with its original index, its label and both quotes.

    Pairs the evidence check relied on come first; the others keep their index and label
    under their own heading. Nothing is dropped and nothing renumbered -- the check's
    reasoning refers to these numbers. A repeated submission span is cross-referenced to
    the earliest pair that carries it, decided before either group is written so the
    reference is the same whichever group the referring pair ends up in.
    """
    pairs = c.get("evidence_pairs") or []
    check = c.get("evidence_check") or {}
    status = _status(c)
    supporting = {int(i) for i in check.get("supporting_pair_indices", []) or []
                  if str(i).isdigit()}

    first_seen: dict = {}
    for i, p in enumerate(pairs, 1):
        cq = " ".join(str(p.get("claim_quote") or "").strip().split())
        if not cq:
            continue
        first_seen.setdefault((cq, bool(p.get("claim_quote_verified"))), i)

    def render(index: int, p: dict) -> None:
        # extend, not += : `out +=` inside this closure would rebind the enclosing
        # function's parameter name and raise before writing anything.
        out.extend([f"**Pair {index} — {_pair_use_label(status, index, supporting)}**", ""])
        cq = str(p.get("claim_quote") or "").strip()
        key = (" ".join(cq.split()), bool(p.get("claim_quote_verified")))
        if cq and first_seen.get(key, index) != index:
            out.extend([f"**Submission:** same passage as Pair {first_seen[key]}.", ""])
        else:
            out.extend(["**Submission passage**", ""])
            _span(cq, bool(p.get("claim_quote_verified")), out)
        out.extend(["**Prior-work passage**", ""])
        _span(p.get("paper_quote"), bool(p.get("paper_quote_verified")), out)
        if p.get("rationale"):
            out.extend(["**Proposed correspondence:** " + p["rationale"].strip(), ""])

    used = [(i, p) for i, p in enumerate(pairs, 1)
            if status == "material" and i in supporting]
    unused = [(i, p) for i, p in enumerate(pairs, 1)
              if not (status == "material" and i in supporting)]

    out += ["##### Evidence pairs", "",
            "Each pair links a submission passage to a prior-work passage. "
            "The label records how the evidence check used it.", ""]
    for i, p in used:
        render(i, p)
    if not pairs:
        out += ["No evidence pairs recorded.", ""]
    elif not used:
        out += [f"No pair was used to support overlap; all {len(unused)} recorded "
                "candidate(s) are listed below, each with its own label.", ""]
    if unused:
        out += [f"##### Pairs not used to support overlap ({len(unused)})", ""]
        for i, p in unused:
            render(i, p)


def _comparison_detail(c: dict, entry: dict, refs: dict, pool: dict,
                       out: List[str]) -> None:
    """One comparison: what is read first, then two blocks the renderers fold.

    Shown directly: source id and full title, the version read and its date, the
    assessment, the full novelty argument, and the open points. The assessment line
    carries the degree and the check's status only -- a rejected overlap level is stated
    once, as an open point directly below it, rather than twice. Then "Full comparison and
    quoted passages" (shared contribution, reported difference, prior-work context and
    every pair) and "Evidence check and limitations" (the check's full record, which
    refers to those pairs by number).
    """
    snapshot = _snapshot(entry, c)
    pm = pool.get(_pid(c), {})
    pairs = c.get("evidence_pairs") or []
    out += ["---", "", f"### {_ref(c, refs)} — {c.get('title') or 'Untitled prior work'}", "",
            f"**Source used:** {_document_label(snapshot)}", ""]
    cite = _cite(c.get("authors") or pm.get("authors"), c.get("year") or pm.get("year"))
    if cite:
        out += [cite, ""]
    out += [f"**Assessment:** {_related_cell((vd.degree(c), _status(c)))}", ""]
    note = c.get("assessment") or c.get("brief_note")
    if note:
        out += ["**Novelty argument:** " + note.strip(), ""]
    for k in _open_points(c):
        out += ["**Open point:** " + _HINT[k], ""]

    # The pairs first: the check below refers to them by number ("Pair 2 does not ...").
    noun = "pair" if len(pairs) == 1 else "pairs"
    out += [f"#### Full comparison and quoted passages · {len(pairs)} {noun}", ""]
    for label, key in (("Shared contribution", "what_is_shared"),
                       ("Reported difference", "submission_delta")):
        if c.get(key):
            out += [f"**{label}:** {c[key].strip()}", ""]
    if c.get("paper_realization"):
        out += ["**Prior-work context**", ""]
        _segments(c["paper_realization"], out)
    _evidence_pair_list(c, out)

    out += ["#### Evidence check and limitations", ""]
    _evidence_check_block(c, out, snapshot)


def _paper_summary(b: dict, a: dict, order: list, claims: list, refs: dict,
                   out: List[str]) -> None:
    """The paper-level summary, rendered — never generated here.

    paper_synthesis.py produces it once from the finished claim reviews and stores it in
    Artifact B; this file only prints what is already on disk, because its output is the
    artifact the system comparison uses and must stay free of model calls.

    If the claim results have changed since the summary was written, it is printed with
    that fact stated. Dropping it silently would hide that a summary exists, and printing
    it silently would let a confident paragraph stand over a report that no longer says
    what it summarises.
    """
    summary = (b or {}).get("paper_summary") or {}
    concern = str(summary.get("main_novelty_concern") or "").strip()
    remaining = str(summary.get("remaining_contribution") or "").strip()
    if not concern and not remaining:
        return
    out += ["## Novelty summary", ""]
    try:
        import paper_synthesis
        names = {c["id"]: c.get("claim_name") or c.get("name") or ""
                 for c in claims if c.get("id")}
        # Exactly the order paper_synthesis derived the summary from -- claims without an
        # Artifact A entry are dropped there too. Passing them here would change the
        # findings text and so the fingerprint, and every render would cry "out of date".
        a_ids = {e.get("claim_id") for e in (a or {}).get("claims", []) or []}
        findings = paper_synthesis.build_findings(
            a, b, [cid for cid in order if cid in a_ids], names, refs)
        if paper_synthesis.is_stale(summary, findings):
            out += ["**Out of date:** the claim results below have changed since this "
                    "summary was written. It has not been regenerated.", ""]
    except Exception:
        # A missing or broken synthesis module must not cost the reader the summary that
        # is sitting right there; it only costs the staleness check.
        pass
    if concern:
        out += ["**Main novelty concern:**", "", concern, ""]
    if remaining:
        out += ["**Remaining contribution:**", "", remaining, ""]


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
                "claims": {}, "detail": {}, "versions": {}})
            row["claims"][cid] = (vd.degree(c), _status(c), vd.degree_confirmed(c))
            row["detail"][cid] = _has_detail(c)
            row["versions"][cid] = _document_label(_snapshot(entry, c))
    # Shared with the paper-level synthesis, so a summary that cites R7 and the table
    # that lists R7 always mean the same paper.
    titles = {pid: row["title"] for pid, row in by_paper.items()}
    paper_order = source_refs.order_from_titles(titles)
    refs = source_refs.assign_from_titles(titles)
    out: List[str] = ["# Novelty Assessment", ""]
    title = meta.get("title") or claims_doc.get("title")
    if title:
        out += [f"**{title}**", ""]
    # Authors and date directly under the title (v4.2; formerly a folded "# Metadata").
    authors = _authors_from_tei(sub, submission_id)
    if authors:
        out += [f"**Authors:** {authors}", ""]
    if meta.get("publication_date"):
        out += [f"**Publication date:** {meta['publication_date']}", ""]
    _paper_summary(b, a, order, claims, refs, out)
    out += ["---", ""] + _LEGEND

    # 1-based claim numbers, matching the "# Claim N — Review" headings and the anchors.
    cols = [(cid, f"Claim {i + 1}", i + 1) for i, cid in enumerate(order) if cid in a_by]
    if by_paper:
        out += ["---", "", "# Related work examined", "",
                "| Source | Paper | Version used · date | " + " | ".join(label for _, label, _n in cols) + " |",
                "|" + "---|" * (3 + len(cols))]
        for pid in paper_order:
            row = by_paper[pid]
            documents = list(dict.fromkeys(row["versions"].values()))
            version = documents[0] if len(documents) == 1 else "; ".join(
                f"{label}: {row['versions'][cid]}" for cid, label, _n in cols if cid in row["versions"])
            name = " — ".join(x for x in (row["title"], row["cite"]) if x)
            # Each assessment links to that source's section for THAT claim, where one
            # exists (see _has_detail): the table says what was concluded, the link says
            # on what -- without it a reader has to scroll for the matching "### R# — …".
            assessments = [_linked(_related_cell(row["claims"].get(cid)), n, refs[pid],
                                   bool(row["detail"].get(cid)))
                           for cid, _label, n in cols]
            cells = [refs[pid], name, version] + assessments
            out.append("| " + " | ".join(_cell(x) for x in cells) + " |")
        out += [""]

    claims_by = {c["id"]: c for c in claims if c.get("id")}
    for i, cid in enumerate(order, 1):
        entry = a_by.get(cid)
        doc_claim = claims_by.get(cid) or {}
        claim_text = ((entry or {}).get("claim_text") or doc_claim.get("claim_text")
                      or (entry or {}).get("claim_name") or "").strip()
        out += ["---", "", f"# Claim {i} — Review", "", claim_text, ""]
        if entry is None:
            # A claim with no review on record stays visible; it is not dropped, and it is
            # not presented as assessed either.
            out += ["**Detailed comparisons:** none recorded", "",
                    "## Claim-level assessment", "", "No review is recorded for this claim.", ""]
            continue
        recorded = b_by.get(cid) or {}
        comparisons = entry.get("comparisons") or []
        details = [c for c in comparisons if _has_detail(c)]
        details.sort(key=vd.sort_key)
        verdict, _derived = _claim_verdict(comparisons, recorded.get("verdict"))

        # What the claim's collapsed row shows. The full assessment follows below; the
        # verdict is repeated here only so it can be read without opening the claim.
        out += [f"**Verdict:** {vd.verdict_label(verdict)}.", ""]
        out += [f"**Detailed comparisons:** "
                f"{_degree_counts(details) if details else 'none recorded'}", ""]

        out += ["## Claim-level assessment", ""]
        stored = recorded.get("claim_assessment") or {}
        stale = False
        if stored:
            try:
                import claim_assessment
                stale = claim_assessment.is_stale(stored, claim_assessment.build_claim_findings(
                    entry, i, claim_text, recorded.get("verdict") or verdict, refs))
            except Exception:
                # As for the novelty summary: a broken module costs the staleness check,
                # never the text that is sitting right there.
                pass
        for paragraph in _claim_assessment(comparisons, recorded.get("verdict"),
                                           recorded.get("rationale"), stored, stale):
            out += [paragraph, ""]
        out += ["## Detailed comparisons", ""]
        if not details:
            out += ["No overlapping comparison or assessment/evidence conflict recorded. "
                    "Every processed comparison for this claim is listed under \"Related "
                    "work examined\".", ""]
        for c in details:
            _comparison_detail(c, entry, refs, pool, out)

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

    # The claim anchors are no longer printed (v4.4); the renderers link each claim's text
    # to its anchor in the submission PDF instead. Claim numbers as build() numbers them.
    claim_anchors = {}
    for n, c in enumerate(claims, 1):
        if c.get("evidence_verified") and str(c.get("evidence_verified")) != "False":
            add_sub(c.get("evidence_quote"))
            key = " ".join(str(c.get("evidence_quote") or "").split())
            if key in sub_seen:
                claim_anchors[str(n)] = {"id": sub_seen[key], "text": key}

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
    paper_order = source_refs.order_from_titles(by_paper_titles)
    refs = source_refs.assign_from_titles(by_paper_titles)

    return {"submission": sub_list, "papers": papers, "refs": refs,
            "claim_anchors": claim_anchors}


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
