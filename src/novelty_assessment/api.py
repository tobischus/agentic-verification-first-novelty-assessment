#!/usr/bin/env python3
"""
Backend API for the verification-first novelty pipeline (bridge to the frontend).

Exposes the orchestrator (Step 0) + the human-in-the-loop operations as REST
endpoints. Long-running pipeline segments run in a background thread; the
frontend polls the state and intervenes at the two HITL checkpoints:

  upload PDF                -> POST   /submissions
  poll state                -> GET    /submissions/{id}/state
  CHECKPOINT 'claims'       -> GET/PATCH /submissions/{id}/claims  then
                               POST   /submissions/{id}/checkpoints/claims/approve
  CHECKPOINT 'papers'       -> GET/PATCH /submissions/{id}/papers  then
                               POST   /submissions/{id}/checkpoints/papers/approve
  final report              -> GET    /submissions/{id}/report   (markdown)
  artifacts (transparency)  -> GET    /submissions/{id}/artifact_a|artifact_b|judge

Run: PYTHONUTF8=1 python src/novelty_assessment/api.py  (serves on :8099)
"""
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import NoveltyPipeline
import claim_extraction as ce

DATA_DIR = os.getenv("NOVELTY_DATA_DIR", "data")

app = FastAPI(title="Verification-First Novelty Assessment API")
# Research prototype: allow the local SPA dev server (and any origin) to call the API.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_running = set()
_lock = threading.Lock()


def _sub_dir(sid: str) -> Path:
    return Path(DATA_DIR) / sid


def _load_json(path: Path):
    # Tolerant of a concurrent writer: a poll may hit a file mid-write (empty/partial)
    # -> return None instead of 500-ing the whole endpoint (e.g. {id}_progress.json,
    # rewritten ~every 0.4s during long stages while the frontend polls /state).
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _start_run(sid: str, pdf: Optional[str] = None, hitl: bool = True) -> bool:
    """Run the pipeline (to next checkpoint/completion) in a background thread."""
    with _lock:
        if sid in _running:
            return False
        _running.add(sid)

    def _target():
        try:
            NoveltyPipeline(DATA_DIR, sid, pdf_path=pdf, hitl=hitl).run()
        finally:
            with _lock:
                _running.discard(sid)

    threading.Thread(target=_target, daemon=True).start()
    return True


@app.get("/")
def health():
    return {"status": "ok", "data_dir": DATA_DIR}


@app.post("/submissions")
async def create_submission(file: UploadFile = File(...), submission_id: Optional[str] = None):
    # Version every upload (Option A): re-uploading the same paper never overwrites a
    # prior run. Each submission gets its own timestamped directory, so the orchestrator
    # always starts a *fresh* run instead of silently resuming/skipping the old outputs.
    base = submission_id or Path(file.filename).stem
    sid = f"{base}__{time.strftime('%Y%m%d-%H%M%S')}"
    d = _sub_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    pdf = d / f"{sid}.pdf"
    pdf.write_bytes(await file.read())
    _start_run(sid, str(pdf), hitl=True)
    return {"submission_id": sid, "base_id": base, "status": "started"}


@app.get("/submissions/{sid}/state")
def get_state(sid: str):
    state = _load_json(_sub_dir(sid) / f"{sid}_pipeline_state.json")
    if state is None:
        raise HTTPException(404, "no such submission")
    state["running"] = sid in _running
    # Live sub-progress of the current long stage (retrieval / artifact_a), if any.
    prog = _load_json(_sub_dir(sid) / f"{sid}_progress.json")
    if prog is not None:
        state["progress"] = prog
    return state


# ----------------------------- checkpoint 'claims' ----------------------------- #


@app.get("/submissions/{sid}/claims")
def get_claims(sid: str):
    doc = _load_json(_sub_dir(sid) / f"{sid}_claims.json")
    if doc is None:
        raise HTTPException(404, "claims not ready")
    # Ensure the title + submission date (used for the retrieval cutoff) are present,
    # backfilling from {id}.json for docs produced before these fields were added.
    meta = _load_json(_sub_dir(sid) / f"{sid}.json") or {}
    for k in ("title", "publication_date", "year", "date_source"):
        if not doc.get(k) and meta.get(k) is not None:
            doc[k] = meta.get(k)
    return doc


class ClaimOp(BaseModel):
    op: str  # accept | edit | delete | add
    claim_id: Optional[str] = None
    name: Optional[str] = None
    claim_text: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None


class ClaimOps(BaseModel):
    operations: List[ClaimOp]


@app.patch("/submissions/{sid}/claims")
def edit_claims(sid: str, ops: ClaimOps):
    path = _sub_dir(sid) / f"{sid}_claims.json"
    doc = _load_json(path)
    if doc is None:
        raise HTTPException(404, "claims not ready")
    for o in ops.operations:
        if o.op == "accept":
            ce.accept_claim(doc, o.claim_id)
        elif o.op == "edit":
            fields = {k: v for k, v in {
                "name": o.name, "claim_text": o.claim_text,
                "description": o.description, "source": o.source,
            }.items() if v is not None}
            ce.edit_claim(doc, o.claim_id, **fields)
        elif o.op == "delete":
            ce.delete_claim(doc, o.claim_id)
        elif o.op == "add":
            ce.add_claim(doc, o.name or "", o.claim_text or "", o.description or "")
        else:
            raise HTTPException(400, f"unknown op: {o.op}")
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


class DateEdit(BaseModel):
    publication_date: str  # YYYY-MM-DD


@app.patch("/submissions/{sid}/date")
def set_date(sid: str, d: DateEdit):
    """HITL: reviewer sets/corrects the submission's publication date (= the
    retrieval cutoff). Needed when the automatic lookup cannot resolve it, e.g.
    a paper renamed between arXiv v1 and the reviewed version. The date should be
    the FIRST public disclosure (arXiv v1), since novelty is judged at disclosure.
    Updates {id}.json (read by retrieval + the agent's admissibility rule) and
    mirrors into {id}_claims.json (read by the frontend header)."""
    val = (d.publication_date or "").strip()
    try:
        time.strptime(val, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "publication_date must be YYYY-MM-DD")
    sub = _sub_dir(sid)
    meta_path = sub / f"{sid}.json"
    meta = _load_json(meta_path)
    if meta is None:
        raise HTTPException(404, "submission metadata not ready")
    for doc, path in ((meta, meta_path),
                      (_load_json(sub / f"{sid}_claims.json"), sub / f"{sid}_claims.json")):
        if doc is None:
            continue  # claims doc may not exist yet; {id}.json alone is fine
        doc["publication_date"] = val
        doc["year"] = val[:4]
        doc["date_source"] = "reviewer"
        doc["date_needs_review"] = False
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "publication_date": val, "year": val[:4], "date_source": "reviewer"}


# ----------------------------- checkpoint 'papers' ----------------------------- #


def _pdf_path(sid: str, paper_id: str) -> Path:
    return _sub_dir(sid) / "related_work_data" / "pdfs" / f"{paper_id}.pdf"


@app.get("/submissions/{sid}/papers")
def get_papers(sid: str):
    rp = _load_json(_sub_dir(sid) / "related_work_data" / "ranked_papers.json")
    if rp is None:
        raise HTTPException(404, "papers not ready")
    # PDF availability only -- whether GROBID has parsed a paper's full text is a
    # separate, later concern decided per deep dive during Review (not shown here).
    for p in rp:
        pp = _pdf_path(sid, p.get("paper_id", ""))
        p["pdf_available"] = pp.exists() and pp.stat().st_size > 0
    return {"count": len(rp), "papers": rp}


@app.post("/submissions/{sid}/papers/{paper_id}/pdf")
async def upload_paper_pdf(sid: str, paper_id: str, file: UploadFile = File(...)):
    """HITL: reviewer uploads a PDF for an EXISTING pool paper that the automatic
    download (S2 openAccessPdf / arXiv / Unpaywall) could not fetch -- e.g. a
    publisher blocks automated downloads (403) even though the paper is open access
    in a browser. Only stores the PDF; GROBID parsing happens later, on demand, if
    this paper is deep-dived (see agent/tools.py ensure_fulltext)."""
    rp = _load_json(_sub_dir(sid) / "related_work_data" / "ranked_papers.json")
    if rp is None or not any(p.get("paper_id") == paper_id for p in rp):
        raise HTTPException(404, "paper not in the related-work pool")
    raw = await file.read()
    if raw[:4] != b"%PDF":
        raise HTTPException(400, "uploaded file is not a valid PDF")
    dest = _pdf_path(sid, paper_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return {"paper_id": paper_id, "pdf_available": True}


class PaperEdit(BaseModel):
    remove: List[str] = []            # paper_ids to drop from the pool
    add: List[dict] = []              # papers to add (need paper_id, title, abstract)


@app.patch("/submissions/{sid}/papers")
def edit_papers(sid: str, edit: PaperEdit):
    path = _sub_dir(sid) / "related_work_data" / "ranked_papers.json"
    rp = _load_json(path)
    if rp is None:
        raise HTTPException(404, "papers not ready")
    rem = set(edit.remove)
    rp = [p for p in rp if p.get("paper_id") not in rem]
    existing = {p.get("paper_id") for p in rp}
    for a in edit.add:
        if a.get("paper_id") and a["paper_id"] not in existing:
            a.setdefault("cited_paper", False)
            rp.append(a)
    path.write_text(json.dumps(rp, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"count": len(rp), "papers": rp}


# ----- add a related paper by DOI/arXiv/title (Semantic Scholar) or PDF (GROBID) ----- #


def _norm_title(s: str) -> str:
    return "".join((s or "").lower().split()).replace("-", "")


_EMB_MODEL = None


def _embed_model():
    """Lazily load the same SPECTER2 model the retrieval stage uses (cached)."""
    global _EMB_MODEL
    if _EMB_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMB_MODEL = SentenceTransformer("allenai/specter2_base")
    return _EMB_MODEL


def _compute_relevance(sid: str, abstract: str):
    """SPECTER2 cosine similarity between the submission and a paper abstract (0-1)."""
    abstract = (abstract or "").strip()
    if not abstract:
        return None
    meta = _load_json(_sub_dir(sid) / f"{sid}.json") or {}
    src = (meta.get("abstract") or "").strip()
    if not src:
        return None
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        e = _embed_model().encode([src, abstract], convert_to_numpy=True)
        sim = float(cosine_similarity([e[0]], [e[1]])[0][0])
        return round(max(0.0, min(1.0, sim)), 4)
    except Exception:
        return None


def _paper_from_s2(d: dict) -> dict:
    authors = ", ".join(a.get("name", "") for a in (d.get("authors") or []))
    ext = d.get("externalIds") or {}
    pid = d.get("paperId") or ("ext_" + (ext.get("DOI") or ext.get("ArXiv") or d.get("title", ""))[:48])
    return {
        "paper_id": pid,
        "title": d.get("title") or "",
        "abstract": d.get("abstract") or "",
        "year": str(d.get("year")) if d.get("year") else "",
        "venue": d.get("venue") or "",
        "authors": authors,
        "citation_count": d.get("citationCount") or 0,
        "cited_paper": False,
        "novel": None,
        "relevance": None,
        "added_by": "reviewer",
    }


def _resolve_paper_query(query: str):
    """Resolve a DOI / arXiv id / URL / title to a paper dict via Semantic Scholar."""
    import re
    import requests

    q = query.strip()
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    headers = {"X-API-KEY": key} if key and key != "---" else {}
    fields = "title,abstract,year,venue,authors,citationCount,externalIds,paperId"
    base = "https://api.semanticscholar.org/graph/v1/paper"
    try:
        idexpr = None
        ql = q.lower()
        if "doi.org/" in ql or ql.startswith("10."):
            idexpr = "DOI:" + q.split("doi.org/")[-1].strip()
        elif "arxiv.org/abs/" in ql or re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", q):
            idexpr = "arXiv:" + q.split("abs/")[-1].strip()
        if idexpr:
            r = requests.get(f"{base}/{idexpr}", params={"fields": fields}, headers=headers, timeout=20)
            if r.status_code == 200 and r.json():
                return _paper_from_s2(r.json())
            return None
        # else: treat as a title -> match endpoint
        r = requests.get(f"{base}/search/match", params={"query": q, "fields": fields}, headers=headers, timeout=20)
        if r.status_code == 200:
            items = (r.json() or {}).get("data") or []
            if items:
                return _paper_from_s2(items[0])
    except Exception:
        return None
    return None


def _resolve_paper_pdf(sid: str, raw: bytes, filename: str):
    """Extract title + abstract from an uploaded related-work PDF via GROBID."""
    from lxml import etree

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "preprocess"))
    from grobid_client import GrobidClient

    uploads = _sub_dir(sid) / "related_work_data" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    pdf_path = uploads / (filename or "added.pdf")
    pdf_path.write_bytes(raw)
    try:
        tei = GrobidClient().pdf_to_tei(str(pdf_path))
        root = etree.fromstring(tei.encode("utf-8"))
        ns = {"t": "http://www.tei-c.org/ns/1.0"}
        title = (root.findtext(".//t:teiHeader//t:titleStmt/t:title", default="", namespaces=ns) or "").strip()
        abs_el = root.find(".//t:teiHeader//t:profileDesc//t:abstract", namespaces=ns)
        abstract = " ".join(abs_el.itertext()).strip() if abs_el is not None else ""
    except Exception:
        return None
    if not title:
        return None
    # Enrich via Semantic Scholar (authors/year/venue + a real paper id for the link),
    # guarded by a title-similarity check so we don't attach a wrong paper's metadata.
    enriched = _resolve_paper_query(title)
    if enriched:
        a, b = _norm_title(title), _norm_title(enriched.get("title", ""))
        if a[:50] in b or b[:50] in a:
            if not enriched.get("abstract"):
                enriched["abstract"] = abstract
            enriched["added_by"] = "reviewer"
            return enriched
    import hashlib
    return {
        "paper_id": "pdf_" + hashlib.sha1(raw).hexdigest()[:12],
        "title": title, "abstract": abstract, "year": "", "venue": "", "authors": "",
        "citation_count": 0, "cited_paper": False, "novel": None,
        "relevance": None, "added_by": "reviewer",
    }


@app.post("/submissions/{sid}/papers/add")
async def add_related_paper(sid: str, query: Optional[str] = Form(None), file: UploadFile = File(None)):
    path = _sub_dir(sid) / "related_work_data" / "ranked_papers.json"
    rp = _load_json(path)
    if rp is None:
        raise HTTPException(404, "papers not ready")
    paper = None
    if query and query.strip():
        paper = _resolve_paper_query(query.strip())
    elif file is not None:
        paper = _resolve_paper_pdf(sid, await file.read(), file.filename or "added.pdf")
    if not paper or not paper.get("title"):
        raise HTTPException(400, "could not resolve a paper from the given DOI/title/PDF")
    if any(p.get("paper_id") == paper["paper_id"] for p in rp):
        return {"added": False, "reason": "already in the list", "count": len(rp), "papers": rp}
    # Relevance score (SPECTER2 cosine to the submission), same metric as the pipeline.
    paper["relevance"] = _compute_relevance(sid, paper.get("abstract"))
    rp.append(paper)
    path.write_text(json.dumps(rp, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"added": True, "paper": paper, "count": len(rp), "papers": rp}


# ------------------------------- approve / resume ------------------------------ #


@app.post("/submissions/{sid}/checkpoints/{cp}/approve")
def approve_checkpoint(sid: str, cp: str):
    pipe = NoveltyPipeline(DATA_DIR, sid)
    if not pipe.state_path.exists():
        raise HTTPException(404, "no such submission")
    pipe.approve(cp)
    _start_run(sid, hitl=True)
    return {"submission_id": sid, "approved": cp, "status": "resuming"}


# --------------------------------- outputs ------------------------------------- #


@app.get("/submissions/{sid}/report", response_class=PlainTextResponse)
def get_report(sid: str):
    p = _sub_dir(sid) / f"{sid}_report.md"
    if not p.exists():
        raise HTTPException(404, "report not ready")
    return p.read_text(encoding="utf-8")


# ---- claim-level review: assemble per-claim Explore/Evidence (verified) ---- #


def _relevance_band(sim):
    if sim is None:
        return None
    if sim >= 0.8:
        return "High"
    if sim >= 0.6:
        return "Medium"
    return "Low"


def _source_label(content_source):
    """Normalize artifact_a's content_source to a short UI badge."""
    cs = (content_source or "").lower()
    if cs.startswith("full"):
        return "Full text"
    if "abstract" in cs:
        return "Abstract + intro"
    return ""


# ---- lazy, per-claim review: fetch-status + on-demand Explore/Evidence ---- #


def _agent_budgets() -> dict:
    """Agent budgets/thresholds (ablation hyperparameters), overridable via env."""
    return {
        "max_steps": int(os.getenv("NOVELTY_AGENT_MAX_STEPS", "24")),
        "max_retrievals": int(os.getenv("NOVELTY_AGENT_MAX_RETRIEVALS", "3")),
        "closest_n": int(os.getenv("NOVELTY_AGENT_CLOSEST_N", "5")),
        "stalled_k": int(os.getenv("NOVELTY_AGENT_STALLED_K", "4")),
        "min_quote_tokens": int(os.getenv("NOVELTY_AGENT_MIN_QUOTE_TOKENS", "10")),
    }


def _run_agent(sid: str, claim: dict) -> dict:
    """Run the per-claim agentic Explore/Verify loop -> artifact_a-compatible entry."""
    from agent.claim_agent import ClaimNoveltyAgent

    agent = ClaimNoveltyAgent(
        DATA_DIR, sid, embedder=_embed_model(),
        model_name=os.getenv("NOVELTY_MODEL", "gpt-4.1"),
        grobid_server=os.getenv("GROBID_SERVER", "http://localhost:8070"),
        **_agent_budgets(),
    )
    return agent.run(claim)


def _clusters_of(ranked):
    out, seen = [], set()
    for p in ranked:
        lab = p.get("cluster_label")
        if lab and lab not in seen:
            seen.add(lab)
            out.append(lab)
    return out


def _assemble_claim(entry, meta):
    """Assemble one claim's Explore/Evidence view from its Artifact-A entry.

    Verified evidence only -- synthesis and judge were removed from the per-claim
    review (the reviewer reads the evidence; no per-claim verdict is rendered)."""
    comps = entry.get("comparisons", []) or []
    comp_by = {c.get("paper_id"): c for c in comps}
    frontier = entry.get("frontier")
    examined = entry.get("examined_papers")
    explore = []
    if frontier:  # agentic: the FULL ranked frontier -- all relevant papers, examined or not
        for p in frontier:
            pid = p.get("paper_id")
            c = comp_by.get(pid, {})
            sim = p.get("similarity")
            explore.append({
                "paper_id": pid, "title": p.get("title", ""),
                "authors": p.get("authors", ""), "year": p.get("year", ""), "venue": p.get("venue", ""),
                "relevance": sim, "band": _relevance_band(sim),
                "provenance": p.get("source"), "cited_by_submission": p.get("cited_by_submission", False),
                "examined": bool(p.get("examined")), "compared": bool(p.get("compared")),
                "challenges": c.get("refutation_status") == "can_refute",
                "overlap_degree": c.get("overlap_degree"),
                "note": c.get("relevance_reason") or c.get("brief_note", ""),
                "source": _source_label(c.get("content_source")) if c
                          else ("Full text" if p.get("has_fulltext") else "Abstract + intro"),
            })
    elif examined:  # older agentic entries (before `frontier` existed)
        for p in sorted(examined, key=lambda x: x.get("similarity") or 0, reverse=True):
            pid = p.get("paper_id")
            c = comp_by.get(pid, {})
            m = meta.get(pid, {})
            sim = p.get("similarity")
            explore.append({
                "paper_id": pid, "title": p.get("title") or c.get("title") or m.get("title", ""),
                "authors": m.get("authors", ""), "year": m.get("year", ""), "venue": m.get("venue", ""),
                "relevance": sim, "band": _relevance_band(sim), "provenance": p.get("source"),
                "examined": True, "compared": bool(p.get("has_comparison")),
                "challenges": c.get("refutation_status") == "can_refute",
                "overlap_degree": c.get("overlap_degree"),
                "note": c.get("relevance_reason") or c.get("brief_note", ""),
                "source": _source_label(c.get("content_source")),
            })
    else:  # baseline (non-agentic builder): Explore = the comparisons themselves
        for c in sorted(comps, key=lambda x: x.get("similarity") or 0, reverse=True):
            m = meta.get(c.get("paper_id"), {})
            sim = c.get("similarity")
            explore.append({
                "paper_id": c.get("paper_id"), "title": c.get("title"),
                "authors": m.get("authors", ""), "year": m.get("year", ""), "venue": m.get("venue", ""),
                "relevance": sim, "band": _relevance_band(sim), "examined": True, "compared": True,
                "challenges": c.get("refutation_status") == "can_refute",
                "overlap_degree": c.get("overlap_degree"),
                "note": c.get("relevance_reason") or c.get("brief_note", ""),
                "source": _source_label(c.get("content_source")),
            })
    verify = []
    for c in comps:
        pairs = c.get("evidence_pairs") or []
        # Only surface quote pairs verified on BOTH sides -- never show ungrounded quotes.
        verified_pairs = [p for p in pairs
                          if p.get("claim_quote_verified") and p.get("paper_quote_verified")]
        _m = meta.get(c.get("paper_id"), {})
        verify.append({
            "paper_id": c.get("paper_id"), "title": c.get("title"),
            # authors/year for the reviewer's context (fall back to the pool meta for
            # claims computed before authors were stored on the comparison itself)
            "authors": c.get("authors") or _m.get("authors", ""),
            "year": c.get("year") or _m.get("year", ""),
            "challenges": c.get("refutation_status") == "can_refute",
            "status": c.get("refutation_status"), "analysis": c.get("brief_note", ""),
            "source": _source_label(c.get("content_source")),
            "depth": c.get("depth"),
            # exact section titles read in full for this comparison (shown as a box)
            "sections_used": c.get("sections_used", []),
            # outcome of the on-demand GROBID fetch for this deep dive (None = never
            # attempted, e.g. an abstract-only triage comparison)
            "fulltext_fetch_status": c.get("fulltext_fetch_status"),
            "overlap_degree": c.get("overlap_degree"),
            "overlap_dimensions": c.get("overlap_dimensions", []),
            "what_is_shared": c.get("what_is_shared", ""),
            "submission_delta": c.get("submission_delta", ""),
            # section-based deep dive: narrative of how this paper realizes the claim
            # (segments of prose + inline verified quotes) + the overlap assessment
            "paper_realization": c.get("paper_realization", []),
            "assessment": c.get("assessment", ""),
            "evidence": [{"claim_quote": p.get("claim_quote"), "paper_quote": p.get("paper_quote"),
                          "rationale": p.get("rationale")} for p in verified_pairs],
            "verified": len(verified_pairs) > 0,
        })
    return {
        "claim_id": entry.get("claim_id"),
        "claim_text": entry.get("claim_text") or entry.get("claim_name", ""),
        # section-based understanding of what the SUBMISSION does for this claim
        # (verified-quote segments), shown between the claim box and the evidence
        "claim_realization": entry.get("claim_realization", []),
        "claim_sections_used": entry.get("claim_sections_used", []),
        "explore": explore, "verify": verify,
        # wall-clock breakdown per phase (rerank/understand_submission/triage/deep_dive/
        # reentry/other/total + per-deep-dive-paper parse-vs-compare split) so the reviewer
        # can see what makes a claim slow -- rendered as a timing panel in the Review UI.
        "timings": entry.get("timings"),
        # agentic transparency: how the loop reached its evidence + whether it was sufficient
        "agent": {
            "verdict": entry.get("agent_verdict"),
            "evidence_sufficient": entry.get("evidence_sufficient", True),
            "stop_reason": entry.get("stop_reason"),
            "retrieval_rounds": entry.get("retrieval_rounds", 0),
            "pool_sources": entry.get("pool_sources", {}),
            "n_steps": len(entry.get("trajectory", []) or []),
        },
    }


@app.get("/submissions/{sid}/review/claims")
def review_claims(sid: str):
    """The claim list + reference count + clusters that drive the review walkthrough."""
    claims_doc = _load_json(_sub_dir(sid) / f"{sid}_claims.json")
    if claims_doc is None:
        raise HTTPException(404, "claims not ready")
    ranked = _load_json(_sub_dir(sid) / "related_work_data" / "ranked_papers.json") or []
    a = _load_json(_sub_dir(sid) / f"{sid}_artifact_a.json") or {"claims": []}
    computed = {e.get("claim_id") for e in a.get("claims", [])}
    claims = [
        {"claim_id": c["id"], "claim_text": c.get("claim_text") or c.get("name", ""),
         "computed": c["id"] in computed}
        for c in claims_doc.get("claims", []) if c.get("status") != "rejected"
    ]
    return {"submission_id": sid, "n_reference_papers": len(ranked),
            "clusters": _clusters_of(ranked), "claims": claims}


# The agent loop is long-running, so a claim is computed in a BACKGROUND thread that
# streams progress (trajectory + running token cost) into a live file the frontend polls.
_claim_running = set()         # (sid, claim_id) currently computing
_claim_lock = threading.Lock()
_artifact_lock = threading.Lock()  # serialise read-modify-write of artifact_a/b.json


def _live_path(sid: str, cid: str) -> Path:
    return _sub_dir(sid) / f"{sid}_claim_{cid}_live.json"


def _write_live(sid: str, cid: str, payload: dict):
    try:
        _live_path(sid, cid).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _persist_claim_cost(sid: str, cid: str, cost: dict):
    p = _sub_dir(sid) / f"{sid}_agent_cost.json"
    doc = _load_json(p) or {"per_claim": {}}
    doc.setdefault("per_claim", {})[cid] = {**(cost or {}), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _assembled_for(sid: str, cid: str):
    """Assemble one finished claim's Explore/Evidence view from artifact_a."""
    sub = _sub_dir(sid)
    a = _load_json(sub / f"{sid}_artifact_a.json") or {"claims": []}
    ae = next((e for e in a.get("claims", []) if e.get("claim_id") == cid), None)
    if ae is None:
        return None
    ranked = _load_json(sub / "related_work_data" / "ranked_papers.json") or []
    meta = {p.get("paper_id"): p for p in ranked}
    return _assemble_claim(ae, meta)


def _claim_worker(sid: str, cid: str):
    """Run the agent for one claim, streaming progress, then persist evidence + cost.

    The per-claim review is evidence-only: no synthesis (Artifact B) or judge stage is
    run here -- the agent's verified comparison ledger (Artifact A) is the whole review."""
    try:
        sub = _sub_dir(sid)
        claims_doc = _load_json(sub / f"{sid}_claims.json") or {"claims": []}
        claim = next((c for c in claims_doc.get("claims", [])
                      if c["id"] == cid and c.get("status") != "rejected"), None)
        if claim is None:
            _write_live(sid, cid, {"status": "error", "claim_id": cid, "error": "claim not found"})
            return
        budgets = _agent_budgets()
        _write_live(sid, cid, {"status": "running", "claim_id": cid, "step": 0,
                               "max_steps": budgets["max_steps"], "trajectory": [],
                               "cost": {"prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0}})

        from agent.claim_agent import ClaimNoveltyAgent
        agent = ClaimNoveltyAgent(
            DATA_DIR, sid, embedder=_embed_model(),
            model_name=os.getenv("NOVELTY_MODEL", "gpt-4.1"),
            grobid_server=os.getenv("GROBID_SERVER", "http://localhost:8070"), **budgets,
        )
        entry = agent.run(claim, progress_cb=lambda info: _write_live(sid, cid, info))

        with _artifact_lock:
            a_path = sub / f"{sid}_artifact_a.json"
            a = _load_json(a_path) or {"submission_id": sid, "agentic": True, "n_related_pool": 0, "claims": []}
            a["claims"] = [e for e in a["claims"] if e.get("claim_id") != cid] + [entry]
            a["n_related_pool"] = sum(entry.get("pool_sources", {}).values()) or a.get("n_related_pool", 0)
            a_path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")

        _persist_claim_cost(sid, cid, entry.get("cost", {}))
        _write_live(sid, cid, {
            "status": "done", "claim_id": cid,
            "step": len(entry.get("trajectory", []) or []), "max_steps": budgets["max_steps"],
            "trajectory": entry.get("trajectory", []), "cost": entry.get("cost", {}),
            "verdict": entry.get("agent_verdict"), "evidence_sufficient": entry.get("evidence_sufficient"),
            "stop_reason": entry.get("stop_reason"), "retrieval_rounds": entry.get("retrieval_rounds", 0),
            "review": _assembled_for(sid, cid),
        })
    except Exception as e:
        _write_live(sid, cid, {"status": "error", "claim_id": cid, "error": repr(e)[:300]})
    finally:
        with _claim_lock:
            _claim_running.discard((sid, cid))


@app.post("/submissions/{sid}/review/claim/{claim_id}")
def compute_claim(sid: str, claim_id: str):
    """Start (or reuse) the agentic per-claim assessment. Non-blocking: returns
    immediately with a status; the frontend polls .../live for the streamed
    trajectory + cost, and the assembled review once done."""
    sub = _sub_dir(sid)
    if _load_json(sub / f"{sid}_claims.json") is None:
        raise HTTPException(404, "claims not ready")
    a = _load_json(sub / f"{sid}_artifact_a.json") or {"claims": []}
    if any(e.get("claim_id") == claim_id for e in a.get("claims", [])):
        return {"status": "done", "review": _assembled_for(sid, claim_id)}
    with _claim_lock:
        if (sid, claim_id) in _claim_running:
            return {"status": "running"}
        _claim_running.add((sid, claim_id))
    threading.Thread(target=_claim_worker, args=(sid, claim_id), daemon=True).start()
    return {"status": "running"}


@app.get("/submissions/{sid}/review/claim/{claim_id}/live")
def claim_live(sid: str, claim_id: str):
    """Live progress of an in-flight claim: {status, step, trajectory[], cost, review?}."""
    live = _load_json(_live_path(sid, claim_id))
    if live is not None:
        return live
    rev = _assembled_for(sid, claim_id)  # computed in an earlier session -> no live file
    if rev is not None:
        return {"status": "done", "claim_id": claim_id, "trajectory": [], "cost": {}, "review": rev}
    return {"status": "idle", "claim_id": claim_id}


@app.get("/submissions/{sid}/agent-cost")
def agent_cost(sid: str):
    """Aggregate agent token cost across all computed claims (money spent so far)."""
    doc = _load_json(_sub_dir(sid) / f"{sid}_agent_cost.json") or {"per_claim": {}}
    per = doc.get("per_claim", {})
    return {
        "per_claim": per,
        "total_usd": round(sum((v.get("usd") or 0) for v in per.values()), 4),
        "total_prompt_tokens": sum((v.get("prompt_tokens") or 0) for v in per.values()),
        "total_completion_tokens": sum((v.get("completion_tokens") or 0) for v in per.values()),
        "model": os.getenv("NOVELTY_MODEL", "gpt-4.1"),
    }


@app.get("/submissions/{sid}/pipeline-cost")
def pipeline_cost(sid: str):
    """Aggregate token/cost across the WHOLE run so far -- document processing
    (title fallback), claim extraction, retrieval, and the per-claim review agent --
    so the reviewer sees what an entire run costs, not just one stage. Works
    incrementally (pipeline_state.json's metrics are updated per-stage as it runs),
    so this can be shown from the Claims tab onward, not only after Review."""
    sub = _sub_dir(sid)
    state = _load_json(sub / f"{sid}_pipeline_state.json") or {}
    metrics = state.get("metrics", {})

    stages = {}
    total_usd, total_pt, total_ct = 0.0, 0, 0
    for name in ("document_processing", "claim_extraction", "retrieval", "fetch_pdfs"):
        m = metrics.get(name) or {}
        usd = float(m.get("usd") or 0.0)
        pt, ct = int(m.get("prompt_tokens") or 0), int(m.get("completion_tokens") or 0)
        if name == "retrieval":
            # retrieval's keyword-generation + RankGPT reranking cost is tracked
            # separately in metadata.json (litellm cost_per_token) -- not all of it
            # flows through the langchain callback that captures the other stages,
            # so this is ADDITIVE to metrics['retrieval']['usd'], not a duplicate.
            rw_meta = _load_json(sub / "related_work_data" / "metadata.json") or {}
            usd += float(rw_meta.get("total_cost") or 0.0)
        stages[name] = {"usd": round(usd, 4), "prompt_tokens": pt, "completion_tokens": ct}
        total_usd += usd
        total_pt += pt
        total_ct += ct

    agent = _load_json(sub / f"{sid}_agent_cost.json") or {"per_claim": {}}
    per = agent.get("per_claim", {})
    review = {
        "usd": round(sum((v.get("usd") or 0) for v in per.values()), 4),
        "prompt_tokens": sum((v.get("prompt_tokens") or 0) for v in per.values()),
        "completion_tokens": sum((v.get("completion_tokens") or 0) for v in per.values()),
        "n_claims": len(per),
    }
    stages["review"] = review
    total_usd += review["usd"]
    total_pt += review["prompt_tokens"]
    total_ct += review["completion_tokens"]

    return {
        "submission_id": sid,
        "stages": stages,
        "total_usd": round(total_usd, 4),
        "total_prompt_tokens": total_pt,
        "total_completion_tokens": total_ct,
        "model": os.getenv("NOVELTY_MODEL", state.get("model") or "gpt-4.1"),
    }


@app.get("/submissions/{sid}/review/claim/{claim_id}/trajectory")
def claim_trajectory(sid: str, claim_id: str):
    """The agent's step-by-step trajectory + stop reason for one claim (transparency)."""
    a = _load_json(_sub_dir(sid) / f"{sid}_artifact_a.json") or {"claims": []}
    e = next((x for x in a.get("claims", []) if x.get("claim_id") == claim_id), None)
    if e is None:
        raise HTTPException(404, "claim not computed yet")
    return {
        "claim_id": claim_id,
        "agent_verdict": e.get("agent_verdict"),
        "evidence_sufficient": e.get("evidence_sufficient"),
        "stop_reason": e.get("stop_reason"),
        "retrieval_rounds": e.get("retrieval_rounds", 0),
        "pool_sources": e.get("pool_sources", {}),
        "candidates_examined": e.get("candidates_examined"),
        "trajectory": e.get("trajectory", []),
    }


# Overlap degrees that count as "the prior work delivers (part of) the same contribution".
_OVERLAP_DEGREES = ("same", "substantial", "partial")
_DEGREE_RANK = {"same": 0, "substantial": 1, "partial": 2}


@app.get("/submissions/{sid}/review/summary")
def review_summary(sid: str):
    """Cross-claim summary of the evidence-based review: for every computed claim, the
    prior-work papers that OVERLAP the claim (the important contexts) with their overlap
    degree + comparison. No final novelty verdict -- just the gathered contexts."""
    sub = _sub_dir(sid)
    a = _load_json(sub / f"{sid}_artifact_a.json")
    if a is None:
        raise HTTPException(404, "no claims computed yet")
    claims_doc = _load_json(sub / f"{sid}_claims.json") or {"claims": []}
    order = [c["id"] for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    ranked = _load_json(sub / "related_work_data" / "ranked_papers.json") or []
    meta = {p.get("paper_id"): p for p in ranked}

    out_claims, distinct_overlap = [], set()
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        comps = e.get("comparisons", []) or []
        overlaps = []
        for c in comps:
            deg = (c.get("overlap_degree") or "").lower()
            challenges = c.get("refutation_status") == "can_refute"
            if not (challenges or deg in _OVERLAP_DEGREES):
                continue
            _m = meta.get(c.get("paper_id"), {})
            distinct_overlap.add(c.get("paper_id"))
            overlaps.append({
                "paper_id": c.get("paper_id"), "title": c.get("title"),
                "authors": c.get("authors") or _m.get("authors", ""),
                "year": c.get("year") or _m.get("year", ""),
                "overlap_degree": deg, "challenges": challenges,
                "what_is_shared": c.get("what_is_shared", ""),
                "submission_delta": c.get("submission_delta", ""),
                "assessment": c.get("assessment", ""),
                "paper_realization": c.get("paper_realization", []),
                "sections_used": c.get("sections_used", []),
                "cited_by_submission": c.get("cited_by_submission", False),
            })
        overlaps.sort(key=lambda o: (not o["challenges"], _DEGREE_RANK.get(o["overlap_degree"], 9)))
        out_claims.append({
            "claim_id": cid,
            "claim_text": e.get("claim_text") or e.get("claim_name", ""),
            "claim_realization": e.get("claim_realization", []),
            "n_compared": len(comps),
            "overlaps": overlaps,
        })
    return {
        "submission_id": sid, "title": claims_doc.get("title", ""),
        "n_claims": len(out_claims),
        # DISTINCT overlapping papers -- a paper that overlaps several claims counts once
        "n_overlap_papers": len(distinct_overlap),
        "claims": out_claims,
    }


# ----------------------- overall novelty conclusion ------------------------ #


def _author_year(authors: str, year) -> str:
    """'Haoyu Han, Harry Shomer, ...', '2025' -> 'Han et al. (2025)'."""
    names = [a.strip() for a in (authors or "").split(",") if a.strip()]
    if not names:
        return ""
    surname = names[0].split()[-1] if names[0].split() else names[0]
    cite = f"{surname} et al." if len(names) > 1 else names[0]
    return f"{cite} ({year})" if year else cite


def _segments_text(segments) -> str:
    return " ".join((s.get("content") or "").strip() for s in (segments or [])
                    if (s.get("content") or "").strip())


def _conclusion_path(sid: str) -> Path:
    return _sub_dir(sid) / f"{sid}_conclusion.json"


_CONCLUSION_PROMPT = """You are writing the concluding paragraph of a novelty assessment for a scientific paper under review. Base your assessment STRICTLY and ONLY on the evidence gathered below — do NOT introduce outside knowledge, do NOT invent prior work, methods, or results that are not stated. If the evidence is thin, say so rather than embellishing.

The evidence comes from a claim-by-claim comparison of the submission against prior work. For each claimed contribution you are given: what the submission itself does, and the overlapping prior work found (with the degree of overlap, what is shared, and what the submission adds beyond it).

Write ONE cohesive paragraph (roughly 120-220 words) that concludes on the paper's overall novelty. It should:
- state what the paper contributes overall;
- honestly acknowledge overlap with prior work, citing specific papers inline as "Surname et al. (Year)" exactly as given in the evidence;
- judge whether the contribution is largely incremental or genuinely novel, and WHERE the novelty actually lies (e.g. method vs. scope/depth/analysis/evaluation), grounded in the "submission adds beyond it" notes;
- note the submission's distinguishing strengths;
- optionally close with a constructive note (e.g. that the paper should acknowledge the overlap more explicitly), only if the evidence supports it.
Neutral, precise, evidence-based academic prose. No headings, no bullet lists, no preamble — just the paragraph.

SUBMISSION TITLE: {title}
SUBMISSION ABSTRACT: {abstract}

EVIDENCE BY CLAIM:
{evidence}
"""


def _build_conclusion_input(sid: str):
    """Assemble the (title, abstract, evidence-text) for the conclusion LLM call from
    artifact_a. Returns None if no claims are computed yet."""
    sub = _sub_dir(sid)
    a = _load_json(sub / f"{sid}_artifact_a.json")
    if a is None or not a.get("claims"):
        return None
    submeta = _load_json(sub / f"{sid}.json") or {}
    claims_doc = _load_json(sub / f"{sid}_claims.json") or {"claims": []}
    order = [c["id"] for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    ranked = _load_json(sub / "related_work_data" / "ranked_papers.json") or []
    meta = {p.get("paper_id"): p for p in ranked}
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}

    blocks, any_overlap = [], False
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        lines = [f"CLAIM: {e.get('claim_text') or e.get('claim_name','')}"]
        real = _segments_text(e.get("claim_realization"))
        if real:
            lines.append(f"  What the submission does: {real[:900]}")
        overlaps = []
        for c in (e.get("comparisons") or []):
            deg = (c.get("overlap_degree") or "").lower()
            challenges = c.get("refutation_status") == "can_refute"
            if not (challenges or deg in _OVERLAP_DEGREES):
                continue
            _m = meta.get(c.get("paper_id"), {})
            cite = _author_year(c.get("authors") or _m.get("authors", ""),
                                c.get("year") or _m.get("year", ""))
            head = f"{cite} — \"{c.get('title','')}\"" if cite else f"\"{c.get('title','')}\""
            bits = [f"overlap: {deg}" + (" (challenges the claim's novelty)" if challenges else "")]
            if c.get("what_is_shared"):
                bits.append(f"shared: {c['what_is_shared']}")
            if c.get("submission_delta"):
                bits.append(f"submission adds: {c['submission_delta']}")
            if c.get("assessment"):
                bits.append(f"assessment: {c['assessment']}")
            overlaps.append(f"    - {head}; " + "; ".join(bits))
        if overlaps:
            any_overlap = True
            lines.append("  Overlapping prior work:")
            lines.extend(overlaps)
        else:
            lines.append("  Overlapping prior work: none found (no prior work delivers this contribution).")
        blocks.append("\n".join(lines))
    return {
        "title": submeta.get("title", ""),
        "abstract": (submeta.get("abstract", "") or "")[:2500],
        "evidence": "\n\n".join(blocks),
        "n_claims": len(blocks),
        "any_overlap": any_overlap,
    }


@app.get("/submissions/{sid}/review/conclusion")
def get_conclusion(sid: str):
    """Cached overall-novelty conclusion, or {text: None} if not generated yet."""
    doc = _load_json(_conclusion_path(sid))
    if doc and doc.get("text"):
        return doc
    return {"text": None}


@app.post("/submissions/{sid}/review/conclusion")
def generate_conclusion(sid: str):
    """Generate (and cache) the concluding overall-novelty paragraph from the gathered
    claim-level evidence. Grounded ONLY in artifact_a -- no fresh analysis."""
    data = _build_conclusion_input(sid)
    if data is None:
        raise HTTPException(404, "no claims computed yet -- run the claim-level review first")
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not set")
    model = os.getenv("NOVELTY_CONCLUSION_MODEL", "gpt-4.1")
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.2}
    llm = ChatOpenAI(model_name=model, api_key=api_key, max_retries=4, timeout=180, **kw)
    prompt = _CONCLUSION_PROMPT.format(title=data["title"], abstract=data["abstract"],
                                       evidence=data["evidence"])
    try:
        text = (llm.invoke(prompt).content or "").strip()
    except Exception as e:
        raise HTTPException(502, f"conclusion generation failed: {repr(e)[:200]}")
    doc = {"text": text, "model": model, "n_claims": data["n_claims"],
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        _conclusion_path(sid).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return doc


@app.get("/submissions/{sid}/{artifact}")
def get_artifact(sid: str, artifact: str):
    if artifact not in ("artifact_a", "artifact_b", "judge"):
        raise HTTPException(404, "unknown artifact")
    doc = _load_json(_sub_dir(sid) / f"{sid}_{artifact}.json")
    if doc is None:
        raise HTTPException(404, f"{artifact} not ready")
    return doc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8099, log_level="info")
