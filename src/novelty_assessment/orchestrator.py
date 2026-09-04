#!/usr/bin/env python3
"""
Step 0: Pipeline Orchestrator (verification-first novelty assessment).

Drives the full pipeline PDF -> reviewer report as a RESUMABLE STATE MACHINE
with human-in-the-loop (HITL) checkpoints, so a frontend can pause the pipeline,
let the reviewer intervene, and resume.

Stages (in order):
  1. document_processing  (GROBID -> metadata + full text + quality gates)
  2. claim_extraction     -> CHECKPOINT 'claims'  (reviewer accepts/edits/deletes/adds claims)
  3. retrieval            (S2 enrichment + retrieve/rank) -> CHECKPOINT 'papers' (reviewer validates the pool)
  4. artifact_a           (full-text fetch + claim-level evidence comparison)
  5. artifact_b           (synthesis, only from Artifact A)
  6. judge                (does B follow from A?)
  7. export               (reviewer report)

HITL flow (frontend):
  run() -> runs until a checkpoint -> status 'awaiting_review:<cp>'
  reviewer edits the relevant artifact (e.g. {id}_claims.json via claim_extraction HITL ops)
  approve('<cp>'); run()  -> continues to the next checkpoint / completion

Autonomous mode (hitl=False): checkpoints auto-approve; runs straight through
(for evaluation / batch).

State is persisted in {id}_pipeline_state.json. Stages are idempotent: a stage
whose output already exists is skipped, so the pipeline is safely re-runnable.
"""
import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from contextlib import nullcontext
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("orchestrator")

# OpenAI cost tracking: a context manager that tallies token usage of every
# langchain ChatOpenAI call inside it (claim_extraction, artifact_a/b, judge,
# title fallback). retrieval's ChatLiteLLM keyword call + RankGPT are NOT captured
# here (different client) -- their cost is small and reported as n/a.
try:
    from langchain_community.callbacks import get_openai_callback
except Exception:  # pragma: no cover
    try:
        from langchain.callbacks import get_openai_callback
    except Exception:
        get_openai_callback = None

# Pricing is NOT duplicated here. This module used to keep its own small table, which is
# how claim extraction came to be billed at the pipeline model's rate: the stage runs on
# gpt-5.6-luna, the table only knew gpt-4.x, and the mismatch overstated the stage by 8.6x.
# claim_extraction._usd is the single source of truth (and handles the gpt-5.6 variants).
def _price_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    sys.path.insert(0, _HERE)
    from claim_extraction import _usd
    return _usd(model, prompt_tokens, completion_tokens)

# Fallback per-stage duration estimates (seconds) for the frontend ETA, used until a
# real rolling-average baseline accumulates in {data_dir}/_stage_baseline.json.
_DEFAULT_ESTIMATES = {
    "document_processing": 60,
    "claim_extraction": 45,
    "retrieval": 240,
    "fetch_pdfs": 60,  # download-only now; GROBID parsing happens per deep dive instead
    "artifact_a": 300,
    "artifact_b": 30,
    "judge": 30,
    "export": 3,
}


def _fmt_dur(seconds) -> str:
    seconds = int(round(seconds or 0))
    m, s = divmod(seconds, 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"

_PREPROCESS = str(Path(__file__).resolve().parents[1] / "preprocess")
_RETRIEVAL = str(Path(__file__).resolve().parents[1] / "retrieval")
_HERE = str(Path(__file__).resolve().parent)

# Make the sub-progress reporter importable by every stage module (incl. the
# retrieval modules in src/retrieval, which do an optional `import progress`).
sys.path.insert(0, _HERE)
try:
    import progress as _progress
except Exception:
    _progress = None

# Outputs cached per PDF-hash so a re-upload of the SAME paper reuses prior work instead
# of redoing it. Restored into the new (versioned) submission dir, so the corresponding
# stages are skipped by idempotency.
#   UPSTREAM (stages 1-4): the expensive document_processing + claim_extraction + retrieval.
#   DOWNSTREAM (agent results + everything synthesised from them): the per-claim Artifact A,
#     the synthesis/judge, the overall conclusion, the agent cost and the exported report.
# Downstream files are written AFTER stage 4 -- by the on-demand review in api.py or the
# batch run_agentic_claims() -- so the cache is refreshed again at those points
# (api.py._snapshot_cache / run_agentic_claims -> snapshot_cache), not only after
# retrieval/fetch_pdfs. This lets a re-upload of a fully-reviewed paper restore the
# finished assessment instead of re-running the slow, paid per-claim agent.
_CACHEABLE = [
    # upstream (stages 1-4)
    "{id}.json",                                    # metadata + S2-enriched cited papers
    "{id}_fulltext.json",
    "{id}_quality.json",
    "{id}.grobid.tei.xml",
    "{id}_claims.json",
    "{id}_pdf_status.json",                         # fetch_pdfs' idempotency marker: caching
                                                    # it makes fetch_pdfs SKIP on a cache hit,
                                                    # so _save_to_cache() (which rewrites
                                                    # cached_id) is NOT re-triggered on every
                                                    # re-upload -> cached_id stays stable and
                                                    # the downstream artefacts never get
                                                    # orphaned under a stale prefix.
    "related_work_data/ranked_papers.json",
    "related_work_data/all_retrieved_papers.json",
    "related_work_data/metadata.json",
    # downstream (agent results + everything derived from them)
    "{id}_artifact_a.json",                         # the per-claim agent evidence ledger
    "{id}_artifact_b.json",
    "{id}_judge.json",
    "{id}_conclusion.json",
    "{id}_agent_cost.json",
    "{id}_report.md",
]

# Directory trees cached as-is (files keyed by paper_id, NOT by submission id -> no rewrite).
# Caching these lets a re-upload of the SAME PDF reuse the downloaded PDFs (no re-download)
# and any full text ALREADY parsed on demand during a prior review (agent/tools.py
# ensure_fulltext). Parsing happens lazily per deep dive, i.e. AFTER stage 4 -- but the
# review now refreshes the cache after each claim (api.py._snapshot_cache), so the
# GROBID full text of deep-dived papers is snapshotted then and reused on re-upload.
_CACHEABLE_DIRS = [
    "related_work_data/pdfs",
    "related_work_data/grobid_fulltext",
]

# stage name -> (checkpoint-after or None, output file (relative to submission dir) used for idempotency)
# The pipeline now STOPS after fetch_pdfs (status=completed). The per-claim evidence
# (Artifact A comparison + B synthesis + Judge verdict) is computed ON DEMAND, one claim
# at a time, from the frontend review walkthrough via api.py. The final cross-claim
# summary (export) is deferred.
#
# fetch_pdfs only DOWNLOADS a PDF per pool paper (no GROBID) -- the reviewer sees which
# papers have a PDF in Related Work and can upload one manually for the rest. GROBID
# full-text parsing happens ON DEMAND, per paper, only when the claim agent actually
# deep-dives it (agent/tools.py ClaimToolbox.ensure_fulltext) -- most papers are never
# deep-dived, so most PDFs are never GROBID-parsed at all.
#
# The 'papers' checkpoint sits AFTER fetch_pdfs (not directly after retrieval), so the
# reviewer sees PDF availability -- and can upload a missing PDF -- before approving
# the pool, not only after.
STAGES = [
    ("document_processing", None, "{id}_quality.json"),
    ("claim_extraction", "claims", "{id}_claims.json"),
    ("retrieval", None, "related_work_data/ranked_papers.json"),
    ("fetch_pdfs", "papers", "{id}_pdf_status.json"),
]


class NoveltyPipeline:
    def __init__(self, data_dir, submission_id, pdf_path=None, model="gpt-4.1",
                 grobid_server="http://localhost:8070", k_per_claim=10, hitl=True,
                 use_cache=True, agent_max_steps=24, agent_max_retrievals=3,
                 agent_closest_n=5):
        self.data_dir = data_dir
        self.submission_id = submission_id
        self.pdf_path = pdf_path
        self.model = model
        self.grobid_server = grobid_server
        self.k_per_claim = k_per_claim
        self.hitl = hitl
        self.use_cache = use_cache
        # Agent budgets (ablation hyperparameters) for the autonomous agentic run.
        self.agent_max_steps = agent_max_steps
        self.agent_max_retrievals = agent_max_retrievals
        self.agent_closest_n = agent_closest_n
        self.sub_dir = Path(data_dir) / submission_id
        self.state_path = self.sub_dir / f"{submission_id}_pipeline_state.json"

    # ----------------------------- state ----------------------------- #

    def _load_state(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        self.sub_dir.mkdir(parents=True, exist_ok=True)
        return {
            "submission_id": self.submission_id,
            "pdf_path": self.pdf_path,
            "hitl": self.hitl,
            "stages_done": [],
            "checkpoints": {},
            "status": "created",
            "last_error": None,
        }

    def _save_state(self, state):
        state["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _output_exists(self, output_rel):
        return (self.sub_dir / output_rel.format(id=self.submission_id)).exists()

    # ----------------------------- stages ---------------------------- #

    def _run_stage(self, name, state):
        if name == "document_processing":
            sys.path.insert(0, _PREPROCESS)
            from grobid_client import GrobidClient
            pdf = state.get("pdf_path") or str(self.sub_dir / f"{self.submission_id}.pdf")
            GrobidClient(self.grobid_server).process_for_pipeline(pdf, self.data_dir, self.submission_id)

        elif name == "claim_extraction":
            sys.path.insert(0, _HERE)
            from claim_extraction import DEFAULT_EXTRACTION_MODEL, ClaimExtractor
            # NOT self.model: extraction uses its own (stronger) model -- see
            # claim_extraction.DEFAULT_EXTRACTION_MODEL for why.
            ClaimExtractor(model_name=DEFAULT_EXTRACTION_MODEL).extract(
                self.data_dir, self.submission_id)

        elif name == "retrieval":
            sys.path.insert(0, _RETRIEVAL)
            import match_papers_to_s2
            import retrieval as retrieval_mod
            match_papers_to_s2.process_for_pipeline(self.data_dir, self.submission_id)
            retrieval_mod.process_for_pipeline(self.data_dir, self.submission_id)

        elif name == "fetch_pdfs":
            # PDF-only (no GROBID): the per-claim agent parses full text on demand for
            # whichever papers it actually deep-dives (see agent/tools.py ensure_fulltext).
            # The per-claim evidence comparisons (Artifact A), synthesis (B) and verdict
            # (Judge) are computed ON DEMAND, claim by claim, from the frontend review
            # walkthrough (see api.py /review/claim/...).
            sys.path.insert(0, _HERE)
            from fetch_fulltext import FullTextFetcher
            try:
                FullTextFetcher(self.grobid_server).download_pdfs(self.data_dir, self.submission_id)
            except Exception as e:  # PDF download is best-effort; papers stay on abstract+intro
                logger.warning(f"PDF download partial/failed (continuing): {repr(e)[:120]}")
            self._write_pdf_status()

        elif name == "artifact_b":
            sys.path.insert(0, _HERE)
            from artifact_b import ArtifactBBuilder
            ArtifactBBuilder(model_name=self.model).build(self.data_dir, self.submission_id)

        elif name == "judge":
            sys.path.insert(0, _HERE)
            from artifact_judge import Judge
            Judge(model_name=self.model).judge(self.data_dir, self.submission_id)

        elif name == "export":
            sys.path.insert(0, _HERE)
            from export_report import build_report
            build_report(self.data_dir, self.submission_id)

        else:
            raise ValueError(f"unknown stage: {name}")

    def _write_pdf_status(self):
        """Record which related-work papers have a downloaded PDF vs none (yet).

        This is about PDF AVAILABILITY only -- whether GROBID has parsed a paper's
        full text is a separate, later concern (decided per deep dive, see
        agent/tools.py ensure_fulltext), not tracked here."""
        rwd = self.sub_dir / "related_work_data"
        try:
            ranked = json.loads((rwd / "ranked_papers.json").read_text(encoding="utf-8"))
        except Exception:
            ranked = []
        with_pdf, no_pdf = [], []
        for p in ranked:
            pid = p.get("paper_id")
            pdf_path = rwd / "pdfs" / f"{pid}.pdf"
            has_pdf = pdf_path.exists() and pdf_path.stat().st_size > 0
            item = {
                "paper_id": pid, "title": p.get("title", ""),
                "authors": p.get("authors", ""), "year": p.get("year", ""),
                "venue": p.get("venue", ""),
            }
            (with_pdf if has_pdf else no_pdf).append(item)
        status = {
            "submission_id": self.submission_id,
            "n_total": len(ranked), "n_with_pdf": len(with_pdf),
            "with_pdf": with_pdf, "no_pdf": no_pdf,
        }
        (self.sub_dir / f"{self.submission_id}_pdf_status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            f"[{self.submission_id}] PDFs: {len(with_pdf)}/{len(ranked)} papers "
            f"({len(no_pdf)} no PDF)"
        )

    # ------------------------------ run ------------------------------- #

    def approve(self, checkpoint: str):
        """Mark a HITL checkpoint approved (frontend calls this after the reviewer acts)."""
        state = self._load_state()
        state["checkpoints"][checkpoint] = "approved"
        if state["status"].startswith("awaiting_review"):
            state["status"] = "running"
        self._save_state(state)
        return state

    # --------------------------- metrics / ETA ----------------------------- #

    def _baseline_path(self):
        return Path(self.data_dir) / "_stage_baseline.json"

    def _load_estimates(self):
        """Per-stage duration estimates: rolling baseline of past runs, else defaults."""
        est = dict(_DEFAULT_ESTIMATES)
        try:
            data = json.loads(self._baseline_path().read_text(encoding="utf-8"))
            for k, v in data.items():
                if isinstance(v, (int, float)) and v > 0:
                    est[k] = round(float(v), 1)
        except Exception:
            pass
        return est

    def _update_baseline(self, name, seconds):
        """Exponential moving average of stage durations across runs (alpha=0.4)."""
        path = self._baseline_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            data = {}
        prev = data.get(name)
        data[name] = round(seconds if prev is None else 0.6 * prev + 0.4 * seconds, 1)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _stage_model(self, name: str) -> str:
        """Which model a stage actually bills to. Not every stage uses self.model:
        claim extraction deliberately runs on its own, stronger model."""
        if name == "claim_extraction":
            sys.path.insert(0, _HERE)
            from claim_extraction import DEFAULT_EXTRACTION_MODEL
            return DEFAULT_EXTRACTION_MODEL
        return self.model

    def _stage_cost(self, cb, stage_name: str = ""):
        """(prompt_tokens, completion_tokens, usd) from an OpenAI callback (None -> skip).

        Prices against the model the STAGE ran on. Pricing everything at self.model billed
        claim extraction -- which runs on gpt-5.6-luna -- at gpt-4.1 rates and overstated it
        by a factor of 8.6 on the first full run, while the artifact itself recorded the
        correct figure. Cost numbers end up in the thesis, so they have to be right.
        """
        if cb is None:
            return None
        pt = int(getattr(cb, "prompt_tokens", 0) or 0)
        ct = int(getattr(cb, "completion_tokens", 0) or 0)
        usd = float(getattr(cb, "total_cost", 0.0) or 0.0)
        if not usd and (pt or ct):  # callback didn't know the price -> use our table
            usd = _price_usd(self._stage_model(stage_name), pt, ct)
        return pt, ct, round(usd, 4)

    def _write_summary(self, state):
        """Write {id}_timing.json and log a per-stage time/cost table to the terminal."""
        metrics = state.get("metrics", {})
        total_s = sum((metrics.get(n, {}).get("seconds") or 0) for n, _, _ in STAGES)
        total_usd = sum((metrics.get(n, {}).get("usd") or 0) for n, _, _ in STAGES)
        summary = {
            "submission_id": self.submission_id,
            "model": self.model,
            "total_seconds": round(total_s, 1),
            "total_human": _fmt_dur(total_s),
            "total_usd": round(total_usd, 4),
            "stages": {n: metrics.get(n, {}) for n, _, _ in STAGES},
        }
        (self.sub_dir / f"{self.submission_id}_timing.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("=" * 66)
        logger.info(f"PIPELINE SUMMARY  {self.submission_id}  (model={self.model})")
        logger.info(f"{'stage':<22}{'time':>10}{'tokens':>16}{'cost USD':>16}")
        logger.info("-" * 66)
        for n, _, _ in STAGES:
            m = metrics.get(n, {})
            secs = m.get("seconds")
            toks = (m.get("prompt_tokens") or 0) + (m.get("completion_tokens") or 0)
            usd = m.get("usd")
            logger.info(
                f"{n:<22}"
                f"{(_fmt_dur(secs) if secs is not None else '-'):>10}"
                f"{(f'{toks:,}' if toks else '-'):>16}"
                f"{(f'${usd:.4f}' if usd else '-'):>16}"
            )
            # within-stage breakdown (which phase of retrieval/artifact_a was slow)
            phases = m.get("phases") or {}
            if phases:
                for ph, ps in phases.items():
                    logger.info(f"  - {ph:<20}{_fmt_dur(ps):>8}")
                other = (secs or 0) - sum(phases.values())
                if other > 1:
                    logger.info(f"  - {'(other/overhead)':<20}{_fmt_dur(other):>8}")
        logger.info("-" * 66)
        logger.info(f"{'TOTAL':<22}{_fmt_dur(total_s):>10}{'':>16}{f'${total_usd:.4f}':>16}")
        logger.info("=" * 66)

    # --------------------------- upstream cache ---------------------------- #

    def _pdf_hash(self):
        """Content hash of the submission PDF (stable key for 'the same paper')."""
        for p in (self.pdf_path, str(self.sub_dir / f"{self.submission_id}.pdf")):
            if p and Path(p).exists():
                try:
                    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
                except Exception:
                    pass
        return None

    def _cache_dir(self, h):
        return Path(self.data_dir) / "_cache" / h

    def _restore_from_cache(self):
        """Restore cached upstream outputs for this PDF into the submission dir, so
        document_processing/claim_extraction/retrieval are skipped (idempotent)."""
        if not self.use_cache:
            return
        h = self._pdf_hash()
        if not h:
            return
        cdir = self._cache_dir(h)
        meta_path = cdir / "_cache_meta.json"
        if not meta_path.exists():
            return
        try:
            cached_id = json.loads(meta_path.read_text(encoding="utf-8")).get("cached_id")
        except Exception:
            return
        if not cached_id:
            return
        restored = 0
        for tmpl in _CACHEABLE:
            src = cdir / "files" / tmpl.format(id=cached_id)
            if not src.exists():
                continue
            dst = self.sub_dir / tmpl.format(id=self.submission_id)
            if dst.exists():
                continue  # never overwrite anything already in this run
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix in (".json", ".md"):
                # rewrite the cached submission_id so paths/fields/report headers match this run
                dst.write_text(
                    src.read_text(encoding="utf-8").replace(cached_id, self.submission_id),
                    encoding="utf-8",
                )
            else:
                shutil.copy2(src, dst)
            restored += 1
        # Restore cached directory trees (PDFs + GROBID full text), file-by-file,
        # never overwriting anything already present in this run.
        restored_dir_files = 0
        for d in _CACHEABLE_DIRS:
            src_dir = cdir / "files" / d
            if not src_dir.is_dir():
                continue
            dst_dir = self.sub_dir / d
            for src_f in src_dir.rglob("*"):
                if not src_f.is_file():
                    continue
                dst_f = dst_dir / src_f.relative_to(src_dir)
                if dst_f.exists():
                    continue
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_f, dst_f)
                restored_dir_files += 1
        if restored or restored_dir_files:
            logger.info(
                f"[{self.submission_id}] cache HIT ({h}): restored {restored} files "
                f"+ {restored_dir_files} pdf/full-text files -> skipping "
                f"document_processing/claim_extraction/retrieval/fetch_pdfs"
            )

    def _save_to_cache(self):
        """Snapshot this run's outputs into the per-PDF cache for fast re-runs.

        Cached files are stored under this run's submission_id prefix, and cached_id is
        updated to match. To avoid orphaning artefacts already cached under a PREVIOUS
        cached_id that this run did NOT reproduce in its own dir (e.g. a snapshot taken
        after fetch_pdfs, before the review agent has run), those are carried forward under
        the new prefix (with the id rewritten) instead of being left stranded."""
        if not self.use_cache:
            return
        h = self._pdf_hash()
        if not h:
            return
        cdir = self._cache_dir(h)
        files = cdir / "files"
        prev_id = None
        meta_path = cdir / "_cache_meta.json"
        if meta_path.exists():
            try:
                prev_id = json.loads(meta_path.read_text(encoding="utf-8")).get("cached_id")
            except Exception:
                prev_id = None
        try:
            for tmpl in _CACHEABLE:
                src = self.sub_dir / tmpl.format(id=self.submission_id)
                dst = files / tmpl.format(id=self.submission_id)
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                elif prev_id and prev_id != self.submission_id and not dst.exists():
                    # not produced this run -> carry the previously cached copy forward so
                    # the cached_id switch below doesn't strand it under the old prefix
                    old = files / tmpl.format(id=prev_id)
                    if old.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if old.suffix in (".json", ".md"):
                            dst.write_text(
                                old.read_text(encoding="utf-8").replace(prev_id, self.submission_id),
                                encoding="utf-8",
                            )
                        else:
                            shutil.copy2(old, dst)
            # Mirror cached directory trees (PDFs + GROBID full text) into the cache.
            for d in _CACHEABLE_DIRS:
                src_dir = self.sub_dir / d
                if not src_dir.is_dir():
                    continue
                dst_dir = cdir / "files" / d
                for src_f in src_dir.rglob("*"):
                    if not src_f.is_file():
                        continue
                    dst_f = dst_dir / src_f.relative_to(src_dir)
                    dst_f.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_f, dst_f)
            (cdir / "_cache_meta.json").write_text(
                json.dumps({"cached_id": self.submission_id,
                            "saved": time.strftime("%Y-%m-%d %H:%M:%S")}),
                encoding="utf-8",
            )
            logger.info(f"[{self.submission_id}] cached outputs ({h}) for fast re-runs")
        except Exception as exc:
            logger.warning(f"cache save failed: {exc}")

    def snapshot_cache(self):
        """Public entry point to refresh the per-PDF cache. Called after the DOWNSTREAM
        artefacts (Artifact A + everything synthesised from it) are written by the
        on-demand review (api.py) or the batch agentic run, so those results are cached
        too -- not just the upstream stages snapshotted during run()."""
        self._save_to_cache()

    # ------------------------------ run ------------------------------- #

    def run(self):
        """Run stages until a pending checkpoint (HITL) or completion."""
        state = self._load_state()
        if self.pdf_path and not state.get("pdf_path"):
            state["pdf_path"] = self.pdf_path
        # Re-upload of the same PDF: pull cached upstream outputs in so the expensive
        # stages are skipped (no-op if no cache / files already present).
        self._restore_from_cache()
        state["status"] = "running"
        state["estimates"] = self._load_estimates()
        state.setdefault("metrics", {})
        self._save_state(state)

        for name, checkpoint, output_rel in STAGES:
            done = name in state["stages_done"] or self._output_exists(output_rel)
            if not done:
                logger.info(f"[{self.submission_id}] running stage: {name}")
                state["current_stage"] = {"name": name, "started_epoch": time.time()}
                self._save_state(state)
                if _progress:
                    _progress.configure(self.sub_dir / f"{self.submission_id}_progress.json")
                t0 = time.time()
                cb_ctx = get_openai_callback() if get_openai_callback else nullcontext()
                try:
                    with cb_ctx as cb:
                        self._run_stage(name, state)
                except Exception as e:
                    if _progress:
                        _progress.clear()
                    state["metrics"][name] = {"seconds": round(time.time() - t0, 1), "status": "failed"}
                    state["current_stage"] = None
                    state["status"] = "failed"
                    state["last_error"] = f"{name}: {repr(e)[:300]}"
                    self._save_state(state)
                    logger.error(state["last_error"])
                    return state
                phase_secs = _progress.durations() if _progress else None
                if _progress:
                    _progress.clear()
                seconds = time.time() - t0
                metric = {"seconds": round(seconds, 1), "status": "done"}
                if phase_secs:
                    metric["phases"] = phase_secs  # within-stage breakdown (retrieval/artifact_a)
                cost = self._stage_cost(cb, name)
                if cost is not None:
                    pt, ct, usd = cost
                    metric.update({"prompt_tokens": pt, "completion_tokens": ct, "usd": usd})
                state["metrics"][name] = metric
                state["current_stage"] = None
                self._update_baseline(name, seconds)
                self._save_state(state)
                logger.info(
                    f"[{self.submission_id}] stage '{name}' done in {_fmt_dur(seconds)}"
                    + (f" (${metric['usd']:.4f}, {pt + ct:,} tok)" if "usd" in metric and (metric.get("usd") or pt or ct) else "")
                )
                # retrieval just finished -> snapshot upstream outputs for re-runs;
                # fetch_pdfs just finished -> also snapshot the downloaded PDFs so a
                # re-upload of the same PDF skips the (rate-limited) re-download.
                if name in ("retrieval", "fetch_pdfs"):
                    self._save_to_cache()
            else:
                logger.info(f"[{self.submission_id}] skip (already done): {name}")
            if name not in state["stages_done"]:
                state["stages_done"].append(name)
                self._save_state(state)

            if checkpoint and state["checkpoints"].get(checkpoint) != "approved":
                if self.hitl:
                    state["checkpoints"][checkpoint] = "awaiting"
                    state["status"] = f"awaiting_review:{checkpoint}"
                    self._save_state(state)
                    logger.info(f"[{self.submission_id}] paused for reviewer at checkpoint '{checkpoint}'")
                    return state
                state["checkpoints"][checkpoint] = "approved"  # autonomous
                self._save_state(state)

        state["status"] = "completed"
        state["current_stage"] = None
        self._save_state(state)
        self._write_summary(state)
        logger.info(f"[{self.submission_id}] pipeline completed")
        return state

    # --------------------------- agentic claims ---------------------------- #

    def run_agentic_claims(self):
        """Autonomous per-claim agent -> Artifact B -> Judge -> report (batch / evaluation).

        Runs the DFS agent for every accepted claim, assembles the artifact_a.json
        aggregate (same shape the non-agentic builder produced, plus agentic extras),
        then reuses the unchanged synthesis / judge / export steps. Requires stages
        1-4 to have run first (claims + ranked_papers + full text present)."""
        sys.path.insert(0, _HERE)
        from agent.claim_agent import ClaimNoveltyAgent
        from artifact_b import ArtifactBBuilder
        from artifact_judge import Judge
        from export_report import build_report

        claims_doc = json.loads(
            (self.sub_dir / f"{self.submission_id}_claims.json").read_text(encoding="utf-8")
        )
        claims = [c for c in claims_doc["claims"] if c.get("status") != "rejected"]
        agent = ClaimNoveltyAgent(
            self.data_dir, self.submission_id, model_name=self.model,
            grobid_server=self.grobid_server, max_steps=self.agent_max_steps,
            max_retrievals=self.agent_max_retrievals, closest_n=self.agent_closest_n,
        )
        entries = []
        for c in claims:
            logger.info(f"[{self.submission_id}] agent: claim {c['id']} ({c.get('name','')[:50]})")
            entries.append(agent.run(c))

        artifact_a = {
            "submission_id": self.submission_id,
            "agentic": True,
            "closest_n": self.agent_closest_n,
            "n_related_pool": max((sum(e.get("pool_sources", {}).values()) for e in entries), default=0),
            "claims": entries,
        }
        (self.sub_dir / f"{self.submission_id}_artifact_a.json").write_text(
            json.dumps(artifact_a, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        ArtifactBBuilder(model_name=self.model).build(self.data_dir, self.submission_id)
        Judge(model_name=self.model).judge(self.data_dir, self.submission_id)
        report = build_report(self.data_dir, self.submission_id)
        # Fold the finished agent results + synthesis/judge/report into the per-PDF cache,
        # so a re-upload of this paper restores them instead of re-running the agent.
        self._save_to_cache()
        logger.info(f"[{self.submission_id}] agentic claims + report done ({len(entries)} claims)")
        return report


def main():
    ap = argparse.ArgumentParser(description="Step 0: novelty pipeline orchestrator")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--pdf", default=None, help="submission PDF (required on first run)")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--grobid-server", default="http://localhost:8070")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--no-hitl", action="store_true", help="autonomous: auto-approve checkpoints")
    ap.add_argument("--approve", default=None, help="approve a checkpoint (claims|papers) then continue")
    ap.add_argument("--status", action="store_true", help="print pipeline state and exit")
    ap.add_argument("--agentic-claims", action="store_true",
                    help="after stages 1-4, run the per-claim agent -> Artifact B -> Judge -> report")
    ap.add_argument("--max-steps", type=int, default=24, help="agent: max tool steps per claim")
    ap.add_argument("--max-retrievals", type=int, default=3, help="agent: max retrieve_more per claim")
    ap.add_argument("--closest-n", type=int, default=5, help="agent: closest-set size the gate requires covered")
    args = ap.parse_args()

    pipe = NoveltyPipeline(
        args.data_dir, args.submission_id, pdf_path=args.pdf, model=args.model,
        grobid_server=args.grobid_server, k_per_claim=args.k, hitl=not args.no_hitl,
        agent_max_steps=args.max_steps, agent_max_retrievals=args.max_retrievals,
        agent_closest_n=args.closest_n,
    )

    if args.status:
        print(json.dumps(pipe._load_state(), indent=2, ensure_ascii=False))
        return
    if args.approve:
        pipe.approve(args.approve)

    state = pipe.run()
    print(f"\nstatus: {state['status']}")
    print(f"stages done: {state['stages_done']}")
    print(f"checkpoints: {state['checkpoints']}")
    if state.get("last_error"):
        print(f"error: {state['last_error']}")

    # Autonomous agentic claim assessment (needs stages 1-4 completed / auto-approved).
    if args.agentic_claims and state["status"] == "completed":
        print("\nrunning agentic per-claim assessment ...")
        pipe.run_agentic_claims()
        print(f"report: {pipe.sub_dir / (args.submission_id + '_report.md')}")


if __name__ == "__main__":
    main()
