#!/usr/bin/env python3
"""One file per task carrying everything a rater reads in the dashboard.

The dashboard shows a rater a submission, two reports labelled A and B, and the rating
form. None of that is in one place: the reports are frozen files, the questions live in
prompts/criteria.json, the instructions in prompts/human_instructions.md, and which report
is "A" is a per-participant property stored on the assignment. Reading a task the way a
rater sees it therefore means opening five things at once, and checking what 30 tasks
actually contain is not something anyone will do that way.

So this writes one file per task (20 in main_study_v2), each self-contained: the paper, the two systems, both raters'
A/B orientation, the submission text, both reports in full, and every question with its
exact wording and answer options.

Two things it deliberately does NOT do:

  resolve A/B to one rater     Both raters see the same pair in OPPOSITE order (that is
                               what orientation_for guarantees). A file that picked one
                               of them would misrepresent the other. Each report is
                               therefore named by its SYSTEM, with a table saying which
                               label each rater saw it under.
  re-render anything           Report text comes from the frozen files the study is
                               seeded from, byte for byte. Rendering again here could
                               silently produce something the raters were never shown.

Usage
-----
  python -m final_evaluation.scripts.export_task_texts
  python -m final_evaluation.scripts.export_task_texts --study main_study_v2 --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FE_ROOT = REPO_ROOT / "final_evaluation"
sys.path.insert(0, str(REPO_ROOT))

from final_evaluation.dashboard.backend import db as db_mod          # noqa: E402
from final_evaluation.dashboard.backend import models                # noqa: E402
from final_evaluation.dashboard.backend.settings import get_settings  # noqa: E402

#: PDF-only reports have no text to inline; the study shows the PDF itself.
_PDF_NOTE = ("This report is shown to the rater as a PDF, not as text. The file is "
             "`{path}`. The text below is the extraction used for the automated judge "
             "(E1), included here so this file is readable on its own -- it is NOT what "
             "the rater sees rendered.")


def _fmt_criteria(crit: dict) -> list:
    out = ["## The rating form", "",
           "For EACH criterion below the rater picks one winner and may add a short "
           "reason.", "",
           f"**Answer options:** {', '.join(crit['winner_values'])}  ",
           f"**Reason:** optional free text, at most {crit['reason_max_words']} words  ",
           "**If \"unclear\" is chosen, one reason must be given from:** "
           + ", ".join(f"`{r}`" for r in crit["unclear_reasons"]),
           "",
           f"Rubric version: `{crit['rubric_version']}`", ""]
    for i, c in enumerate(crit["criteria"], 1):
        out += [f"### Criterion {i}: {c['key']}", "",
                f"**Question shown:** {c['short_question']}", "",
                "**Full description:**", "", c["full_description"], ""]
    return out


def _report_section(label: str, system: str, rep, text: str, is_pdf: bool,
                    pdf_path: str) -> list:
    head = [f"## Report — system `{system}`", ""]
    head += [f"*(Rater sees this as **Report {label}**; see the orientation table above.)*",
             "",
             f"Content version: `{getattr(rep, 'content_version', '') or '-'}`  ",
             f"View type: `{getattr(rep, 'view_type', '') or '-'}`", ""]
    if is_pdf:
        head += ["> " + _PDF_NOTE.format(path=pdf_path), ""]
    head += ["---", "", text.strip() or "*(no text available)*", ""]
    return head


def export(study_id: str, out_dir: Path) -> dict:
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()

    import yaml
    cfg_path = FE_ROOT / "config" / ("main.yaml" if study_id != "dashboard_pilot_v1"
                                     else "pilot.yaml")
    study_dir = (yaml.safe_load(cfg_path.read_text(encoding="utf-8")).get("inputs_dir")
                 or "pilot")
    crit = json.loads((FE_ROOT / "prompts" / "criteria.json").read_text(encoding="utf-8"))
    instructions = (FE_ROOT / "prompts" / "human_instructions.md").read_text(encoding="utf-8")

    tasks = (db.query(models.Task)
             .filter(models.Task.study_id == study_id)
             .all())
    papers = {p.id: p for p in db.query(models.Paper)
              .filter(models.Paper.study_id == study_id).all()}
    reports = {r.id: r for r in db.query(models.Report)
               .filter(models.Report.study_id == study_id).all()}
    participants = sorted(
        db.query(models.Participant).filter(models.Participant.study_id == study_id).all(),
        key=lambda p: p.ordinal)
    assigns = {}
    for a in db.query(models.Assignment).filter(models.Assignment.study_id == study_id).all():
        assigns.setdefault(a.task_id, {})[a.participant_id] = a

    out_dir.mkdir(parents=True, exist_ok=True)
    written, missing = [], []

    # Stable file numbering: paper key, then the pair. Independent of database ids, so a
    # re-export produces the same file names.
    ordered = sorted(tasks, key=lambda t: (papers[t.paper_id].paper_key,
                                           t.system_a, t.system_b))
    for n, t in enumerate(ordered, 1):
        paper = papers[t.paper_id]
        rep_a, rep_b = reports.get(t.report_a_id), reports.get(t.report_b_id)
        if rep_a is None or rep_b is None:
            missing.append(t.pair_key)
            continue

        lines = [f"# Task {n} of {len(ordered)} — {paper.title}", "",
                 f"**Paper key:** `{paper.paper_key}`  ",
                 f"**Systems compared:** `{t.system_a}` vs `{t.system_b}`  ",
                 f"**Pair key:** `{t.pair_key}`  ",
                 f"**Study:** `{study_id}`", "",
                 "## Which report each rater sees as A", "",
                 "Both raters get the same pair in OPPOSITE order -- this is fixed per "
                 "assignment, not chosen by the rater.", "",
                 "| Rater | Report A | Report B |", "|---|---|---|"]
        for p in participants:
            a = (assigns.get(t.id) or {}).get(p.id)
            if a is None:
                lines.append(f"| {p.code_display or p.id[:8]} | *(not assigned)* | |")
                continue
            sa, sb = ((t.system_a, t.system_b) if a.orientation == "forward"
                      else (t.system_b, t.system_a))
            lines.append(f"| {p.code_display or p.id[:8]} | `{sa}` | `{sb}` |")
        lines += ["", "---", "", "## Instructions shown to the rater", "",
                  instructions.strip(), "", "---", "",
                  "## Question asked once per paper", "",
                  "**How familiar are you with this paper?** — one of `low`, `moderate`, "
                  "`high`; plus **have you read it before?** (yes/no)", "", "---", ""]

        # the submission
        sub_txt = _asset_text(db, paper.submission_text_asset_id)
        lines += ["## Submission (the paper being reviewed)", "",
                  f"Shown as a PDF alongside the reports; the text below is the frozen "
                  f"extraction the study stores for it.", "", "---", "",
                  (sub_txt or "*(no submission text stored)*").strip(), "", "---", ""]

        for label, system, rep in (("A", t.system_a, rep_a), ("B", t.system_b, rep_b)):
            txt, is_pdf, path = _report_text(db, rep, study_dir, paper.paper_key)
            lines += _report_section(label, system, rep, txt, is_pdf, path) + ["---", ""]

        lines += _fmt_criteria(crit)
        lines += ["## Also recorded", "",
                  "- **Technical issues:** free text, optional, reported per task.",
                  "- Every answer is autosaved; a task is finalised in one step and then "
                  "read-only.", ""]

        name = f"{n:02d}__{paper.paper_key}__{t.system_a}_vs_{t.system_b}.md"
        (out_dir / name).write_text("\n".join(lines), encoding="utf-8")
        written.append(name)

    db.close()
    return {"written": written, "missing": missing, "out_dir": str(out_dir)}


def _asset_text(db, asset_id) -> str:
    if not asset_id:
        return ""
    from final_evaluation.dashboard.backend import storage
    asset = db.query(models.Asset).get(asset_id)
    if asset is None:
        return ""
    try:
        # `resolve` is the backend's read path -- it returns a local file for LocalStorage
        # and a signed URL for Supabase, so only the local case can be inlined here.
        res = storage.backend_from_env().resolve(asset.storage_key, asset.content_type)
        if getattr(res, "kind", "") != "file":
            return f"*(asset {asset_id} is not a local file: {res.kind})*"
        return Path(res.path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:                       # noqa: BLE001
        return f"*(could not read stored asset {asset_id}: {exc})*"


def _report_text(db, rep, study_dir: str, paper_key: str) -> tuple:
    """(text, is_pdf, pdf_path).

    A markdown report is stored as an asset and IS what the rater reads. A PDF report has
    no text asset -- the rater is shown the PDF itself -- so its E1 text file stands in
    here, from the frozen inputs, and the caller labels it as a stand-in.
    """
    is_pdf = (getattr(rep, "view_type", "") or "") == "pdf"
    if not is_pdf:
        return _asset_text(db, getattr(rep, "content_asset_id", None)), False, ""
    a = db.query(models.Asset).get(getattr(rep, "content_asset_id", None) or "")
    path = getattr(a, "storage_key", "") if a else ""
    e1 = (FE_ROOT / "inputs" / study_dir / paper_key
          / f"{rep.system_id}.e1_text.md")
    text = e1.read_text(encoding="utf-8") if e1.is_file() else ""
    if not text:
        text = f"*(no E1 text file at {e1.relative_to(REPO_ROOT).as_posix()})*"
    return text, True, path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study", default="main_study_v2")
    ap.add_argument("--out", default="final_evaluation/task_texts")
    args = ap.parse_args()
    res = export(args.study, REPO_ROOT / args.out)
    print(f"{len(res['written'])} Dateien -> {args.out}")
    for n in res["written"]:
        print("   ", n)
    if res["missing"]:
        print("OHNE REPORT:", res["missing"])
    return 1 if res["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
