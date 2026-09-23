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

#: Which subdirectory of inputs/ and manifests/ this import writes to. The pilot's own
#: name is the default, so a call that does not set it behaves exactly as before; run()
#: sets it from the study config's `inputs_dir`. Without this the main study's import
#: would overwrite the pilot's frozen inputs, which are cited by already-collected
#: ratings and must not move.
_STUDY_DIR = "pilot"


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
    d = FE_ROOT / "inputs" / _STUDY_DIR / paper
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(paper: str, name: str, content: bytes) -> dict:
    p = _out_dir(paper) / name
    p.write_bytes(content)
    return {"path": str(p.relative_to(FE_ROOT)), "sha256": _sha256_bytes(content),
           "bytes": len(content)}


def _import_rendered(be, paper: str, system: str, spec: dict) -> dict:
    # A run that has not happened yet leaves no artifact. Report that as a blocker so the
    # manifest says which (paper, system) is still missing, instead of aborting the whole
    # import over the first one.
    if not spec.get("artifact_a"):
        return {"blocker": "no `artifact_a` in the source entry"}
    artifact_a = REPO_ROOT / spec["artifact_a"]
    if not artifact_a.is_file():
        return {"blocker": f"not run yet: {spec['artifact_a']} does not exist"}
    artifact_b = REPO_ROOT / (spec.get("artifact_b") or spec["artifact_a"])
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
    """A completed DeepReviewer job's own output, markdown or their native PDF.

    `file:` decides which: `final_report.md` is the review as text, `final_report.pdf`
    their rendered report. A `.pdf` is shown the same way OpenNovelty's is -- their
    layout and branding, no re-rendering by this repository.

    One thing to know before naming a PDF here: DeepReviewer's OWN `final_report.pdf`
    merges the review with the full annotated submission (measured: 47 pages over a
    34-page paper). `eval/deepreviewer_review_pdf.py` re-renders the same report through
    their builder with the merge skipped, writing `final_report_review_only.pdf` beside
    it; that is the file to name for a study where the submission is already shown
    separately and report length is a presentation variable.
    """
    # `job_dir` is left as a TODO in a generated sources file until the job has actually
    # been run, so an absent key means "not run yet" and belongs in the manifest.
    if not spec.get("job_dir"):
        return {"blocker": "no `job_dir` in the source entry -- DeepReviewer has not run "
                           "for this paper"}
    src = REPO_ROOT / spec["job_dir"] / spec["file"]
    if not src.is_file():
        return {"blocker": f"missing file: {spec['job_dir']}/{spec['file']}"}
    data = src.read_bytes()
    if src.suffix.lower() == ".pdf":
        f = _write(paper, f"{system}.pdf", data)
        return {"view_type": "pdf", "text_file": None, "content_file": f,
               "content_version": f"deepreviewer_native_pdf:{f['sha256'][:16]}",
               "provenance": {"kind": "deepreviewer_job", "job_dir": spec["job_dir"],
                              "file": spec["file"], "view": "native pdf",
                              "note": spec.get("resolution_note", "").strip()}}
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
    """The submission PDF, plus the frozen text the E1 judge reads.

    Both are recorded as blockers rather than raised when unresolved: a source the study
    has not settled yet (the main study's submission text comes from DeepReviewer's MinerU
    output, which does not exist until those jobs run) must show up in the manifest next to
    the others, not stop the remaining papers from importing at all.
    """
    out = {}
    pdf_rel = spec.get("pdf")
    if not pdf_rel:
        out["pdf_blocker"] = "no `pdf:` in the submission source entry"
    elif (REPO_ROOT / pdf_rel).is_file():
        out["pdf_file"] = _write(paper, "submission.pdf", (REPO_ROOT / pdf_rel).read_bytes())
    else:
        out["pdf_blocker"] = f"missing file: {pdf_rel}"

    text_rel = spec.get("text")
    if not text_rel:
        out["text_blocker"] = ("no `text:` in the submission source entry -- the E1 judge "
                               "input is unresolved for this paper")
    elif (REPO_ROOT / text_rel).is_file():
        out["text_file"] = _write(paper, "submission.txt", (REPO_ROOT / text_rel).read_bytes())
    else:
        out["text_blocker"] = f"missing file: {text_rel}"
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


def _import_deepreviewer_e1_text(paper: str, spec: dict) -> dict:
    """E1's text for a DeepReviewer report that E2 shows as a PDF.

    Unlike OpenNovelty's, this needs no extractor and carries no equivalence caveat: the
    PDF is rendered FROM `final_report.md` by their own builder, so the markdown is the
    report's source rather than a reading of its output. E1 and E2 therefore see the same
    content by construction -- `needs_manual_equivalence_check` is False for that reason,
    not as an assumption.
    """
    md = REPO_ROOT / spec["job_dir"] / "final_report.md"
    if not md.is_file():
        return {"blocker": f"missing E1 source: {spec['job_dir']}/final_report.md"}
    f = _write(paper, "deepreviewer.e1_text.md", md.read_bytes())
    return {"e1_text_file": f, "needs_manual_equivalence_check": False,
            "note": "source markdown of the rendered PDF, not an extraction from it"}


def run(sources_path: str, config_path: str = "final_evaluation/config/pilot.yaml") -> dict:
    global _STUDY_DIR
    sources = yaml.safe_load((REPO_ROOT / sources_path).read_text(encoding="utf-8"))
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    _STUDY_DIR = cfg.get("inputs_dir") or "pilot"
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
            # A report E2 shows as a PDF still needs text for E1.
            if kind == "native_pdf" and system == "opennovelty":
                result["e1"] = _import_opennovelty_e1_text(paper, spec)
            elif kind == "deepreviewer_job" and result.get("view_type") == "pdf":
                result["e1"] = _import_deepreviewer_e1_text(paper, spec)
            entry["systems"][system] = result
            if result.get("blocker"):
                manifest["blockers"].append(f"{paper}/{system}: {result['blocker']}")
        manifest["papers"][paper] = entry

    out_path = FE_ROOT / "manifests" / _STUDY_DIR / "reports.json"
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
    print(f"\nwritten: final_evaluation/manifests/{_STUDY_DIR}/reports.json")
