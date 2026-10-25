"""Run log of one claim run (Section 4.10).

Records the configuration (code version, models, budgets, prompt and schema hashes), every
text sent to a model as a hashed context snapshot, the provenance and decision trace of
each prior paper, and the outcome of the claim.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _short(digest: str) -> str:
    return digest[:12]


def git_commit(repo_root: Path, save_diff_to: Optional[Path] = None) -> dict:
    """Current commit, and for a modified working tree the saved and hashed diff."""
    def run(*args) -> str:
        try:
            return subprocess.run(args, cwd=str(repo_root), capture_output=True,
                                  text=True, timeout=20).stdout
        except Exception:
            return ""
    commit = run("git", "rev-parse", "HEAD").strip()
    status = run("git", "status", "--porcelain").strip()
    info = {
        "commit": commit,
        "short": commit[:10],
        "branch": run("git", "rev-parse", "--abbrev-ref", "HEAD").strip(),
        "dirty": bool(status),
    }
    if not status:
        return info
    diff = run("git", "diff", "HEAD")
    info["dirty_files"] = [ln[3:] for ln in status.splitlines() if ln[3:]]
    info["diff_sha256"] = sha256_text(diff)
    if save_diff_to is not None and diff:
        try:
            save_diff_to.parent.mkdir(parents=True, exist_ok=True)
            save_diff_to.write_bytes(diff.encode("utf-8"))
            info["diff_path"] = save_diff_to.name
            info["diff_chars"] = len(diff)
        except Exception:
            pass
    return info


def prompt_hashes(module) -> dict:
    """Short hashes of the module-level upper-case strings of at least 120 characters."""
    out = {}
    for name, value in vars(module).items():
        bare = name.lstrip("_")
        if not isinstance(value, str) or len(value) < 120:
            continue
        if bare and bare == bare.upper():
            out[bare] = _short(sha256_text(value))
    return out


def schema_hashes(models: dict) -> dict:
    """Short hashes of the JSON schemas, whose field descriptions are part of the prompt."""
    out = {}
    for name, model in (models or {}).items():
        try:
            out[name] = _short(sha256_text(
                json.dumps(model.model_json_schema(), sort_keys=True)))
        except Exception:
            continue
    return out


class RunLog:
    def __init__(self, submission_id: str, claim_id: str, data_dir: str = "data"):
        self.run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.submission_id = submission_id
        self.claim_id = claim_id
        self.data_dir = data_dir
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.config: dict = {}
        self.contexts: dict = {}
        self.submission_selection: dict = {}
        self.comparisons: dict = {}
        self.outcome: dict = {}

    def register_context(self, kind: str, text: str, **meta) -> str:
        """Record a text sent to a model and save a snapshot; returns its content-based id."""
        digest = sha256_text(text or "")
        cid = f"{kind}:{_short(digest)}"
        if cid not in self.contexts:
            entry = {
                "id": cid,
                "kind": kind,
                "sha256": digest,
                "chars": len(text or ""),
                **meta,
            }
            path = self._snapshot(cid, text)
            if path:
                entry["snapshot_path"] = path
            self.contexts[cid] = entry
        return cid

    def _snapshot(self, cid: str, text: str) -> str:
        try:
            rel = Path("contexts") / self.run_id / f"{cid.replace(':', '_')}.txt"
            out = self._log_dir() / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            # Bytes, so the file hashes to the recorded sha256 on every platform.
            out.write_bytes((text or "").encode("utf-8"))
            return rel.as_posix()
        except Exception:
            return ""

    def _log_dir(self) -> Path:
        return Path(self.data_dir) / self.submission_id / "run_logs"

    def paper_source(self, paper_id: str, pool_entry: dict) -> None:
        """The pinned version and parsed text a comparison is based on."""
        p = pool_entry or {}
        self.comparisons.setdefault(paper_id, {}).update({
            "paper_id": paper_id,
            "title": p.get("title", ""),
            "version_status": p.get("version_status", ""),
            "pinned_version": p.get("pinned_version", ""),
            "pinned_version_date": p.get("pinned_version_date", ""),
            "pinned_url": p.get("pinned_url", ""),
            "pdf_sha256": p.get("doc_sha256", ""),
            "abstract_source": p.get("abstract_source", ""),
            "history_complete": p.get("history_complete", None),
            "missing_versions": p.get("missing_versions", []),
            "parsed_text_path": p.get("parsed_text_path", ""),
            "parsed_text_sha256": p.get("parsed_text_sha256", ""),
        })

    def paper_outcome(self, paper_id: str, comp: dict, pool_entry: dict = None,
                      sections_used: list = None,
                      fulltext_fetch_status: str = "") -> None:
        """Final state, comparison, evidence and decision trace of one paper."""
        c = comp or {}
        diag = c.get("map_diag") or {}
        prov = self.comparisons.setdefault(paper_id, {"paper_id": paper_id})
        if pool_entry:
            self.paper_source(paper_id, pool_entry)

        if diag.get("call_failed"):
            state = "technical_error"
        elif c.get("unresolved") or c.get("insufficient"):
            state = "budget_exhausted"
        elif c.get("dismissed") or (c.get("map_diag") or {}).get("dismissed"):
            state = "dismissed"
        elif c.get("overlap_degree"):
            state = "checked"
        else:
            state = "not_compared"

        prov.update({
            "final_state": state,
            "final_comparison": {
                "overlap_degree": c.get("overlap_degree", ""),
                "refutation_status": c.get("refutation_status", ""),
                "assessment": c.get("assessment", ""),
                "what_is_shared": c.get("what_is_shared", ""),
                "submission_delta": c.get("submission_delta", ""),
                "brief_note": c.get("brief_note", ""),
            },
            "comparison_proposal": c.get("comparison_proposal") or {},
            "evidence_check": c.get("evidence_check") or {},
            "evidence_pairs": c.get("evidence_pairs") or [],
            "map_diag": {k: v for k, v in diag.items() if k != "loop"},
            "unresolved_deficit": c.get("unresolved_deficit", ""),
            "unresolved_reason": c.get("unresolved_reason", ""),
            "sections_used": list(sections_used or c.get("sections_used") or []),
            "fulltext_fetch_status": (fulltext_fetch_status
                                      or c.get("fulltext_fetch_status", "")),
            "decision_trace": list(diag.get("loop") or []),
        })

    def round_contexts(self, paper_id: str, turn: int, **context_ids) -> None:
        """The context ids a call in a given round received."""
        rounds = self.comparisons.setdefault(paper_id, {}).setdefault("rounds", [])
        rounds.append({"turn": turn, **{k: v for k, v in context_ids.items() if v}})

    def finish(self, verdict: str, comparisons: list, stop_reason: str = "",
               evidence_sufficient: Optional[bool] = None) -> dict:
        """Claim outcome with the papers that remained open and why."""
        open_papers, seen = [], set()
        for c in comparisons or []:
            pid = c.get("paper_id")
            if (c.get("map_diag") or {}).get("call_failed"):
                state, reason = "technical_error", "the evidence map call did not complete"
            elif c.get("unresolved") or c.get("insufficient"):
                state = "budget_exhausted"
                reason = (c.get("unresolved_deficit", "")
                          or c.get("unresolved_reason", "")
                          or c.get("paper_state", ""))
            else:
                continue
            seen.add(pid)
            open_papers.append({
                "paper_id": pid, "title": c.get("title", ""),
                "state": state, "reason": reason,
                "semantic_degree": c.get("overlap_degree", ""),
            })
        for pid, prov in self.comparisons.items():
            status = prov.get("version_status")
            if pid in seen or not status or status in ("pinned", "single"):
                continue
            open_papers.append({
                "paper_id": pid, "title": prov.get("title", ""),
                "state": "not_admissible", "reason": f"version {status}",
            })

        for c in comparisons or []:
            pid = c.get("paper_id")
            if pid and pid not in self.comparisons:
                self.paper_outcome(pid, c)
        by_state = {}
        for prov in self.comparisons.values():
            st = prov.get("final_state") or "not_compared"
            by_state[st] = by_state.get(st, 0) + 1

        self.outcome = {
            "claim_verdict": verdict,
            "stop_reason": stop_reason,
            "evidence_sufficient": evidence_sufficient,
            "review_complete": not open_papers,
            "n_compared": len(comparisons or []),
            "n_papers_recorded": len(self.comparisons),
            "papers_by_state": by_state,
            "open_papers": open_papers,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return self.outcome

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "submission_id": self.submission_id,
            "claim_id": self.claim_id,
            "started_at": self.started_at,
            "config": self.config,
            "submission_selection": self.submission_selection,
            "contexts": list(self.contexts.values()),
            "prior_work": list(self.comparisons.values()),
            "outcome": self.outcome,
        }

    def write(self) -> Optional[Path]:
        try:
            d = self._log_dir()
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{self.claim_id}_{self.run_id}.json"
            self.outcome["bundle"] = f"{p.stem}.zip"
            p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
            self._bundle(p)
            return p
        except Exception:
            return None

    def _bundle(self, log_path: Path) -> Optional[Path]:
        """Zip the log with its context snapshots and the saved diff."""
        try:
            d = self._log_dir()
            zpath = log_path.with_suffix(".zip")
            diff_name = ((self.config.get("git") or {}).get("diff_path") or "")
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(log_path, log_path.name)
                if diff_name and (d / diff_name).exists():
                    z.write(d / diff_name, diff_name)
                for c in self.contexts.values():
                    rel = c.get("snapshot_path") or ""
                    src = d / rel
                    if rel and src.exists():
                        z.write(src, rel)
            return zpath
        except Exception:
            return None
