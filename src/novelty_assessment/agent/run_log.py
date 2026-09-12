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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _short(digest: str) -> str:
    return digest[:12]


def git_commit(repo_root: Path) -> dict:
    """The commit the run executed at, and whether the tree was modified.

    A commit alone is misleading in a working repository: most runs here happen on an
    edited tree, and reporting only the hash would claim a reproducibility the files do
    not have.
    """
    def run(*args) -> str:
        try:
            return subprocess.run(args, cwd=str(repo_root), capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    commit = run("git", "rev-parse", "HEAD")
    return {
        "commit": commit,
        "short": commit[:10],
        "branch": run("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(run("git", "status", "--porcelain")),
    }


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

        The id comes from the content, so it is stable across runs and cannot be
        reused by a different selection. The text itself is NOT stored: it is already
        on disk in its source documents, and copying it here would turn a provenance
        record into a second, diverging copy of the corpus.
        """
        digest = sha256_text(text or "")
        cid = f"{kind}:{_short(digest)}"
        if cid not in self.contexts:
            self.contexts[cid] = {
                "id": cid,
                "kind": kind,
                "sha256": digest,
                "chars": len(text or ""),
                **meta,
            }
        return cid

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

        self.outcome = {
            "claim_verdict": verdict,
            "stop_reason": stop_reason,
            "evidence_sufficient": evidence_sufficient,
            # Complete means every compared paper reached a verdict its own checks
            # accepted -- not merely that the loop stopped.
            "review_complete": not open_papers,
            "n_compared": len(comparisons or []),
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
            d = Path(self.data_dir) / self.submission_id / "run_logs"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{self.claim_id}_{self.run_id}.json"
            p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
            return p
        except Exception:
            return None
