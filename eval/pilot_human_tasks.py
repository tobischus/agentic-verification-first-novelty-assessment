#!/usr/bin/env python3
"""Fix the six human rating tasks BEFORE any LLM judgement is read.

Order matters here and is the whole reason this is a separate script run at a separate
time: tasks picked after seeing the model's verdicts would be picked, consciously or not,
where the verdicts are convenient. So the selection is made from the seed alone and
written to disk, and the rating sheet carries no model output.

What is selected, per the pilot protocol:
  - agent vs. linear on both papers (the comparison the thesis is about);
  - two further system pairs per paper, drawn with the pilot seed.

The sheet is blinded the way the judge is blinded: each task shows report A and report B
by file, never the system name. The key is written to a separate file that the rater does
not open until the ratings are in.

Usage
-----
  python eval/pilot_human_tasks.py
"""
import itertools
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "eval" / "out" / "pilot_v1"
REPORT_DIR = REPO / "comparison" / "outputs"
SEED = 42
PAPERS = ("graphrag_when_to_use", "transducing_language_models")
SYSTEMS = ("agent", "linear", "opennovelty", "deepreviewer", "afzal")
CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
            "conclusion_warrant", "reviewer_usefulness")


def available(paper: str) -> list:
    return [s for s in SYSTEMS if (REPORT_DIR / f"{paper}__{s}.md").exists()]


def main():
    rng = random.Random(SEED)
    tasks, key = [], []
    for paper in PAPERS:
        systems = available(paper)
        fixed = [("agent", "linear")] if {"agent", "linear"} <= set(systems) else []
        others = [p for p in itertools.combinations(sorted(systems), 2)
                  if set(p) != {"agent", "linear"}]
        rng.shuffle(others)
        for pair in fixed + others[:2]:
            # Which report is shown first is also drawn, so the sheet does not put one
            # system in position A throughout.
            x, y = (pair if rng.random() < 0.5 else (pair[1], pair[0]))
            tid = f"H{len(tasks) + 1:02d}"
            tasks.append({
                "task_id": tid,
                "paper_id": paper,
                "submission": f"eval/out/pilot_v1/{paper}__submission.txt",
                "report_a": f"comparison/outputs/{paper}__{x}.md",
                "report_b": f"comparison/outputs/{paper}__{y}.md",
            })
            key.append({"task_id": tid, "paper_id": paper, "system_a": x, "system_b": y})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "human_tasks.json").write_text(
        json.dumps({"pilot_version": "pilot_v1", "seed": SEED, "tasks": tasks},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "human_tasks_KEY.json").write_text(
        json.dumps({"pilot_version": "pilot_v1", "seed": SEED, "key": key,
                    "note": "do not open before the human ratings are recorded"},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    sheet = ["# Pilot v1 — human rating sheet", "",
             "Rate each task BEFORE reading any LLM judgement. Same rubric as the judge:",
             "for each criterion choose A, B, tie (comparable, including equally weak) or",
             "unclear (the material does not permit a defensible preference). Do not use",
             "tie for insufficient information, and do not form an overall winner.", "",
             "You receive the submission and both reports. You do NOT use the prior-work",
             "papers, a reference assessment, or any system's internals -- the same",
             "evidence boundary the judge has, so the two ratings are comparable.", ""]
    for t in tasks:
        sheet += [f"## {t['task_id']} — {t['paper_id']}", "",
                  f"- submission: `{t['submission']}`",
                  f"- report A: `{t['report_a']}`",
                  f"- report B: `{t['report_b']}`", ""]
        for c in CRITERIA:
            sheet.append(f"  - {c}: winner = ______  note: ")
        sheet.append("")
    (OUT_DIR / "human_rating_sheet.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")

    print(f"{len(tasks)} tasks fixed with seed {SEED}:")
    for t in tasks:
        print(f"  {t['task_id']} {t['paper_id'][:26]:26} "
              f"A={Path(t['report_a']).stem.split('__')[-1]:12} "
              f"B={Path(t['report_b']).stem.split('__')[-1]}")
    print(f"\nwritten: {OUT_DIR/'human_tasks.json'}, human_tasks_KEY.json, "
          f"human_rating_sheet.md")


if __name__ == "__main__":
    main()
