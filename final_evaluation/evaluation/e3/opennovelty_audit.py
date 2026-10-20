"""E3 for OpenNovelty: are the passages it shows from prior work real, and is that work prior?

Added 2026-10-01, after E1 and after E3's automatic part (PROTOCOL 8c); descriptive, no test.
Of the three external systems only OpenNovelty shows passages from prior work: each "Prior Art
Analysis" carries "Evidence k - Rationale: ... - Original: <submission> - Candidate: <prior
paper>". Afzal et al. and DeepReviewer 2.0 quote the submission only (checked: every quoted
span of DeepReviewer is in the submission; Afzal's are the authors' phrases, titles and
category names), so they have nothing to audit here.

Per evidence item:
  candidate quote   looked up in the candidate paper's full text (arXiv PDF, or the open-access
                    PDF Semantic Scholar names), same normalisation and threshold as E3:
                    exact substring, or rapidfuzz partial_ratio >= 90; else not found. A
                    candidate whose text cannot be fetched is "not auditable".
  original quote    looked up in the submission text the same way.
  candidate date    first public date (arXiv v1, else Semantic Scholar) against the
                    submission's `publication_date`; the candidate being the submission itself
                    (same arXiv id or same title) is counted separately.

Read-only on the frozen inputs; network only for the candidate papers. The fetched PDFs are
cached and their sha256 recorded in the output.

  python -m final_evaluation.evaluation.e3.opennovelty_audit [--cache DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import fitz
from rapidfuzz import fuzz

from final_evaluation.evaluation import agent_linear as al

FE = al.FE
OUT = FE / "results" / "main" / "e3" / "opennovelty_audit.json"
NEAR = 90.0
UA = {"User-Agent": "novelty-thesis-e3-audit/1.0 (academic research)"}


def _s2_key() -> str | None:
    """The Semantic Scholar key from the environment or the repo's .env; never printed."""
    import os
    k = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if k:
        return k
    env = al.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SEMANTIC_SCHOLAR_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"') or None
    return None


S2_KEY = _s2_key()


def _s2(path: str):
    """GET on the Semantic Scholar graph API, retrying on rate limits; None if not found."""
    url = "https://api.semanticscholar.org/graph/v1/" + path
    hdr = dict(UA, **({"x-api-key": S2_KEY} if S2_KEY else {}))
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=30) as r:
                time.sleep(1.1)
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(4 * (k + 1))
        except Exception:
            time.sleep(4 * (k + 1))
    return None


def direct_pdf(uri: str) -> str | None:
    """Venue pages whose PDF sits at a fixed, derivable address."""
    if "proceedings.neurips.cc" in uri and "-Abstract" in uri:
        return re.sub(r"-Abstract(-\w+)?\.html$", lambda m: "-Paper" + (m.group(1) or "") + ".pdf",
                      uri.replace("/hash/", "/file/"))
    if "aclanthology.org" in uri:
        return uri if uri.endswith(".pdf") else uri.rstrip("/") + ".pdf"
    if "openaccess.thecvf.com" in uri and uri.endswith(".html"):
        return uri.replace("/html/", "/papers/").replace(".html", ".pdf")
    if "openreview.net" in uri:
        oid = re.search(r"id=([^&]+)", uri)
        return f"https://openreview.net/pdf?id={oid.group(1)}" if oid else None
    return None


def squash(t: str) -> str:
    """Lowercase letters and digits only: OpenNovelty's text is lowercased and its word
    boundaries are unreliable ("proposescalinginter- rl"), so spaces cannot be compared."""
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _find_one(q: str, text_squashed: str) -> str:
    if q in text_squashed:
        return "exact"
    return "near" if fuzz.partial_ratio(q, text_squashed) >= NEAR else "not_found"


def find(quote: str, text_squashed: str) -> str:
    """OpenNovelty elides with "..." inside a quote, so each piece between ellipses is looked up
    on its own (pieces under 20 characters are too short to place); the quote is found when
    every piece is, and is "near" when any piece needed the fuzzy match."""
    pieces = [squash(p) for p in re.split(r"\.{3}|…", quote)]
    pieces = [p for p in pieces if len(p) >= 20]
    if not pieces:
        return "too_short"
    res = [_find_one(p, text_squashed) for p in pieces]
    if "not_found" in res:
        return "not_found"
    return "near" if "near" in res else "exact"


def pdf_text_with_links(path: Path) -> str:
    """The PDF's text with each link's target written after its anchor text as <<uri>>."""
    doc = fitz.open(path)
    parts = []
    for page in doc:
        links = [l for l in page.get_links() if l.get("uri")]
        prev_uri, prev_line = None, None
        for w in page.get_text("words"):
            r = fitz.Rect(w[:4])
            uri = next((l["uri"] for l in links
                        if (r & fitz.Rect(l["from"])).get_area() > 0.5 * r.get_area()), None)
            if prev_line is not None and (w[5], w[6]) != prev_line:
                parts.append("\n")
            if prev_uri and uri != prev_uri:
                parts.append(f" <<{prev_uri}>> ")
            parts.append(w[4] + " ")
            prev_uri, prev_line = uri, (w[5], w[6])
        if prev_uri:
            parts.append(f" <<{prev_uri}>> ")
        parts.append("\n")
    return "".join(parts)


# A candidate title can wrap over up to three lines before its "URL: View paper" link.
_CAND = re.compile(r"(?m)^(\d+)\.\s+((?:(?!URL:)[^\n]*\n){1,3}?)\s*URL:\s*View paper\s*<<([^>]+)>>")
_EVID = re.compile(r"Evidence\s+(\d+)\s*-\s*Rationale:(.*?)-\s*Original:(.*?)-\s*Candidate:(.*?)"
                   r"(?=Evidence\s+\d+\s*-\s*Rationale:|\n\s*\d+\.\s+\S|\Z)", re.S)


def evidence_items(text: str) -> list:
    """[(candidate number, title, uri, original quote, candidate quote)] in document order."""
    heads = list(_CAND.finditer(text))
    items = []
    for i, h in enumerate(heads):
        block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        title = " ".join(h.group(2).split())
        for e in _EVID.finditer(block):
            orig = " ".join(e.group(3).split())
            # the last item of a report runs into the appendix that follows it
            cand = re.split(r"\s+Appendix:", " ".join(e.group(4).split()))[0]
            items.append({"candidate_no": int(h.group(1)), "title": title, "uri": h.group(3),
                          "original": orig, "candidate": cand})
    return items


def _get(url: str, binary=False, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except Exception:
            time.sleep(3 * (k + 1))
    return None


def arxiv_id(uri: str) -> str | None:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})|10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})",
                  uri, re.I)
    return (m.group(1) or m.group(2)) if m else None


def resolve(uri: str, title: str, meta_cache: dict) -> dict:
    """{arxiv, pdf_url, date, how} for a candidate link."""
    if uri in meta_cache:
        return meta_cache[uri]
    out = {"arxiv": arxiv_id(uri), "pdf_url": None, "date": None, "how": None}
    fields = "title,externalIds,publicationDate,openAccessPdf"
    m = re.search(r"semanticscholar\.org/paper/([0-9a-f]{40})", uri)
    doi = re.search(r"(?:doi\.org/|/doi/(?:abs/|full/|pdf/)?)(10\.\d{4,9}/[^?#\s]+)", uri)
    d = None
    if m:
        d = _s2(f"paper/{m.group(1)}?fields={fields}")
    elif out["arxiv"]:
        d = _s2(f"paper/arXiv:{out['arxiv']}?fields={fields}")
    elif doi:
        d = _s2(f"paper/DOI:{doi.group(1)}?fields={fields}")
    if d is None and not out["arxiv"]:
        r = _s2(f"paper/search/match?query={urllib.parse.quote(title[:250])}&fields={fields}")
        d = (r.get("data") or [None])[0] if r else None
    if d:
        out["arxiv"] = out["arxiv"] or (d.get("externalIds") or {}).get("ArXiv")
        out["date"] = d.get("publicationDate")
        out["s2_title"] = d.get("title")
        out["pdf_url"] = (d.get("openAccessPdf") or {}).get("url") or None
        out["how"] = "s2_open_access" if out["pdf_url"] else None
    if out["arxiv"]:
        feed = _get(f"http://export.arxiv.org/api/query?id_list={out['arxiv']}")
        time.sleep(3)
        mm = re.search(r"<published>(\d{4}-\d{2}-\d{2})", feed or "")
        if mm:
            out["date"] = mm.group(1)            # arXiv v1 = first public version
        t = re.search(r"<entry>.*?<title>(.*?)</title>", feed or "", re.S)
        out["arxiv_title"] = " ".join(t.group(1).split()) if t else None
        out["pdf_url"], out["how"] = f"https://arxiv.org/pdf/{out['arxiv']}", "arxiv"
    if not out["pdf_url"] and direct_pdf(uri):
        out["pdf_url"], out["how"] = direct_pdf(uri), "venue_pdf"
    meta_cache[uri] = out
    return out


def fulltext(pdf_url: str, cache: Path) -> tuple[str | None, str | None]:
    f = cache / (hashlib.sha1(pdf_url.encode()).hexdigest() + ".pdf")
    if not f.exists():
        data = _get(pdf_url, binary=True)
        time.sleep(2)
        if not data or not data[:5] == b"%PDF-":
            return None, None
        f.write_bytes(data)
    try:
        text = "".join(p.get_text() for p in fitz.open(f))
    except Exception:
        return None, None
    return text, hashlib.sha256(f.read_bytes()).hexdigest()


def main(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    meta_file = cache / "_meta.json"
    meta_cache = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    text_cache, rows = {}, []
    for _, paper, entry in al.paper_entries():
        sub_dir = al.ROOT / "data" / paper
        sub_meta = json.loads((sub_dir / f"{paper}.json").read_text(encoding="utf-8"))
        sub_date = sub_meta.get("publication_date") or "9999"
        inp = next(p for p in (FE / "inputs").glob(f"*/{paper}") if (p / "opennovelty.pdf").exists())
        sub_sq = squash((inp / "submission.txt").read_text(encoding="utf-8", errors="ignore"))
        sub_title = squash(sub_meta.get("title") or "")[:60]
        for it in evidence_items(pdf_text_with_links(inp / "opennovelty.pdf")):
            m = resolve(it["uri"], it["title"], meta_cache)
            text, sha = (None, None)
            if m.get("pdf_url"):
                if m["pdf_url"] not in text_cache:
                    text_cache[m["pdf_url"]] = fulltext(m["pdf_url"], cache)
                text, sha = text_cache[m["pdf_url"]]
            titles = {squash(t)[:60] for t in (m.get("arxiv_title"), m.get("s2_title"), it["title"]) if t}
            is_self = bool(sub_title) and sub_title in titles
            rows.append({
                "paper": paper, **it, "resolved_via": m.get("how"), "arxiv": m.get("arxiv"),
                "pdf_url": m.get("pdf_url"), "pdf_sha256": sha,
                "candidate_date": m.get("date"), "submission_date": sub_date,
                "candidate_is_submission": is_self,
                "candidate_before_submission": (None if not m.get("date") or is_self
                                                else m["date"] < sub_date),
                "candidate_quote": find(it["candidate"], squash(text)) if text else "not_auditable",
                "original_quote": find(it["original"], sub_sq),
            })
            print(f"{paper[:28]:28} #{it['candidate_no']:<2} {rows[-1]['candidate_quote']:13} "
                  f"orig={rows[-1]['original_quote']:9} date={m.get('date')} self={is_self} "
                  f"{it['title'][:50]}")

    def share(key, val, among=None):
        pool = [r for r in rows if among is None or among(r)]
        return {"n": len(pool), "count": sum(r[key] == val for r in pool)}
    summary = {
        "post_hoc": "added 2026-10-01 after E1 and E3 (8c); descriptive, no test",
        "evidence_items": len(rows),
        "papers_with_evidence": len({r["paper"] for r in rows}),
        "candidate_quote": {k: sum(r["candidate_quote"] == k for r in rows)
                            for k in ("exact", "near", "not_found", "not_auditable", "too_short")},
        "original_quote": {k: sum(r["original_quote"] == k for r in rows)
                           for k in ("exact", "near", "not_found", "too_short")},
        "candidate_is_submission": sum(r["candidate_is_submission"] for r in rows),
        "candidate_not_before_submission": sum(r["candidate_before_submission"] is False for r in rows),
        "candidate_undated": sum(r["candidate_before_submission"] is None and not r["candidate_is_submission"]
                                 for r in rows),
    }
    meta_file.write_text(json.dumps(meta_cache, indent=1), encoding="utf-8")
    OUT.write_text(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print("written:", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(FE / "results" / "main" / "e3" / "_opennovelty_pdfs"))
    main(Path(ap.parse_args().cache))
