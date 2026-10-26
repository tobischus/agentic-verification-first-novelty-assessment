"""Backend API of the reviewer interface (Section 4.8).

Runs the pipeline up to the two checkpoints, lets the reviewer edit claims and prior work,
runs the comparison per claim in a background thread and serves the report.

Run: PYTHONUTF8=1 python src/novelty_assessment/api.py  (serves on :8099)
"""

import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import NoveltyPipeline
import claim_extraction as ce
import verdict as vd

DATA_DIR = os.getenv("NOVELTY_DATA_DIR", "data")
AGENT_MODEL = os.getenv("NOVELTY_MODEL", "gpt-5.6-luna")
CONCLUSION_MODEL = os.getenv("NOVELTY_CONCLUSION_MODEL", AGENT_MODEL)
GROBID_SERVER = os.getenv("GROBID_SERVER", "http://localhost:8070")

app = FastAPI(title="Verification-First Novelty Assessment API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_running = set()
_lock = threading.Lock()


def _sub_dir(sid: str) -> Path:
    return Path(DATA_DIR) / sid


def _load_json(path: Path):
    """JSON content of a file, or None if it is missing or being written."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _start_run(sid: str, pdf: Optional[str] = None) -> bool:
    """Run the pipeline to the next checkpoint in a background thread."""
    with _lock:
        if sid in _running:
            return False
        _running.add(sid)

    def _target():
        try:
            NoveltyPipeline(
                DATA_DIR, sid, pdf_path=pdf, hitl=True, grobid_server=GROBID_SERVER
            ).run()
        finally:
            with _lock:
                _running.discard(sid)

    threading.Thread(target=_target, daemon=True).start()
    return True


@app.post("/submissions")
async def create_submission(file: UploadFile = File(...), submission_id: Optional[str] = None):
    """Store an uploaded PDF under a new timestamped submission id and start the pipeline."""
    base = submission_id or Path(file.filename).stem
    sid = f"{base}__{time.strftime('%Y%m%d-%H%M%S')}"
    d = _sub_dir(sid)
    d.mkdir(parents=True, exist_ok=True)
    pdf = d / f"{sid}.pdf"
    pdf.write_bytes(await file.read())
    _start_run(sid, str(pdf))
    return {"submission_id": sid, "base_id": base, "status": "started"}


@app.get("/submissions/{sid}/state")
def get_state(sid: str):
    state = _load_json(_sub_dir(sid) / f"{sid}_pipeline_state.json")
    if state is None:
        raise HTTPException(404, "no such submission")
    state["running"] = sid in _running
    prog = _load_json(_sub_dir(sid) / f"{sid}_progress.json")
    if prog is not None:
        state["progress"] = prog
    return state


@app.get("/submissions/{sid}/claims")
def get_claims(sid: str):
    doc = _load_json(_sub_dir(sid) / f"{sid}_claims.json")
    if doc is None:
        raise HTTPException(404, "claims not ready")
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
    """Claims checkpoint: accept, edit, delete or add claims."""
    path = _sub_dir(sid) / f"{sid}_claims.json"
    doc = _load_json(path)
    if doc is None:
        raise HTTPException(404, "claims not ready")
    for o in ops.operations:
        if o.op == "accept":
            ce.accept_claim(doc, o.claim_id)
        elif o.op == "edit":
            fields = {
                k: v
                for k, v in {
                    "name": o.name,
                    "claim_text": o.claim_text,
                    "description": o.description,
                    "source": o.source,
                }.items()
                if v is not None
            }
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
    """Set the submission date t(S) by hand when it could not be determined."""
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
    for doc, path in (
        (meta, meta_path),
        (_load_json(sub / f"{sid}_claims.json"), sub / f"{sid}_claims.json"),
    ):
        if doc is None:
            continue
        doc["publication_date"] = val
        doc["year"] = val[:4]
        doc["date_source"] = "reviewer"
        doc["date_needs_review"] = False
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "publication_date": val, "year": val[:4], "date_source": "reviewer"}


def _pdf_path(sid: str, paper_id: str) -> Path:
    return _sub_dir(sid) / "related_work_data" / "pdfs" / f"{paper_id}.pdf"


@app.get("/submissions/{sid}/papers")
def get_papers(sid: str):
    rp = _load_json(_sub_dir(sid) / "related_work_data" / "ranked_papers.json")
    if rp is None:
        raise HTTPException(404, "papers not ready")
    for p in rp:
        pp = _pdf_path(sid, p.get("paper_id", ""))
        p["pdf_available"] = pp.exists() and pp.stat().st_size > 0
    return {"count": len(rp), "papers": rp}


@app.post("/submissions/{sid}/papers/{paper_id}/pdf")
async def upload_paper_pdf(sid: str, paper_id: str, file: UploadFile = File(...)):
    """Prior-work checkpoint: upload the PDF of a pool paper that could not be downloaded."""
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


def _submission_pdf_path(sid: str) -> Optional[Path]:
    recorded = (_load_json(_sub_dir(sid) / f"{sid}_pipeline_state.json") or {}).get("pdf_path")
    for cand in (Path(recorded) if recorded else None, _sub_dir(sid) / f"{sid}.pdf"):
        if cand and cand.exists():
            return cand
    return None


@app.get("/submissions/{sid}/pdf")
def submission_pdf(sid: str):
    path = _submission_pdf_path(sid)
    if path is None:
        raise HTTPException(404, "no PDF stored for this submission")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{sid}.pdf"'},
    )


@app.get("/submissions/{sid}/papers/{paper_id}/pdf")
def paper_pdf(sid: str, paper_id: str):
    path = _pdf_path(sid, paper_id)
    if not path.exists():
        raise HTTPException(404, "no PDF stored for this paper")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{paper_id}.pdf"'},
    )


class PaperEdit(BaseModel):
    remove: List[str] = []
    add: List[dict] = []


@app.patch("/submissions/{sid}/papers")
def edit_papers(sid: str, edit: PaperEdit):
    """Prior-work checkpoint: remove papers from the pool or add given records."""
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


def _norm_title(s: str) -> str:
    return "".join((s or "").lower().split()).replace("-", "")


_EMB_MODEL = None


def _embed_model():
    """The SPECTER2 model, loaded once."""
    global _EMB_MODEL
    if _EMB_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _EMB_MODEL = SentenceTransformer("allenai/specter2_base")
    return _EMB_MODEL


def _compute_relevance(sid: str, abstract: str):
    """Cosine similarity of the submission abstract and a paper abstract."""
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
    pid = d.get("paperId") or (
        "ext_" + (ext.get("DOI") or ext.get("ArXiv") or d.get("title", ""))[:48]
    )
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
    """Resolve a DOI, arXiv id or title to a paper record via Semantic Scholar."""
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
            r = requests.get(
                f"{base}/{idexpr}", params={"fields": fields}, headers=headers, timeout=20
            )
            if r.status_code == 200 and r.json():
                return _paper_from_s2(r.json())
            return None
        r = requests.get(
            f"{base}/search/match",
            params={"query": q, "fields": fields},
            headers=headers,
            timeout=20,
        )
        if r.status_code == 200:
            items = (r.json() or {}).get("data") or []
            if items:
                return _paper_from_s2(items[0])
    except Exception:
        return None
    return None


def _resolve_paper_pdf(sid: str, raw: bytes, filename: str):
    """Title and abstract of an uploaded prior-work PDF via GROBID, enriched from Semantic Scholar."""
    from lxml import etree

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "preprocess"))
    from grobid_client import GrobidClient

    uploads = _sub_dir(sid) / "related_work_data" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    pdf_path = uploads / (filename or "added.pdf")
    pdf_path.write_bytes(raw)
    try:
        tei = GrobidClient(GROBID_SERVER).pdf_to_tei(str(pdf_path))
        root = etree.fromstring(tei.encode("utf-8"))
        ns = {"t": "http://www.tei-c.org/ns/1.0"}
        title = (
            root.findtext(".//t:teiHeader//t:titleStmt/t:title", default="", namespaces=ns) or ""
        ).strip()
        abs_el = root.find(".//t:teiHeader//t:profileDesc//t:abstract", namespaces=ns)
        abstract = " ".join(abs_el.itertext()).strip() if abs_el is not None else ""
    except Exception:
        return None
    if not title:
        return None
    enriched = _resolve_paper_query(title)
    if enriched:
        a, b = _norm_title(title), _norm_title(enriched.get("title", ""))
        if a[:50] in b or b[:50] in a:
            if not enriched.get("abstract"):
                enriched["abstract"] = abstract
            enriched["added_by"] = "reviewer"
            return enriched
    return {
        "paper_id": "pdf_" + hashlib.sha1(raw).hexdigest()[:12],
        "title": title,
        "abstract": abstract,
        "year": "",
        "venue": "",
        "authors": "",
        "citation_count": 0,
        "cited_paper": False,
        "novel": None,
        "relevance": None,
        "added_by": "reviewer",
    }


@app.post("/submissions/{sid}/papers/add")
async def add_related_paper(
    sid: str, query: Optional[str] = Form(None), file: UploadFile = File(None)
):
    """Prior-work checkpoint: add a paper by DOI, arXiv id, title or PDF."""
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
    paper["relevance"] = _compute_relevance(sid, paper.get("abstract"))
    rp.append(paper)
    path.write_text(json.dumps(rp, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"added": True, "paper": paper, "count": len(rp), "papers": rp}


@app.post("/submissions/{sid}/checkpoints/{cp}/approve")
def approve_checkpoint(sid: str, cp: str):
    pipe = NoveltyPipeline(DATA_DIR, sid)
    if not pipe.state_path.exists():
        raise HTTPException(404, "no such submission")
    pipe.approve(cp)
    _start_run(sid)
    return {"submission_id": sid, "approved": cp, "status": "resuming"}


def _relevance_band(sim):
    if sim is None:
        return None
    if sim >= 0.8:
        return "High"
    if sim >= 0.6:
        return "Medium"
    return "Low"


def _source_label(content_source):
    cs = (content_source or "").lower()
    if cs.startswith("full"):
        return "Full text"
    if "abstract" in cs:
        return "Abstract + intro"
    return ""


def _clusters_of(ranked):
    out, seen = [], set()
    for p in ranked:
        lab = p.get("cluster_label")
        if lab and lab not in seen:
            seen.add(lab)
            out.append(lab)
    return out


def _assemble_claim(entry, meta):
    """The review view of one claim: ranked prior work and the detailed comparisons."""
    comps = entry.get("comparisons", []) or []
    comp_by = {c.get("paper_id"): c for c in comps}
    explore = []
    for p in entry.get("frontier") or []:
        pid = p.get("paper_id")
        c = comp_by.get(pid, {})
        sim = p.get("similarity")
        explore.append(
            {
                "paper_id": pid,
                "title": p.get("title", ""),
                "authors": p.get("authors", ""),
                "year": p.get("year", ""),
                "venue": p.get("venue", ""),
                "relevance": sim,
                "band": _relevance_band(sim),
                "provenance": p.get("source"),
                "cited_by_submission": p.get("cited_by_submission", False),
                "examined": bool(p.get("examined")),
                "compared": bool(p.get("compared")),
                "challenges": vd.challenges(c),
                "overlap_degree": c.get("overlap_degree"),
                "note": c.get("relevance_reason") or c.get("brief_note", ""),
                "source": _source_label(c.get("content_source"))
                if c
                else ("Full text" if p.get("has_fulltext") else "Abstract + intro"),
            }
        )
    verify = []
    for c in comps:
        pairs = c.get("evidence_pairs") or []
        # 1-based indices, as referenced by the evidence check's supporting_pair_indices.
        verified_indexed = [
            (i, p)
            for i, p in enumerate(pairs, 1)
            if p.get("claim_quote_verified") and p.get("paper_quote_verified")
        ]
        _m = meta.get(c.get("paper_id"), {})
        check = c.get("evidence_check") or {}
        verify.append(
            {
                "paper_id": c.get("paper_id"),
                "title": c.get("title"),
                "authors": c.get("authors") or _m.get("authors", ""),
                "year": c.get("year") or _m.get("year", ""),
                "challenges": vd.challenges(c),
                "status": c.get("refutation_status"),
                "analysis": c.get("brief_note", ""),
                "source": _source_label(c.get("content_source")),
                "depth": c.get("depth"),
                "sections_used": c.get("sections_used", []),
                "fulltext_fetch_status": c.get("fulltext_fetch_status"),
                "overlap_degree": c.get("overlap_degree"),
                "is_overlap": vd.is_overlap(c),
                "overlap_rank": vd.degree_rank(vd.degree(c)),
                "overlap_dimensions": c.get("overlap_dimensions", []),
                "what_is_shared": c.get("what_is_shared", ""),
                "submission_delta": c.get("submission_delta", ""),
                "paper_realization": c.get("paper_realization", []),
                "assessment": c.get("assessment", ""),
                "evidence": [
                    {
                        "pair_index": i,
                        "claim_quote": p.get("claim_quote"),
                        "paper_quote": p.get("paper_quote"),
                        "rationale": p.get("rationale"),
                    }
                    for i, p in verified_indexed
                ],
                "verified": bool(verified_indexed),
                "decision_trace": list((c.get("map_diag") or {}).get("loop") or []),
                "evidence_status": check.get("status"),
                "supporting_pair_indices": check.get("supporting_pair_indices", []),
                "evidence_reasoning": check.get("reasoning", ""),
                "grounded_pairs": len(verified_indexed),
                "insufficient": bool(c.get("insufficient")),
                "unresolved": bool(c.get("unresolved") or c.get("insufficient")),
                "unresolved_reason": c.get("unresolved_reason", ""),
                "unresolved_deficit": c.get("unresolved_deficit", ""),
                "paper_state": c.get("paper_state", ""),
            }
        )
    return {
        "claim_id": entry.get("claim_id"),
        "claim_text": entry.get("claim_text") or entry.get("claim_name", ""),
        "claim_realization": entry.get("claim_realization", []),
        "explore": explore,
        "verify": verify,
        "timings": entry.get("timings"),
        "agent": {
            "verdict": entry.get("agent_verdict"),
            "evidence_sufficient": entry.get("evidence_sufficient", True),
            "review_complete": entry.get("review_complete", True),
            "unresolved_count": entry.get("unresolved_count", 0),
            "unresolved_papers": entry.get("unresolved_papers", []),
            "stop_reason": entry.get("stop_reason"),
            "retrieval_rounds": entry.get("retrieval_rounds", 0),
            "pool_sources": entry.get("pool_sources", {}),
            "n_steps": len(entry.get("trajectory", []) or []),
        },
    }


@app.get("/submissions/{sid}/review/claims")
def review_claims(sid: str):
    """Claim list of the review, with the computed claims marked."""
    claims_doc = _load_json(_sub_dir(sid) / f"{sid}_claims.json")
    if claims_doc is None:
        raise HTTPException(404, "claims not ready")
    ranked = _load_json(_sub_dir(sid) / "related_work_data" / "ranked_papers.json") or []
    a = _load_json(_sub_dir(sid) / f"{sid}_artifact_a.json") or {"claims": []}
    computed = {e.get("claim_id") for e in a.get("claims", [])}
    claims = [
        {
            "claim_id": c["id"],
            "claim_text": c.get("claim_text") or c.get("name", ""),
            "computed": c["id"] in computed,
        }
        for c in claims_doc.get("claims", [])
        if c.get("status") != "rejected"
    ]
    return {
        "submission_id": sid,
        "n_reference_papers": len(ranked),
        "clusters": _clusters_of(ranked),
        "claims": claims,
    }


_claim_running = set()
_claim_lock = threading.Lock()
_artifact_lock = threading.Lock()


def _live_path(sid: str, cid: str) -> Path:
    return _sub_dir(sid) / f"{sid}_claim_{cid}_live.json"


def _write_live(sid: str, cid: str, payload: dict):
    try:
        _live_path(sid, cid).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _assembled_for(sid: str, cid: str):
    sub = _sub_dir(sid)
    a = _load_json(sub / f"{sid}_artifact_a.json") or {"claims": []}
    ae = next((e for e in a.get("claims", []) if e.get("claim_id") == cid), None)
    if ae is None:
        return None
    ranked = _load_json(sub / "related_work_data" / "ranked_papers.json") or []
    meta = {p.get("paper_id"): p for p in ranked}
    return _assemble_claim(ae, meta)


def _ensure_claim_assessments(sid: str, only: Optional[str] = None) -> List[str]:
    """Write the claim explanations (first report stage) where missing or stale."""
    import claim_assessment as ca

    contexts, b_path, b, refs = ca.contexts_for(DATA_DIR, sid)
    stored = {v.get("claim_id"): v.get("claim_assessment") for v in b.get("per_claim", [])}
    todo = [
        x
        for x in contexts
        if (only is None or x[0] == only)
        and x[0] in stored
        and (not stored[x[0]] or ca.is_stale(stored[x[0]], x[4]))
    ]
    if not todo:
        return []
    assessor = ca.ClaimAssessor(model_name=CONCLUSION_MODEL)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda x: assessor.assess(x[4], x[2], x[3], refs), todo))
    by_id = {x[0]: r for x, r in zip(todo, results)}
    with _artifact_lock:
        b = _load_json(b_path) or b
        for v in b.get("per_claim", []):
            if v.get("claim_id") in by_id:
                v["claim_assessment"] = by_id[v["claim_id"]]
        b_path.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(by_id)


def _claim_worker(sid: str, cid: str):
    """Run the agent for one claim, stream its progress, then store the results."""
    try:
        sub = _sub_dir(sid)
        claims_doc = _load_json(sub / f"{sid}_claims.json") or {"claims": []}
        claim = next(
            (
                c
                for c in claims_doc.get("claims", [])
                if c["id"] == cid and c.get("status") != "rejected"
            ),
            None,
        )
        if claim is None:
            _write_live(sid, cid, {"status": "error", "claim_id": cid, "error": "claim not found"})
            return
        _write_live(
            sid,
            cid,
            {
                "status": "running",
                "claim_id": cid,
                "step": 0,
                "max_steps": 0,
                "trajectory": [],
                "cost": {"prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0},
            },
        )

        from agent.claim_agent import ClaimNoveltyAgent

        agent = ClaimNoveltyAgent(
            DATA_DIR,
            sid,
            embedder=_embed_model(),
            model_name=AGENT_MODEL,
            grobid_server=GROBID_SERVER,
            max_retrievals=int(os.getenv("NOVELTY_AGENT_MAX_RETRIEVALS", "1")),
        )
        entry = agent.run(claim, progress_cb=lambda info: _write_live(sid, cid, info))

        with _artifact_lock:
            a_path = sub / f"{sid}_artifact_a.json"
            a = _load_json(a_path) or {
                "submission_id": sid,
                "agentic": True,
                "n_related_pool": 0,
                "claims": [],
            }
            a["claims"] = [e for e in a["claims"] if e.get("claim_id") != cid] + [entry]
            a["n_related_pool"] = sum(entry.get("pool_sources", {}).values()) or a.get(
                "n_related_pool", 0
            )
            a_path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")

            b_path = sub / f"{sid}_artifact_b.json"
            b_doc = _load_json(b_path) or {
                "submission_id": sid,
                "generated_from": f"{sid}_artifact_a.json",
                "per_claim": [],
                "overall_assessment": "",
            }
            b_doc["per_claim"] = [v for v in b_doc.get("per_claim", []) if v.get("claim_id") != cid]
            b_doc["per_claim"].append(
                {
                    "claim_id": entry["claim_id"],
                    "claim_name": entry.get("claim_name", ""),
                    "verdict": entry.get("agent_verdict"),
                    "rationale": "",
                    "challenging_papers": [],
                }
            )
            b_path.write_text(json.dumps(b_doc, ensure_ascii=False, indent=2), encoding="utf-8")

        _write_live(
            sid,
            cid,
            {
                "status": "running",
                "claim_id": cid,
                "step": len(entry.get("trajectory", []) or []),
                "max_steps": 0,
                "trajectory": entry.get("trajectory", []),
                "cost": entry.get("cost", {}),
                "last_action": "writing the claim-level assessment",
            },
        )
        try:
            _ensure_claim_assessments(sid, only=cid)
        except Exception as e:
            print(f"[{sid}] claim assessment for {cid} skipped: {repr(e)[:160]}")

        _write_live(
            sid,
            cid,
            {
                "status": "done",
                "claim_id": cid,
                "step": len(entry.get("trajectory", []) or []),
                "max_steps": 0,
                "trajectory": entry.get("trajectory", []),
                "cost": entry.get("cost", {}),
                "verdict": entry.get("agent_verdict"),
                "evidence_sufficient": entry.get("evidence_sufficient"),
                "stop_reason": entry.get("stop_reason"),
                "retrieval_rounds": entry.get("retrieval_rounds", 0),
                "review": _assembled_for(sid, cid),
            },
        )
    except Exception as e:
        _write_live(sid, cid, {"status": "error", "claim_id": cid, "error": repr(e)[:300]})
    finally:
        with _claim_lock:
            _claim_running.discard((sid, cid))


@app.post("/submissions/{sid}/review/claim/{claim_id}")
def compute_claim(sid: str, claim_id: str):
    """Start the comparison for one claim; progress is polled via .../live."""
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


@app.post("/submissions/{sid}/review/claim/{claim_id}/assessment")
def claim_assessment_for(sid: str, claim_id: str):
    """Make sure a computed claim has a current explanation."""
    a = _load_json(_sub_dir(sid) / f"{sid}_artifact_a.json") or {"claims": []}
    if not any(e.get("claim_id") == claim_id for e in a.get("claims", [])):
        raise HTTPException(404, "claim not computed yet")
    try:
        return {"status": "done", "generated": _ensure_claim_assessments(sid, only=claim_id)}
    except Exception as e:
        raise HTTPException(502, f"claim assessment failed: {repr(e)[:200]}")


@app.post("/submissions/{sid}/review/finalize")
def finalize_review(sid: str):
    """Update all claim explanations and write the paper-level summary."""
    sub = _sub_dir(sid)
    if _load_json(sub / f"{sid}_artifact_a.json") is None:
        raise HTTPException(404, "no claims computed yet -- run the claim-level review first")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(500, "OPENAI_API_KEY not set")
    try:
        regenerated = _ensure_claim_assessments(sid)
    except Exception as e:
        raise HTTPException(502, f"claim assessment failed: {repr(e)[:200]}")
    import paper_synthesis

    summary_written = False
    try:
        findings, _b_path, b = paper_synthesis.context_for(DATA_DIR, sid)
        stored = b.get("paper_summary")
        if not stored or paper_synthesis.is_stale(stored, findings):
            with _artifact_lock:
                paper_synthesis.build(DATA_DIR, sid, model_name=CONCLUSION_MODEL)
            summary_written = True
    except Exception as e:
        raise HTTPException(502, f"novelty summary failed: {repr(e)[:200]}")
    return {"status": "done", "claims_regenerated": regenerated, "summary_written": summary_written}


@app.get("/submissions/{sid}/review/claim/{claim_id}/live")
def claim_live(sid: str, claim_id: str):
    live = _load_json(_live_path(sid, claim_id))
    if live is not None:
        return live
    rev = _assembled_for(sid, claim_id)
    if rev is not None:
        return {"status": "done", "claim_id": claim_id, "trajectory": [], "cost": {}, "review": rev}
    return {"status": "idle", "claim_id": claim_id}


@app.get("/submissions/{sid}/review/export", response_class=PlainTextResponse)
def export_assessment(sid: str):
    """The report as text, rendered from the artifacts by a template."""
    from battle_export import build

    try:
        return build(DATA_DIR, sid)
    except FileNotFoundError:
        raise HTTPException(404, "no claims computed yet -- run the claim-level review first")


@app.get("/submissions/{sid}/review/quote_index")
def export_quote_index(sid: str):
    """For each verified quote of the report, the document and position it is found in."""
    from battle_export import quote_index

    return quote_index(DATA_DIR, sid)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8099, log_level="info")
