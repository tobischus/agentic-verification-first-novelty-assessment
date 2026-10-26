"""Resources and ledger of one claim run.

Loads the submission and the version-pinned prior-work pool, serves section menus and
section text, parses prior papers on demand, verifies quotes and records comparisons.
"""

import hashlib
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
from rapidfuzz import fuzz

from . import evidence
from . import evidence_map
from . import retrieve_more as rm
from .passages import (
    PassageIndex,
    chunks_from_grobid_text,
    chunks_from_plain,
    chunks_from_sections,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "retrieval"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper_versions as pv  # noqa: E402

# How deeply a paper was examined, recorded per comparison.
_DEPTH_RANK = {
    "abstract_only": 0,
    "abstract_intro": 1,
    "fulltext_unavailable": 1,
    "targeted_sections": 2,
    "fulltext_available_targeted_read": 2,
    "fulltext_complete": 3,
}

# Version statuses that may be used as evidence (see FullTextFetcher.USABLE_STATUSES).
_USABLE_VERSION_STATUSES = ("pinned", "single")


class ClaimToolbox:
    def __init__(
        self,
        data_dir: str,
        submission_id: str,
        claim: dict,
        embedder,
        *,
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
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self.retrieve_k = retrieve_k
        self.fetch_fulltext_for_new = fetch_fulltext_for_new
        self.grobid_server = grobid_server

        self.sub_dir = Path(data_dir) / submission_id
        self._meta = self._load_json(self.sub_dir / f"{submission_id}.json") or {}
        self.cutoff_year = self._cutoff_year()
        self.sub_title = (self._meta.get("title") or "").strip()
        self.sub_pub_date = self._meta.get("publication_date") or datetime.now().strftime(
            "%Y-%m-%d"
        )

        ft = self._load_json(self.sub_dir / f"{submission_id}_fulltext.json") or {}
        sub_sections = ft.get("sections", [])
        self._submission_index = PassageIndex(
            chunks_from_sections(sub_sections, "submission"), embedder
        )
        # D(S): submission quotes are verified against the body and the abstract only.
        self._submission_text = "\n\n".join(
            [s.get("text", "") for s in sub_sections] + [self._meta.get("abstract", "")]
        )

        self.pool = {}
        self._load_pool()
        self._score_pool()

        self._paper_index = {}
        self._paper_text = {}
        # Papers are processed in parallel: ledger updates and index builds are serialized.
        self._lock = threading.RLock()
        self._embed_lock = threading.Lock()

        self.ledger = {
            "examined": {},
            "comparisons": [],
            "retrievals": [],
            "trajectory": [],
        }
        self.claim_realization = []
        self._sections_read = {}
        self._fulltext_status = {}

        # Version-gate decisions taken while the pool was built, before the ledger existed.
        for note in getattr(self, "_version_gate_notes", []):
            self._log("version_gate", note)
        self._version_gate_notes = []

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
        return datetime.now().year

    def _load_intro(self, pid: str) -> str:
        """Stored introduction, only if it was extracted from the pinned PDF."""
        entry = self._versions_manifest().get(pid) or {}
        recorded = entry.get("intro_from_sha256")
        if not recorded or recorded != entry.get("doc_sha256"):
            return ""
        for rel in (f"introductions/{pid}_intro.txt", f"ours/related_papers/{pid}_intro.txt"):
            p = self.sub_dir / rel
            if p.exists():
                return p.read_text(encoding="utf-8")
        return ""

    def paper_provenance(self, pid: str) -> dict:
        """Pool record updated with the current entry of the version manifest."""
        p = dict(self.pool.get(pid) or {})
        self._versions_cache = None
        e = self._versions_manifest().get(pid) or {}
        if e:
            p.update(
                {
                    "version_status": e.get("status", p.get("version_status", "")),
                    "pinned_version": e.get("version", p.get("pinned_version", "")),
                    "pinned_version_date": e.get("version_date", p.get("pinned_version_date", "")),
                    "pinned_url": e.get("url", p.get("pinned_url", "")),
                    "doc_sha256": e.get("doc_sha256", p.get("doc_sha256", "")),
                    "parsed_text_path": e.get("parsed_text_path", ""),
                    "parsed_text_sha256": e.get("parsed_text_sha256", ""),
                    "history_complete": e.get("history_complete", None),
                    "missing_versions": e.get("missing_versions", []),
                }
            )
        return p

    def _versions_manifest(self) -> dict:
        """related_work_data/versions.json, cached until a pin changes."""
        if getattr(self, "_versions_cache", None) is None:
            self._versions_cache = (
                self._load_json(self.sub_dir / "related_work_data" / "versions.json") or {}
            )
        return self._versions_cache

    def _cutoff_date(self) -> str:
        """The submission date t(S), read as the fetcher reads it."""
        return str(self._meta.get("publication_date") or self._meta.get("year") or "")

    def _pin_is_stale(self, entry: dict) -> bool:
        """True if a pin was computed for a different submission date or gap."""
        if not entry:
            return True
        return (
            entry.get("submission_date") != self._cutoff_date()
            or int(entry.get("min_gap_days") or -1) != pv.DEFAULT_MIN_GAP_DAYS
        )

    @staticmethod
    def _version_abstract(entry: dict, record: dict) -> tuple:
        """(abstract, source) of the pinned version; withheld if only another version's is known."""
        if entry.get("abstract_source") == "version" and entry.get("abstract"):
            return entry["abstract"], "version"
        status = entry.get("status") or ""
        if status in ("", "single"):
            return (record.get("abstract", "") or ""), (entry.get("abstract_source") or "record")
        return "", "unavailable_for_pinned_version"

    def _resolve_missing_pin(self, pid: str, record: dict) -> dict:
        """Pin a paper without a valid pin and store the result in the manifest."""
        try:
            from fetch_fulltext import FullTextFetcher

            fetcher = FullTextFetcher(self.grobid_server)
            entry = (
                fetcher.pin_for_record(
                    self.data_dir,
                    self.submission_id,
                    {
                        "paper_id": pid,
                        "title": record.get("title", ""),
                        "externalIds": record.get("externalIds", {}),
                        "doi": record.get("doi"),
                        "publication_date": record.get("publication_date", ""),
                        "year": record.get("year", ""),
                        "abstract": record.get("abstract", ""),
                    },
                )
                or {}
            )
            self._versions_cache = None
            return entry
        except Exception as e:
            self._note_version_gate(f"{pid}: could not resolve a version ({type(e).__name__})")
            return {}

    def _note_version_gate(self, message: str) -> None:
        if getattr(self, "ledger", None) is not None:
            self._log("version_gate", message)
            return
        if not hasattr(self, "_version_gate_notes"):
            self._version_gate_notes = []
        self._version_gate_notes.append(message)

    def _load_fulltext_file(self, pid: str) -> str:
        """Parsed text of the pinned version, or "" if its provenance does not check out.

        The manifest must name the file, the file must match its recorded hash, and it
        must have been parsed from the PDF that is currently pinned.
        """
        entry = self._versions_manifest().get(pid) or {}
        named = entry.get("parsed_text_path")
        want_pdf = entry.get("doc_sha256")
        parsed_from = entry.get("parsed_from_sha256")
        want_text = entry.get("parsed_text_sha256")
        if not (named and want_pdf and parsed_from and want_text):
            return ""
        if parsed_from != want_pdf:
            return ""
        p = self.sub_dir / "related_work_data" / named
        if not p.exists():
            return ""
        # Hash the bytes as written; decoded text differs in line endings on Windows.
        if hashlib.sha256(p.read_bytes()).hexdigest() != want_text:
            return ""
        return p.read_text(encoding="utf-8")

    def _add_pool_paper(self, p: dict, source: str):
        """Add a candidate if it is not the submission and has an admissible version."""
        pid = p.get("paper_id")
        if not pid or pid in self.pool:
            return
        title = p.get("title", "") or ""
        if self.sub_title and fuzz.ratio(title.lower(), self.sub_title.lower()) >= 90:
            return

        entry = self._versions_manifest().get(pid) or {}
        status = entry.get("status") or p.get("version_status") or ""
        if not status or self._pin_is_stale(entry):
            entry = self._resolve_missing_pin(pid, p)
            status = entry.get("status") or ""
        if status not in _USABLE_VERSION_STATUSES:
            self._note_version_gate(
                f"{pid}: not usable as evidence ({status or 'unresolved'}) | {title[:50]}"
            )
            return

        abstract, abstract_source = self._version_abstract(entry, p)
        self.pool[pid] = {
            "paper_id": pid,
            "title": p.get("title", "") or "",
            "abstract": abstract,
            "authors": p.get("authors", "") or "",
            "year": p.get("year", "") or "",
            "venue": p.get("venue", "") or "",
            "cited_paper": bool(p.get("cited_paper", False)),
            "intro": self._load_intro(pid),
            "fulltext": self._load_fulltext_file(pid),
            "source": source,
            "version_status": status,
            "pinned_version": entry.get("version") or p.get("pinned_version", ""),
            "pinned_version_date": entry.get("version_date") or p.get("pinned_version_date", ""),
            "pinned_url": entry.get("url", ""),
            "doc_sha256": entry.get("doc_sha256", ""),
            "abstract_source": abstract_source,
            "parsed_text_path": entry.get("parsed_text_path", ""),
            "parsed_text_sha256": entry.get("parsed_text_sha256", ""),
            "history_complete": entry.get("history_complete", None),
            "missing_versions": entry.get("missing_versions", []),
        }

    def _load_pool(self):
        ranked = self._load_json(self.sub_dir / "related_work_data" / "ranked_papers.json") or []
        for p in ranked:
            self._add_pool_paper(p, "reviewer" if p.get("added_by") == "reviewer" else "initial")
        agent_papers = (
            self._load_json(self.sub_dir / "related_work_data" / "agent_retrieved_papers.json")
            or []
        )
        for p in agent_papers:
            self._add_pool_paper(p, "agent")

    def _score_pool(self):
        """Embedding similarity of each pool paper to the claim."""
        if not self.pool:
            return
        claim_doc = (
            f"{self.claim.get('name', '')}. {self.claim.get('description', '')} "
            f"{self.claim.get('claim_text', '')}"
        ).strip()
        pids = list(self.pool)
        docs = [f"{self.pool[pid]['title']}. {self.pool[pid]['abstract']}" for pid in pids]
        embs = self.embedder.encode([claim_doc] + docs, convert_to_numpy=True)
        claim_emb, cand_embs = embs[0], embs[1:]
        sims = (
            cand_embs
            @ claim_emb
            / (np.linalg.norm(cand_embs, axis=1) * np.linalg.norm(claim_emb) + 1e-9)
        )
        for pid, s in zip(pids, sims):
            self.pool[pid]["sim"] = float(s)

    def _has_fulltext(self, pid: str) -> bool:
        return bool(self.pool.get(pid, {}).get("fulltext"))

    def ensure_fulltext(self, pid: str) -> str:
        """Fetch and parse the pinned PDF of a paper when it is first examined.

        Returns "already_had", "ok", "no_version", "no_pdf", "parse_empty",
        "parse_error" or "parse_unverified".
        """
        if pid == "submission" or self._has_fulltext(pid):
            self._fulltext_status.setdefault(pid, "already_had")
            return "already_had"
        try:
            from fetch_fulltext import FullTextFetcher

            fetcher = FullTextFetcher(self.grobid_server)
            pdf_path = self.sub_dir / "related_work_data" / "pdfs" / f"{pid}.pdf"
            status = self._prepare_pinned_pdf(fetcher, pid, pdf_path)
            if status:
                self._fulltext_status[pid] = status
                self._log("ensure_fulltext", f"{pid} -> {status}")
                return status
            status = fetcher.parse_one(self.data_dir, self.submission_id, pid)
        except Exception:
            status = "parse_error"
        if status == "ok":
            self._versions_cache = None
            text = self._load_fulltext_file(pid)
            if not text:
                self._fulltext_status[pid] = "parse_unverified"
                self._log(
                    "ensure_fulltext", f"{pid} -> parsed text failed its own provenance check"
                )
                return "parse_unverified"
            self.pool[pid]["fulltext"] = text
            self._paper_index.pop(pid, None)
            self._paper_text.pop(pid, None)
        self._fulltext_status[pid] = status
        self._log("ensure_fulltext", f"{pid} -> {status}")
        return status

    def _prepare_pinned_pdf(self, fetcher, pid: str, pdf_path: Path) -> str:
        """Make sure the PDF on disk is the pinned version; returns "" or an abort status."""
        pin = self._versions_manifest().get(pid) or {}
        if not pin.get("status"):
            pin = self._resolve_missing_pin(pid, self.pool.get(pid, {})) or {}
        if pin.get("status") not in _USABLE_VERSION_STATUSES:
            return "no_version"

        recorded = pin.get("doc_sha256")
        if pdf_path.exists() and recorded and fetcher._sha256(pdf_path) == recorded:
            return ""
        p = self.pool.get(pid, {})
        ok = fetcher.ensure_pdf(
            {
                "paper_id": pid,
                "title": p.get("title", ""),
                "doi": p.get("doi"),
                "externalIds": p.get("externalIds", {}),
            },
            pdf_path.parent,
            pin=pin,
        )
        if not ok:
            return "no_pdf"
        fetcher.record_pdf_hash(self.data_dir, self.submission_id, pid, pdf_path)
        self._versions_cache = None
        return ""

    def _paper_source_text(self, pid: str) -> str:
        """D(p): the parsed full text, or abstract and introduction if there is none."""
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
            with self._embed_lock:
                if pid not in self._paper_index:
                    p = self.pool.get(pid, {})
                    if p.get("fulltext"):
                        chunks = chunks_from_grobid_text(p["fulltext"], pid)
                        if len(chunks) < 2:
                            chunks = chunks_from_plain(p["fulltext"], pid)
                    else:
                        blob = "\n\n".join(
                            x
                            for x in (
                                ("Abstract: " + p.get("abstract", "")) if p.get("abstract") else "",
                                ("Introduction: " + p.get("intro", "")) if p.get("intro") else "",
                            )
                            if x
                        )
                        chunks = chunks_from_plain(blob, pid)
                    self._paper_index[pid] = PassageIndex(chunks, self.embedder)
        return self._paper_index[pid]

    def _log(self, action: str, summary: str):
        with self._lock:
            self.ledger["trajectory"].append(
                {"step": len(self.ledger["trajectory"]) + 1, "action": action, "detail": summary}
            )

    def _bump_depth(self, pid: str, depth: str):
        with self._lock:
            e = self.ledger["examined"].setdefault(
                pid,
                {
                    "depth": "abstract_only",
                    "source": self.pool.get(pid, {}).get("source", "?"),
                    "similarity": round(self.pool.get(pid, {}).get("sim", 0.0), 4),
                    "has_comparison": False,
                },
            )
            if _DEPTH_RANK.get(depth, 0) > _DEPTH_RANK.get(e["depth"], 0):
                e["depth"] = depth

    def _ranked(self) -> List[dict]:
        """Pool papers ordered by similarity to the claim."""
        return sorted(self.pool.values(), key=lambda p: p.get("sim", 0.0), reverse=True)

    def search_submission(self, query: str, k: int = 5) -> dict:
        hits = self._submission_index.search(query, k=k)
        self._log("search_submission", f'q="{query[:60]}" -> {len(hits)} passages')
        return {"query": query, "passages": hits}

    def section_menu(self, paper_id: str) -> List[dict]:
        """Section names with previews and sizes."""
        return self._index_for(paper_id).section_previews()

    def read_sections(
        self, paper_id: str, names: List[str], max_total: int = 40000, exact: bool = False
    ) -> dict:
        """Complete text of the named sections; records which sections were read."""
        idx = self._index_for(paper_id)
        got = idx.get_sections(names, max_total=max_total, exact=exact)
        if paper_id != "submission":
            self._bump_depth(paper_id, "targeted_sections" if got else "abstract_intro")
        lst = self._sections_read.setdefault(paper_id, [])
        for s in got:
            nm = s.get("name")
            if nm and nm not in lst:
                lst.append(nm)
        self._log(
            "read_sections",
            f"{paper_id}: {len(got)} sections ({sum(len(s['text']) for s in got)} chars)",
        )
        return {"paper_id": paper_id, "sections": got}

    def verify_segments(self, segments: List[dict], source: str) -> List[dict]:
        """Verify the quote segments of an explanation against the source text.

        A verified quote is shortened for display; a quote that cannot be verified is
        shown as plain text.
        """
        src = self._submission_text if source == "submission" else self._paper_source_text(source)
        out = []
        for seg in segments or []:
            kind = (seg.get("kind") or "text").lower()
            content = (seg.get("content") or "").strip()
            if not content:
                continue
            if kind == "quote":
                chk, span = evidence.verify_contiguous(
                    content, src, self.min_quote_tokens, self.fuzzy_threshold
                )
                if chk.verified:
                    out.append(
                        {
                            "kind": "quote",
                            "verified": True,
                            "content": evidence_map.trim_display_span(span),
                        }
                    )
                else:
                    out.append({"kind": "text", "verified": False, "content": content})
            else:
                out.append({"kind": "text", "content": content})
        return out

    def read_paper(self, paper_id: str, query: str, k: int = 5) -> dict:
        """Top-k passages of a paper for a query."""
        if paper_id not in self.pool:
            return {"error": f"unknown paper_id '{paper_id}'"}
        has_ft = self._has_fulltext(paper_id)
        payload = {"query": query, "passages": self._index_for(paper_id).search(query, k=k)}
        depth = "fulltext_available_targeted_read" if has_ft else "fulltext_unavailable"
        self._bump_depth(paper_id, depth)
        self._log("read_paper", f"{paper_id} [query] -> depth={depth}")
        return {"paper_id": paper_id, "has_fulltext": has_ft, **payload}

    def retrieve_more(self, query: str, k: Optional[int] = None) -> dict:
        """Search for new admissible candidates and add them to the pool."""
        k = k or self.retrieve_k
        new = rm.retrieve(
            query,
            self.claim,
            self.embedder,
            exclude_ids=set(self.pool),
            source_title=self.sub_title,
            source_pub_date=self.sub_pub_date,
            source_year=self.cutoff_year,
            source_abstract=self._meta.get("abstract", ""),
            k=k,
        )
        added = []
        for p in new:
            self._add_pool_paper(p, "agent")
            pid = p["paper_id"]
            if pid in self.pool:
                self.pool[pid]["sim"] = float(p.get("similarity", 0.0))
                added.append(pid)
        if added:
            self._persist_agent_papers(new, query)
            if self.fetch_fulltext_for_new:
                self._best_effort_fulltext(added[: self.fetch_fulltext_for_new])
        self.ledger["retrievals"].append({"query": query, "n_new": len(added), "added_ids": added})
        self._log("retrieve_more", f'q="{query[:60]}" -> {len(added)} new papers')
        return {
            "query": query,
            "n_new": len(added),
            "papers": [
                {
                    "paper_id": p["paper_id"],
                    "title": p["title"],
                    "similarity": round(p.get("similarity", 0.0), 4),
                    "has_fulltext": self._has_fulltext(p["paper_id"]),
                }
                for p in new
            ],
        }

    def record_comparison(
        self,
        paper_id: str,
        refutation_status: str,
        brief_note: str = "",
        overlap_degree: str = "none",
        what_is_shared: str = "",
        submission_delta: str = "",
        evidence_pairs: Optional[List[dict]] = None,
        paper_realization: Optional[List[dict]] = None,
        assessment: str = "",
        fulltext_fetch_status: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Verify the evidence pairs again and store the comparison in the ledger.

        `can_refute` without a pair verified on both sides is downgraded.
        """
        if paper_id not in self.pool:
            return
        paper_text = self._paper_source_text(paper_id)
        verified_pairs = []
        for ep in evidence_pairs or []:
            v = evidence.verify_pair(
                ep.get("claim_quote", ""),
                ep.get("paper_quote", ""),
                self._submission_text,
                paper_text,
                self.min_quote_tokens,
                self.fuzzy_threshold,
            )
            carried = {
                k: val
                for k, val in ep.items()
                if k
                not in (
                    "claim_quote",
                    "paper_quote",
                    "rationale",
                    "claim_quote_verified",
                    "paper_quote_verified",
                    "fully_verified",
                )
            }
            verified_pairs.append(
                {
                    **carried,
                    "claim_quote": ep.get("claim_quote", ""),
                    "paper_quote": ep.get("paper_quote", ""),
                    "rationale": ep.get("rationale", ""),
                    "claim_quote_verified": v["claim_quote_verified"],
                    "paper_quote_verified": v["paper_quote_verified"],
                    "fully_verified": v["fully_verified"],
                }
            )

        status = refutation_status
        note = brief_note
        if status == "can_refute" and not any(p["fully_verified"] for p in verified_pairs):
            status = "cannot_refute"
            note = "[downgraded: no beidseitig-verified evidence quote pair] " + note

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
            "content_source": "full text"
            if self._has_fulltext(paper_id)
            else "abstract + introduction",
            "depth": depth,
            "sections_used": list(self._sections_read.get(paper_id, [])),
            "relevance_reason": "",
            "refutation_status": status,
            "overlap_dimensions": [],
            "overlap_degree": overlap_degree,
            "what_is_shared": what_is_shared,
            "submission_delta": submission_delta,
            "evidence_pairs": verified_pairs,
            "paper_realization": self.verify_segments(paper_realization, paper_id)
            if paper_realization
            else [],
            "assessment": assessment,
            "fulltext_fetch_status": fulltext_fetch_status,
            "brief_note": note,
            **(extra or {}),
        }
        with self._lock:
            self.ledger["comparisons"] = [
                c for c in self.ledger["comparisons"] if c["paper_id"] != paper_id
            ]
            self.ledger["comparisons"].append(comp)
            self.ledger["examined"].setdefault(
                paper_id,
                {"depth": depth, "source": p["source"], "similarity": round(p.get("sim", 0.0), 4)},
            )["has_comparison"] = True
            self._log("record_comparison", f"{paper_id} -> {status} ({overlap_degree})")

    def _persist_agent_papers(self, papers: List[dict], query: str):
        path = self.sub_dir / "related_work_data" / "agent_retrieved_papers.json"
        existing = self._load_json(path) or []
        have = {p.get("paper_id") for p in existing}
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in papers:
            if p["paper_id"] in have:
                continue
            existing.append(
                {
                    **{
                        k: p.get(k)
                        for k in (
                            "paper_id",
                            "title",
                            "abstract",
                            "year",
                            "publication_date",
                            "venue",
                            "authors",
                            "citation_count",
                            "externalIds",
                            "doi",
                        )
                    },
                    "cited_paper": False,
                    "source": "agent",
                    "retrieval_query": query,
                    "for_claim": self.claim.get("id"),
                    "retrieved_at": stamp,
                    "similarity": round(p.get("similarity", 0.0), 4),
                }
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    def _best_effort_fulltext(self, paper_ids: List[str]):
        """Fetch and parse the pinned versions of newly retrieved papers."""
        try:
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
                    record = {
                        "paper_id": pid,
                        "title": p["title"],
                        "doi": p.get("doi"),
                        "externalIds": p.get("externalIds", {}),
                        "publication_date": p.get("publication_date", ""),
                        "year": p.get("year", ""),
                        "abstract": p.get("abstract", ""),
                    }
                    pin = fetcher.pin_for_record(self.data_dir, self.submission_id, record)
                    if pin and pin.get("status") not in _USABLE_VERSION_STATUSES:
                        continue
                    if fetcher.ensure_pdf(record, pdfs_dir, pin=pin or None):
                        fetcher.record_pdf_hash(
                            self.data_dir, self.submission_id, pid, pdfs_dir / f"{pid}.pdf"
                        )
                        self._versions_cache = None
                        if fetcher.parse_one(self.data_dir, self.submission_id, pid) == "ok":
                            p["fulltext"] = (ft_dir / f"{pid}.txt").read_text(encoding="utf-8")
                            self._paper_index.pop(pid, None)
                            self._paper_text.pop(pid, None)
                except Exception:
                    continue
        except Exception:
            return

    def retrievals_done(self) -> int:
        return len(self.ledger["retrievals"])

    def artifact_entry(self) -> dict:
        """The claim's entry in the artifact: comparisons, examined papers and trajectory."""
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
        frontier = self._ranked()[:20]
        frontier_out = [
            {
                "paper_id": p["paper_id"],
                "title": p["title"],
                "authors": p.get("authors", ""),
                "year": p.get("year", ""),
                "venue": p.get("venue", ""),
                "similarity": round(p.get("sim", 0.0), 4),
                "source": p["source"],
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
