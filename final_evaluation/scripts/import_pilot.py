"""Materialise the pilot's frozen inputs from config/sources.pilot.yaml.

Reads ONLY that file (plus config/pilot.yaml for the task/system list) -- never globs
comparison/outputs/ itself, so an untracked draft appearing there later cannot silently
change what a re-import produces. See sources.pilot.yaml's own header for how each
(paper, system) source was resolved, including the one ambiguous case.

For `kind: rendered` entries (agent, linear) this CALLS `battle_export.build()` /
`battle_export.quote_index()` from the main pipeline, live, at import time. That is
rendering an already-computed, already-frozen review to text -- zero model calls, the
same deterministic function this repository already uses for its own comparison export
-- not a new review and not "erneute Reportgenerierung" in the sense the brief rules out.

Writes to `final_evaluation/inputs/pilot/<paper>/` and
`final_evaluation/manifests/pilot/reports.json`. Idempotent: re-running overwrites the
frozen files and the manifest with the SAME deterministic content (the artifact JSON and
battle_export.py are the only two things a re-render can pick up; if either has changed,
that is the intended trigger to refresh with a bumped content_version, not a bug).

Usage
-----
  python -m final_evaluation.cli import-pilot --sources final_evaluation/config/sources.pilot.yaml
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FE_ROOT = REPO_ROOT / "final_evaluation"
SRC_NOVELTY = REPO_ROOT / "src" / "novelty_assessment"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return _sha256_bytes(p.read_bytes())


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _load_battle_export():
    if str(SRC_NOVELTY) not in sys.path:
        sys.path.insert(0, str(SRC_NOVELTY))
    import battle_export  # noqa
    return battle_export


def _out_dir(paper: str) -> Path:
    d = FE_ROOT / "inputs" / "pilot" / paper
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(paper: str, name: str, content: bytes) -> dict:
    p = _out_dir(paper) / name
    p.write_bytes(content)
    return {"path": str(p.relative_to(FE_ROOT)), "sha256": _sha256_bytes(content),
           "bytes": len(content)}


def _import_rendered(be, paper: str, system: str, spec: dict) -> dict:
    artifact_a = REPO_ROOT / spec["artifact_a"]
    artifact_b = REPO_ROOT / spec["artifact_b"]
    variant = spec["variant"]
    text = be.build(str(REPO_ROOT / "data"), paper, variant=variant)
    qidx = be.quote_index(str(REPO_ROOT / "data"), paper, variant=variant)

    text_file = _write(paper, f"{system}.md", text.encode("utf-8"))
    qidx_file = _write(paper, f"{system}.quote_index.json",
                       json.dumps(qidx, ensure_ascii=False, indent=1).encode("utf-8"))
    be_script_sha = _sha256_file(Path(be.__file__))
    content_version = (f"battle_export:{be_script_sha[:12]}"
                      f"+a:{_sha256_file(artifact_a)[:12]}"
                      f"+b:{(_sha256_file(artifact_b)[:12] if artifact_b.is_file() else 'missing')}")
    return {
        "view_type": "markdown", "text_file": text_file, "quote_index_file": qidx_file,
        "content_version": content_version,
        "provenance": {
            "kind": "rendered", "renderer": "battle_export.build+quote_index",
            "renderer_sha256": be_script_sha, "renderer_source": "src/novelty_assessment/battle_export.py",
            "artifact_a_path": spec["artifact_a"], "artifact_a_sha256": _sha256_file(artifact_a),
            "artifact_b_path": spec["artifact_b"],
            "artifact_b_sha256": _sha256_file(artifact_b) if artifact_b.is_file() else None,
            "note": spec.get("resolution_note", "").strip(),
        },
    }


def _import_native_pdf(paper: str, system: str, spec: dict) -> dict:
    src = REPO_ROOT / spec["path"]
    if not src.is_file():
        return {"blocker": f"missing file: {spec['path']}"}
    data = src.read_bytes()
    f = _write(paper, f"{system}.pdf", data)
    return {"view_type": "pdf", "text_file": None, "content_file": f,
           "content_version": f"native_pdf:{f['sha256'][:16]}",
           "provenance": {"kind": "native_pdf", "source_path": spec["path"],
                          "note": spec.get("resolution_note", "").strip()}}


def _import_deepreviewer(paper: str, system: str, spec: dict) -> dict:
    src = REPO_ROOT / spec["job_dir"] / spec["file"]
    if not src.is_file():
        return {"blocker": f"missing file: {spec['job_dir']}/{spec['file']}"}
    data = src.read_bytes()
    f = _write(paper, f"{system}.md", data)
    return {"view_type": "markdown", "text_file": f,
           "content_version": f"deepreviewer_native:{f['sha256'][:16]}",
           "provenance": {"kind": "deepreviewer_job", "job_dir": spec["job_dir"], "file": spec["file"],
                          "note": spec.get("resolution_note", "").strip()}}


def _import_concat_text(paper: str, system: str, spec: dict) -> dict:
    parts_text = []
    missing = []
    hashes = []
    for part in spec["parts"]:
        if part == "---":
            parts_text.append("---")
            continue
        p = REPO_ROOT / part
        if not p.is_file():
            missing.append(part)
            continue
        t = p.read_text(encoding="utf-8").strip()
        parts_text.append(t)
        hashes.append({"path": part, "sha256": _sha256_file(p)})
    if missing:
        return {"blocker": f"missing file(s): {', '.join(missing)}"}
    joined = ("\n\n".join(parts_text)).strip() + "\n"
    f = _write(paper, f"{system}.md", joined.encode("utf-8"))
    return {"view_type": "markdown", "text_file": f,
           "content_version": f"concat_text:{f['sha256'][:16]}",
           "provenance": {"kind": "concat_text", "part_hashes": hashes,
                          "note": spec.get("resolution_note", "").strip()}}


def _import_submission(paper: str, spec: dict) -> dict:
    out = {}
    pdf_src = REPO_ROOT / spec["pdf"]
    if pdf_src.is_file():
        out["pdf_file"] = _write(paper, "submission.pdf", pdf_src.read_bytes())
    else:
        out["pdf_blocker"] = f"missing file: {spec['pdf']}"
    text_src = REPO_ROOT / spec["text"]
    if text_src.is_file():
        out["text_file"] = _write(paper, "submission.txt", text_src.read_bytes())
    else:
        out["text_blocker"] = f"missing file: {spec['text']}"
    return out


def _import_opennovelty_e1_text(paper: str, pdf_spec: dict) -> dict:
    """A TEXT rendering of the OpenNovelty PDF for E1, using the SAME extractor already
    used (and validated) for the transducing report earlier in this project --
    eval/pdf_to_md.py, font-size heading inference, nothing summarised or reordered.
    Explicitly NOT claimed content-equivalent to the native PDF/graphic without a manual
    check -- see validate_inputs.py's e1_e2 check, which flags this pair for review
    rather than asserting equivalence.
    """
    pdf_path = REPO_ROOT / pdf_spec["path"]
    if not pdf_path.is_file():
        return {"blocker": f"missing file: {pdf_spec['path']}"}
    sys.path.insert(0, str(REPO_ROOT / "eval"))
    import importlib
    pdf_to_md = importlib.import_module("pdf_to_md")
    text = pdf_to_md.convert(str(pdf_path)) if hasattr(pdf_to_md, "convert") else None
    if text is None:
        # Fall back to invoking it as a script into a temp file, matching how it was
        # run earlier in this project (eval/pdf_to_md.py --pdf ... --out ...).
        tmp_out = _out_dir(paper) / "_opennovelty_e1_tmp.md"
        r = subprocess.run([sys.executable, str(REPO_ROOT / "eval" / "pdf_to_md.py"),
                            "--pdf", str(pdf_path), "--out", str(tmp_out)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not tmp_out.is_file():
            return {"blocker": f"eval/pdf_to_md.py failed: {r.stderr[-400:]}"}
        text = tmp_out.read_text(encoding="utf-8")
        tmp_out.unlink(missing_ok=True)
    f = _write(paper, "opennovelty.e1_text.md", text.encode("utf-8"))
    return {"e1_text_file": f, "needs_manual_equivalence_check": True}


def run(sources_path: str, config_path: str = "final_evaluation/config/pilot.yaml") -> dict:
    sources = yaml.safe_load((REPO_ROOT / sources_path).read_text(encoding="utf-8"))
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    be = _load_battle_export()

    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_head": _git_head(),
               "papers": {}, "blockers": []}

    for paper in cfg["papers"]:
        psrc = sources[paper]
        entry = {"submission": _import_submission(paper, psrc["submission"]), "systems": {}}
        for system in cfg["systems"]:
            spec = psrc.get(system)
            if spec is None:
                entry["blockers" ] = entry.get("blockers", [])
                manifest["blockers"].append(f"{paper}/{system}: no entry in sources.pilot.yaml")
                continue
            kind = spec["kind"]
            if kind == "rendered":
                result = _import_rendered(be, paper, system, spec)
            elif kind == "native_pdf":
                result = _import_native_pdf(paper, system, spec)
            elif kind == "deepreviewer_job":
                result = _import_deepreviewer(paper, system, spec)
            elif kind == "concat_text":
                result = _import_concat_text(paper, system, spec)
            else:
                result = {"blocker": f"unknown source kind: {kind}"}
            if kind == "native_pdf" and system == "opennovelty":
                result["e1"] = _import_opennovelty_e1_text(paper, spec)
            entry["systems"][system] = result
            if result.get("blocker"):
                manifest["blockers"].append(f"{paper}/{system}: {result['blocker']}")
        manifest["papers"][paper] = entry

    out_path = FE_ROOT / "manifests" / "pilot" / "reports.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def print_report(manifest: dict) -> None:
    print(f"git HEAD: {manifest['git_head']}")
    for paper, entry in manifest["papers"].items():
        print(f"\n{paper}:")
        sub = entry["submission"]
        print(f"  submission: pdf={'ok' if 'pdf_file' in sub else 'BLOCKED: ' + sub.get('pdf_blocker','')}"
             f", text={'ok' if 'text_file' in sub else 'BLOCKED: ' + sub.get('text_blocker','')}")
        for system, r in entry["systems"].items():
            if r.get("blocker"):
                print(f"  {system}: BLOCKED -- {r['blocker']}")
            else:
                print(f"  {system}: ok ({r['view_type']}, content_version={r['content_version']})")
    if manifest["blockers"]:
        print(f"\n{len(manifest['blockers'])} BLOCKER(S):")
        for b in manifest["blockers"]:
            print(f"  - {b}")
    else:
        print("\nNo blockers.")
    print(f"\nwritten: final_evaluation/manifests/pilot/reports.json")
