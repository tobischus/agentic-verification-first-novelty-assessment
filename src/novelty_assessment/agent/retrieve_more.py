#!/usr/bin/env python3
"""
On-demand Semantic Scholar retrieval for the agent (the R7 re-entry mechanism).

When the finish-gate escalates ("frontier unprobed / insufficient evidence"), the
agent calls retrieve_more(query). This runs a fresh S2 search, applies the same
submission-date cutoff as the pipeline (prior work only), dedups against the
current pool, and ranks the new candidates by SPECTER2 similarity to the CLAIM.

Kept deliberately light: it does the S2 fetch + ranking with a shared embedder
(no second SPECTER2 load, no PaperRankingSystem init). Persistence into
agent_retrieved_papers.json and optional full-text fetch are handled by the
toolbox, so provenance stays separate from the initial ranked_papers.json.
"""
import os
import re
import time
from datetime import datetime
from typing import List, Optional

import numpy as np
import requests
from rapidfuzz import fuzz

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,paperId,publicationDate,year,venue,authors,citationCount,externalIds"


def _same_paper(candidate_abstract: str, submission_abstract: str,
                n: int = 10, min_shared: int = 2, token_ratio: float = 95.0) -> bool:
    """Mirror of retrieval.is_same_paper: detect the submission's own (possibly renamed)
    version by shared long verbatim abstract n-grams -- different papers on the same topic
    essentially never share a 10-word span, two versions of one paper share several even
    after heavy editing. Kept local to avoid importing the heavy retrieval module."""
    ca = (candidate_abstract or "").strip()
    sa = (submission_abstract or "").strip()
    if len(ca) < 80 or len(sa) < 80 or "no abstract available" in ca.lower():
        return False

    def shingles(t):
        w = re.findall(r"[a-z0-9]+", t.lower())
        return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)} if len(w) >= n else set()

    if len(shingles(ca) & shingles(sa)) >= min_shared:
        return True
    return fuzz.token_set_ratio(ca.lower(), sa.lower()) >= token_ratio


def _s2_get(url: str, params: dict, headers: dict, max_attempts: int = 5):
    """GET with adaptive backoff on 429/5xx (honours Retry-After)."""
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
        return r  # genuine 4xx -> no point retrying
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
    """Same admissibility rule as retrieval.merge_paper_collections.is_valid_paper:
    exclude the submission itself (near-duplicate title OR near-duplicate abstract, which
    catches a renamed earlier version) and any paper not clearly published BEFORE the
    submission (>=90 days older with full dates; strictly earlier year otherwise; rejected
    when no usable date)."""
    title = (paper.get("title") or "").lower()
    # self / near-duplicate exclusion (title, then abstract for renamed versions)
    if source_title and fuzz.ratio(title, source_title.lower()) >= 90:
        return False
    if source_abstract and _same_paper(paper.get("abstract", ""), source_abstract):
        return False
    pdate = paper.get("publication_date")
    # PRIORITY 1: full dates on both sides -> must be >3 months older than the submission
    if source_pub_date and pdate:
        try:
            pub = datetime.strptime(pdate, "%Y-%m-%d")
            src = datetime.strptime(source_pub_date, "%Y-%m-%d")
            return (src - pub).days >= 90
        except ValueError:
            pass
    # PRIORITY 2: years only -> must be a strictly earlier year
    py = paper.get("year") or (pdate[:4] if pdate else None)
    if source_year and py:
        try:
            return int(py) < int(source_year)
        except (ValueError, TypeError):
            pass
    # PRIORITY 3: no usable date -> reject (conservative, same as the pipeline)
    return False


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
    """Fetch + rank new prior-work candidates for a claim. Returns top-k paper dicts.

    Applies the SAME cutoff/self-exclusion rule as the main retrieval, so the agent
    can only bring in prior work published before the submission (never the submission
    itself or papers newer than it).

    embedder: a loaded SentenceTransformer (SPECTER2), shared with the toolbox.
    exclude_ids: paper_ids already in the pool (initial + agent + reviewer).
    """
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    headers = {"X-API-KEY": key} if key and key != "---" else {}
    params = {"query": query, "fields": _FIELDS, "limit": max_from_s2}
    if source_year:  # coarse pre-filter; is_valid_prior_work does the precise cut
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

    # Rank the fresh candidates by SPECTER2 similarity to the claim (same signal as
    # ArtifactABuilder.select_candidates), so the best new prior work surfaces first.
    claim_doc = f"{claim.get('name','')}. {claim.get('description','')} {claim.get('claim_text','')}".strip()
    cand_docs = [f"{p['title']}. {p['abstract']}" for p in fresh]
    embs = embedder.encode([claim_doc] + cand_docs, convert_to_numpy=True)
    claim_emb, cand_embs = embs[0], embs[1:]
    sims = cand_embs @ claim_emb / (
        np.linalg.norm(cand_embs, axis=1) * np.linalg.norm(claim_emb) + 1e-9
    )
    order = np.argsort(-sims)[:k]
    out = []
    for idx in order:
        p = dict(fresh[idx])
        p["similarity"] = float(sims[idx])
        out.append(p)
    return out
