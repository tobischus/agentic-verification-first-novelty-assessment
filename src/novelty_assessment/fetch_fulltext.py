#!/usr/bin/env python3
"""
Full-text acquisition for related-work candidate papers, split into two
independent phases so GROBID work happens only where it is actually needed:

  Phase 1 (download_pdfs) -- runs for the WHOLE pool right after retrieval.
    Only ensures a PDF is on disk (S2 openAccessPdf / arXiv / Unpaywall). No
    GROBID call. This is what the pipeline's "fetch_pdfs" stage runs; the
    reviewer sees PDF-available/not-available per paper in Related Work and
    can upload a PDF manually for the ones that failed.

  Phase 2 (parse_one / parse_pdfs) -- parses an ALREADY-DOWNLOADED PDF into
    sectioned full text IN PROCESS via PyMuPDF (pdf_sections.py; GROBID is no
    longer used for related work -- it was the bottleneck: minutes per paper on
    a low-RAM machine vs ~1s in-process). Only called ON DEMAND for a paper once
    the agent actually deep-dives it during the claim review (agent/tools.py
    ClaimToolbox.ensure_fulltext) -- most pool papers never reach a deep dive,
    so most PDFs are never parsed at all.

`fetch()` still runs both phases back-to-back for CLI / batch use (evaluation
runs that need every paper's full text upfront, not just the deep-dived ones).
artifact_a._load_fulltext() and agent/tools.py both pick up
related_work_data/grobid_fulltext/{paper_id}.txt automatically, whichever path
produced it.
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from lxml import etree
from dotenv import load_dotenv

# Reuse the Step-1 GROBID client + TEI parser.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "preprocess"))
from grobid_client import GrobidClient
from extract_metadata import EnhancedGrobidParser

load_dotenv()

_UA = {"User-Agent": "Mozilla/5.0 (novelty-assessment-pipeline)"}

# Per-paper diagnostics: which URL was tried, why a download/GROBID step failed.
# Visible in the backend console so "why did only N/M get full text?" is answerable
# without re-deriving it from disk afterwards.
logger = logging.getLogger("fetch_fulltext")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[fetch_fulltext] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


class FullTextFetcher:
    def __init__(self, grobid_server: str = "http://localhost:8070"):
        # Full-text fetch is best-effort (artifact_a falls back to abstract+intro), so
        # keep the GROBID timeout bounded -- a hung/overloaded GROBID must not stall the
        # pipeline (the default was 300s). 90s was too short for large PDFs (e.g. a 7MB
        # paper on a low-RAM machine) -> they timed out as grobid_error; 180s is the
        # compromise between large-PDF headroom and not waiting forever on a dead GROBID.
        self.client = GrobidClient(grobid_server, timeout=180)
        self.parser = EnhancedGrobidParser()

    # --------------------------- PDF download --------------------------- #

    @staticmethod
    def _arxiv_id_by_title(title: str) -> str:
        # A SHORT title-prefix phrase matches reliably; a long full-title phrase fails
        # arXiv's phrase matching (esp. across hyphens) -> would return no id and no PDF.
        words = re.findall(r"[A-Za-z0-9]+", title or "")
        if len(words) < 3:
            return ""
        phrase = " ".join(words[:8])

        def norm(s):
            return "".join((s or "").lower().split()).replace("-", "")

        want = norm(title)
        ns = "{http://www.w3.org/2005/Atom}"
        try:
            res = requests.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f'ti:"{phrase}"', "start": 0, "max_results": 5},
                timeout=30,
            )
            if res.status_code != 200:
                return ""
            for entry in ET.fromstring(res.content).findall(f"{ns}entry"):
                etitle = norm(entry.findtext(f"{ns}title") or "")
                # verify it's really the same paper before trusting the hit
                if want and (want[:50] in etitle or etitle[:50] in want):
                    aid = entry.findtext(f"{ns}id") or ""
                    return aid.split("/abs/")[-1]
        except Exception:
            pass
        return ""

    @staticmethod
    def _try_download(url: str, dest: Path):
        """Return (ok, detail) where detail explains the outcome for logging."""
        try:
            r = requests.get(url, timeout=40, headers=_UA)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                return True, f"ok {len(r.content)}B"
            if r.status_code == 200:
                return False, f"not-a-pdf ({r.content[:4]!r})"
            return False, f"http {r.status_code}"
        except Exception as e:
            return False, f"err {type(e).__name__}"

    @staticmethod
    def _is_valid_pdf(path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                return f.read(5).startswith(b"%PDF")
        except Exception:
            return False

    def _unpaywall_pdf_urls(self, doi: str) -> list:
        """Direct-PDF URLs from Unpaywall (incl. constructed PMC links). Needs UNPAYWALL_EMAIL."""
        email = os.getenv("UNPAYWALL_EMAIL")
        if not doi or not email:
            return []
        urls = []
        try:
            j = requests.get(
                f"https://api.unpaywall.org/v2/{doi}", params={"email": email}, timeout=20
            ).json()
            for loc in [j.get("best_oa_location")] + (j.get("oa_locations") or []):
                if not loc:
                    continue
                if loc.get("url_for_pdf"):
                    urls.append(loc["url_for_pdf"])
                m = re.search(r"pmc/articles/(?:PMC)?(\d+)", loc.get("url_for_landing_page") or "")
                if m:
                    urls.append(f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{m.group(1)}/pdf/")
        except Exception:
            pass
        return urls

    @staticmethod
    def _s2_get(url: str, headers: dict, max_attempts: int = 5):
        """GET an S2 endpoint with adaptive backoff on 429/5xx (honours Retry-After).

        The per-paper openAccessPdf lookup used to do a single sleep(5) retry, which
        collapses during S2 throttle storms -> no openAccessPdf / arXiv-id -> no PDF.
        """
        delay = 2.0
        for attempt in range(max_attempts):
            try:
                r = requests.get(url, headers=headers, timeout=30)
            except Exception:
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                ra = r.headers.get("Retry-After")
                wait = float(ra) if (ra and ra.isdigit()) else delay
                time.sleep(min(wait, 30))
                delay = min(delay * 2, 30)
                continue
            return r  # genuine 4xx (404 etc.) -> no point retrying
        return None

    def ensure_pdf(self, paper: dict, pdfs_dir: Path, pin: dict = None) -> bool:
        """Ensure a VALID {paper_id}.pdf exists; try S2 / Unpaywall(+PMC) / arXiv.

        With `pin` (a paper_versions record), the pinned version's URL is the ONLY one
        tried for a paper that has one. The alternatives below all resolve to "whatever
        that identifier serves today": `arxiv.org/pdf/2301.12345.pdf` is the newest
        version, and an openAccessPdf or publisher link is the current file. Falling back
        to them after a pin would quietly restore the very thing pinning exists to stop --
        comparing a submission against a document written after it.
        """
        pid, title = paper["paper_id"], paper.get("title", "")
        dest = pdfs_dir / f"{pid}.pdf"
        if dest.exists():
            if self._is_valid_pdf(dest):
                # A file being present says nothing about WHICH document it is. Callers
                # other than download_pdfs (the agent's mid-run fetch) reach this with a
                # PDF left over from before pinning existed, i.e. whatever the unversioned
                # URL served that day. Accept it only when the pin vouches for this exact
                # file; otherwise it and its parsed texts are stale by definition.
                recorded = (pin or {}).get("doc_sha256")
                if not pin or (recorded and recorded == self._sha256(dest)):
                    return True
                logger.info(f"  cached PDF does not match the pinned "
                            f"{pin.get('version') or 'version'} -- discarding it")
                dest.unlink()
                self._drop_derived_texts(pdfs_dir.parent, pid)
            else:
                dest.unlink()  # corrupt cached download (HTML/empty) -> re-fetch

        if pin and pin.get("url"):
            ok, detail = self._try_download(pin["url"], dest)
            if ok:
                logger.info(f"  downloaded [{detail}] <- {pin['url']}  "
                            f"(pinned {pin.get('version', '?')} of {pin.get('version_date', '?')})")
                return True
            # No fallback: a pinned paper is either fetched at its pinned version or not
            # fetched at all. The deep dive can still run on the abstract.
            logger.info(f"  download FAILED [{detail}] <- {pin['url']}  "
                        f"(pinned {pin.get('version', '?')}; NOT falling back to the current version)")
            return False

        urls, doi = [], paper.get("doi")

        # PRIMARY: use externalIds already persisted in ranked_papers.json (from S2 enrichment,
        # see match_papers_to_s2 / retrieval). This means the arXiv id / DOI are known WITHOUT
        # any fetch-time S2 call -> downloads stay robust even when S2 is throttling.
        ext = paper.get("externalIds") or {}
        if ext.get("ArXiv"):
            urls.append(f"https://arxiv.org/pdf/{ext['ArXiv']}.pdf")
        doi = doi or ext.get("DOI")

        # SECONDARY: ask S2 for an openAccessPdf url (and fill arXiv/DOI if not persisted).
        # Skipped entirely if we already have an arXiv PDF url above.
        if not urls:
            api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
            headers = {"X-API-KEY": api_key} if api_key else {}
            try:
                r = self._s2_get(
                    f"https://api.semanticscholar.org/graph/v1/paper/{pid}"
                    "?fields=openAccessPdf,externalIds",
                    headers,
                )
                if r is not None and r.status_code == 200:
                    data = r.json()
                    oa = data.get("openAccessPdf") or {}
                    if oa.get("url"):
                        urls.append(oa["url"])
                    ext2 = data.get("externalIds") or {}
                    if ext2.get("ArXiv"):
                        urls.append(f"https://arxiv.org/pdf/{ext2['ArXiv']}.pdf")
                    doi = doi or ext2.get("DOI")
            except Exception:
                pass

        # Publisher-specific direct-PDF patterns (eLife serves a clean PDF here,
        # which S2/Unpaywall only expose as an HTML landing page).
        if doi:
            m = re.search(r"10\.7554/elife\.(\d+)", doi, re.I)
            if m:
                urls.append(f"https://elifesciences.org/articles/{m.group(1)}.pdf")

        urls += self._unpaywall_pdf_urls(doi)
        if not any("arxiv.org" in u for u in urls):
            arx = self._arxiv_id_by_title(title)
            if arx:
                urls.append(f"https://arxiv.org/pdf/{arx}.pdf")

        urls = list(dict.fromkeys(urls))  # dedup, preserve order
        if not urls:
            logger.info(f"  no candidate URL (no arXiv id / DOI / openAccessPdf) | {title[:55]}")
            return False
        for url in urls:
            ok, detail = self._try_download(url, dest)
            if ok:
                logger.info(f"  downloaded [{detail}] <- {url}")
                return True
            logger.info(f"  download FAILED [{detail}] <- {url}")
        return False

    # ----------------------------- GROBID ------------------------------ #

    def pdf_to_fulltext(self, pdf_path: Path) -> str:
        tei = self.client.pdf_to_tei(str(pdf_path))
        root = etree.fromstring(tei.encode("utf-8"))
        sections = self.parser.extract_full_text_sections(root)
        return "\n\n".join(
            (f"## {s['section']}\n{s['text']}" if s["section"] else s["text"])
            for s in sections
            if s["text"]
        )

    # ------------------------------ run -------------------------------- #

    def _has_fulltext(self, rwd: Path, pid: str) -> bool:
        return (
            (rwd / "nougat_output" / f"{pid}.mmd").exists()
            or (rwd / "grobid_fulltext" / f"{pid}.txt").exists()
            or (rwd / "mineru_output" / f"{pid}.md").exists()
        )

    @staticmethod
    def _dirs(data_dir: str, submission_id: str):
        rwd = Path(data_dir) / submission_id / "related_work_data"
        pdfs_dir, ft_dir = rwd / "pdfs", rwd / "grobid_fulltext"
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        ft_dir.mkdir(parents=True, exist_ok=True)
        return rwd, pdfs_dir, ft_dir

    # --------------------------- version pinning ------------------------- #
    # Which version of each paper the review is allowed to read, decided once and
    # recorded, so that the file on disk, the text parsed out of it and the quotes
    # verified against that text all refer to the same document -- and so a reviewer can
    # see which document that was. See src/retrieval/paper_versions.py for the rules.

    VERSIONS_FILE = "versions.json"

    # The two statuses a paper may be read at: a specific admissible version, or the one
    # document a source without version history has, checked against the cutoff. Everything
    # else (unavailable / uncertain / unresolved) is a paper the review does not read.
    USABLE_STATUSES = ("pinned", "single")

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _derived_texts(rwd: Path, pid: str) -> list:
        """Every file derived from this paper's PDF, whichever parser produced it.

        The readers downstream (tools._load_fulltext_file, artifact_a) try these in a
        fixed order and take the first that exists -- nougat BEFORE grobid. So dropping
        only the grobid dump on a version change leaves a stale nougat or mineru file to
        win, and the review then quotes text from a document that is no longer on disk.
        """
        return [
            rwd / "nougat_output" / f"{pid}.mmd",
            rwd / "grobid_fulltext" / f"{pid}.txt",
            rwd / "mineru_output" / f"{pid}.md",
            rwd / "mineru_output" / pid / f"{pid}.md",
        ]

    def _drop_derived_texts(self, rwd: Path, pid: str) -> int:
        dropped = 0
        for p in self._derived_texts(rwd, pid):
            if p.exists():
                try:
                    p.unlink()
                    dropped += 1
                except OSError:
                    logger.info(f"  could not remove stale text {p}")
        return dropped

    def _versions_path(self, rwd: Path) -> Path:
        return rwd / self.VERSIONS_FILE

    def _load_versions(self, rwd: Path) -> dict:
        p = self._versions_path(rwd)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            logger.info(f"  versions manifest unreadable, starting a new one: {p}")
            return {}

    def _save_versions(self, rwd: Path, data: dict) -> None:
        self._versions_path(rwd).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def _submission_date(data_dir: str, submission_id: str) -> str:
        """The date the prior-work cutoff is measured against."""
        meta_path = Path(data_dir) / submission_id / f"{submission_id}.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        return str(meta.get("publication_date") or meta.get("year") or "")

    def resolve_versions(self, data_dir: str, submission_id: str, paper_ids=None,
                         force: bool = False) -> dict:
        """Pin each paper to the newest version that is still prior work.

        Writes related_work_data/versions.json: per paper the status, version, that
        version's date, the version-bound URL and (once downloaded) the file's sha256.
        Returns the same mapping.

        Papers whose version cannot be pinned are recorded with the reason and are NOT
        given a URL, so the downloader leaves them alone rather than fetching the current
        file. That is the whole point: an unpinnable paper should be visibly absent, not
        invisibly wrong.
        """
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "retrieval"))
        import paper_versions as pv

        rwd, _, _ = self._dirs(data_dir, submission_id)
        ranked = json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))
        by_id = {p["paper_id"]: p for p in ranked}
        if paper_ids is None:
            paper_ids = list(by_id)

        sub_date = self._submission_date(data_dir, submission_id)
        if not sub_date:
            logger.info("no submission date on file -- cannot pin versions against a cutoff")
            return {}

        manifest = self._load_versions(rwd)
        todo = [pid for pid in paper_ids
                if force or pid not in manifest or not manifest[pid].get("resolved_at")]
        logger.info(f"pinning versions against submission date {sub_date} "
                    f"({len(todo)} to resolve, {len(paper_ids) - len(todo)} already recorded)")

        for i, pid in enumerate(todo, 1):
            rec = by_id.get(pid)
            if rec is None:
                continue
            pin = pv.resolve_version(rec, sub_date)
            entry = pin.to_dict()
            entry["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            entry["record_date"] = rec.get("publication_date") or rec.get("year") or ""
            entry["title"] = rec.get("title", "")
            # Keep any hash from a previous download only if the version is unchanged.
            old = manifest.get(pid) or {}
            if old.get("version") == entry.get("version") and old.get("doc_sha256"):
                entry["doc_sha256"] = old["doc_sha256"]
            manifest[pid] = entry

            title = rec.get("title", "")[:55]
            if pin.usable:
                logger.info(f"[ver {i}/{len(todo)}] {pid} {title} -> "
                            f"{pin.status} {pin.version or '(single)'} {pin.version_date}")
            else:
                # Loud on purpose: this is a paper the review will NOT read, and the
                # reason belongs in front of whoever reads the log.
                logger.info(f"[ver {i}/{len(todo)}] {pid} {title} -> {pin.status.upper()}: "
                            f"{pin.note} (latest {pin.latest_version} {pin.latest_version_date})")

        self._save_versions(rwd, manifest)
        self._apply_version_abstracts(rwd, ranked, manifest)
        counts = {}
        for pid in paper_ids:
            counts[(manifest.get(pid) or {}).get("status", "unrecorded")] = \
                counts.get((manifest.get(pid) or {}).get("status", "unrecorded"), 0) + 1
        logger.info(f"version pinning: {counts}")
        return manifest

    def pin_for_record(self, data_dir: str, submission_id: str, record: dict) -> dict:
        """Pin ONE paper, for candidates that arrive after the batch pass (retrieve_more).

        Same rules and same manifest as `resolve_versions`; separate only because a paper
        the agent just retrieved is not in ranked_papers.json yet, so there is nothing to
        look it up in. Returns the pin dict (empty when it cannot be resolved).
        """
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "retrieval"))
        import paper_versions as pv

        pid = record.get("paper_id") or ""
        rwd, _, _ = self._dirs(data_dir, submission_id)
        manifest = self._load_versions(rwd)
        if manifest.get(pid, {}).get("resolved_at"):
            return manifest[pid]

        sub_date = self._submission_date(data_dir, submission_id)
        if not sub_date or not pid:
            return {}
        pin = pv.resolve_version(record, sub_date)
        entry = pin.to_dict()
        entry["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry["record_date"] = record.get("publication_date") or record.get("year") or ""
        entry["title"] = record.get("title", "")
        manifest[pid] = entry
        self._save_versions(rwd, manifest)
        if not pin.usable:
            logger.info(f"[ver] {pid} {record.get('title','')[:55]} -> "
                        f"{pin.status.upper()}: {pin.note}")
        return entry

    def record_pdf_hash(self, data_dir: str, submission_id: str, paper_id: str,
                        pdf_path: Path) -> str:
        """Bind the file now on disk to its manifest entry.

        Without this the hash only ever gets written by the batch downloader, so a paper
        fetched mid-run by the agent would be judged "does not match the pin" on the next
        pass and fetched again, every time.
        """
        rwd, _, _ = self._dirs(data_dir, submission_id)
        manifest = self._load_versions(rwd)
        entry = manifest.get(paper_id)
        if not entry or not pdf_path.exists():
            return ""
        digest = self._sha256(pdf_path)
        entry["doc_sha256"] = digest
        entry["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest[paper_id] = entry
        self._save_versions(rwd, manifest)
        return digest

    def _apply_version_abstracts(self, rwd: Path, ranked: list, manifest: dict) -> None:
        """Put the PINNED version's own abstract into ranked_papers.json.

        The abstract S2 holds is the current record's, which for a paper pinned to an
        older version is a different text than the one being compared -- a later abstract
        can describe results the pinned version does not contain. Where arXiv gave us the
        version's own abstract, it replaces the record's; where it did not, the record's
        abstract stays but is labelled as such, so nothing silently passes a current
        summary off as evidence about an older document.
        """
        changed = 0
        for p in ranked:
            entry = manifest.get(p.get("paper_id")) or {}
            if not entry:
                continue
            p["pinned_version"] = entry.get("version", "")
            p["pinned_version_date"] = entry.get("version_date", "")
            p["version_status"] = entry.get("status", "")
            src = entry.get("abstract_source") or ""
            if src == "version" and entry.get("abstract"):
                if (p.get("abstract") or "").strip() != entry["abstract"].strip():
                    p["abstract_latest_record"] = p.get("abstract", "")
                    p["abstract"] = entry["abstract"]
                    changed += 1
            p["abstract_source"] = src or "record"
        (rwd / "ranked_papers.json").write_text(
            json.dumps(ranked, ensure_ascii=False, indent=1), encoding="utf-8")
        if changed:
            logger.info(f"  replaced {changed} abstract(s) with the pinned version's own text")

    # ---- PHASE 1: download PDFs only, no GROBID dependency (runs for the whole pool) --- #

    def download_pdfs(self, data_dir: str, submission_id: str, paper_ids=None,
                      pin_versions: bool = True) -> dict:
        """Ensure a PDF is on disk for each target paper. Returns {paper_id: bool}.

        With `pin_versions`, each paper is first pinned to the newest version that is
        still prior work, and only that version is fetched. A file already on disk counts
        as present only if the manifest says it IS that version: everything downloaded
        before pinning existed came from an unversioned URL, which served whatever was
        current that day, so those are re-fetched rather than trusted.
        """
        rwd, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        ranked = json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))
        by_id = {p["paper_id"]: p for p in ranked}

        if paper_ids is None:
            paper_ids = list(by_id)

        manifest = (self.resolve_versions(data_dir, submission_id, paper_ids)
                    if pin_versions else {})

        try:
            import progress as _progress  # optional sub-progress for the frontend
        except Exception:
            _progress = None
        n = len(paper_ids)
        logger.info(f"downloading PDFs for {n} paper(s) (of {len(by_id)} ranked)")
        if _progress:
            _progress.start_phase("Downloading PDFs", n)
        results = {}
        for idx, pid in enumerate(paper_ids):
            if _progress:
                _progress.report(idx, n)
            if pid not in by_id:
                results[pid] = False
                continue
            title = by_id[pid].get("title", "")[:60]
            pin = manifest.get(pid) or {}
            pdf_path = pdfs_dir / f"{pid}.pdf"

            # Admissibility is the STATUS, not the presence of a URL. A "single" paper --
            # a journal article, say -- is admissible and has no version-bound URL to
            # give, because its source publishes no version history; testing for a URL
            # skipped every one of those, which is most non-arXiv prior work.
            if pin_versions and pin and pin.get("status") not in self.USABLE_STATUSES:
                # Pinning ran and could not settle on a version. Not an error to retry:
                # a decision, and it stands until the record or the source changes.
                results[pid] = False
                logger.info(f"[dl {idx+1}/{n}] {pid}  {title} -> skipped "
                            f"({pin.get('status', 'unresolved')}: {pin.get('note', '')})")
                continue

            if pdf_path.exists() and self._is_valid_pdf(pdf_path):
                on_disk = pin.get("doc_sha256")
                if not pin_versions or not pin:
                    results[pid] = True
                    logger.info(f"[dl {idx+1}/{n}] {pid}  {title} -> already on disk")
                    continue
                if on_disk and on_disk == self._sha256(pdf_path):
                    results[pid] = True
                    logger.info(f"[dl {idx+1}/{n}] {pid}  {title} -> already on disk "
                                f"({pin.get('version') or 'single'})")
                    continue
                # Either no hash was ever recorded (downloaded before pinning) or the file
                # is a different document than the pin names. Both mean the cached PDF --
                # and every text parsed out of it -- cannot be attributed to the pinned
                # version, so all of it goes.
                logger.info(f"[dl {idx+1}/{n}] {pid}  {title} -> cached PDF is not the "
                            f"pinned {pin.get('version') or 'version'}, re-fetching")
                pdf_path.unlink()
                dropped = self._drop_derived_texts(rwd, pid)
                if dropped:
                    logger.info(f"  dropped {dropped} stale parsed text(s) with it")
            else:
                logger.info(f"[dl {idx+1}/{n}] {pid}  {title}")

            t0 = time.time()
            ok = self.ensure_pdf(by_id[pid], pdfs_dir, pin=pin or None)
            results[pid] = ok
            if ok and pin_versions and pin:
                pin["doc_sha256"] = self._sha256(pdf_path)
                pin["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                manifest[pid] = pin
            if not ok:
                logger.info(f"  -> no_pdf (no downloadable PDF found)  [{time.time()-t0:.1f}s]")
            time.sleep(1)  # be nice to S2/arXiv
        if _progress:
            _progress.report(n, n)
        if pin_versions and manifest:
            self._save_versions(rwd, manifest)
        n_ok = sum(1 for v in results.values() if v)
        logger.info(f"PDF download done: {n_ok}/{n} available on disk")
        return results

    # ---- PHASE 2: parse an already-downloaded PDF, IN PROCESS (called on demand) --- #
    # PyMuPDF replaces GROBID here: the agent only needs section titles + verbatim
    # body text, and GROBID (Docker service) was the bottleneck -- minutes per paper
    # on a low-RAM machine, crashes cascading over the queue. PyMuPDF parses in ~1s
    # in-process with no service dependency. The output keeps the exact grobid-dump
    # format ("## Section\ntext"), so everything downstream is unchanged, and quote
    # verification stays sound (quotes verify against this parsed text itself).

    def parse_one(self, data_dir: str, submission_id: str, paper_id: str) -> str:
        """Parse ONE paper's already-downloaded PDF into sectioned full text.

        Called on demand when a paper reaches a deep dive (not upfront for the
        whole pool). Returns a short status string:
          "ok"           -- parsed, related_work_data/grobid_fulltext/{pid}.txt written
          "no_pdf"       -- no PDF on disk for this paper (download/upload it first)
          "parse_empty"  -- PDF has ~no extractable text (scanned/image-only)
          "parse_error"  -- parser raised (malformed/encrypted PDF)
        """
        from pdf_sections import pdf_to_sectioned_text

        _, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        pdf_path = pdfs_dir / f"{paper_id}.pdf"
        if not pdf_path.exists() or not self._is_valid_pdf(pdf_path):
            return "no_pdf"
        try:
            t0 = time.time()
            text = pdf_to_sectioned_text(pdf_path)
        except Exception as e:
            logger.info(f"[parse] {paper_id} -> parse_error: {repr(e)[:120]}")
            return "parse_error"
        if len(text) < 500:
            logger.info(f"[parse] {paper_id} -> parse_empty ({len(text)} chars)")
            return "parse_empty"
        (ft_dir / f"{paper_id}.txt").write_text(text, encoding="utf-8")
        # Bind the text to the exact PDF it came out of. Readers check this against the
        # manifest's current hash, so a text cannot outlive the document it describes --
        # which is what happened when a version change replaced the PDF underneath it.
        try:
            rwd, _, _ = self._dirs(data_dir, submission_id)
            manifest = self._load_versions(rwd)
            entry = manifest.get(paper_id)
            if entry is not None:
                entry["parsed_from_sha256"] = self._sha256(pdf_path)
                entry["parsed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                manifest[paper_id] = entry
                self._save_versions(rwd, manifest)
        except Exception as e:
            logger.info(f"[parse] {paper_id}: could not record provenance ({type(e).__name__})")
        logger.info(f"[parse] {paper_id} -> ok ({len(text)} chars)  [{time.time()-t0:.1f}s]")
        return "ok"

    def parse_pdfs(self, data_dir: str, submission_id: str, paper_ids=None) -> dict:
        """Parse several already-downloaded PDFs (batch form of parse_one)."""
        rwd, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        if paper_ids is None:
            paper_ids = [p.stem for p in pdfs_dir.glob("*.pdf") if not (ft_dir / f"{p.stem}.txt").exists()]
        return {pid: self.parse_one(data_dir, submission_id, pid) for pid in paper_ids}

    # ---- CLI / batch convenience: both phases back-to-back --- #

    def fetch(self, data_dir: str, submission_id: str, paper_ids=None) -> dict:
        """Download + parse every target paper (used by the CLI / batch evaluation
        runs that want every paper's full text upfront). The live pipeline instead
        calls download_pdfs() at retrieval time and parse_one() on demand per deep
        dive -- see agent/tools.py ClaimToolbox.ensure_fulltext."""
        rwd, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        by_id = {p["paper_id"]: p for p in
                 json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))}
        if paper_ids is None:
            paper_ids = [pid for pid in by_id if not self._has_fulltext(rwd, pid)]

        dl = self.download_pdfs(data_dir, submission_id, paper_ids)
        have_pdf = [pid for pid, ok in dl.items() if ok]
        results = {pid: "no_pdf" for pid, ok in dl.items() if not ok}

        try:
            import progress as _progress
            _progress.start_phase("Parsing full text", len(have_pdf))
        except Exception:
            _progress = None
        for idx, pid in enumerate(have_pdf):
            if _progress:
                _progress.report(idx, len(have_pdf))
            status = self.parse_one(data_dir, submission_id, pid)
            results[pid] = f"ok ({(ft_dir / f'{pid}.txt').stat().st_size} chars)" if status == "ok" else status
        if _progress:
            _progress.report(len(have_pdf), len(have_pdf))

        n_ok = sum(1 for v in results.values() if str(v).startswith("ok"))
        tally = {}
        for v in results.values():
            key = str(v).split(":")[0].split(" ")[0]
            tally[key] = tally.get(key, 0) + 1
        logger.info(f"DONE: {n_ok}/{len(paper_ids)} full text. breakdown: {tally}")
        return results


def main():
    ap = argparse.ArgumentParser(description="Phase 2: fetch full text (PDF download + GROBID) for candidates")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--server", default="http://localhost:8070")
    ap.add_argument("--paper-ids", nargs="*", default=None, help="specific paper ids (default: all pool papers lacking full text)")
    args = ap.parse_args()

    results = FullTextFetcher(args.server).fetch(args.data_dir, args.submission_id, args.paper_ids)
    ok = sum(1 for v in results.values() if v.startswith("ok"))
    print(f"Full-text fetch: {ok}/{len(results)} succeeded")
    for pid, status in results.items():
        print(f"  {status:28} {pid}")


if __name__ == "__main__":
    main()
