"""Deterministic Markdown report built from the stored artifacts."""

import json
import re
from pathlib import Path
from typing import List

import source_refs
import verdict as vd


_LQ, _RQ = "“", "”"


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _authors_from_tei(sub: Path, sid: str) -> str:
    """Author list of the submission, read from the GROBID header."""
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
    """Verified spans in quotation marks, the system's prose plain, and rejected quotes labelled as such."""
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
    "material": "material evidence",
    "nonmaterial": "nonmaterial",
    "insufficient": "insufficient evidence",
}


def _claim_verdict(comparisons: list, recorded: str):
    """(verdict, is_derived). Artifact B's verdict, else derived from the comparisons."""
    if recorded:
        return recorded, False
    derived = "challenged" if any(vd.challenges(c) for c in comparisons or []) else "not_challenged"
    return derived, True


def _claim_assessment(
    comparisons: list,
    recorded_verdict: str,
    recorded_rationale: str,
    stored: dict = None,
    stale: bool = False,
) -> List[str]:
    """The claim explanation as paragraphs: the verdict line, then the stored explanation."""
    verdict, derived = _claim_verdict(comparisons, recorded_verdict)
    paragraphs = [f"**Assessment:** {vd.verdict_label(verdict)}."]
    text = str((stored or {}).get("text") or "").strip()
    if text and not derived:
        if stale:
            paragraphs.append(
                "**Out of date:** the comparisons below have changed since this "
                "assessment was written. It has not been regenerated."
            )
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
    """Count of detailed comparisons with their overlap levels, strongest first, e.g. 13 (12 partial overlap, 1 superficial)."""
    counts: dict = {}
    for c in details:
        d = vd.degree(c) or "not compared"
        counts[d] = counts.get(d, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: vd.degree_rank(kv[0]))

    def label(d):
        return vd.overlap_label(d) or d

    if len(ordered) == 1:
        return f"{len(details)} ({label(ordered[0][0])})"
    return f"{len(details)} (" + ", ".join(f"{n} {label(d)}" for d, n in ordered) + ")"


def _cite(authors, year=None) -> str:
    if isinstance(authors, list):
        authors = ", ".join(a.get("name", "") if isinstance(a, dict) else str(a) for a in authors)
    names = [n.strip() for n in str(authors or "").split(",") if n.strip()]
    name = (names[0].split()[-1] + " et al." if len(names) > 1 else names[0]) if names else ""
    return " · ".join(str(x) for x in (name, year) if x)


def _status(c: dict) -> str:
    return str((c.get("evidence_check") or {}).get("status") or "").strip().lower()


_conflict = vd.conflicts


def _cell(text: str) -> str:
    """Keep prose in one Markdown table cell without turning source pipes into columns."""
    return " ".join(str(text or "").split()).replace("|", "&#124;")


def _pid(c: dict) -> str:
    return str(c.get("paper_id") or c.get("title") or "unidentified source")


def _ref(c: dict, refs: dict) -> str:
    return refs.get(_pid(c), c.get("title") or "Unidentified source")


def _snapshot(entry: dict, c: dict) -> dict:
    """This claim's embedded run record, never the current manifest."""
    result = {
        k: c[k]
        for k in (
            "pinned_version",
            "pinned_version_date",
            "pinned_url",
            "version_status",
            "final_state",
            "unresolved_reason",
            "unresolved_deficit",
        )
        if c.get(k) is not None
    }
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
    match = re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", date)
    day = date[:10] if match else "exact date not recorded"
    label = f"{version or 'version not recorded'} · {day}"
    url = str(snapshot.get("pinned_url") or "").strip()
    if url.startswith(("https://", "http://")) and version:
        label = f"[{label}](<{url}>)"
    return label


def _related_cell(entry) -> str:
    """Degree and evidence status in one cell, noting when the check did not confirm the degree."""
    if entry is None:
        return "not assessed"
    degree, status = entry[0], entry[1]
    confirmed = entry[2] if len(entry) > 2 else None
    cell = f"{vd.overlap_label(degree) or degree or 'not compared'} · " + _EC_PHRASE.get(
        status, "no evidence check"
    )
    if status == "material" and confirmed is False and (degree or "").lower() in vd.OVERLAP_DEGREES:
        cell += "; proposed degree not confirmed"
    return cell


def _has_detail(c: dict) -> bool:
    """Whether this comparison gets its own section under "Detailed comparisons"."""
    return bool(vd.is_overlap(c) or _conflict(c))


def _anchor(claim_index: int, ref: str) -> str:
    """The jump target for one (claim, source) detail section."""
    return f"cmp-{claim_index}-{ref}"


def _linked(label: str, claim_index: int, ref: str, linkable: bool) -> str:
    return f"[{label}](#{_anchor(claim_index, ref)})" if linkable else label


_LEGEND = [
    "# How to read the assessments",
    "",
    "Each comparison carries two separate assessments: the overlap level proposed by the "
    "comparison, and the evidence check of the quoted passages.",
    "",
    "**Overlap level**",
    "",
    "- **same contribution:** the prior work already delivers essentially the claimed "
    "contribution.",
    "- **substantial overlap:** the prior work already delivers the central contribution or "
    "most of it; what remains is mainly a different design, scope, data or extension.",
    "- **partial overlap:** the prior work delivers a meaningful part of the claimed "
    "contribution; the submission keeps a distinct central contribution.",
    "- **superficial:** a real relationship -- topic, tools, evaluation setting or similar -- "
    "but no substantive part of the contribution is shared.",
    "- **none:** the prior work does not deliver any meaningful part of the claimed contribution.",
    "",
    "**Evidence check**",
    "",
    "- **material evidence:** the passages establish a meaningful shared element. Whether "
    'they also support the proposed overlap level is stated separately ("proposed degree '
    'not confirmed" in the table below, an open point in the comparison).',
    "- **nonmaterial:** the examined passages do not establish a meaningful shared element.",
    "- **insufficient evidence:** the check was inconclusive.",
    "- **no evidence check:** none was recorded.",
    "",
    "Missing support does not establish that there is no overlap.",
    "",
]

_HINT = {
    "insufficient": "The available evidence did not resolve this comparison.",
    "nocheck": "No evidence check was recorded for this comparison.",
    "notsupported": "The evidence check does not support this overlap level.",
    "conflict": "The comparison and evidence check disagree.",
}


def _open_points(c: dict) -> list:
    """Which open-point sentences apply to one comparison, from stored fields only."""
    status = _status(c)
    keys = []
    if status not in _EC_PHRASE:
        keys.append("nocheck")
    elif status == "insufficient":
        keys.append("insufficient")
    if _conflict(c):
        keys.append("conflict")
    elif (
        status == "material"
        and vd.degree(c) in vd.OVERLAP_DEGREES
        and (c.get("evidence_check") or {}).get("proposed_degree_supported") is False
    ):
        keys.append("notsupported")
    return keys


def _missing_check_reason(c: dict, snapshot: dict) -> str:
    if (
        snapshot.get("final_state") == "dismissed"
        or c.get("dismissed")
        or (c.get("map_diag") or {}).get("dismissed")
    ):
        return "dismissed before the evidence check"
    if snapshot.get("final_state") == "technical_error" or (c.get("map_diag") or {}).get(
        "call_failed"
    ):
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
    """Everything the evidence check recorded about one comparison, in one place."""
    snapshot = snapshot or {}
    pairs = c.get("evidence_pairs") or []
    check = c.get("evidence_check") or {}
    status = _status(c)
    supporting = {
        int(i) for i in check.get("supporting_pair_indices", []) or [] if str(i).isdigit()
    }
    out += ["**Status:** " + _EC_PHRASE.get(status, "no evidence check recorded") + ".", ""]
    if status == "material":
        indices = ", ".join(str(i) for i in sorted(supporting)) or "none recorded"
        out += [f"**Supporting pairs:** {indices}.", ""]
        missing = sorted(supporting - set(range(1, len(pairs) + 1)))
        if missing:
            out += [
                "**Record inconsistency:** supporting indices without a stored pair: "
                + ", ".join(map(str, missing))
                + ".",
                "",
            ]
    elif status in ("nonmaterial", "insufficient") and pairs:
        out += ["**Supporting pairs:** none.", ""]
    pds = check.get("proposed_degree_supported")
    if pds is not None:
        out += [f"**Proposed overlap level supported:** {'yes' if pds else 'no'}.", ""]
    if check.get("reasoning"):
        out += [check["reasoning"].strip(), ""]
    questions = []
    for q in (
        check.get("unresolved_question"),
        c.get("unresolved_deficit") or snapshot.get("unresolved_deficit"),
    ):
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
    """Every pair, with its original index, its label and both quotes."""
    pairs = c.get("evidence_pairs") or []
    check = c.get("evidence_check") or {}
    status = _status(c)
    supporting = {
        int(i) for i in check.get("supporting_pair_indices", []) or [] if str(i).isdigit()
    }

    first_seen: dict = {}
    for i, p in enumerate(pairs, 1):
        cq = " ".join(str(p.get("claim_quote") or "").strip().split())
        if not cq:
            continue
        first_seen.setdefault((cq, bool(p.get("claim_quote_verified"))), i)

    def render(index: int, p: dict) -> None:
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

    used = [(i, p) for i, p in enumerate(pairs, 1) if status == "material" and i in supporting]
    unused = [
        (i, p) for i, p in enumerate(pairs, 1) if not (status == "material" and i in supporting)
    ]

    out += [
        "##### Evidence pairs",
        "",
        "Each pair links a submission passage to a prior-work passage. "
        "The label records how the evidence check used it.",
        "",
    ]
    for i, p in used:
        render(i, p)
    if not pairs:
        out += ["No evidence pairs recorded.", ""]
    elif not used:
        out += [
            f"No pair was used to support overlap; all {len(unused)} recorded "
            "candidate(s) are listed below, each with its own label.",
            "",
        ]
    if unused:
        out += [f"##### Pairs not used to support overlap ({len(unused)})", ""]
        for i, p in unused:
            render(i, p)


def _comparison_detail(c: dict, entry: dict, refs: dict, pool: dict, out: List[str]) -> None:
    """One comparison: what is read first, then two blocks the renderers fold."""
    snapshot = _snapshot(entry, c)
    pm = pool.get(_pid(c), {})
    pairs = c.get("evidence_pairs") or []
    out += [
        "---",
        "",
        f"### {_ref(c, refs)} — {c.get('title') or 'Untitled prior work'}",
        "",
        f"**Source used:** {_document_label(snapshot)}",
        "",
    ]
    cite = _cite(c.get("authors") or pm.get("authors"), c.get("year") or pm.get("year"))
    if cite:
        out += [cite, ""]
    out += [f"**Assessment:** {_related_cell((vd.degree(c), _status(c)))}", ""]
    note = c.get("assessment") or c.get("brief_note")
    if note:
        out += ["**Novelty argument:** " + note.strip(), ""]
    for k in _open_points(c):
        out += ["**Open point:** " + _HINT[k], ""]

    noun = "pair" if len(pairs) == 1 else "pairs"
    out += [f"#### Full comparison and quoted passages · {len(pairs)} {noun}", ""]
    for label, key in (
        ("Shared contribution", "what_is_shared"),
        ("Reported difference", "submission_delta"),
    ):
        if c.get(key):
            out += [f"**{label}:** {c[key].strip()}", ""]
    if c.get("paper_realization"):
        out += ["**Prior-work context**", ""]
        _segments(c["paper_realization"], out)
    _evidence_pair_list(c, out)

    out += ["#### Evidence check and limitations", ""]
    _evidence_check_block(c, out, snapshot)


def _paper_summary(b: dict, a: dict, order: list, claims: list, refs: dict, out: List[str]) -> None:
    """The stored paper-level summary, rendered."""
    summary = (b or {}).get("paper_summary") or {}
    concern = str(summary.get("main_novelty_concern") or "").strip()
    remaining = str(summary.get("remaining_contribution") or "").strip()
    if not concern and not remaining:
        return
    out += ["## Novelty summary", ""]
    try:
        import paper_synthesis

        names = {c["id"]: c.get("claim_name") or c.get("name") or "" for c in claims if c.get("id")}
        a_ids = {e.get("claim_id") for e in (a or {}).get("claims", []) or []}
        findings = paper_synthesis.build_findings(
            a, b, [cid for cid in order if cid in a_ids], names, refs
        )
        if paper_synthesis.is_stale(summary, findings):
            out += [
                "**Out of date:** the claim results below have changed since this "
                "summary was written. It has not been regenerated.",
                "",
            ]
    except Exception:
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
            row = by_paper.setdefault(
                pid,
                {
                    "title": c.get("title") or pid,
                    "cite": _cite(
                        c.get("authors") or pm.get("authors"), c.get("year") or pm.get("year")
                    ),
                    "claims": {},
                    "detail": {},
                    "versions": {},
                },
            )
            row["claims"][cid] = (vd.degree(c), _status(c), vd.degree_confirmed(c))
            row["detail"][cid] = _has_detail(c)
            row["versions"][cid] = _document_label(_snapshot(entry, c))
    titles = {pid: row["title"] for pid, row in by_paper.items()}
    paper_order = source_refs.order_from_titles(titles)
    refs = source_refs.assign_from_titles(titles)
    out: List[str] = ["# Novelty Assessment", ""]
    title = meta.get("title") or claims_doc.get("title")
    if title:
        out += [f"**{title}**", ""]
    authors = _authors_from_tei(sub, submission_id)
    if authors:
        out += [f"**Authors:** {authors}", ""]
    if meta.get("publication_date"):
        out += [f"**Publication date:** {meta['publication_date']}", ""]
    _paper_summary(b, a, order, claims, refs, out)
    out += ["---", ""] + _LEGEND

    cols = [(cid, f"Claim {i + 1}", i + 1) for i, cid in enumerate(order) if cid in a_by]
    if by_paper:
        out += [
            "---",
            "",
            "# Related work examined",
            "",
            "| Source | Paper | Version used · date | "
            + " | ".join(label for _, label, _n in cols)
            + " |",
            "|" + "---|" * (3 + len(cols)),
        ]
        for pid in paper_order:
            row = by_paper[pid]
            documents = list(dict.fromkeys(row["versions"].values()))
            version = (
                documents[0]
                if len(documents) == 1
                else "; ".join(
                    f"{label}: {row['versions'][cid]}"
                    for cid, label, _n in cols
                    if cid in row["versions"]
                )
            )
            name = " — ".join(x for x in (row["title"], row["cite"]) if x)
            assessments = [
                _linked(
                    _related_cell(row["claims"].get(cid)),
                    n,
                    refs[pid],
                    bool(row["detail"].get(cid)),
                )
                for cid, _label, n in cols
            ]
            cells = [refs[pid], name, version] + assessments
            out.append("| " + " | ".join(_cell(x) for x in cells) + " |")
        out += [""]

    claims_by = {c["id"]: c for c in claims if c.get("id")}
    for i, cid in enumerate(order, 1):
        entry = a_by.get(cid)
        doc_claim = claims_by.get(cid) or {}
        claim_text = (
            (entry or {}).get("claim_text")
            or doc_claim.get("claim_text")
            or (entry or {}).get("claim_name")
            or ""
        ).strip()
        out += ["---", "", f"# Claim {i} — Review", "", claim_text, ""]
        if entry is None:
            out += [
                "**Detailed comparisons:** none recorded",
                "",
                "## Claim-level assessment",
                "",
                "No review is recorded for this claim.",
                "",
            ]
            continue
        recorded = b_by.get(cid) or {}
        comparisons = entry.get("comparisons") or []
        details = [c for c in comparisons if _has_detail(c)]
        details.sort(key=vd.sort_key)
        verdict, _derived = _claim_verdict(comparisons, recorded.get("verdict"))

        out += [f"**Verdict:** {vd.verdict_label(verdict)}.", ""]
        out += [
            f"**Detailed comparisons:** {_degree_counts(details) if details else 'none recorded'}",
            "",
        ]

        out += ["## Claim-level assessment", ""]
        stored = recorded.get("claim_assessment") or {}
        stale = False
        if stored:
            try:
                import claim_assessment

                stale = claim_assessment.is_stale(
                    stored,
                    claim_assessment.build_claim_findings(
                        entry, i, claim_text, recorded.get("verdict") or verdict, refs
                    ),
                )
            except Exception:
                pass
        for paragraph in _claim_assessment(
            comparisons, recorded.get("verdict"), recorded.get("rationale"), stored, stale
        ):
            out += [paragraph, ""]
        out += ["## Detailed comparisons", ""]
        if not details:
            out += [
                "No overlapping comparison or assessment/evidence conflict recorded. "
                'Every processed comparison for this claim is listed under "Related '
                'work examined".',
                "",
            ]
        for c in details:
            _comparison_detail(c, entry, refs, pool, out)

    return "\n".join(out).rstrip() + "\n"


def quote_index(data_dir: str, submission_id: str, variant: str = "") -> dict:
    """Every verified quote the export blockquotes, keyed by its normalized text."""
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

    by_paper_titles = {pid: papers[pid]["title"] for pid in papers}
    for entry in a.get("claims", []) or []:
        for c in entry.get("comparisons", []) or []:
            by_paper_titles.setdefault(_pid(c), c.get("title") or _pid(c))
    refs = source_refs.assign_from_titles(by_paper_titles)

    return {"submission": sub_list, "papers": papers, "refs": refs, "claim_anchors": claim_anchors}
