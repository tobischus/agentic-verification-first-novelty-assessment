"""Which version of a prior paper the review may read, and where to get it."""
from __future__ import annotations

import logging
import re
import threading
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

ARXIV_DELAY_S = 3.0

DEFAULT_MIN_GAP_DAYS = 90



def date_bounds(value) -> Optional[Tuple[date, date]]:
    """The earliest and latest day a (possibly partial) date string could mean."""
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
    """Is `candidate` at least `min_gap_days` before `submission`? Over whole intervals."""
    cand = candidate if isinstance(candidate, tuple) else date_bounds(candidate)
    sub = submission if isinstance(submission, tuple) else date_bounds(submission)
    if not cand or not sub:
        return "unknown"
    gap = timedelta(days=min_gap_days)
    if cand[1] + gap <= sub[0]:
        return "ok"
    if cand[0] + gap > sub[1]:
        return "too_recent"
    return "unknown"




@dataclass
class PinnedVersion:
    """What the review is allowed to read of one paper, and the record of where it came from."""
    paper_id: str
    status: str
    version: str = ""
    version_date: str = ""
    url: str = ""
    abstract: str = ""
    abstract_source: str = ""
    latest_version: str = ""
    latest_version_date: str = ""
    note: str = ""
    doc_sha256: str = ""
    checked_versions: List[dict] = field(default_factory=list)
    submission_date: str = ""
    min_gap_days: int = DEFAULT_MIN_GAP_DAYS
    history_complete: bool = True
    missing_versions: List[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("pinned", "single")

    def to_dict(self) -> dict:
        return asdict(self)


_ARXIV_MAX_ATTEMPTS = 4
_arxiv_gate = threading.Lock()
_arxiv_last_call = 0.0


def _arxiv_wait() -> None:
    global _arxiv_last_call
    with _arxiv_gate:
        gap = time.monotonic() - _arxiv_last_call
        if gap < ARXIV_DELAY_S:
            time.sleep(ARXIV_DELAY_S - gap)
        _arxiv_last_call = time.monotonic()


def _arxiv_query(id_list: List[str], session: Optional[requests.Session] = None,
                 timeout: int = 30) -> List[dict]:
    """Atom entries for the given (possibly version-suffixed) arXiv ids."""
    get = (session or requests).get
    res = None
    for attempt in range(1, _ARXIV_MAX_ATTEMPTS + 1):
        _arxiv_wait()
        try:
            res = get(_ARXIV_API,
                      params={"id_list": ",".join(id_list), "max_results": len(id_list)},
                      timeout=timeout)
        except Exception as e:
            logger.debug("arXiv query failed for %s: %s", id_list, type(e).__name__)
            if attempt == _ARXIV_MAX_ATTEMPTS:
                return []
            time.sleep(ARXIV_DELAY_S * attempt)
            continue
        if res.status_code not in (429, 503):
            break
        if attempt == _ARXIV_MAX_ATTEMPTS:
            logger.warning("arXiv still rate-limiting after %d attempts (%s) -- these "
                           "papers will be recorded unresolved and refused as evidence "
                           "until they are re-resolved", _ARXIV_MAX_ATTEMPTS, id_list[:2])
            return []
        try:
            delay = float(res.headers.get("Retry-After", "") or 0)
        except ValueError:
            delay = 0.0
        delay = max(delay, ARXIV_DELAY_S * (2 ** attempt))
        logger.info("arXiv HTTP %s -- waiting %.0fs before retry %d/%d",
                    res.status_code, delay, attempt + 1, _ARXIV_MAX_ATTEMPTS)
        time.sleep(delay)
    if res is None or res.status_code != 200:
        logger.debug("arXiv query for %s: HTTP %s", id_list,
                     res.status_code if res is not None else "no response")
        return []
    try:
        root = ET.fromstring(res.content)
    except ET.ParseError:
        return []
    out = []
    for entry in root.findall(f"{_NS}entry"):
        raw_id = (entry.findtext(f"{_NS}id") or "").strip()
        tail = raw_id.split("/abs/")[-1]
        m = re.match(r"^(.*?)(v\d+)?$", tail)
        base, ver = (m.group(1), m.group(2) or "") if m else (tail, "")
        published = (entry.findtext(f"{_NS}published") or "")[:10]
        updated = (entry.findtext(f"{_NS}updated") or "")[:10]
        out.append({
            "arxiv_id": base,
            "version": ver,
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
    """The newest version of an arXiv paper that is still admissible prior work."""
    aid = re.sub(r"^arxiv[:/]*", "", (arxiv_id or "").strip(), flags=re.I)
    aid = re.sub(r"v\d+$", "", aid)
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
        status = "uncertain" if verdict == "unknown" else "unavailable"
        return PinnedVersion(
            pid, status, latest_version=head["version"] or "v1",
            latest_version_date=head["date"], checked_versions=checked,
            note=f"only version {head['version'] or 'v1'} ({head['date']}): {verdict}")

    if delay_s:
        time.sleep(delay_s)
    older = _arxiv_query([f"{aid}v{k}" for k in range(1, n)], session=session)
    by_version = {e["version"]: e for e in older}
    missing = [k for k in range(1, n) if f"v{k}" not in by_version]
    for k in range(n - 1, 0, -1):
        e = by_version.get(f"v{k}")
        if not e:
            continue
        checked.append({"version": e["version"], "date": e["date"]})
        if gap_verdict(e["date"], submission_date, min_gap_days) == "ok":
            gaps = [f"v{m}" for m in missing if m > k]
            note = ""
            if gaps:
                note = (f"admissible, but {', '.join(gaps)} could not be read -- a newer "
                        f"admissible version may exist above {e['version']}")
                logger.info("%s: pinned %s with an incomplete history (%s unread)",
                            pid, e["version"], ", ".join(gaps))
            return PinnedVersion(
                pid, "pinned", version=e["version"], version_date=e["date"],
                url=f"https://arxiv.org/pdf/{aid}{e['version']}.pdf",
                abstract=e["abstract"], abstract_source="version",
                latest_version=head["version"] or f"v{n}",
                latest_version_date=head["date"], checked_versions=checked,
                history_complete=not gaps, missing_versions=gaps, note=note)

    if missing:
        return PinnedVersion(
            pid, "unresolved", latest_version=head["version"] or f"v{n}",
            latest_version_date=head["date"], checked_versions=checked,
            note=f"version history incomplete: {len(missing)} of {n} versions "
                 f"({', '.join('v' + str(k) for k in missing[:6])}) could not be read")

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
    """Pin one retrieved paper to the version the review may read."""
    pid = record.get("paper_id") or ""
    ext = record.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv") or ext.get("arXiv") or ext.get("arxiv")

    def stamped(pin: PinnedVersion) -> PinnedVersion:
        """Record the cutoff (submission date, required gap) this verdict answers."""
        pin.submission_date = str(submission_date or "")
        pin.min_gap_days = min_gap_days
        return pin

    if arxiv_id:
        pin = arxiv_admissible_version(arxiv_id, submission_date, paper_id=pid,
                                       min_gap_days=min_gap_days, session=session,
                                       delay_s=delay_s)
        if pin.usable or pin.status != "unresolved":
            return stamped(pin)
        logger.info("%s: arXiv history unreadable, no version can be pinned", pid)
        return stamped(pin)

    stated = record.get("publication_date") or record.get("year") or ""
    verdict = gap_verdict(stated, submission_date, min_gap_days)
    if verdict == "ok":
        return stamped(PinnedVersion(
            pid, "single", version_date=(date_bounds(stated) or (None, None))[0].isoformat(),
            abstract=record.get("abstract", ""), abstract_source="record",
            note="source exposes no version history; single document checked against the cutoff"))
    if verdict == "too_recent":
        return stamped(PinnedVersion(
            pid, "unavailable", note=f"stated date {stated!r} is not prior work"))
    return stamped(PinnedVersion(
        pid, "uncertain",
        note=f"stated date {stated!r} is too coarse to establish a {min_gap_days}-day gap"))
