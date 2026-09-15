"""Read-only scan of the repository for existing pilot materials. Changes nothing.

Prints what it finds per paper x system, and -- this is the point of running it BEFORE
writing config/sources.pilot.yaml by hand -- calls out every case where more than one
candidate file exists for the same (paper, system) with no recorded way to tell which one
is bound to which run. Those go in the report as AMBIGUOUS, not as a silently-picked
"newest by mtime" choice; config/sources.pilot.yaml then has to name, for each such case,
either a specific resolved path with its provenance, or record the paper x system as a
blocker for validate-inputs to also report.

Usage
-----
  python -m final_evaluation.cli inventory --config final_evaluation/config/pilot.yaml
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fmt(p: Path) -> dict:
    st = p.stat()
    return {"path": str(p.relative_to(REPO_ROOT)), "bytes": st.st_size,
           "mtime": st.st_mtime, "sha256": _sha256(p)[:16]}


def scan_comparison_outputs(paper_keys: list[str]) -> dict:
    out_dir = REPO_ROOT / "comparison" / "outputs"
    found: dict[str, dict[str, list]] = {p: {} for p in paper_keys}
    if not out_dir.is_dir():
        return found
    for f in sorted(out_dir.glob("*.md")):
        if f.name == "PROVENANCE.md":
            continue
        m = re.match(r"^(.+?)__([a-z0-9_]+)\.md$", f.name)
        if not m:
            continue
        paper, system = m.group(1), m.group(2)
        # normalise "agent_v2"/"agent_v3"/... to the base system id "agent", flagged
        base_system = re.sub(r"_v\d+$", "", system)
        if paper not in found:
            continue
        found[paper].setdefault(base_system, []).append(_fmt(f))
    return found


def scan_data_dirs(paper_keys: list[str]) -> dict:
    data_dir = REPO_ROOT / "data"
    out = {}
    for paper in paper_keys:
        d = data_dir / paper
        entry = {"exists": d.is_dir()}
        if d.is_dir():
            entry["pdf"] = (d / f"{paper}.pdf").is_file()
            entry["artifact_a_agent"] = (d / f"{paper}_artifact_a_agent.json").is_file()
            entry["artifact_b_agent"] = (d / f"{paper}_artifact_b_agent.json").is_file()
            entry["artifact_a_linear"] = (d / f"{paper}_artifact_a_linear.json").is_file()
            entry["artifact_b_linear"] = (d / f"{paper}_artifact_b_linear.json").is_file()
            entry["summary_txt"] = (d / "summary.txt").is_file()
            entry["novelty_delta_analysis_txt"] = (d / "novelty_delta_analysis.txt").is_file()
        out[paper] = entry
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def scan_deepreviewer_jobs(paper_titles: dict[str, str]) -> dict:
    """paper_titles: {paper_key: full title}. DeepReviewer's `job.json.title` is the
    UPLOAD FILENAME's stem, truncated to ~30 chars, and often prefixed with an arXiv-ish
    numeric id ("15574_When_to_use_Graphs_in_RA") -- not the paper's real title. Matched
    by stripping a leading digit run, slugifying both sides, and checking the (short,
    truncated) job title is a prefix of the (full) configured title's slug."""
    root = REPO_ROOT / "DeepReviewer-v2" / "data" / "jobs"
    out = {p: [] for p in paper_titles}
    if not root.is_dir():
        return out
    for job_dir in sorted(root.iterdir()):
        job_json = job_dir / "job.json"
        if not job_json.is_file():
            continue
        try:
            meta = json.loads(job_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        title = (meta.get("title") or "").strip()
        job_slug = _slug(re.sub(r"^\d+_?", "", title))
        for paper, needle in paper_titles.items():
            paper_slug = _slug(needle)
            is_match = len(job_slug) >= 12 and paper_slug.startswith(job_slug)
            if is_match and meta.get("status") == "completed":
                report_md = job_dir / "final_report.md"
                out[paper].append({
                    "job_dir": str(job_dir.relative_to(REPO_ROOT)),
                    "title": title, "has_final_report_md": report_md.is_file(),
                    "created_at": meta.get("created_at"), "updated_at": meta.get("updated_at"),
                })
    return out


def scan_opennovelty_pdfs(paper_titles: dict[str, str]) -> dict:
    root = REPO_ROOT / "comparison" / "OpenNovelty"
    out = {p: [] for p in paper_titles}
    if not root.is_dir():
        return out
    for pdf in sorted(root.glob("*.pdf")):
        for paper, needle in paper_titles.items():
            slug = re.sub(r"[^a-z0-9]+", "_", needle.lower())
            if slug[:30] in re.sub(r"[^a-z0-9]+", "_", pdf.stem.lower()):
                out[paper].append(_fmt(pdf))
    return out


def scan_pilot_v1_submissions(paper_keys: list[str]) -> dict:
    root = REPO_ROOT / "eval" / "out" / "pilot_v1"
    out = {}
    for paper in paper_keys:
        f = root / f"{paper}__submission.txt"
        out[paper] = _fmt(f) if f.is_file() else None
    return out


def run(config_path: str) -> dict:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    papers = cfg["papers"]  # {paper_key: {title: ...}}
    paper_keys = list(papers.keys())
    titles = {k: v["title"] for k, v in papers.items()}

    report = {
        "comparison_outputs": scan_comparison_outputs(paper_keys),
        "data_dirs": scan_data_dirs(paper_keys),
        "deepreviewer_jobs": scan_deepreviewer_jobs(titles),
        "opennovelty_pdfs": scan_opennovelty_pdfs(titles),
        "pilot_v1_submissions": scan_pilot_v1_submissions(paper_keys),
        "ambiguous": [],
    }
    for paper, systems in report["comparison_outputs"].items():
        for system, candidates in systems.items():
            if len(candidates) > 1:
                report["ambiguous"].append({
                    "paper": paper, "system": system,
                    "candidates": [c["path"] for c in candidates],
                    "note": "multiple undocumented variants -- see config/sources.pilot.yaml "
                            "for which one (if any) is bound, and why",
                })
    for paper in paper_keys:
        for name, results in (("deepreviewer_jobs", report["deepreviewer_jobs"]),
                              ("opennovelty_pdfs", report["opennovelty_pdfs"])):
            if len(results.get(paper, [])) > 1:
                report["ambiguous"].append({
                    "paper": paper, "system": name, "candidates": results[paper],
                    "note": "more than one match by title -- resolve explicitly",
                })
    return report


def print_report(report: dict) -> None:
    print("=== data/<paper>/ ===")
    for paper, d in report["data_dirs"].items():
        print(f"  {paper}: {d}")
    print("\n=== comparison/outputs/*.md (by paper x system) ===")
    for paper, systems in report["comparison_outputs"].items():
        print(f"  {paper}:")
        for system, candidates in sorted(systems.items()):
            flag = "  <-- AMBIGUOUS" if len(candidates) > 1 else ""
            print(f"    {system}: {len(candidates)} file(s){flag}")
            for c in candidates:
                print(f"       {c['path']}  ({c['bytes']} bytes, sha256 {c['sha256']})")
    print("\n=== DeepReviewer job dirs (completed, title-matched) ===")
    for paper, jobs in report["deepreviewer_jobs"].items():
        print(f"  {paper}: {len(jobs)} match(es)")
        for j in jobs:
            print(f"    {j['job_dir']}  final_report.md={j['has_final_report_md']}  "
                 f"updated_at={j.get('updated_at')}")
    print("\n=== OpenNovelty native PDFs (title-matched) ===")
    for paper, pdfs in report["opennovelty_pdfs"].items():
        print(f"  {paper}: {len(pdfs)} match(es)")
        for p in pdfs:
            print(f"    {p['path']}  ({p['bytes']} bytes)")
    print("\n=== eval/out/pilot_v1 frozen submission texts ===")
    for paper, f in report["pilot_v1_submissions"].items():
        print(f"  {paper}: {f['path'] if f else 'MISSING'}")
    if report["ambiguous"]:
        print("\n=== AMBIGUOUS -- resolve explicitly in config/sources.pilot.yaml ===")
        for a in report["ambiguous"]:
            print(f"  {a['paper']} / {a['system']}: {a['note']}")
            for c in a["candidates"]:
                print(f"     - {c}")
    else:
        print("\nNo ambiguous multi-candidate cases found.")
