#!/usr/bin/env python3
"""Which VERSION of a prior paper the review is allowed to read, and where to get it.

A retrieved paper is not one document. An arXiv preprint from 2023 can have a v4 from
2026, and `https://arxiv.org/pdf/2301.12345.pdf` -- the URL the fetcher used -- always
serves the newest one. So a paper admitted on its 2023 date could be compared, quoted and
cited as its 2026 text: the reviewer sees a verbatim-verified quote from a document that
did not exist when the submission was written. Verification cannot catch this, because the
quote IS verbatim in the file that was downloaded. Only pinning the version can.

Three things this module decides, and one it refuses to:

  admissibility  Is a candidate far enough before the submission to count as prior work?
                 Dates come at different granularities ("2024", "2024-03", "2024-03-15"),
                 so every date is read as the INTERVAL it could mean and the answer is
                 given over the whole interval -- see `gap_verdict`.
  version        Which version is the newest one still admissible (`resolve_version`).
  provenance     The pinned version's number, date, URL and (for arXiv) its own abstract,
                 so what is compared is what was downloaded.

  refuses        To guess. When the version history cannot be read, or a date's granularity
                 cannot settle the gap, the status says so and the caller is expected to
                 log it and leave the paper out -- never to quietly fall back to whatever
                 the unversioned URL happens to serve today.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from calendar import monthrange
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger("paper_versions")

_ARXIV_API = "http://export.arxiv.org/api/query"
_NS = "{http://www.w3.org/2005/Atom}"

# arXiv asks for ~3s between API calls. Kept as a module constant so a caller that
# resolves a whole pool can see (and, in a test, shorten) what it is paying.
ARXIV_DELAY_S = 3.0

# How far before the submission a paper must stand to count as prior work. The date path
# of the old retrieval filter already used 90 days; the year path did not, which is what
# this module exists to make uniform.
DEFAULT_MIN_GAP_DAYS = 90

# ------------------------------- dates ------------------------------------ #


def date_bounds(value) -> Optional[Tuple[date, date]]:
    """The earliest and latest day a (possibly partial) date string could mean.

    "2024-03-15" -> that day, twice. "2024-03" -> the whole month. "2024" -> the whole
    year. Anything unparseable -> None, which callers must treat as "unknown", never as
    "fine". A bare year really is a 365-day interval, and pretending otherwise is how
    "published an earlier year" came to pass for admissible when the true gap was one day.
    """
    s = str(value or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", s)
    if not m:
        return None
    year = int(m.group(1))
    if not (1800 <= year <= 2200):
        return None
    month, day = m.group(2), m.group(3)
    try:
        if month and day:
            d = date(year, int(month), int(day))
            return d, d
        if month:
            mo = int(month)
            return date(year, mo, 1), date(year, mo, monthrange(year, mo)[1])
        return date(year, 1, 1), date(year, 12, 31)
    except ValueError:
        return None


def gap_verdict(candidate, submission, min_gap_days: int = DEFAULT_MIN_GAP_DAYS) -> str:
    """Is `candidate` at least `min_gap_days` before `submission`? Over whole intervals.

    Returns one of:
      "ok"         every date the candidate could carry is far enough before every date
                   the submission could carry.
      "too_recent" no date the candidate could carry is far enough before -- it fails
                   whatever the granularity hides.
      "unknown"    the granularity decides the answer, so there is no answer. A 2024 paper
                   against a 2025 submission lands here: Jan 2024 -> Dec 2025 is nearly two
                   years, Dec 2024 -> Jan 2025 is a day, and the records cannot tell them
                   apart. The old year rule called this whole class admissible.

    Both arguments accept a date string or an already-computed (earliest, latest) pair.
    """
    cand = candidate if isinstance(candidate, tuple) else date_bounds(candidate)
    sub = submission if isinstance(submission, tuple) else date_bounds(submission)
    if not cand or not sub:
        return "unknown"
    gap = timedelta(days=min_gap_days)
    if cand[1] + gap <= sub[0]:      # worst case still far enough
        return "ok"
    if cand[0] + gap > sub[1]:       # best case already too close
        return "too_recent"
    return "unknown"


# ------------------------------ versions ----------------------------------- #


@dataclass
class PinnedVersion:
    """What the review is allowed to read of one paper, and the record of where it came from.

    `status` is the whole point of the dataclass:
      "pinned"       a specific version was chosen and is admissible.
      "single"       the source has no version history (a journal DOI, say); the one
                     document it has was checked against the cutoff and is admissible.
      "unavailable"  no admissible version exists -- every version is too recent.
      "unresolved"   the version history could not be read (network, API, malformed id).
      "uncertain"    a date's granularity cannot establish the gap (see `gap_verdict`).
    Only "pinned" and "single" may be compared against; the other three are for the log.
    """
    paper_id: str
    status: str
    version: str = ""              # "v2", or "" where the source has no versions
    version_date: str = ""         # ISO date of THAT version
    url: str = ""                  # version-bound download URL
    abstract: str = ""             # that version's own abstract, where the source gives one
    abstract_source: str = ""      # "version" | "record" -- which document the abstract is of
    latest_version: str = ""       # newest version that exists, admissible or not
    latest_version_date: str = ""
    note: str = ""                 # why a non-usable status came out that way
    doc_sha256: str = ""           # filled in by the downloader, not here
    checked_versions: List[dict] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("pinned", "single")

    def to_dict(self) -> dict:
        return asdict(self)


def _arxiv_query(id_list: List[str], session: Optional[requests.Session] = None,
                 timeout: int = 30) -> List[dict]:
    """Atom entries for the given (possibly version-suffixed) arXiv ids.

    arXiv answers a versioned id with that version's own metadata -- its date in `updated`
    and, importantly, the abstract as it read at that version. Several ids in one call, so
    a whole version history costs one request rather than one per version.
    """
    get = (session or requests).get
    try:
        res = get(_ARXIV_API,
                  params={"id_list": ",".join(id_list), "max_results": len(id_list)},
                  timeout=timeout)
    except Exception as e:
        logger.debug("arXiv query failed for %s: %s", id_list, type(e).__name__)
        return []
    if res.status_code != 200:
        logger.debug("arXiv query for %s: HTTP %s", id_list, res.status_code)
        return []
    try:
        root = ET.fromstring(res.content)
    except ET.ParseError:
        return []
    out = []
    for entry in root.findall(f"{_NS}entry"):
        raw_id = (entry.findtext(f"{_NS}id") or "").strip()
        # "http://arxiv.org/abs/2301.12345v3" -> ("2301.12345", "v3")
        tail = raw_id.split("/abs/")[-1]
        m = re.match(r"^(.*?)(v\d+)?$", tail)
        base, ver = (m.group(1), m.group(2) or "") if m else (tail, "")
        published = (entry.findtext(f"{_NS}published") or "")[:10]
        updated = (entry.findtext(f"{_NS}updated") or "")[:10]
        out.append({
            "arxiv_id": base,
            "version": ver,
            # `updated` is THIS version's date; `published` is always v1's.
            "date": updated or published,
            "v1_date": published,
            "abstract": " ".join((entry.findtext(f"{_NS}summary") or "").split()),
            "title": " ".join((entry.findtext(f"{_NS}title") or "").split()),
        })
    return out


def arxiv_admissible_version(arxiv_id: str, submission_date, paper_id: str = "",
                             min_gap_days: int = DEFAULT_MIN_GAP_DAYS,
                             session: Optional[requests.Session] = None,
                             delay_s: float = ARXIV_DELAY_S) -> PinnedVersion:
    """The newest version of an arXiv paper that is still admissible prior work.

    Costs one request in the common case -- the newest version is old enough -- and two
    when it is not, because the remaining versions are asked for together. Walking down
    from the newest is what "newest admissible" means: v4 may postdate the submission
    while v2 sits comfortably before it, and v2 is then the document to read.
    """
    aid = re.sub(r"^arxiv[:/]*", "", (arxiv_id or "").strip(), flags=re.I)
    aid = re.sub(r"v\d+$", "", aid)          # a version suffix in the id is not our pin
    pid = paper_id or aid
    if not aid:
        return PinnedVersion(pid, "unresolved", note="no arXiv id")

    latest = _arxiv_query([aid], session=session)
    if not latest:
        return PinnedVersion(pid, "unresolved",
                             note="arXiv version history unavailable")
    head = latest[0]
    n = int(re.sub(r"\D", "", head["version"]) or 1)
    checked = [{"version": head["version"] or "v1", "date": head["date"]}]

    verdict = gap_verdict(head["date"], submission_date, min_gap_days)
    if verdict == "ok":
        return PinnedVersion(
            pid, "pinned", version=head["version"] or "v1", version_date=head["date"],
            url=f"https://arxiv.org/pdf/{aid}{head['version']}.pdf",
            abstract=head["abstract"], abstract_source="version",
            latest_version=head["version"] or "v1", latest_version_date=head["date"],
            checked_versions=checked)
    if n <= 1:
        # Only v1 exists and it is not admissible -- there is no older version to fall
        # back to, whichever way the date failed.
        status = "uncertain" if verdict == "unknown" else "unavailable"
        return PinnedVersion(
            pid, status, latest_version=head["version"] or "v1",
            latest_version_date=head["date"], checked_versions=checked,
            note=f"only version {head['version'] or 'v1'} ({head['date']}): {verdict}")

    if delay_s:
        time.sleep(delay_s)
    older = _arxiv_query([f"{aid}v{k}" for k in range(1, n)], session=session)
    by_version = {e["version"]: e for e in older}
    for k in range(n - 1, 0, -1):
        e = by_version.get(f"v{k}")
        if not e:
            continue
        checked.append({"version": e["version"], "date": e["date"]})
        if gap_verdict(e["date"], submission_date, min_gap_days) == "ok":
            return PinnedVersion(
                pid, "pinned", version=e["version"], version_date=e["date"],
                url=f"https://arxiv.org/pdf/{aid}{e['version']}.pdf",
                abstract=e["abstract"], abstract_source="version",
                latest_version=head["version"] or f"v{n}",
                latest_version_date=head["date"], checked_versions=checked)

    # Nothing admissible. Distinguish "every version really is too recent" from "the dates
    # are too coarse to tell", because the second is a data problem and the first is not.
    verdicts = {gap_verdict(c["date"], submission_date, min_gap_days) for c in checked}
    status = "uncertain" if "unknown" in verdicts else "unavailable"
    return PinnedVersion(
        pid, status, latest_version=head["version"] or f"v{n}",
        latest_version_date=head["date"], checked_versions=checked,
        note=f"no admissible version among {len(checked)} checked")


def resolve_version(record: dict, submission_date,
                    min_gap_days: int = DEFAULT_MIN_GAP_DAYS,
                    session: Optional[requests.Session] = None,
                    delay_s: float = ARXIV_DELAY_S) -> PinnedVersion:
    """Pin one retrieved paper to the version the review may read.

    `record` is a ranked_papers.json entry (paper_id, externalIds, publication_date/year,
    abstract). arXiv ids get a real version history; everything else has exactly one
    document, which is still checked against the cutoff rather than assumed to be fine.
    """
    pid = record.get("paper_id") or ""
    ext = record.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv") or ext.get("arXiv") or ext.get("arxiv")

    if arxiv_id:
        pin = arxiv_admissible_version(arxiv_id, submission_date, paper_id=pid,
                                       min_gap_days=min_gap_days, session=session,
                                       delay_s=delay_s)
        if pin.usable or pin.status != "unresolved":
            return pin
        # fall through: an unreadable arXiv history still leaves the record's own date,
        # but it can only ever yield the un-versioned document -- which is the thing this
        # module refuses to pin. Report it as unresolved below.
        logger.info("%s: arXiv history unreadable, no version can be pinned", pid)
        return pin

    stated = record.get("publication_date") or record.get("year") or ""
    verdict = gap_verdict(stated, submission_date, min_gap_days)
    if verdict == "ok":
        return PinnedVersion(
            pid, "single", version_date=(date_bounds(stated) or (None, None))[0].isoformat(),
            abstract=record.get("abstract", ""), abstract_source="record",
            note="source exposes no version history; single document checked against the cutoff")
    if verdict == "too_recent":
        return PinnedVersion(pid, "unavailable", note=f"stated date {stated!r} is not prior work")
    return PinnedVersion(
        pid, "uncertain",
        note=f"stated date {stated!r} is too coarse to establish a {min_gap_days}-day gap")
