"""Resumable pipeline up to the comparison (Figure 4.1).

Stages: document processing, claim extraction (checkpoint "claims"), retrieval with
version pinning, and PDF download (checkpoint "papers"). The comparison is then run per
claim from the API. State, per-stage time and cost are kept in {id}_pipeline_state.json.
With hitl=False both checkpoints are approved automatically.
"""

import argparse
import json
import logging
import sys
import time
from contextlib import nullcontext
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("orchestrator")

try:
    from langchain_community.callbacks import get_openai_callback
except Exception:
    get_openai_callback = None

_PREPROCESS = str(Path(__file__).resolve().parents[1] / "preprocess")
_RETRIEVAL = str(Path(__file__).resolve().parents[1] / "retrieval")
_HERE = str(Path(__file__).resolve().parent)

sys.path.insert(0, _HERE)
try:
    import progress as _progress
except Exception:
    _progress = None

# (stage, checkpoint after the stage, output file that marks the stage as done)
STAGES = [
    ("document_processing", None, "{id}_quality.json"),
    ("claim_extraction", "claims", "{id}_claims.json"),
    ("retrieval", None, "related_work_data/ranked_papers.json"),
    ("fetch_pdfs", "papers", "{id}_pdf_status.json"),
]


def _price_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    from claim_extraction import _usd

    return _usd(model, prompt_tokens, completion_tokens)


def _fmt_dur(seconds) -> str:
    seconds = int(round(seconds or 0))
    m, s = divmod(seconds, 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


class NoveltyPipeline:
    def __init__(
        self,
        data_dir,
        submission_id,
        pdf_path=None,
        model="gpt-4.1",
        grobid_server="http://localhost:8070",
        hitl=True,
    ):
        self.data_dir = data_dir
        self.submission_id = submission_id
        self.pdf_path = pdf_path
        self.model = model
        self.grobid_server = grobid_server
        self.hitl = hitl
        self.sub_dir = Path(data_dir) / submission_id
        self.state_path = self.sub_dir / f"{submission_id}_pipeline_state.json"

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
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _output_exists(self, output_rel):
        return (self.sub_dir / output_rel.format(id=self.submission_id)).exists()

    def _run_stage(self, name, state):
        if name == "document_processing":
            sys.path.insert(0, _PREPROCESS)
            from grobid_client import GrobidClient

            pdf = state.get("pdf_path") or str(self.sub_dir / f"{self.submission_id}.pdf")
            GrobidClient(self.grobid_server).process_for_pipeline(
                pdf, self.data_dir, self.submission_id
            )

        elif name == "claim_extraction":
            from claim_extraction import DEFAULT_EXTRACTION_MODEL, ClaimExtractor

            ClaimExtractor(model_name=DEFAULT_EXTRACTION_MODEL).extract(
                self.data_dir, self.submission_id
            )

        elif name == "retrieval":
            sys.path.insert(0, _RETRIEVAL)
            import match_papers_to_s2
            import retrieval as retrieval_mod

            match_papers_to_s2.process_for_pipeline(self.data_dir, self.submission_id)
            retrieval_mod.process_for_pipeline(self.data_dir, self.submission_id)

        elif name == "fetch_pdfs":
            # Download only; prior papers are parsed when the comparison first reads them.
            from fetch_fulltext import FullTextFetcher

            try:
                FullTextFetcher(self.grobid_server).download_pdfs(self.data_dir, self.submission_id)
            except Exception as e:
                logger.warning(f"PDF download partial/failed (continuing): {repr(e)[:120]}")
            self._write_pdf_status()

        else:
            raise ValueError(f"unknown stage: {name}")

    def _write_pdf_status(self):
        """Record which pool papers have a downloaded PDF."""
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
                "paper_id": pid,
                "title": p.get("title", ""),
                "authors": p.get("authors", ""),
                "year": p.get("year", ""),
                "venue": p.get("venue", ""),
            }
            (with_pdf if has_pdf else no_pdf).append(item)
        status = {
            "submission_id": self.submission_id,
            "n_total": len(ranked),
            "n_with_pdf": len(with_pdf),
            "with_pdf": with_pdf,
            "no_pdf": no_pdf,
        }
        (self.sub_dir / f"{self.submission_id}_pdf_status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            f"[{self.submission_id}] PDFs: {len(with_pdf)}/{len(ranked)} papers "
            f"({len(no_pdf)} no PDF)"
        )

    def approve(self, checkpoint: str):
        """Mark a checkpoint as approved."""
        state = self._load_state()
        state["checkpoints"][checkpoint] = "approved"
        if state["status"].startswith("awaiting_review"):
            state["status"] = "running"
        self._save_state(state)
        return state

    def _stage_model(self, name: str) -> str:
        if name == "claim_extraction":
            from claim_extraction import DEFAULT_EXTRACTION_MODEL

            return DEFAULT_EXTRACTION_MODEL
        return self.model

    def _stage_cost(self, cb, stage_name: str = ""):
        """(prompt_tokens, completion_tokens, usd) of a stage, priced by the stage's model."""
        if cb is None:
            return None
        pt = int(getattr(cb, "prompt_tokens", 0) or 0)
        ct = int(getattr(cb, "completion_tokens", 0) or 0)
        usd = float(getattr(cb, "total_cost", 0.0) or 0.0)
        if not usd and (pt or ct):
            usd = _price_usd(self._stage_model(stage_name), pt, ct)
        return pt, ct, round(usd, 4)

    def _write_summary(self, state):
        """Write {id}_timing.json and log time and cost per stage."""
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
        logger.info(f"pipeline summary {self.submission_id}: {_fmt_dur(total_s)}, ${total_usd:.4f}")
        for n, _, _ in STAGES:
            m = metrics.get(n, {})
            logger.info(f"  {n:<22}{_fmt_dur(m.get('seconds')):>10}  ${m.get('usd') or 0:.4f}")

    def run(self):
        """Run stages until a checkpoint awaits approval or all stages are done."""
        state = self._load_state()
        if self.pdf_path and not state.get("pdf_path"):
            state["pdf_path"] = self.pdf_path
        state["status"] = "running"
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
                    state["metrics"][name] = {
                        "seconds": round(time.time() - t0, 1),
                        "status": "failed",
                    }
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
                    metric["phases"] = phase_secs
                cost = self._stage_cost(cb, name)
                if cost is not None:
                    pt, ct, usd = cost
                    metric.update({"prompt_tokens": pt, "completion_tokens": ct, "usd": usd})
                state["metrics"][name] = metric
                state["current_stage"] = None
                self._save_state(state)
                logger.info(f"[{self.submission_id}] stage '{name}' done in {_fmt_dur(seconds)}")
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
                    logger.info(
                        f"[{self.submission_id}] paused for reviewer at checkpoint '{checkpoint}'"
                    )
                    return state
                state["checkpoints"][checkpoint] = "approved"
                self._save_state(state)

        state["status"] = "completed"
        state["current_stage"] = None
        self._save_state(state)
        self._write_summary(state)
        logger.info(f"[{self.submission_id}] pipeline completed")
        return state


def main():
    ap = argparse.ArgumentParser(description="Pipeline up to the comparison")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--pdf", default=None, help="submission PDF (required on first run)")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--grobid-server", default="http://localhost:8070")
    ap.add_argument("--no-hitl", action="store_true", help="approve both checkpoints automatically")
    ap.add_argument(
        "--approve", default=None, help="approve a checkpoint (claims|papers) then continue"
    )
    ap.add_argument("--status", action="store_true", help="print pipeline state and exit")
    args = ap.parse_args()

    pipe = NoveltyPipeline(
        args.data_dir,
        args.submission_id,
        pdf_path=args.pdf,
        model=args.model,
        grobid_server=args.grobid_server,
        hitl=not args.no_hitl,
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


if __name__ == "__main__":
    main()
