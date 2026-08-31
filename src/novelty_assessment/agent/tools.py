#!/usr/bin/env python3
"""
ClaimToolbox: the resources + tool implementations + the evidence ledger for one
claim's agent run.

The toolbox owns everything that keeps the agent's context small and its evidence
honest:
  * loads the submission and the related-work pool once (initial / reviewer / agent
    provenance), builds passage indices lazily per paper;
  * exposes the read tools that return only top-k passages (never whole PDFs);
  * runs retrieve_more (R7) into a SEPARATE agent_retrieved_papers.json;
  * verifies every quote in record_comparison against the real source text
    (evidence-grounding invariant) and downgrades unverifiable can_refute;
  * tracks the ledger signals the finish-gate reads (examined depth, comparisons,
    retrievals, closest_set), so the STOP decision is deterministic and
    ledger-checkable rather than model-asserted.

The gate policy itself (accept/reject + escalation messages) lives in
claim_agent.py; the toolbox only supplies the signals.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
from rapidfuzz import fuzz

from . import evidence
from . import retrieve_more as rm
from .passages import (
    PassageIndex,
    chunks_from_grobid_text,
    chunks_from_plain,
    chunks_from_sections,
)

# depth ladder (relative to availability); higher = deeper. abstract_only is the
# only level that does NOT count as "sufficiently examined".
_DEPTH_RANK = {
    "abstract_only": 0,
    "abstract_intro": 1,
    "fulltext_unavailable": 1,
    "targeted_sections": 2,
    "fulltext_available_targeted_read": 2,
}
_SUFFICIENT_DEPTHS = {
    "abstract_intro",
    "fulltext_unavailable",
    "targeted_sections",
    "fulltext_available_targeted_read",
}


class ClaimToolbox:
    def __init__(
        self,
        data_dir: str,
        submission_id: str,
        claim: dict,
        embedder,
        *,
        closest_n: int = 5,
        list_top: int = 15,
        min_quote_tokens: int = evidence.DEFAULT_MIN_QUOTE_TOKENS,
        fuzzy_threshold: float = evidence.DEFAULT_FUZZY_THRESHOLD,
        retrieve_k: int = 10,
        fetch_fulltext_for_new: int = 3,
        grobid_server: str = "http://localhost:8070",
    ):
        self.data_dir = data_dir
        self.submission_id = submission_id
        self.claim = claim
        self.embedder = embedder
        self.closest_n = closest_n
        self.list_top = list_top
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.retrieve_k = retrieve_k
        self.fetch_fulltext_for_new = fetch_fulltext_for_new
        self.grobid_server = grobid_server

        self.sub_dir = Path(data_dir) / submission_id
        self._meta = self._load_json(self.sub_dir / f"{submission_id}.json") or {}
        self.cutoff_year = self._cutoff_year()
        # Submission identity + date for the SAME prior-work admissibility rule the main
        # retrieval uses (exclude the submission itself; only papers published before it).
        self.sub_title = (self._meta.get("title") or "").strip()
        self.sub_pub_date = self._meta.get("publication_date") or datetime.now().strftime("%Y-%m-%d")

        # --- submission text + index + verification corpus ---
        ft = self._load_json(self.sub_dir / f"{submission_id}_fulltext.json") or {}
        sub_sections = ft.get("sections", [])
        self._submission_index = PassageIndex(chunks_from_sections(sub_sections, "submission"), embedder)
        # what a claim_quote is verified against: body + abstract + the claim itself
        self._submission_text = "\n\n".join(
            [s.get("text", "") for s in sub_sections]
            + [self._meta.get("abstract", ""), claim.get("claim_text", ""), claim.get("description", "")]
        )

        # --- related-work pool (with provenance) + claim similarity ---
        self.pool = {}
        self._load_pool()
        self._score_pool()  # fills pool[pid]['sim']

        self._paper_index = {}   # pid -> PassageIndex (lazy)
        self._paper_text = {}    # pid -> full source text for verification (lazy)
        self._citation_ctx = self._load_citation_contexts()

        # Deep dives run in PARALLEL (independent per-paper LLM comparisons), so every
        # mutation of the shared ledger/progress state is serialized by this lock. The
        # slow work (PDF parse, LLM call, embedding index build) stays outside the lock,
        # so only the fast bookkeeping is serialized -- no loss of parallelism.
        self._lock = threading.RLock()
        # Separate lock for the SPECTER2 embedder: PassageIndex encodes eagerly on build,
        # and one PyTorch model shared across deep-dive threads is not guaranteed
        # thread-safe for concurrent forward passes. Serializing the (~200ms) index build
        # is negligible next to the ~60s LLM comparison it precedes.
        self._embed_lock = threading.Lock()

        # --- ledger ---
        self.ledger = {
            "examined": {},      # pid -> {depth, source, similarity, has_comparison}
            "comparisons": [],   # artifact_a-shaped comparison dicts (+ extras)
            "retrievals": [],    # [{query, n_new, added_ids}]
            "trajectory": [],    # compact action log (no raw reasoning)
        }
        # section-based understanding of what the SUBMISSION does for this claim
        # (verified-quote segments), built once and reused across every comparison
        self.claim_realization = []
        # which sections were actually read in full per paper_id (incl. "submission"),
        # so the review can show "sections used for the comparison" instead of "full text"
        self._sections_read = {}
        self._steps_since_progress = 0

    # ------------------------------ loading ------------------------------ #

    @staticmethod
    def _load_json(p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        except Exception:
            return None

    def _cutoff_year(self) -> Optional[int]:
        for v in (self._meta.get("year"), (self._meta.get("publication_date") or "")[:4]):
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        # No date in metadata (e.g. anonymised submission) -> fall back to the current
        # year, same "under review now" logic as retrieval.process_for_pipeline, so
        # retrieve_more never pulls papers newer than the submission.
        return datetime.now().year

    def _load_intro(self, pid: str) -> str:
        for rel in (f"introductions/{pid}_intro.txt", f"ours/related_papers/{pid}_intro.txt"):
            p = self.sub_dir / rel
            if p.exists():
                return p.read_text(encoding="utf-8")
        return ""

    def _load_fulltext_file(self, pid: str) -> str:
        for rel in (
            f"related_work_data/nougat_output/{pid}.mmd",
            f"related_work_data/grobid_fulltext/{pid}.txt",
            f"related_work_data/mineru_output/{pid}.md",
            f"related_work_data/mineru_output/{pid}/{pid}.md",
        ):
            p = self.sub_dir / rel
            if p.exists():
                return p.read_text(encoding="utf-8")
        return ""

    def _add_pool_paper(self, p: dict, source: str):
        pid = p.get("paper_id")
        if not pid or pid in self.pool:
            return
        # never let the submission itself into the pool (near-duplicate title)
        title = p.get("title", "") or ""
        if self.sub_title and fuzz.ratio(title.lower(), self.sub_title.lower()) >= 90:
            return
        self.pool[pid] = {
            "paper_id": pid,
            "title": p.get("title", "") or "",
            "abstract": p.get("abstract", "") or "",
            "authors": p.get("authors", "") or "",
            "year": p.get("year", "") or "",
            "venue": p.get("venue", "") or "",
            "cited_paper": bool(p.get("cited_paper", False)),
            "intro": self._load_intro(pid),
            "fulltext": self._load_fulltext_file(pid),
            "source": source,
        }

    def _load_pool(self):
        ranked = self._load_json(self.sub_dir / "related_work_data" / "ranked_papers.json") or []
        for p in ranked:
            self._add_pool_paper(p, "reviewer" if p.get("added_by") == "reviewer" else "initial")
        agent_papers = self._load_json(
            self.sub_dir / "related_work_data" / "agent_retrieved_papers.json"
        ) or []
        for p in agent_papers:
            self._add_pool_paper(p, "agent")

    def _score_pool(self):
        if not self.pool:
            return
        claim_doc = (
            f"{self.claim.get('name','')}. {self.claim.get('description','')} "
            f"{self.claim.get('claim_text','')}"
        ).strip()
        pids = list(self.pool)
        docs = [f"{self.pool[pid]['title']}. {self.pool[pid]['abstract']}" for pid in pids]
        embs = self.embedder.encode([claim_doc] + docs, convert_to_numpy=True)
        claim_emb, cand_embs = embs[0], embs[1:]
        sims = cand_embs @ claim_emb / (
            np.linalg.norm(cand_embs, axis=1) * np.linalg.norm(claim_emb) + 1e-9
        )
        for pid, s in zip(pids, sims):
            self.pool[pid]["sim"] = float(s)

    def _load_citation_contexts(self) -> dict:
        """cited-paper title -> citation context sentences (best-effort, from {id}.json)."""
        id_to_title = {c.get("id"): (c.get("title") or "") for c in self._meta.get("cited_papers", [])}
        out = {}
        for ctx in self._meta.get("citation_contexts", []):
            title = id_to_title.get(ctx.get("cited_paper_id"))
            if title:
                out.setdefault(title, []).append(ctx.get("context_sentence", ""))
        return out

    # ------------------------------ helpers ------------------------------ #

    def _has_fulltext(self, pid: str) -> bool:
        return bool(self.pool.get(pid, {}).get("fulltext"))

    def ensure_fulltext(self, pid: str) -> str:
        """GROBID-parse this paper's full text ON DEMAND, the first time it is
        actually deep-dived (most pool papers never reach this point, so most PDFs
        are never GROBID-parsed at all -- see fetch_fulltext.py's phase split).

        Returns a short status: "already_had" | "ok" | "no_pdf" | "parse_empty" |
        "parse_error". The caller records this on the comparison so the reviewer
        sees WHY a deep dive used only the abstract (no PDF ever obtained vs. the
        available PDF could not be parsed). Parsing is IN PROCESS (PyMuPDF, ~1s)
        -- no GROBID service involved for related work."""
        if pid == "submission" or self._has_fulltext(pid):
            return "already_had"
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from fetch_fulltext import FullTextFetcher

            status = FullTextFetcher(self.grobid_server).parse_one(
                self.data_dir, self.submission_id, pid
            )
        except Exception:
            status = "parse_error"
        if status == "ok":
            ft_path = self.sub_dir / "related_work_data" / "grobid_fulltext" / f"{pid}.txt"
            text = ft_path.read_text(encoding="utf-8")
            self.pool[pid]["fulltext"] = text
            self._paper_index.pop(pid, None)  # rebuild the section/passage index from full text
            self._paper_text.pop(pid, None)
        self._log("ensure_fulltext", f"{pid} -> {status}")
        return status

    def _paper_source_text(self, pid: str) -> str:
        """Full source text of a paper for quote verification (fulltext or abstract+intro)."""
        if pid not in self._paper_text:
            p = self.pool.get(pid, {})
            if p.get("fulltext"):
                txt = p["fulltext"]
            else:
                txt = "\n\n".join(x for x in (p.get("abstract", ""), p.get("intro", "")) if x)
            self._paper_text[pid] = txt
        return self._paper_text[pid]

    def _index_for(self, pid: str) -> PassageIndex:
        if pid == "submission":
            return self._submission_index
        if pid not in self._paper_index:
            # double-checked under the embed lock: serialize the eager SPECTER2 encode
            # across parallel deep-dive threads (and avoid two threads building the same
            # index -- though each pid is normally handled by exactly one worker).
            with self._embed_lock:
                if pid not in self._paper_index:
                    p = self.pool.get(pid, {})
                    if p.get("fulltext"):
                        chunks = chunks_from_grobid_text(p["fulltext"], pid)
                        if len(chunks) < 2:
                            chunks = chunks_from_plain(p["fulltext"], pid)
                    else:
                        blob = "\n\n".join(
                            x for x in (
                                ("Abstract: " + p.get("abstract", "")) if p.get("abstract") else "",
                                ("Introduction: " + p.get("intro", "")) if p.get("intro") else "",
                            ) if x
                        )
                        chunks = chunks_from_plain(blob, pid)
                    self._paper_index[pid] = PassageIndex(chunks, self.embedder)
        return self._paper_index[pid]

    def _log(self, action: str, summary: str, progress: bool = False):
        with self._lock:
            self.ledger["trajectory"].append(
                {"step": len(self.ledger["trajectory"]) + 1, "action": action, "detail": summary}
            )
            self._steps_since_progress = 0 if progress else self._steps_since_progress + 1

    def _bump_depth(self, pid: str, depth: str):
        with self._lock:
            e = self.ledger["examined"].setdefault(
                pid,
                {"depth": "abstract_only", "source": self.pool.get(pid, {}).get("source", "?"),
                 "similarity": round(self.pool.get(pid, {}).get("sim", 0.0), 4), "has_comparison": False},
            )
            if _DEPTH_RANK.get(depth, 0) > _DEPTH_RANK.get(e["depth"], 0):
                e["depth"] = depth

    def _ranked(self) -> List[dict]:
        """Pool papers ordered by claim similarity.

        There used to be an LLM reranker in front of this. It was removed: triage reads
        the ENTIRE pool regardless of order, so the ordering only affected which papers
        land in the top-20 `frontier` shown in the review UI -- one LLM call per claim for
        display order. Ordering still matters if a pool ever exceeds the 30-paper triage
        chunk size (it would change which abstracts are judged together); pools are
        currently ~20."""
        return sorted(self.pool.values(), key=lambda p: p.get("sim", 0.0), reverse=True)

    # ------------------------------- tools ------------------------------- #

    def search_submission(self, query: str, k: int = 5) -> dict:
        hits = self._submission_index.search(query, k=k)
        self._log("search_submission", f'q="{query[:60]}" -> {len(hits)} passages')
        return {"query": query, "passages": hits}

    def list_related_work(self, top: Optional[int] = None) -> dict:
        top = top or self.list_top
        ordered = self._ranked()[:top]
        items = []
        for p in ordered:
            pid = p["paper_id"]
            items.append({
                "paper_id": pid,
                "title": p["title"],
                "year": p["year"],
                "venue": p["venue"],
                "similarity": round(p.get("sim", 0.0), 4),
                "source": p["source"],
                "cited_by_submission": p["cited_paper"],
                "has_fulltext": self._has_fulltext(pid),
                "abstract_snippet": (p["abstract"][:240] + "…") if len(p["abstract"]) > 240 else p["abstract"],
                "examined_depth": self.ledger["examined"].get(pid, {}).get("depth"),
            })
        self._log("list_related_work", f"returned {len(items)} of {len(self.pool)} pool papers")
        return {"pool_size": len(self.pool), "closest_n": self.closest_n, "papers": items}

    def list_sections(self, paper_id: str) -> dict:
        idx = self._index_for(paper_id)
        secs = idx.section_names()
        self._log("list_sections", f"{paper_id}: {len(secs)} sections")
        return {"paper_id": paper_id, "sections": secs, "has_fulltext": self._has_fulltext(paper_id)}

    def section_menu(self, paper_id: str) -> List[dict]:
        """Section titles + short previews + sizes, so the agent can choose which to read."""
        return self._index_for(paper_id).section_previews()

    def read_sections(self, paper_id: str, names: List[str], max_total: int = 40000) -> dict:
        """Load the FULL text of the chosen sections (no small cap) into context. This is
        the section-based deep read: the agent picks sections by what they are about."""
        idx = self._index_for(paper_id)
        got = idx.get_sections(names, max_total=max_total)
        if paper_id != "submission":
            self._bump_depth(paper_id, "targeted_sections" if got else "abstract_intro")
        # remember the actual section titles loaded (document order, de-duped) so the
        # review can report exactly which sections backed each comparison
        lst = self._sections_read.setdefault(paper_id, [])
        for s in got:
            nm = s.get("name")
            if nm and nm not in lst:
                lst.append(nm)
        self._log("read_sections", f"{paper_id}: {len(got)} sections ({sum(len(s['text']) for s in got)} chars)")
        return {"paper_id": paper_id, "sections": got}

    def verify_segments(self, segments: List[dict], source: str) -> List[dict]:
        """Verify a realization's quote segments against the true source text.

        source = 'submission' or a paper_id. A quote that is found verbatim (>= min
        length, whitespace/OCR-tolerant) is kept as a verified quote and completed to
        its full sentence; a quote that cannot be located is DEMOTED to plain prose, so
        the narrative never presents an unverified span as a verbatim quote."""
        src = self._submission_text if source == "submission" else self._paper_source_text(source)
        out = []
        for seg in segments or []:
            kind = (seg.get("kind") or "text").lower()
            content = (seg.get("content") or "").strip()
            if not content:
                continue
            if kind == "quote":
                chk = evidence.verify_quote(content, src, self.min_quote_tokens, self.fuzzy_threshold)
                if chk.verified:
                    out.append({"kind": "quote", "verified": True,
                                "content": evidence.expand_to_sentence(content, src)})
                else:
                    out.append({"kind": "text", "verified": False, "content": content})
            else:
                out.append({"kind": "text", "content": content})
        return out

    def read_paper(self, paper_id: str, query: Optional[str] = None,
                   section: Optional[str] = None, k: int = 5) -> dict:
        if paper_id != "submission" and paper_id not in self.pool:
            return {"error": f"unknown paper_id '{paper_id}'"}
        has_ft = self._has_fulltext(paper_id) if paper_id != "submission" else True
        idx = self._index_for(paper_id)

        if section:
            text = idx.get_section(section)
            mode, payload = "section", {"section": section, "text": text or "(section not found)"}
            depth = "fulltext_available_targeted_read" if has_ft else "abstract_intro"
        elif query:
            payload = {"query": query, "passages": idx.search(query, k=k)}
            mode = "query"
            depth = "fulltext_available_targeted_read" if has_ft else "fulltext_unavailable"
        else:
            ab_txt = self.pool.get(paper_id, {}).get("abstract", "") if paper_id != "submission" else ""
            payload = {"abstract": ab_txt or self._meta.get("abstract", "")}
            mode, depth = "abstract", "abstract_only"

        if paper_id != "submission":
            self._bump_depth(paper_id, depth)
        self._log("read_paper", f"{paper_id} [{mode}] -> depth={depth}")
        return {"paper_id": paper_id, "has_fulltext": has_ft, **payload}

    def retrieve_more(self, query: str, k: Optional[int] = None) -> dict:
        k = k or self.retrieve_k
        new = rm.retrieve(
            query, self.claim, self.embedder,
            exclude_ids=set(self.pool),
            source_title=self.sub_title, source_pub_date=self.sub_pub_date,
            source_year=self.cutoff_year, source_abstract=self._meta.get("abstract", ""), k=k,
        )
        added = []
        for p in new:
            self._add_pool_paper(p, "agent")
            pid = p["paper_id"]
            self.pool[pid]["sim"] = float(p.get("similarity", 0.0))
            added.append(pid)
        if added:
            self._persist_agent_papers(new, query)
            if self.fetch_fulltext_for_new:
                self._best_effort_fulltext(added[: self.fetch_fulltext_for_new])
        self.ledger["retrievals"].append({"query": query, "n_new": len(added), "added_ids": added})
        self._log("retrieve_more", f'q="{query[:60]}" -> {len(added)} new papers', progress=True)
        return {
            "query": query,
            "n_new": len(added),
            "papers": [
                {"paper_id": p["paper_id"], "title": p["title"],
                 "similarity": round(p.get("similarity", 0.0), 4),
                 "has_fulltext": self._has_fulltext(p["paper_id"])}
                for p in new
            ],
        }

    def record_comparison(
        self,
        paper_id: str,
        refutation_status: str,
        relevance_reason: str = "",
        brief_note: str = "",
        overlap_dimensions: Optional[List[str]] = None,
        overlap_degree: str = "none",
        what_is_shared: str = "",
        submission_delta: str = "",
        evidence_pairs: Optional[List[dict]] = None,
        paper_realization: Optional[List[dict]] = None,
        assessment: str = "",
        fulltext_fetch_status: Optional[str] = None,
        log: bool = True,
    ) -> dict:
        if paper_id not in self.pool:
            return {"error": f"unknown paper_id '{paper_id}'"}
        paper_text = self._paper_source_text(paper_id)
        verified_pairs = []
        for ep in (evidence_pairs or []):
            v = evidence.verify_pair(
                ep.get("claim_quote", ""), ep.get("paper_quote", ""),
                self._submission_text, paper_text,
                self.min_quote_tokens, self.fuzzy_threshold,
            )
            # passages are cut to a char budget, so copied quotes can end mid-sentence;
            # once verified, restore the complete sentence from the true source text
            claim_q, paper_q = ep.get("claim_quote", ""), ep.get("paper_quote", "")
            if v["claim_quote_verified"]:
                claim_q = evidence.expand_to_sentence(claim_q, self._submission_text)
            if v["paper_quote_verified"]:
                paper_q = evidence.expand_to_sentence(paper_q, paper_text)
            verified_pairs.append({
                "claim_quote": claim_q,
                "paper_quote": paper_q,
                "rationale": ep.get("rationale", ""),
                "claim_quote_verified": v["claim_quote_verified"],
                "paper_quote_verified": v["paper_quote_verified"],
                "fully_verified": v["fully_verified"],
            })

        status = refutation_status
        note = brief_note
        downgraded = False
        if status == "can_refute" and not any(p["fully_verified"] for p in verified_pairs):
            status = "cannot_refute"
            note = "[downgraded: no beidseitig-verified evidence quote pair] " + note
            downgraded = True

        p = self.pool[paper_id]
        depth = self.ledger["examined"].get(paper_id, {}).get("depth", "abstract_only")
        comp = {
            "paper_id": paper_id,
            "title": p["title"],
            "authors": p.get("authors", "") or "",
            "year": p.get("year", "") or "",
            "cited_by_submission": p["cited_paper"],
            "similarity": round(p.get("sim", 0.0), 4),
            "source": p["source"],
            "content_source": "full text" if self._has_fulltext(paper_id) else "abstract + introduction",
            "depth": depth,
            # the exact section titles read in full for this comparison (empty for
            # abstract-only triage) -- shown in the review instead of a "full text" badge
            "sections_used": list(self._sections_read.get(paper_id, [])),
            "relevance_reason": relevance_reason,
            "refutation_status": status,
            "overlap_dimensions": overlap_dimensions or [],
            "overlap_degree": overlap_degree,
            "what_is_shared": what_is_shared,
            "submission_delta": submission_delta,
            "evidence_pairs": verified_pairs,
            # narrative of how THIS paper realizes the claimed contribution, with inline
            # verified quotes (segments: {kind:text|quote, verified?}); + the overlap assessment
            "paper_realization": self.verify_segments(paper_realization, paper_id) if paper_realization else [],
            "assessment": assessment,
            # outcome of the on-demand GROBID fetch for THIS deep dive (None = never
            # attempted, e.g. an abstract-only triage comparison that never went deep)
            "fulltext_fetch_status": fulltext_fetch_status,
            "brief_note": note,
        }
        # Serialize the shared-ledger read-modify-write: parallel deep dives call this
        # concurrently, and the rebuild-then-append below would otherwise lose a comparison.
        with self._lock:
            already = any(c["paper_id"] == paper_id for c in self.ledger["comparisons"])
            # last write wins per paper
            self.ledger["comparisons"] = [c for c in self.ledger["comparisons"] if c["paper_id"] != paper_id]
            self.ledger["comparisons"].append(comp)
            self.ledger["examined"].setdefault(
                paper_id,
                {"depth": depth, "source": p["source"], "similarity": round(p.get("sim", 0.0), 4)},
            )["has_comparison"] = True
            if log:
                self._log("record_comparison", f"{paper_id} -> {status} ({overlap_degree})", progress=not already)
        if already:
            note = "This paper was ALREADY compared -- do not compare it again. Move on to a NEW candidate or call finish."
        elif downgraded:
            note = "Evidence must be beidseitig verified (claim + paper side, >= min length) to count."
        else:
            note = "recorded"
        return {
            "paper_id": paper_id,
            "recorded_status": status,
            "already_compared": already,
            "downgraded": downgraded,
            "verified_pairs": sum(1 for p_ in verified_pairs if p_["fully_verified"]),
            "unverified_pairs": sum(1 for p_ in verified_pairs if not p_["fully_verified"]),
            "note": note,
        }

    # ------------------- retrieve_more persistence / fulltext ------------- #

    def _persist_agent_papers(self, papers: List[dict], query: str):
        path = self.sub_dir / "related_work_data" / "agent_retrieved_papers.json"
        existing = self._load_json(path) or []
        have = {p.get("paper_id") for p in existing}
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in papers:
            if p["paper_id"] in have:
                continue
            existing.append({
                **{k: p.get(k) for k in ("paper_id", "title", "abstract", "year",
                                         "publication_date", "venue", "authors",
                                         "citation_count", "externalIds", "doi")},
                "cited_paper": False,
                "source": "agent",
                "retrieval_query": query,
                "for_claim": self.claim.get("id"),
                "retrieved_at": stamp,
                "similarity": round(p.get("similarity", 0.0), 4),
            })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    def _best_effort_fulltext(self, paper_ids: List[str]):
        """Download + parse full text for a few new papers (best-effort, in-process
        PyMuPDF parsing -- no GROBID dependency)."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from fetch_fulltext import FullTextFetcher

            fetcher = FullTextFetcher(self.grobid_server)
            pdfs_dir = self.sub_dir / "related_work_data" / "pdfs"
            ft_dir = self.sub_dir / "related_work_data" / "grobid_fulltext"
            pdfs_dir.mkdir(parents=True, exist_ok=True)
            ft_dir.mkdir(parents=True, exist_ok=True)
            for pid in paper_ids:
                p = self.pool.get(pid)
                if not p or (ft_dir / f"{pid}.txt").exists():
                    continue
                try:
                    if fetcher.ensure_pdf(
                        {"paper_id": pid, "title": p["title"], "doi": p.get("doi"),
                         "externalIds": p.get("externalIds", {})},
                        pdfs_dir,
                    ):
                        if fetcher.parse_one(self.data_dir, self.submission_id, pid) == "ok":
                            p["fulltext"] = (ft_dir / f"{pid}.txt").read_text(encoding="utf-8")
                            self._paper_index.pop(pid, None)
                            self._paper_text.pop(pid, None)
                except Exception:
                    continue
        except Exception:
            return

    # ------------------------- gate signals ------------------------------ #

    def closest_set(self) -> List[str]:
        return [p["paper_id"] for p in self._ranked()[: self.closest_n]]

    def _sufficiently_examined(self, pid: str) -> bool:
        e = self.ledger["examined"].get(pid)
        if not (e and e.get("has_comparison")):
            return False
        comp = next((c for c in self.ledger["comparisons"] if c["paper_id"] == pid), None)
        deg = (comp or {}).get("overlap_degree")
        # Papers that PLAUSIBLY overlap (partial/substantial/same) must be read at depth
        # (full-text passages). Papers judged clearly distinct (none/superficial) are fine
        # from the abstract -- no need to spend full-text budget on obviously-unrelated work.
        if deg in ("same", "substantial", "partial"):
            return e.get("depth") in _SUFFICIENT_DEPTHS
        return True

    def closest_covered(self) -> bool:
        cs = self.closest_set()
        return bool(cs) and all(self._sufficiently_examined(pid) for pid in cs)

    def uncovered_closest(self) -> List[str]:
        """Titles of closest-set papers that still lack a sufficient comparison."""
        return [self.pool[pid]["title"] for pid in self.closest_set()
                if not self._sufficiently_examined(pid)]

    def retrievals_done(self) -> int:
        return len(self.ledger["retrievals"])

    def has_substantial_overlap(self) -> bool:
        for c in self.ledger["comparisons"]:
            if (
                c["refutation_status"] == "can_refute"
                and c.get("overlap_degree") in ("same", "substantial")
                and any(p.get("fully_verified") for p in c.get("evidence_pairs", []))
                and c.get("depth") in _SUFFICIENT_DEPTHS
            ):
                return True
        return False

    def stalled(self, stalled_k: int) -> bool:
        return self._steps_since_progress >= stalled_k

    # ------------------------- final artifact ---------------------------- #

    def artifact_entry(self, verdict_note: str = "") -> dict:
        comps = self.ledger["comparisons"]
        examined = self.ledger["examined"]
        examined_papers = [
            {
                "paper_id": pid,
                "title": self.pool.get(pid, {}).get("title", ""),
                "similarity": info.get("similarity"),
                "source": info.get("source"),
                "depth": info.get("depth"),
                "has_comparison": bool(info.get("has_comparison")),
            }
            for pid, info in examined.items()
        ]
        # The full ranked frontier (claim-similarity order) so the reviewer sees ALL
        # relevant prior work -- which the agent examined/compared, and which it did not.
        frontier = self._ranked()[:20]
        frontier_out = [
            {
                "paper_id": p["paper_id"], "title": p["title"], "authors": p.get("authors", ""),
                "year": p.get("year", ""), "venue": p.get("venue", ""),
                "similarity": round(p.get("sim", 0.0), 4), "source": p["source"],
                "has_fulltext": bool(p.get("fulltext")),
                "cited_by_submission": bool(p.get("cited_paper")),
                "examined": p["paper_id"] in examined,
                "compared": bool(examined.get(p["paper_id"], {}).get("has_comparison")),
            }
            for p in frontier
        ]
        return {
            "claim_id": self.claim["id"],
            "claim_name": self.claim.get("name", ""),
            "claim_text": self.claim.get("claim_text", ""),
            "claim_realization": self.claim_realization,
            "candidates_examined": len(self.ledger["examined"]),
            "can_refute_count": sum(1 for c in comps if c["refutation_status"] == "can_refute"),
            "comparisons": comps,
            "examined_papers": examined_papers,
            "frontier": frontier_out,
            "retrieval_rounds": self.retrievals_done(),
            "pool_sources": {
                s: sum(1 for p in self.pool.values() if p["source"] == s)
                for s in ("initial", "reviewer", "agent")
            },
            "trajectory": self.ledger["trajectory"],
        }
