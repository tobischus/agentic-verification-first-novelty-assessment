"""Additional Semantic Scholar search for a claim when its prior-work pool is empty.

New candidates pass the same admissibility rule as the main retrieval and are ranked by
embedding similarity to the claim.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "retrieval"))
import paper_versions as pv

logger = logging.getLogger("retrieve_more")

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,paperId,publicationDate,year,venue,authors,citationCount,externalIds"


def _same_paper(
    candidate_abstract: str,
    submission_abstract: str,
    n: int = 10,
    min_shared: int = 2,
    token_ratio: float = 95.0,
) -> bool:
    """Same rule as retrieval.is_same_paper: shared ten-word sequences in the abstracts."""
    ca = (candidate_abstract or "").strip()
    sa = (submission_abstract or "").strip()
    if len(ca) < 80 or len(sa) < 80 or "no abstract available" in ca.lower():
        return False

    def shingles(t):
        w = re.findall(r"[a-z0-9]+", t.lower())
        return {" ".join(w[i : i + n]) for i in range(len(w) - n + 1)} if len(w) >= n else set()

    if len(shingles(ca) & shingles(sa)) >= min_shared:
        return True
    return fuzz.token_set_ratio(ca.lower(), sa.lower()) >= token_ratio


def _s2_get(url: str, params: dict, headers: dict, max_attempts: int = 5):
    """GET with backoff on 429 and 5xx responses."""
    delay = 2.0
    for _ in range(max_attempts):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
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


def _to_paper(d: dict) -> dict:
    ext = d.get("externalIds") or {}
    authors = ", ".join(a.get("name", "") for a in (d.get("authors") or []))
    return {
        "paper_id": d.get("paperId") or "",
        "title": d.get("title") or "",
        "abstract": d.get("abstract") or "",
        "year": str(d.get("year")) if d.get("year") else "",
        "publication_date": d.get("publicationDate") or "",
        "venue": d.get("venue") or "",
        "authors": authors,
        "citation_count": d.get("citationCount") or 0,
        "externalIds": ext,
        "doi": ext.get("DOI"),
        "cited_paper": False,
    }


def is_valid_prior_work(
    paper: dict,
    source_title: Optional[str],
    source_pub_date: Optional[str],
    source_year: Optional[int],
    source_abstract: Optional[str] = None,
) -> bool:
    """Not the submission itself and dated at least 90 days before it (Equation 3.1)."""
    title = (paper.get("title") or "").lower()
    if source_title and fuzz.ratio(title, source_title.lower()) >= 90:
        return False
    if source_abstract and _same_paper(paper.get("abstract", ""), source_abstract):
        return False

    stated = paper.get("publication_date") or paper.get("year")
    source_stated = source_pub_date or (str(source_year) if source_year else "")
    verdict = pv.gap_verdict(stated, source_stated, pv.DEFAULT_MIN_GAP_DAYS)
    if verdict != "ok":
        logger.info(
            "retrieve_more: not prior work (%s): %r vs submission %r | %s",
            verdict,
            stated,
            source_stated,
            (paper.get("title") or "")[:60],
        )
    return verdict == "ok"


def retrieve(
    query: str,
    claim: dict,
    embedder,
    exclude_ids: set,
    source_title: Optional[str] = None,
    source_pub_date: Optional[str] = None,
    source_year: Optional[int] = None,
    source_abstract: Optional[str] = None,
    k: int = 10,
    max_from_s2: int = 25,
) -> List[dict]:
    """New admissible candidates for a claim, ranked by similarity to the claim."""
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    headers = {"X-API-KEY": key} if key and key != "---" else {}
    params = {"query": query, "fields": _FIELDS, "limit": max_from_s2}
    if source_year:
        params["year"] = f"-{source_year}"

    r = _s2_get(_S2_SEARCH, params, headers)
    if r is None or r.status_code != 200:
        return []
    items = (r.json() or {}).get("data") or []

    fresh = []
    seen = set(exclude_ids)
    for it in items:
        p = _to_paper(it)
        pid = p["paper_id"]
        if not pid or pid in seen or not p["title"] or not p["abstract"]:
            continue
        if not is_valid_prior_work(p, source_title, source_pub_date, source_year, source_abstract):
            continue
        seen.add(pid)
        fresh.append(p)
    if not fresh:
        return []

    claim_doc = f"{claim.get('name', '')}. {claim.get('description', '')} {claim.get('claim_text', '')}".strip()
    cand_docs = [f"{p['title']}. {p['abstract']}" for p in fresh]
    embs = embedder.encode([claim_doc] + cand_docs, convert_to_numpy=True)
    claim_emb, cand_embs = embs[0], embs[1:]
    sims = (
        cand_embs
        @ claim_emb
        / (np.linalg.norm(cand_embs, axis=1) * np.linalg.norm(claim_emb) + 1e-9)
    )
    order = np.argsort(-sims)[:k]
    out = []
    for idx in order:
        p = dict(fresh[idx])
        p["similarity"] = float(sims[idx])
        out.append(p)
    return out
