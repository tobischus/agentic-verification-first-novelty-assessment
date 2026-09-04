#!/usr/bin/env python3
"""
Step 4: Claim-Level Paper Selection + Comparison -> Artifact A.

The verification-first evidence layer. For each reviewer-validated claim
(from Step 2) it:
  1. SELECTS the most relevant comparison papers from the global related work
     (Step 3) via SPECTER2 similarity recall (claim -> papers), top-k.
  2. COMPARES the claim against each candidate with an LLM, producing a
     three-way refutation judgment (can_refute / cannot_refute / unclear) plus
     VERBATIM evidence quotes from both the claim and the candidate paper.
  3. VERIFIES each evidence quote against the candidate's source text; a
     can_refute with no verified evidence is downgraded to cannot_refute.

Artifact A does NOT produce a final novelty verdict -- it only assembles
checkable evidence. The synthesized assessment (Artifact B) is Step 5, and a
Judge (Step 6) checks that B follows from A.

Design decisions (thesis): Q1 two-stage hybrid (embedding recall -> LLM judge);
Q2 top-k per claim (k is the ablation hyperparameter); Q3 clusters are a
retrieval/navigation signal only, never a direct judgment input.
"""
import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

import numpy as np
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from agent import evidence as ev
# The comparison prompt and its output schema are IMPORTED from the agent rather than
# restated here. RQ1 asks what the agentic workflow adds; that only isolates the workflow
# if the comparison step is literally the same call with the same instructions and the same
# fields. Two copies would drift, and the ablation would quietly start measuring prompt
# wording instead. This module differs from the agent in HOW it selects and reads papers,
# and in that it never re-enters -- not in what it asks the model.
from agent.claim_agent import (_PAPER_COMPARE, _SectionComparison, _fmt_sections_full,
                               _segments_to_text)

load_dotenv()
#TODO: Definition of Novelty here!

def _fill(tpl: str, **kw) -> str:
    """str.format is unusable here: the prompts contain literal braces."""
    out = tpl
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _claim_str(claim: dict) -> str:
    """The claim as the comparison prompt expects it -- same shape the agent passes."""
    return " ".join(x for x in (claim.get("claim_text", ""), claim.get("description", "")) if x)


def variant_path(sub_dir: Path, submission_id: str, kind: str, variant: str = "") -> Path:
    """{id}_{kind}.json, or {id}_{kind}_{variant}.json when a variant is named.

    The agent and the linear baseline are two systems producing the same kind of artifact
    for the same submission. Without a variant they write to the same file, so running one
    silently destroys the other's result -- which is fatal for the RQ1 ablation, where both
    have to sit side by side and be compared.
    """
    tail = f"_{variant}" if variant else ""
    return sub_dir / f"{submission_id}_{kind}{tail}.json"


class ArtifactABuilder:
    """Builds Artifact A: per-claim evidence-based comparisons against prior work."""

    def __init__(
        self,
        model_name: str = "gpt-4.1",
        embedding_model: str = "allenai/specter2_base",
        temperature: float = 0.0,
        k_per_claim: int = 10,
        max_paper_chars: int = 24000,
        max_concurrency: int = 2,
        min_quote_tokens: int = ev.DEFAULT_MIN_QUOTE_TOKENS,
        fuzzy_threshold: float = ev.DEFAULT_FUZZY_THRESHOLD,
    ):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        # max_retries lets the client back off on OpenAI 429 (TPM) limits.
        self.llm = ChatOpenAI(
            model_name=model_name, temperature=temperature, api_key=api_key, max_retries=8
        )
        self.max_concurrency = max_concurrency
        self.k_per_claim = k_per_claim
        self.max_paper_chars = max_paper_chars
        # Identical to the agent's defaults ON PURPOSE: this class is the non-agentic
        # baseline in the RQ1 ablation, so verification must not be a second variable.
        self.min_quote_tokens = min_quote_tokens
        self.fuzzy_threshold = fuzzy_threshold
        self._embedding_model_name = embedding_model
        self._embedder = None  # lazy

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self._embedding_model_name)
        return self._embedder

    # ----------------------------- loading ----------------------------- #

    def _load_intro(self, sub_dir: Path, paper_id: str) -> str:
        for rel in (
            f"introductions/{paper_id}_intro.txt",
            f"ours/related_papers/{paper_id}_intro.txt",
        ):
            p = sub_dir / rel
            if p.exists():
                return p.read_text(encoding="utf-8")
        return ""

    def _load_fulltext(self, sub_dir: Path, paper_id: str) -> str:
        """Full OCR text of a candidate paper, if it was OCR'd (Nougat/MinerU)."""
        for rel in (
            f"related_work_data/nougat_output/{paper_id}.mmd",
            f"related_work_data/grobid_fulltext/{paper_id}.txt",
            f"related_work_data/mineru_output/{paper_id}.md",
            f"related_work_data/mineru_output/{paper_id}/{paper_id}.md",
        ):
            p = sub_dir / rel
            if p.exists():
                return p.read_text(encoding="utf-8")
        return ""

    def load_submission_text(self, data_dir: str, submission_id: str) -> str:
        """Corpus a claim_quote is verified against -- the SAME one the agent uses
        (agent/tools.py ClaimToolbox): the submission's body sections plus its abstract.
        The per-claim strings are appended in build_one, because the comparison prompt
        shows the model the claim text and description rather than the paper body."""
        sub_dir = Path(data_dir) / submission_id
        parts = []
        ft = sub_dir / f"{submission_id}_fulltext.json"
        if ft.exists():
            doc = json.loads(ft.read_text(encoding="utf-8"))
            parts += [s.get("text", "") for s in doc.get("sections", [])]
        meta = sub_dir / f"{submission_id}.json"
        if meta.exists():
            parts.append(json.loads(meta.read_text(encoding="utf-8")).get("abstract", "") or "")
        return "\n\n".join(p for p in parts if p)

    def prepare_fulltexts(self, data_dir: str, submission_id: str,
                          grobid_server: str = "http://localhost:8070") -> dict:
        """GROBID-parse every pool paper that has a PDF, before any comparison runs.

        The pipeline parses full text lazily, only for papers the AGENT chooses to deep-dive.
        This baseline then read whichever full texts happened to be on disk, so its evidence
        depended on what the agent had done first: run it before the agent and it sees
        abstracts only, run it after and it inherits the agent's selection. Neither isolates
        the workflow, which is the one thing the RQ1 ablation has to do. Parsing everything
        up front gives both systems the same text and makes the run order irrelevant.
        """
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fetch_fulltext import FullTextFetcher

        sub_dir = Path(data_dir) / submission_id
        ranked = json.loads(
            (sub_dir / "related_work_data" / "ranked_papers.json").read_text(encoding="utf-8"))
        fetcher = FullTextFetcher(grobid_server)
        stats = {"already_had": 0, "ok": 0, "no_pdf": 0, "failed": 0}
        for p in ranked:
            pid = p.get("paper_id")
            if not pid:
                continue
            if (sub_dir / "related_work_data" / "grobid_fulltext" / f"{pid}.txt").exists():
                stats["already_had"] += 1
                continue
            try:
                status = fetcher.parse_one(data_dir, submission_id, pid)
            except Exception:
                status = "parse_error"
            stats[status if status in ("ok", "no_pdf") else "failed"] += 1
        return stats

    def load_related_work(self, data_dir: str, submission_id: str) -> List[dict]:
        """Load the global related-work pool (ranked_papers) with available content."""
        sub_dir = Path(data_dir) / submission_id
        ranked = json.loads(
            (sub_dir / "related_work_data" / "ranked_papers.json").read_text(encoding="utf-8")
        )

        # Structured fields per related paper (top-k from Step 5), if present.
        structured = {}
        srep_path = sub_dir / "structured_representation.json"
        if srep_path.exists():
            srep = json.loads(srep_path.read_text(encoding="utf-8"))["structured_representation"]
            for item in srep.get("selected_papers", []):
                structured[item["paper_id"]] = item.get("parsed", {})

        papers = []
        for p in ranked:
            pid = p["paper_id"]
            papers.append(
                {
                    "paper_id": pid,
                    "title": p.get("title", "") or "",
                    "abstract": p.get("abstract", "") or "",
                    "cited_paper": p.get("cited_paper", False),
                    "intro": self._load_intro(sub_dir, pid),
                    "fulltext": self._load_fulltext(sub_dir, pid),
                    "structured": structured.get(pid, {}),
                }
            )
        return papers

    def load_citation_contexts_by_title(self, data_dir: str, submission_id: str) -> dict:
        """Map cited-paper title -> list of citation context sentences (best-effort)."""
        sub_dir = Path(data_dir) / submission_id
        main = json.loads((sub_dir / f"{submission_id}.json").read_text(encoding="utf-8"))
        # bib id -> title
        id_to_title = {c["id"]: (c.get("title") or "") for c in main.get("cited_papers", [])}
        title_to_contexts = {}
        for ctx in main.get("citation_contexts", []):
            bid = ctx.get("cited_paper_id")
            title = id_to_title.get(bid)
            if title:
                title_to_contexts.setdefault(title, []).append(ctx.get("context_sentence", ""))
        return title_to_contexts

    @staticmethod
    def _match_citation_context(cand_title: str, title_to_contexts: dict, threshold: int = 85) -> List[str]:
        for title, ctxs in title_to_contexts.items():
            if fuzz.token_set_ratio(cand_title, title) >= threshold:
                return ctxs
        return []

    # --------------------------- selection ----------------------------- #

    def select_candidates(self, claim: dict, papers: List[dict], k: int) -> List[dict]:
        """SPECTER2 recall: rank papers by similarity to the claim, return top-k."""
        if not papers:
            return []
        claim_doc = f"{claim['name']}. {claim.get('description','')} {claim.get('claim_text','')}".strip()
        cand_docs = [f"{p['title']}. {p['abstract']}" for p in papers]
        embs = self.embedder.encode([claim_doc] + cand_docs, convert_to_numpy=True)
        claim_emb, cand_embs = embs[0], embs[1:]
        # cosine similarity
        sims = cand_embs @ claim_emb / (
            np.linalg.norm(cand_embs, axis=1) * np.linalg.norm(claim_emb) + 1e-9
        )
        order = np.argsort(-sims)[:k]
        out = []
        for idx in order:
            p = dict(papers[idx])
            p["similarity"] = float(sims[idx])
            out.append(p)
        return out

    # --------------------------- comparison ---------------------------- #

    def _candidate_content(self, paper: dict) -> tuple:
        """Return (content_source, content_text) for the candidate comparison.

        Prefers full OCR text; falls back to abstract+introduction. The returned
        text is BOTH what is shown to the LLM and what evidence quotes are
        verified against, so quotes can only come from what the model saw.
        """
        if paper.get("fulltext"):
            return "full text (OCR)", paper["fulltext"][: self.max_paper_chars]
        parts = []
        if paper.get("abstract"):
            parts.append("Abstract: " + paper["abstract"])
        if paper.get("intro"):
            parts.append("Introduction: " + paper["intro"])
        return "abstract + introduction", "\n\n".join(parts)[: self.max_paper_chars]

    def _build_prompt(self, claim: dict, content_source: str, content: str,
                      paper: dict, citation_ctxs: List[str]) -> str:
        """The agent's comparison prompt, filled from ONE pass over the whole document.

        The agent picks sections and passes them as `sections`; this baseline passes the
        paper as a single block, which is precisely the difference under test: same question,
        same fields, no selection and no second look."""
        return _fill(
            _PAPER_COMPARE,
            claim=_claim_str(claim)[:1200],
            realization=_segments_to_text(claim.get("realization") or [])[:1600],
            title=paper["title"],
            sections=_fmt_sections_full([{"name": content_source, "text": content}]),
        )

    def _verify(self, quote: str, source: str) -> tuple:
        """(verified, repaired) against the text the model was actually shown."""
        chk = ev.verify_quote(quote, source, self.min_quote_tokens, self.fuzzy_threshold)
        return (True, ev.expand_to_sentence(quote, source)) if chk.verified else (False, quote)

    def _verify_and_finalize(self, comp, paper: dict,
                             content_source: str, content: str,
                             submission_text: str) -> dict:
        """Verify BOTH sides of every evidence pair; downgrade unverifiable can_refute.

        Deliberately IDENTICAL to the agent (agent/tools.py record_comparison): the same
        evidence.verify_pair, the same min_quote_tokens and fuzzy_threshold, and the same
        rule that a can_refute survives only on a both-sides-verified pair.

        It previously checked the PAPER side only, with a plain substring test and no
        minimum quote length -- so a two-word quote passed while the claim side was never
        checked at all. That made this class stricter in one direction and far more
        permissive in the other, which would have turned the RQ1 ablation (agent vs. this
        linear baseline) partly into a comparison of verification strictness rather than
        of the workflow.
        """
        verified_pairs = []
        for ep in comp.evidence_pairs:
            v = ev.verify_pair(ep.claim_quote, ep.paper_quote, submission_text, content,
                               self.min_quote_tokens, self.fuzzy_threshold)
            paper_q = ep.paper_quote
            if v["paper_quote_verified"]:
                paper_q = ev.expand_to_sentence(paper_q, content)
            verified_pairs.append(
                {
                    "claim_quote": ep.claim_quote,
                    "paper_quote": paper_q,
                    "rationale": ep.rationale,
                    "claim_quote_verified": v["claim_quote_verified"],
                    "paper_quote_verified": v["paper_quote_verified"],
                    "fully_verified": v["fully_verified"],
                }
            )
        # The narrative of what the paper does about this claim, with its verbatim spans
        # checked against the same text the model was shown -- the agent verifies its
        # paper_realization the same way, so the two artifacts carry the same guarantee.
        realization = []
        for seg in (getattr(comp, "paper_realization", None) or []):
            text = (seg.content or "").strip()
            if not text:
                continue
            if (seg.kind or "text").lower() == "quote":
                ok, repaired = self._verify(text, content)
                realization.append({"kind": "quote", "verified": True, "content": repaired} if ok
                                   else {"kind": "text", "verified": False, "content": text})
            else:
                realization.append({"kind": "text", "content": text})

        status = comp.refutation_status
        note = comp.assessment or ""
        if status == "can_refute" and not any(p["fully_verified"] for p in verified_pairs):
            # Verification-first hard constraint: no verified evidence -> downgrade.
            status = "cannot_refute"
            note = "[downgraded: no both-sides-verified evidence quote pair] " + note
        return {
            "paper_id": paper["paper_id"],
            "title": paper["title"],
            "authors": paper.get("authors", "") or "",
            "year": paper.get("year", "") or "",
            "cited_by_submission": paper["cited_paper"],
            "similarity": round(paper.get("similarity", 0.0), 4),
            "content_source": content_source,
            "paper_realization": realization,
            "overlap_degree": (comp.overlap_degree or "").lower(),
            "what_is_shared": comp.what_is_shared,
            "submission_delta": comp.submission_delta,
            "assessment": note,
            "refutation_status": status,
            "evidence_pairs": verified_pairs,
            "brief_note": note,
        }

    def compare_claim(self, claim: dict, candidates: List[dict], title_to_contexts: dict,
                      submission_text: str = "") -> List[dict]:
        """Run the LLM comparison for a claim against all its candidates (batched)."""
        if not candidates:
            return []
        contents = [self._candidate_content(c) for c in candidates]  # (source, text)
        ctxs_per_cand = [
            self._match_citation_context(c["title"], title_to_contexts) for c in candidates
        ]
        prompts = [
            self._build_prompt(claim, contents[i][0], contents[i][1], c, ctxs_per_cand[i])
            for i, c in enumerate(candidates)
        ]
        chain = self.llm.with_structured_output(_SectionComparison)
        results = chain.batch(prompts, config={"max_concurrency": self.max_concurrency})
        return [
            self._verify_and_finalize(r, candidates[i], contents[i][0], contents[i][1],
                                      submission_text)
            for i, r in enumerate(results)
        ]

    # ----------------------------- build ------------------------------- #

    def build_one(self, claim: dict, papers: List[dict], title_to_contexts: dict,
                  submission_text: str = "") -> dict:
        """Compute the Artifact-A evidence entry for a SINGLE claim (used for the
        on-demand, per-claim review)."""
        # The comparison prompt shows the model the claim text and description, so a
        # claim_quote legitimately comes from either -- append both to the verification
        # corpus, exactly as the agent does for its own claim-side checks.
        claim_side = "\n\n".join(
            x for x in (submission_text, claim.get("claim_text", ""),
                        claim.get("description", "")) if x
        )
        candidates = self.select_candidates(claim, papers, self.k_per_claim)
        comparisons = self.compare_claim(claim, candidates, title_to_contexts, claim_side)
        refuting = [c for c in comparisons if c["refutation_status"] == "can_refute"]
        return {
            "claim_id": claim["id"],
            "claim_name": claim["name"],
            "claim_text": claim.get("claim_text", ""),
            "candidates_examined": len(comparisons),
            "can_refute_count": len(refuting),
            "comparisons": comparisons,
        }

    def build(self, data_dir: str, submission_id: str, variant: str = "") -> dict:
        sub_dir = Path(data_dir) / submission_id
        claims_doc = json.loads((sub_dir / f"{submission_id}_claims.json").read_text(encoding="utf-8"))
        # validated = not rejected (reuse Step 2 semantics)
        claims = [c for c in claims_doc["claims"] if c.get("status") != "rejected"]

        stats = self.prepare_fulltexts(data_dir, submission_id)
        logger_msg = (f"full text ready for {stats['already_had'] + stats['ok']} pool papers "
                      f"({stats['ok']} newly parsed, {stats['no_pdf']} without a PDF, "
                      f"{stats['failed']} failed)")
        print(logger_msg)
        papers = self.load_related_work(data_dir, submission_id)
        title_to_contexts = self.load_citation_contexts_by_title(data_dir, submission_id)
        submission_text = self.load_submission_text(data_dir, submission_id)

        try:
            import progress as _progress  # optional sub-progress for the frontend
        except Exception:
            _progress = None
        n_claims = len(claims)
        if _progress:
            _progress.start_phase("Comparing claims", n_claims)

        entries = []
        for claim_idx, claim in enumerate(claims):
            if _progress:
                _progress.report(claim_idx, n_claims)
            entries.append(self.build_one(claim, papers, title_to_contexts, submission_text))

        if _progress:
            _progress.report(n_claims, n_claims)

        artifact = {
            "submission_id": submission_id,
            "k_per_claim": self.k_per_claim,
            "n_related_pool": len(papers),
            "claims": entries,
        }
        out_path = variant_path(sub_dir, submission_id, "artifact_a", variant)
        out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return artifact


def main():
    ap = argparse.ArgumentParser(description="Step 4: claim-level comparison -> Artifact A")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--k", type=int, default=10, help="candidates compared per claim")
    ap.add_argument("--variant", default="", help="write {id}_artifact_a_{variant}.json instead, "
                                                 "so a run does not overwrite another system's")
    args = ap.parse_args()

    builder = ArtifactABuilder(model_name=args.model, k_per_claim=args.k)
    art = builder.build(args.data_dir, args.submission_id, variant=args.variant)

    ft = sum(1 for e in art["claims"] for c in e["comparisons"] if c["content_source"].startswith("full"))
    tot = sum(len(e["comparisons"]) for e in art["claims"])
    print(f"Artifact A for {art['submission_id']} (k={art['k_per_claim']}, pool={art['n_related_pool']}):")
    print(f"  comparisons using full text: {ft}/{tot}")
    for e in art["claims"]:
        print(f"\n[{e['claim_id']}] {e['claim_name']}")
        print(f"  examined {e['candidates_examined']} | can_refute: {e['can_refute_count']}")
        for c in e["comparisons"]:
            if c["refutation_status"] != "cannot_refute":
                vq = sum(1 for p in c["evidence_pairs"] if p["paper_quote_verified"])
                print(f"    - {c['refutation_status']} ({c['similarity']}, {c['content_source']}) {c['title'][:45]} [verified quotes: {vq}]")


if __name__ == "__main__":
    main()
