"""GROBID client: PDF to TEI XML, then the pipeline's {id}.json via EnhancedGrobidParser."""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_metadata import EnhancedGrobidParser

DEFAULT_SERVER = "http://localhost:8070"


class GrobidClient:
    """Minimal client around the GROBID REST API."""

    def __init__(self, server_url: str = DEFAULT_SERVER, timeout: int = 300):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout

    def is_alive(self) -> bool:
        """Return True if the GROBID server responds to /api/isalive."""
        try:
            r = requests.get(f"{self.server_url}/api/isalive", timeout=10)
            return r.status_code == 200 and r.text.strip().lower() == "true"
        except requests.RequestException:
            return False

    def wait_until_alive(self, retries: int = 60, delay: float = 2.0) -> bool:
        """Poll the server until it is alive or retries are exhausted."""
        for _ in range(retries):
            if self.is_alive():
                return True
            time.sleep(delay)
        return False

    def pdf_to_tei(self, pdf_path: str) -> str:
        """POST a PDF to processFulltextDocument and return the TEI XML string."""
        pdf = Path(pdf_path)
        if not pdf.exists():
            raise FileNotFoundError(f"PDF not found: {pdf}")

        url = f"{self.server_url}/api/processFulltextDocument"
        data = {
            "segmentSentences": "1",
            "includeRawCitations": "1",
            "consolidateHeader": "0",
            "consolidateCitations": "0",
        }
        with open(pdf, "rb") as fh:
            files = {"input": (pdf.name, fh, "application/pdf")}
            resp = requests.post(url, files=files, data=data, timeout=self.timeout)

        if resp.status_code != 200:
            raise RuntimeError(
                f"GROBID returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return resp.text

    def process_for_pipeline(
        self,
        pdf_path: str,
        data_dir: str,
        submission_id: str,
        recover_missing_title: bool = True,
        title_model: str = "gpt-4.1",
    ) -> dict:
        """PDF -> TEI -> {id}.json + {id}_fulltext.json + {id}_quality.json."""
        if not self.is_alive():
            logging.warning(
                f"GROBID not reachable at {self.server_url}; waiting up to ~90s for it…"
            )
            if not self.wait_until_alive(retries=30, delay=3.0):
                raise ConnectionError(
                    f"GROBID server not reachable at {self.server_url}. Start it with:\n"
                    f"  docker run -d --init --ulimit core=0 -p 8070:8070 "
                    f"--restart unless-stopped --name grobid grobid/grobid:0.9.0-crf"
                )

        tei = self.pdf_to_tei(pdf_path)

        sub_dir = Path(data_dir) / submission_id
        sub_dir.mkdir(parents=True, exist_ok=True)
        tei_path = sub_dir / f"{submission_id}.grobid.tei.xml"
        tei_path.write_text(tei, encoding="utf-8")
        logging.info(f"Saved TEI -> {tei_path}")

        parser = EnhancedGrobidParser()
        parser.process_for_pipeline(str(tei_path), data_dir, submission_id)
        json_path = sub_dir / f"{submission_id}.json"

        if recover_missing_title:
            self._resolve_title(json_path, pdf_path, title_model)

        self._resolve_date(json_path, tei_path)

        from lxml import etree

        root = etree.parse(str(tei_path))
        sections = parser.extract_full_text_sections(root)
        fulltext_path = sub_dir / f"{submission_id}_fulltext.json"
        fulltext_path.write_text(
            json.dumps(
                {
                    "sections": sections,
                    "n_sections": len(sections),
                    "n_chars": sum(len(s["text"]) for s in sections),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        from quality_gates import compute_quality_gates

        metadata = json.loads(json_path.read_text(encoding="utf-8"))
        report = compute_quality_gates(metadata, sections)
        quality_path = sub_dir / f"{submission_id}_quality.json"
        quality_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logging.info(f"Saved metadata JSON -> {json_path}")
        logging.info(
            f"Saved full text -> {fulltext_path} "
            f"({report['counts']['full_text_chars']} chars, {len(sections)} sections)"
        )
        gate_status = (
            "ALL PASSED"
            if report["all_passed"]
            else "FAILED: " + ", ".join(report["failed_gates"])
        )
        logging.info(f"Quality gates: {gate_status}")

        return {
            "submission_id": submission_id,
            "metadata_json": str(json_path),
            "fulltext_json": str(fulltext_path),
            "quality_json": str(quality_path),
            "quality": report,
        }

    @staticmethod
    def _resolve_date(json_path: Path, tei_path: Path) -> None:
        """Record the submission's own date (year + publication_date) in the JSON."""
        from datetime import date
        from lxml import etree

        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        data = json.loads(json_path.read_text(encoding="utf-8"))
        year = pub_date = source = None

        looked_up = GrobidClient._lookup_submission_date(data.get("title", ""))
        if looked_up:
            pub_date, year, source = looked_up

        if year is None:
            try:
                root = etree.parse(str(tei_path))
                hdr = root.find(".//tei:teiHeader", ns)
                if hdr is not None:
                    els = hdr.xpath(
                        ".//tei:sourceDesc//tei:biblStruct//tei:monogr//tei:imprint"
                        "//tei:date[@when]",
                        namespaces=ns,
                    )
                    for e in els:
                        when = (e.get("when") or "").strip()
                        if len(when) >= 4 and when[:4].isdigit():
                            year = when[:4]
                            pub_date = when if len(when) >= 10 else f"{year}-01-01"
                            source = "grobid_header"
                            break
            except Exception as exc:
                logging.warning(f"TEI date extraction failed ({exc})")

        if year is None:
            today = date.today()
            year, pub_date, source = str(today.year), today.isoformat(), "today_fallback"

        data["year"] = year
        data["publication_date"] = pub_date
        data["date_source"] = source
        data["date_needs_review"] = source == "today_fallback"
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logging.info(
            f"Resolved submission date ({source}): year={year}, date={pub_date}"
        )

    @staticmethod
    def _norm_title(s: str) -> str:
        """Title normalized for matching: lowercase, without whitespace and hyphens."""
        return "".join((s or "").lower().split()).replace("-", "")

    @staticmethod
    def _dehyphenate(text: str) -> str:
        """Join intra-word hyphens ('LAN-GUAGE' -> 'LANGUAGE') and collapse whitespace."""
        import re

        return " ".join(re.sub(r"(?<=\w)-(?=\w)", "", text or "").split())

    @staticmethod
    def _title_variants(title: str):
        """Full title + cleaned query variants to try, most specific first."""
        import re

        title = GrobidClient._dehyphenate((title or "").strip())
        out = [title]
        parts = re.split(r"\.\s+", title)
        if len(parts) > 1:
            first = parts[0].strip().rstrip(".")
            if 15 <= len(first) < len(title):
                out.append(first)
        if ":" in title:
            head, _, tail = title.partition(":")
            for seg in (head.strip(), tail.strip()):
                if 15 <= len(seg) < len(title):
                    out.append(seg)
        seen, uniq = set(), []
        for v in out:
            k = v.lower()
            if v and k not in seen:
                seen.add(k)
                uniq.append(v)
        return uniq

    @staticmethod
    def _title_close(a: str, b: str) -> bool:
        """Title match by normalized prefix or high fuzzy similarity."""
        from rapidfuzz import fuzz

        na, nb = GrobidClient._norm_title(a), GrobidClient._norm_title(b)
        if not na or not nb:
            return False
        if na[:60] in nb or nb[:60] in na:
            return True
        return fuzz.token_set_ratio((a or "").lower(), (b or "").lower()) >= 90

    @staticmethod
    def _arxiv_get(params, attempts: int = 3):
        """GET the arXiv API with backoff on 429/503. Returns the response or None."""
        import requests

        for i in range(attempts):
            try:
                r = requests.get("http://export.arxiv.org/api/query", params=params, timeout=25)
            except Exception as exc:
                logging.warning(f"arXiv request failed ({exc})")
                return None
            if r.status_code in (429, 503):
                time.sleep(3 * (i + 1))
                continue
            return r if r.status_code == 200 else None
        return None

    @staticmethod
    def _lookup_submission_date(title: str):
        """Resolve the submission's date for the retrieval cutoff (best-effort)."""
        title = (title or "").strip()
        if len(title) < 10:
            return None

        pub = GrobidClient._arxiv_search_v1(title)
        if pub and len(pub) >= 4:
            return pub[:10], pub[:4], "arxiv_v1"

        s2 = GrobidClient._s2_match(title)
        if not s2:
            return None
        arxiv_id = ((s2.get("externalIds") or {}).get("ArXiv") or "").strip()
        if arxiv_id:
            v1 = GrobidClient._arxiv_v1_date(arxiv_id)
            if v1 and len(v1) >= 4:
                return v1[:10], v1[:4], "arxiv_v1"
        pub = (s2.get("publicationDate") or "").strip()
        yr = s2.get("year")
        if pub and len(pub) >= 4:
            return pub, (str(yr) if yr else pub[:4]), "semantic_scholar"
        if yr:
            return f"{yr}-01-01", str(yr), "semantic_scholar"
        return None

    @staticmethod
    def _arxiv_search_v1(title: str):
        """v1 'published' date for a paper found on arXiv by title (or None)."""
        import re

        from lxml import etree

        ns = {"a": "http://www.w3.org/2005/Atom"}

        def _query(search_query):
            r = GrobidClient._arxiv_get({"search_query": search_query, "max_results": 8})
            if r is None:
                return []
            root = etree.fromstring(r.content)
            out = []
            for e in root.findall(".//a:entry", ns):
                et = e.findtext("a:title", default="", namespaces=ns)
                pub = (e.findtext("a:published", default="", namespaces=ns) or "").strip()
                if et and pub:
                    out.append((et, pub))
            return out

        for q in GrobidClient._title_variants(title):
            words = re.findall(r"[A-Za-z0-9]+", q)
            if len(words) < 3:
                continue
            phrase = " ".join(words[:12])
            try:
                for sq in (f'ti:"{phrase}"', f"ti:{phrase}"):
                    for et, pub in _query(sq):
                        if GrobidClient._title_close(title, et):
                            return pub
            except Exception as exc:
                logging.warning(f"arXiv title search failed ({exc})")
                continue
        return None

    @staticmethod
    def _arxiv_v1_date(arxiv_id: str):
        """v1 'published' date for an exact arXiv id, via the arXiv API (or None)."""
        from lxml import etree

        arxiv_id = (arxiv_id or "").strip()
        if not arxiv_id:
            return None
        r = GrobidClient._arxiv_get({"id_list": arxiv_id, "max_results": 1})
        if r is None:
            return None
        try:
            root = etree.fromstring(r.content)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            pub = root.findtext(".//a:entry/a:published", default="", namespaces=ns)
            return (pub or "").strip() or None
        except Exception as exc:
            logging.warning(f"arXiv v1 date lookup failed ({exc})")
            return None

    @staticmethod
    def _s2_get(url: str, params: dict, headers: dict, attempts: int = 4):
        """GET a Semantic Scholar endpoint with 429 backoff. Returns Response or None."""
        import requests

        for i in range(attempts):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=20)
            except Exception as exc:
                logging.warning(f"S2 request failed ({exc})")
                return None
            if r.status_code == 429:
                time.sleep(1.5 * (i + 1))
                continue
            return r
        return None

    @staticmethod
    def _s2_match(title: str):
        """Semantic Scholar lookup by title. Returns the raw item or None."""
        import os

        key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        headers = {"X-API-KEY": key} if key and key != "---" else {}
        fields = "title,publicationDate,year,externalIds"
        match_url = "https://api.semanticscholar.org/graph/v1/paper/search/match"
        search_url = "https://api.semanticscholar.org/graph/v1/paper/search"

        for q in GrobidClient._title_variants(title):
            r = GrobidClient._s2_get(match_url, {"query": q, "fields": fields}, headers)
            if r is None or r.status_code != 200:
                continue
            items = (r.json() or {}).get("data") or []
            if items and GrobidClient._title_close(title, items[0].get("title", "")):
                return items[0]

        r = GrobidClient._s2_get(search_url, {"query": title, "limit": 5, "fields": fields}, headers)
        if r is not None and r.status_code == 200:
            for it in (r.json() or {}).get("data") or []:
                if GrobidClient._title_close(title, it.get("title", "")):
                    return it
        return None

    @staticmethod
    def _resolve_title(json_path: Path, pdf_path: str, title_model: str) -> None:
        """Clean/recover the title in the produced JSON and record its source."""
        from title_fallback import resolve_title

        data = json.loads(json_path.read_text(encoding="utf-8"))
        title, source = resolve_title(data.get("title"), pdf_path, model=title_model)
        data["title"] = title
        data["title_source"] = source
        data["title_needs_review"] = source != "grobid"
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logging.info(f"Resolved title ({source}): {title!r}")


def main():
    ap = argparse.ArgumentParser(
        description="PDF -> GROBID TEI -> pipeline {id}.json"
    )
    ap.add_argument("--pdf", required=True, help="Path to the submission PDF")
    ap.add_argument("--data-dir", required=True, help="Base data directory")
    ap.add_argument("--submission-id", required=True, help="Submission ID")
    ap.add_argument("--server", default=DEFAULT_SERVER, help="GROBID server URL")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    client = GrobidClient(args.server)
    result = client.process_for_pipeline(
        args.pdf, args.data_dir, args.submission_id
    )
    q = result["quality"]
    c = q["counts"]
    status = (
        "ALL PASSED"
        if q["all_passed"]
        else "FAILED: " + ", ".join(q["failed_gates"])
    )
    print(f"OK -> {result['metadata_json']}")
    print(f"   full text : {c['full_text_chars']} chars in {c['sections']} sections")
    print(f"   references: {c['cited_papers']} | citation contexts: {c['citation_contexts']}")
    print(f"   quality gates: {status}")
    if q["title_needs_review"]:
        print(f"   NOTE: title via {q['title_source']} -> needs reviewer confirmation")


if __name__ == "__main__":
    main()
