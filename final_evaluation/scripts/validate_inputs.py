"""Check the imported pilot materials before they are ever seeded into a study.

What this checks (per PROTOCOL.md section 4): every file the manifest points at exists
and hashes match, all five systems are present per pilot paper, required PDF assets
exist, internal anchors resolve, and the E1 (text) / E2 (display) content pairing is at
least CONSISTENT -- for the four markdown systems E1 and E2 are literally the same file
(trivially equivalent); for OpenNovelty they are not the same artifact (E2 is the native
PDF with its taxonomy graphic, E1 is a text extraction of it), and this script does NOT
claim they are content-equivalent -- extracting text near a diagram is not evidence the
extracted text states the same relationships the diagram draws. It reports that pair as
`needs_manual_check` rather than `equivalent`, which is the honest answer a resolvable
link cannot substitute for.

Usage
-----
  python -m final_evaluation.cli validate-inputs --study dashboard_pilot_v1
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FE_ROOT = REPO_ROOT / "final_evaluation"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_file_entry(entry: dict | None, findings: list, where: str) -> None:
    if entry is None:
        return
    p = FE_ROOT / entry["path"]
    if not p.is_file():
        findings.append({"level": "error", "where": where, "msg": f"missing file: {entry['path']}"})
        return
    actual = _sha256_file(p)
    if actual != entry["sha256"]:
        findings.append({"level": "error", "where": where,
                         "msg": f"hash mismatch for {entry['path']}: manifest={entry['sha256']} "
                                f"actual={actual}"})


def _check_anchor_resolution(paper: str, system: str, text_path: Path, qidx_path: Path | None,
                             findings: list) -> dict:
    """For agent/linear: every '> "..."' blockquote in the rendered text should resolve
    against the quote index (same check performed manually when quote_index() was first
    built -- reproduced here as an automated gate)."""
    if qidx_path is None or not qidx_path.is_file():
        return {"resolvable": None, "total": None}
    text = text_path.read_text(encoding="utf-8")
    idx = json.loads(qidx_path.read_text(encoding="utf-8"))
    sub_texts = {q["text"] for q in idx.get("submission", [])}
    pap_texts = {q["text"] for p in idx.get("papers", {}).values() for q in p.get("quotes", [])}
    total = resolved = 0
    for ln in text.split("\n"):
        t = ln.strip()
        if t.startswith("> "):
            total += 1
            inner = " ".join(t[2:].strip().split())
            inner = re.sub(r'^[“"]', "", inner)
            inner = re.sub(r'[”"]$', "", inner)
            if inner in sub_texts or inner in pap_texts:
                resolved += 1
    if total and resolved / total < 0.8:
        findings.append({"level": "warning", "where": f"{paper}/{system}",
                         "msg": f"only {resolved}/{total} blockquotes resolve against the quote "
                                "index -- technical link resolution is not evidence of semantic "
                                "correctness, but this ratio is low enough to look manually."})
    return {"resolvable": resolved, "total": total}


def run(study: str, config_path: str = "final_evaluation/config/pilot.yaml") -> dict:
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    manifest_path = FE_ROOT / "manifests" / "pilot" / "reports.json"
    findings: list = []
    result = {"study": study, "papers": {}, "findings": findings}

    if not manifest_path.is_file():
        findings.append({"level": "error", "where": "manifest",
                         "msg": f"{manifest_path} not found -- run import-pilot first"})
        return result

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("blockers"):
        for b in manifest["blockers"]:
            findings.append({"level": "error", "where": "import", "msg": b})

    expected_systems = set(cfg["systems"])
    for paper in cfg["papers"]:
        entry = manifest.get("papers", {}).get(paper)
        pres = {"systems_present": [], "systems_missing": [], "anchors": {}, "e1_e2": {}}
        if entry is None:
            findings.append({"level": "error", "where": paper, "msg": "paper missing from manifest"})
            result["papers"][paper] = pres
            continue

        sub = entry.get("submission", {})
        _check_file_entry(sub.get("pdf_file"), findings, f"{paper}/submission")
        _check_file_entry(sub.get("text_file"), findings, f"{paper}/submission")
        if "pdf_file" not in sub:
            findings.append({"level": "error", "where": f"{paper}/submission",
                             "msg": "submission PDF not imported"})

        systems = entry.get("systems", {})
        for sys_id in sorted(expected_systems):
            r = systems.get(sys_id)
            if r is None or r.get("blocker"):
                pres["systems_missing"].append(sys_id)
                findings.append({"level": "error", "where": f"{paper}/{sys_id}",
                                 "msg": r.get("blocker", "not imported") if r else "not imported"})
                continue
            pres["systems_present"].append(sys_id)
            _check_file_entry(r.get("text_file"), findings, f"{paper}/{sys_id}")
            _check_file_entry(r.get("content_file"), findings, f"{paper}/{sys_id}")
            _check_file_entry(r.get("quote_index_file"), findings, f"{paper}/{sys_id}")

            if sys_id in ("agent", "linear") and r.get("text_file") and r.get("quote_index_file"):
                pres["anchors"][sys_id] = _check_anchor_resolution(
                    paper, sys_id, FE_ROOT / r["text_file"]["path"],
                    FE_ROOT / r["quote_index_file"]["path"], findings)

            if r["view_type"] == "markdown":
                pres["e1_e2"][sys_id] = "equivalent_same_file"
            elif sys_id == "opennovelty":
                e1 = r.get("e1", {})
                if e1.get("blocker"):
                    findings.append({"level": "error", "where": f"{paper}/{sys_id}",
                                     "msg": f"E1 text extraction failed: {e1['blocker']}"})
                    pres["e1_e2"][sys_id] = "e1_missing"
                else:
                    pres["e1_e2"][sys_id] = "needs_manual_check"
                    findings.append({"level": "warning", "where": f"{paper}/{sys_id}",
                                     "msg": "E1 text is a PDF text-extraction of the native report; "
                                            "NOT verified to state the same relationships as the "
                                            "taxonomy-tree graphic. Confirm manually before relying "
                                            "on E1 scores for this system."})
            else:
                pres["e1_e2"][sys_id] = "not_applicable"

        if len(pres["systems_present"]) < 5:
            findings.append({"level": "error", "where": paper,
                             "msg": f"only {len(pres['systems_present'])}/5 systems present"})
        result["papers"][paper] = pres

    n_errors = sum(1 for f in findings if f["level"] == "error")
    result["ok"] = n_errors == 0
    result["n_errors"] = n_errors
    result["n_warnings"] = sum(1 for f in findings if f["level"] == "warning")
    return result


def print_report(result: dict) -> None:
    for paper, pres in result["papers"].items():
        print(f"{paper}: {len(pres['systems_present'])}/5 systems "
             f"({', '.join(pres['systems_present'])})")
        if pres["systems_missing"]:
            print(f"  MISSING: {', '.join(pres['systems_missing'])}")
        for sys_id, a in pres.get("anchors", {}).items():
            print(f"  {sys_id} anchors: {a['resolvable']}/{a['total']} blockquotes resolve")
        for sys_id, status in pres.get("e1_e2", {}).items():
            print(f"  {sys_id} E1/E2: {status}")
    print(f"\n{result['n_errors']} error(s), {result['n_warnings']} warning(s)")
    for f in result["findings"]:
        print(f"  [{f['level'].upper()}] {f['where']}: {f['msg']}")
    print("\nVALID -- ready for init-db/seed-pilot" if result["ok"] else "\nNOT VALID -- fix errors above")
