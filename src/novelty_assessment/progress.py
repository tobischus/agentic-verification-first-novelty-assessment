#!/usr/bin/env python3
"""
Tiny file-based sub-progress reporter for the two long pipeline stages
(retrieval, artifact_a). A stage reports its phase + done/total so the frontend
can show a real progress bar and extrapolate the remaining time from the rate so
far (e.g. "reference 30/62", "claim 2/4").

The orchestrator points it at {id}_progress.json before a stage and clears it
after; the API merges that file into /state as `state["progress"]`. Every call is
a best-effort no-op when not configured (e.g. a stage module run standalone), so
instrumenting Afzal's code with optional `import progress` never breaks it.
"""
import json
import os
import time
from pathlib import Path

_CTX = {"path": None, "phase": None, "started": 0.0, "last": 0.0, "phases": {}}
_MIN_INTERVAL = 0.4  # min seconds between disk writes (forced writes bypass this)


def configure(progress_path):
    """Point the reporter at a file (or None to disable). Resets phase timing."""
    _CTX.update(path=Path(progress_path) if progress_path else None,
                phase=None, started=0.0, last=0.0, phases={})


def _finalize_current():
    """Accumulate the elapsed time of the current phase into the breakdown."""
    phase, started = _CTX.get("phase"), _CTX.get("started")
    if phase and started:
        _CTX["phases"][phase] = _CTX["phases"].get(phase, 0.0) + (time.time() - started)


def start_phase(phase, total, indeterminate=False):
    """Begin a phase; resets the per-phase clock the ETA is extrapolated from."""
    _finalize_current()
    _CTX["phase"] = phase
    _CTX["started"] = time.time()
    _write(phase, 0, total, indeterminate, force=True)


def durations():
    """Finalize and return {phase: seconds} measured since the last configure()."""
    _finalize_current()
    _CTX["started"] = time.time()  # avoid double-counting if called again
    return {k: round(v, 1) for k, v in _CTX["phases"].items()}


def report(done, total, phase=None, indeterminate=False):
    _write(phase or _CTX.get("phase"), done, total, indeterminate,
           force=bool(total) and done >= total)


def clear():
    p = _CTX.get("path")
    if not p:
        return
    try:
        Path(p).unlink(missing_ok=True)
    except Exception:
        pass


def _write(phase, done, total, indeterminate, force):
    p = _CTX.get("path")
    if not p:
        return
    now = time.time()
    if not force and now - _CTX["last"] < _MIN_INTERVAL:
        return
    _CTX["last"] = now
    payload = {
        "phase": phase,
        "done": int(done or 0),
        "total": int(total or 0),
        "indeterminate": bool(indeterminate),
        "started_epoch": _CTX.get("started") or now,
        "updated_epoch": now,
    }
    # Atomic write: a reader (the /state poll) must never see a half-written file.
    # Write to a temp file in the same dir, then os.replace (atomic on Win + POSIX).
    try:
        p = Path(p)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, p)
    except Exception:
        pass
