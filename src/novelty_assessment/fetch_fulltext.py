"""Full text of prior papers: version pinning, PDF download and parsing."""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "preprocess"))
from grobid_client import GrobidClient
from extract_metadata import EnhancedGrobidParser

load_dotenv()

_UA = {"User-Agent": "Mozilla/5.0 (novelty-assessment-pipeline)"}

logger = logging.getLogger("fetch_fulltext")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[fetch_fulltext] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


class FullTextFetcher:
    def __init__(self, grobid_server: str = "http://localhost:8070"):
        self.client = GrobidClient(grobid_server, timeout=180)
        self.parser = EnhancedGrobidParser()

    @staticmethod
    def _arxiv_id_by_title(title: str) -> str:
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
                if want and (want[:50] in etitle or etitle[:50] in want):
                    aid = entry.findtext(f"{ns}id") or ""
                    return aid.split("/abs/")[-1]
        except Exception:
            pass
        return ""

    @staticmethod
    def _try_download(url: str, dest: Path):
        """(ok, detail) of one download attempt."""
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
        """GET an S2 endpoint with adaptive backoff on 429/5xx (honours Retry-After)."""
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
            return r
        return None

    def ensure_pdf(self, paper: dict, pdfs_dir: Path, pin: dict = None) -> bool:
        """Ensure a valid {paper_id}.pdf exists, trying S2, Unpaywall/PMC and arXiv."""
        pid, title = paper["paper_id"], paper.get("title", "")
        dest = pdfs_dir / f"{pid}.pdf"

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "retrieval"))
        if not pin:
            logger.info(f"  refusing to fetch {pid} without a version verdict | {title[:45]}")
            return False

        if dest.exists():
            if self._is_valid_pdf(dest):
                recorded = (pin or {}).get("doc_sha256")
                if not pin or (recorded and recorded == self._sha256(dest)):
                    return True
                logger.info(
                    f"  cached PDF does not match the pinned "
                    f"{pin.get('version') or 'version'} -- discarding it"
                )
                dest.unlink()
                self._drop_derived_texts(pdfs_dir.parent, pid)
            else:
                dest.unlink()

        if pin and pin.get("url"):
            ok, detail = self._try_download(pin["url"], dest)
            if ok:
                logger.info(
                    f"  downloaded [{detail}] <- {pin['url']}  "
                    f"(pinned {pin.get('version', '?')} of {pin.get('version_date', '?')})"
                )
                return True
            logger.info(
                f"  download FAILED [{detail}] <- {pin['url']}  "
                f"(pinned {pin.get('version', '?')}; NOT falling back to the current version)"
            )
            return False

        urls, doi = [], paper.get("doi")

        ext = paper.get("externalIds") or {}
        if ext.get("ArXiv"):
            urls.append(f"https://arxiv.org/pdf/{ext['ArXiv']}.pdf")
        doi = doi or ext.get("DOI")

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

        if doi:
            m = re.search(r"10\.7554/elife\.(\d+)", doi, re.I)
            if m:
                urls.append(f"https://elifesciences.org/articles/{m.group(1)}.pdf")

        urls += self._unpaywall_pdf_urls(doi)
        if not any("arxiv.org" in u for u in urls):
            arx = self._arxiv_id_by_title(title)
            if arx:
                urls.append(f"https://arxiv.org/pdf/{arx}.pdf")

        urls = list(dict.fromkeys(urls))
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

    VERSIONS_FILE = "versions.json"

    _MANIFEST_LOCK = threading.RLock()

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
        """Every file derived from this paper's PDF, whichever parser produced it."""
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
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @staticmethod
    def _submission_date(data_dir: str, submission_id: str) -> str:
        """The date the prior-work cutoff is measured against."""
        meta_path = Path(data_dir) / submission_id / f"{submission_id}.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        return str(meta.get("publication_date") or meta.get("year") or "")

    def resolve_versions(
        self, data_dir: str, submission_id: str, paper_ids=None, force: bool = False
    ) -> dict:
        """Pin each paper to the newest version that is still prior work."""
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
        gap = pv.DEFAULT_MIN_GAP_DAYS

        def stale(pid: str) -> bool:
            """Is the recorded verdict still an answer to the question being asked?"""
            e = manifest.get(pid)
            if not e or not e.get("resolved_at"):
                return True
            return (
                e.get("submission_date") != str(sub_date) or int(e.get("min_gap_days") or -1) != gap
            )

        todo = [pid for pid in paper_ids if force or stale(pid)]
        requestioned = [
            pid for pid in todo if (manifest.get(pid) or {}).get("resolved_at") and not force
        ]
        if requestioned:
            logger.info(
                f"cutoff changed since {len(requestioned)} pin(s) were recorded "
                f"-- re-resolving them against {sub_date} / {gap}d"
            )
        logger.info(
            f"pinning versions against submission date {sub_date} "
            f"({len(todo)} to resolve, {len(paper_ids) - len(todo)} already recorded)"
        )

        for i, pid in enumerate(todo, 1):
            rec = by_id.get(pid)
            if rec is None:
                continue
            pin = pv.resolve_version(rec, sub_date)
            entry = pin.to_dict()
            entry["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            entry["record_date"] = rec.get("publication_date") or rec.get("year") or ""
            entry["title"] = rec.get("title", "")
            old = manifest.get(pid) or {}
            if old.get("version") == entry.get("version") and old.get("doc_sha256"):
                for k in (
                    "doc_sha256",
                    "downloaded_at",
                    "parsed_from_sha256",
                    "parsed_at",
                    "parsed_text_path",
                    "parsed_text_sha256",
                ):
                    if old.get(k):
                        entry[k] = old[k]
            manifest[pid] = entry

            title = rec.get("title", "")[:55]
            if pin.usable:
                logger.info(
                    f"[ver {i}/{len(todo)}] {pid} {title} -> "
                    f"{pin.status} {pin.version or '(single)'} {pin.version_date}"
                )
            else:
                logger.info(
                    f"[ver {i}/{len(todo)}] {pid} {title} -> {pin.status.upper()}: "
                    f"{pin.note} (latest {pin.latest_version} {pin.latest_version_date})"
                )

        self._save_versions(rwd, manifest)
        self._apply_version_abstracts(rwd, ranked, manifest)
        counts = {}
        for pid in paper_ids:
            counts[(manifest.get(pid) or {}).get("status", "unrecorded")] = (
                counts.get((manifest.get(pid) or {}).get("status", "unrecorded"), 0) + 1
            )
        logger.info(f"version pinning: {counts}")
        return manifest

    def pin_for_record(self, data_dir: str, submission_id: str, record: dict) -> dict:
        """Pin one paper that arrives after the batch pass."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "retrieval"))
        import paper_versions as pv

        pid = record.get("paper_id") or ""
        rwd, _, _ = self._dirs(data_dir, submission_id)
        manifest = self._load_versions(rwd)
        sub_date = self._submission_date(data_dir, submission_id)
        if not sub_date or not pid:
            return {}

        prev = manifest.get(pid) or {}
        if (
            prev.get("resolved_at")
            and prev.get("submission_date") == str(sub_date)
            and int(prev.get("min_gap_days") or -1) == pv.DEFAULT_MIN_GAP_DAYS
        ):
            return prev
        pin = pv.resolve_version(record, sub_date)
        entry = pin.to_dict()
        entry["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry["record_date"] = record.get("publication_date") or record.get("year") or ""
        entry["title"] = record.get("title", "")
        with self._MANIFEST_LOCK:
            manifest = self._load_versions(rwd)
            manifest[pid] = entry
            self._save_versions(rwd, manifest)
        if not pin.usable:
            logger.info(
                f"[ver] {pid} {record.get('title', '')[:55]} -> {pin.status.upper()}: {pin.note}"
            )
        return entry

    def record_pdf_hash(
        self, data_dir: str, submission_id: str, paper_id: str, pdf_path: Path
    ) -> str:
        """Bind the file now on disk to its manifest entry."""
        rwd, _, _ = self._dirs(data_dir, submission_id)
        with self._MANIFEST_LOCK:
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
        """Write the pinned version's abstract into ranked_papers.json."""
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
            json.dumps(ranked, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        if changed:
            logger.info(f"  replaced {changed} abstract(s) with the pinned version's own text")

    def download_pdfs(
        self, data_dir: str, submission_id: str, paper_ids=None, pin_versions: bool = True
    ) -> dict:
        """Ensure a PDF is on disk for each target paper. Returns {paper_id: bool}."""
        rwd, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        ranked = json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))
        by_id = {p["paper_id"]: p for p in ranked}

        if paper_ids is None:
            paper_ids = list(by_id)

        manifest = self.resolve_versions(data_dir, submission_id, paper_ids) if pin_versions else {}

        try:
            import progress as _progress
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

            if pin_versions and pin.get("status") not in self.USABLE_STATUSES:
                results[pid] = False
                logger.info(
                    f"[dl {idx + 1}/{n}] {pid}  {title} -> skipped "
                    f"({pin.get('status', 'unresolved')}: {pin.get('note', '')})"
                )
                continue

            if pdf_path.exists() and self._is_valid_pdf(pdf_path):
                on_disk = pin.get("doc_sha256")
                if not pin_versions or not pin:
                    results[pid] = True
                    logger.info(f"[dl {idx + 1}/{n}] {pid}  {title} -> already on disk")
                    continue
                if on_disk and on_disk == self._sha256(pdf_path):
                    results[pid] = True
                    logger.info(
                        f"[dl {idx + 1}/{n}] {pid}  {title} -> already on disk "
                        f"({pin.get('version') or 'single'})"
                    )
                    continue
                logger.info(
                    f"[dl {idx + 1}/{n}] {pid}  {title} -> cached PDF is not the "
                    f"pinned {pin.get('version') or 'version'}, re-fetching"
                )
                pdf_path.unlink()
                dropped = self._drop_derived_texts(rwd, pid)
                if dropped:
                    logger.info(f"  dropped {dropped} stale parsed text(s) with it")
            else:
                logger.info(f"[dl {idx + 1}/{n}] {pid}  {title}")

            t0 = time.time()
            ok = self.ensure_pdf(by_id[pid], pdfs_dir, pin=pin or None)
            results[pid] = ok
            if ok and pin_versions and pin:
                pin["doc_sha256"] = self._sha256(pdf_path)
                pin["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                manifest[pid] = pin
            if not ok:
                logger.info(f"  -> no_pdf (no downloadable PDF found)  [{time.time() - t0:.1f}s]")
            time.sleep(1)
        if _progress:
            _progress.report(n, n)
        if pin_versions and manifest:
            self._save_versions(rwd, manifest)
        n_ok = sum(1 for v in results.values() if v)
        logger.info(f"PDF download done: {n_ok}/{n} available on disk")
        return results

    def parse_one(self, data_dir: str, submission_id: str, paper_id: str) -> str:
        """Parse one downloaded PDF into sectioned full text."""
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
        out_path = ft_dir / f"{paper_id}.txt"
        out_path.write_text(text, encoding="utf-8")
        try:
            rwd, _, _ = self._dirs(data_dir, submission_id)
            with self._MANIFEST_LOCK:
                manifest = self._load_versions(rwd)
                entry = manifest.get(paper_id)
                if entry is not None:
                    entry["parsed_from_sha256"] = self._sha256(pdf_path)
                    entry["parsed_text_path"] = out_path.relative_to(rwd).as_posix()
                    entry["parsed_text_sha256"] = self._sha256(out_path)
                    entry["parsed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    manifest[paper_id] = entry
                    self._save_versions(rwd, manifest)
        except Exception as e:
            logger.info(f"[parse] {paper_id}: could not record provenance ({type(e).__name__})")
        logger.info(f"[parse] {paper_id} -> ok ({len(text)} chars)  [{time.time() - t0:.1f}s]")
        return "ok"

    def fetch(self, data_dir: str, submission_id: str, paper_ids=None) -> dict:
        """Download and parse every target paper."""
        rwd, pdfs_dir, ft_dir = self._dirs(data_dir, submission_id)
        by_id = {
            p["paper_id"]: p
            for p in json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))
        }
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
            results[pid] = (
                f"ok ({(ft_dir / f'{pid}.txt').stat().st_size} chars)" if status == "ok" else status
            )
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
    ap = argparse.ArgumentParser(
        description="Phase 2: fetch full text (PDF download + GROBID) for candidates"
    )
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--server", default="http://localhost:8070")
    ap.add_argument(
        "--paper-ids",
        nargs="*",
        default=None,
        help="specific paper ids (default: all pool papers lacking full text)",
    )
    args = ap.parse_args()

    results = FullTextFetcher(args.server).fetch(args.data_dir, args.submission_id, args.paper_ids)
    ok = sum(1 for v in results.values() if v.startswith("ok"))
    print(f"Full-text fetch: {ok}/{len(results)} succeeded")
    for pid, status in results.items():
        print(f"  {status:28} {pid}")


if __name__ == "__main__":
    main()
