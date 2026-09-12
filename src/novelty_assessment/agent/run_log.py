#!/usr/bin/env python3
"""What was configured, what text was actually sent, and how the run ended.

A review is only checkable if someone else can say which document, which excerpt of it
and which settings produced a given verdict. The ledger records what the agent DID --
sections read, degrees assigned, gates refused -- but not enough of what it was working
from: two runs with different models, a changed prompt, or a different slice of the
submission produce different verdicts and look identical in the export.

Three things are recorded here that the ledger cannot hold:

  configuration  the run's identity (id, commit, dirty tree), the model and reasoning
                 effort of each ROLE rather than one global model name, the feature
                 flags and budgets in force, the hashes of every prompt and schema that
                 shaped a call, and the cutoff prior work was measured against.

  contexts       every block of text handed to a model, registered once and referred to
                 afterwards by a short id. The id is derived from the text itself, so
                 the same selection in two runs carries the same id and a different
                 selection cannot borrow one. Hashing the whole source document instead
                 -- which is what the submission basis did -- cannot tell two different
                 selections OF that document apart, and the selection is the thing that
                 changed the answer.

  outcome        the claim's verdict together with what stayed open and why, keeping
                 apart the three ways a paper can fail to reach a verdict: it was
                 checked and passed, the budget ran out with a deficit still standing,
                 or something broke. Those read identically in the current export and
                 mean entirely different things to whoever is reading the review.
"""
from __future__ import annotations

import hashlib
import json
import os
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
    """The commit the run executed at, and the edits on top of it.

    A commit alone is misleading in a working repository: most runs here happen on an
    edited tree, so the hash names code that was not the code that ran. Recording only
    `dirty: true` states the problem without fixing it, so the uncommitted diff is saved
    beside the log and hashed -- two runs whose diff hashes match really did run the same
    source, committed or not.
    """
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
            save_diff_to.write_bytes(diff.encode("utf-8"))   # see _snapshot: no CRLF
            info["diff_path"] = save_diff_to.name
            info["diff_chars"] = len(diff)
        except Exception:
            pass
    return info


def prompt_hashes(module) -> dict:
    """{name: short sha256} for every prompt template in a module.

    Prompts are the part of the system most often edited between runs and the part
    least visible afterwards: a reworded gate changes verdicts while every recorded
    setting stays the same. Module-level upper-case strings are the convention this
    codebase already uses for them.
    """
    out = {}
    for name, value in vars(module).items():
        bare = name.lstrip("_")
        if not isinstance(value, str) or len(value) < 120:
            continue
        if bare and bare == bare.upper():          # PROMPT / _PAPER_COMPARE style names
            out[bare] = _short(sha256_text(value))
    return out


def schema_hashes(models: dict) -> dict:
    """{name: short sha256} over each pydantic schema's JSON form.

    The field descriptions in these schemas are instructions -- they are what the model
    is told a field means -- so a schema edit is a prompt edit and belongs in the same
    record.
    """
    out = {}
    for name, model in (models or {}).items():
        try:
            out[name] = _short(sha256_text(
                json.dumps(model.model_json_schema(), sort_keys=True)))
        except Exception:
            continue
    return out


class RunLog:
    """One claim run's provenance. Written beside the artifacts and attached to the entry."""

    def __init__(self, submission_id: str, claim_id: str, data_dir: str = "data"):
        self.run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.submission_id = submission_id
        self.claim_id = claim_id
        self.data_dir = data_dir
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.config: dict = {}
        self.contexts: dict = {}          # context_id -> descriptor (no text)
        self.submission_selection: dict = {}
        self.comparisons: dict = {}       # paper_id -> provenance
        self.outcome: dict = {}

    # ------------------------------ contexts ------------------------------ #

    def register_context(self, kind: str, text: str, **meta) -> str:
        """Record a block of text that will be sent to a model; return its id.

        The id comes from the content, so it is stable across runs and cannot be reused
        by a different selection. The text is written out beside the log as well: a hash
        proves two runs saw the same context but reconstructs nothing, and the selection
        cannot be rebuilt from the source documents either, because WHICH slice was taken
        is exactly what the record exists to preserve. Snapshots can be turned off with
        NOVELTY_RUNLOG_SNAPSHOTS=0 where the disk cost is not wanted (~250 KB a run).
        """
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
        """Write one context to disk; returns the path relative to the log directory."""
        if os.getenv("NOVELTY_RUNLOG_SNAPSHOTS", "1").strip().lower() in ("0", "false", "no"):
            return ""
        try:
            rel = Path("contexts") / self.run_id / f"{cid.replace(':', '_')}.txt"
            out = self._log_dir() / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            # Bytes, not write_text: on Windows the text writer turns every \n into
            # \r\n, and the file then hashes to something other than the sha256 recorded
            # beside it -- the snapshot would be unverifiable exactly where it matters.
            out.write_bytes((text or "").encode("utf-8"))
            return rel.as_posix()
        except Exception:
            return ""

    def _log_dir(self) -> Path:
        return Path(self.data_dir) / self.submission_id / "run_logs"

    # ---------------------------- comparisons ----------------------------- #

    def paper_source(self, paper_id: str, pool_entry: dict) -> None:
        """Which DOCUMENT of this paper the comparison is about.

        Pulled from the pool entry the version pinning filled in, so the answer sits on
        the comparison rather than only in versions.json, where nothing links it to the
        verdict it produced.
        """
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
            # None, not True, when nothing said: "the history was complete" is a finding
            # and must not be the value a missing field decays into.
            "history_complete": p.get("history_complete", None),
            "missing_versions": p.get("missing_versions", []),
            "parsed_text_path": p.get("parsed_text_path", ""),
            "parsed_text_sha256": p.get("parsed_text_sha256", ""),
        })

    def paper_outcome(self, paper_id: str, comp: dict, pool_entry: dict = None,
                      sections_used: list = None,
                      fulltext_fetch_status: str = "") -> None:
        """Everything already recorded about one paper, exported unshortened.

        The reasoning was never missing -- the loop writes a turn-by-turn trace and the
        checker returns its own verdict with the pairs it relied on -- but only the last
        conflict survived into the export, so a reader could see THAT a paper ended in
        disagreement and not which evidence caused it or what the second pass changed.
        Nothing here is new information; it is the existing trace and the existing
        verdicts, carried through instead of collapsed.
        """
        c = comp or {}
        diag = c.get("map_diag") or {}
        prov = self.comparisons.setdefault(paper_id, {"paper_id": paper_id})
        if pool_entry:
            self.paper_source(paper_id, pool_entry)

        # How this paper ended, as one of four states rather than as several flags a
        # reader has to combine.
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
            # The semantic proposal BEFORE the evidence map saw it: the pair of values is
            # what shows whether grounding changed the reading or only confirmed it.
            "comparison_proposal": c.get("comparison_proposal") or {},
            "evidence_check": c.get("evidence_check") or {},
            "evidence_pairs": c.get("evidence_pairs") or [],
            "map_diag": {k: v for k, v in diag.items() if k != "loop"},
            "unresolved_deficit": c.get("unresolved_deficit", ""),
            "unresolved_reason": c.get("unresolved_reason", ""),
            # No "paper_state" beside final_state: one field, one name. The loop's own
            # value ("unresolved_budget") already feeds the state above.
            "sections_used": list(sections_used or c.get("sections_used") or []),
            "fulltext_fetch_status": (fulltext_fetch_status
                                      or c.get("fulltext_fetch_status", "")),
            # The loop's own turn-by-turn record, complete and unshortened: proposed vs
            # executed action, why each read was asked for, the degree each round
            # proposed, what the checker said, and the re-entry reason.
            "decision_trace": list(diag.get("loop") or []),
        })

    def round_contexts(self, paper_id: str, turn: int, **context_ids) -> None:
        """Which context ids a given call in a given round actually received.

        "Sections read" says what was available; this says what went into the prompt.
        They differ whenever a re-entry adds sections between two comparisons, and the
        difference is exactly what explains two different degrees for one paper.
        """
        rounds = self.comparisons.setdefault(paper_id, {}).setdefault("rounds", [])
        rounds.append({"turn": turn, **{k: v for k, v in context_ids.items() if v}})

    # ------------------------------ outcome ------------------------------- #

    def finish(self, verdict: str, comparisons: list, stop_reason: str = "",
               evidence_sufficient: Optional[bool] = None) -> dict:
        """The claim's result, and what was left unsettled.

        `open_papers` separates the three endings deliberately. A paper whose budget ran
        out with a deficit standing, one whose version could never be pinned, and one
        that simply found no overlap all end without a usable comparison, and the export
        renders them alike -- which lets "nothing was found" stand in for "we stopped
        looking".
        """
        open_papers, seen = [], set()
        for c in comparisons or []:
            pid = c.get("paper_id")
            # A failed map call is a technical error even when the loop also marked the
            # paper unresolved: reporting it as "budget" would send a reader looking for
            # a budget to raise.
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
        # Papers that never reached a comparison at all because no admissible version of
        # them could be established. They are absent from `comparisons` entirely, so a
        # count taken from that list alone reports them as though they had been examined.
        for pid, prov in self.comparisons.items():
            status = prov.get("version_status")
            if pid in seen or not status or status in ("pinned", "single"):
                continue
            open_papers.append({
                "paper_id": pid, "title": prov.get("title", ""),
                "state": "not_admissible", "reason": f"version {status}",
            })

        # Every counted paper must be findable here by id and final state. n_compared
        # counted the ledger while prior_work only held papers that reached a comparison
        # call, so a paper dismissed before one was counted and then absent -- the two
        # numbers disagreed with no way to see which paper the difference was.
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
            # Complete means every compared paper reached a verdict its own checks
            # accepted -- not merely that the loop stopped.
            "review_complete": not open_papers,
            "n_compared": len(comparisons or []),
            "n_papers_recorded": len(self.comparisons),
            "papers_by_state": by_state,
            "open_papers": open_papers,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return self.outcome

    # ------------------------------- output ------------------------------- #

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
        """Pack log + every referenced snapshot + the uncommitted diff into one zip.

        A snapshot_path the reader cannot open proves nothing: the hash can be checked
        against the text only when both travel together. One file is what gets handed on,
        so the bundle is what has to be self-contained.
        """
        if os.getenv("NOVELTY_RUNLOG_BUNDLE", "1").strip().lower() in ("0", "false", "no"):
            return None
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
