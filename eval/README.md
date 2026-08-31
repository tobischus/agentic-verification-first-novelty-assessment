# First evaluation run

Compares **my agentic pipeline** against **Afzal's baseline** (`ours/summary.txt`),
both judged against the **human novelty assessments** from the Afzal et al. (2026)
dataset, using the paper's LLM-as-Judge method (Figures 13 & 14, GPT-4.1).

## Run it (one call, from the repo root)

```powershell
.\run-eval.ps1              # 18 papers (default)
.\run-eval.ps1 -N 15
.\run-eval.ps1 -Ids "1XxNbecjXe,2NqssmiXLu"
.\run-eval.ps1 -SkipJudge   # pipeline only, no judge
```

**Prerequisites:** GROBID running (see `Start.txt`) and `.env` with `OPENAI_API_KEY`
+ `SEMANTIC_SCHOLAR_API_KEY`.

**Resumable at the score level:** a paper counts as done only once its final
Afzal-vs-mine score comparison is written. Re-run `.\run-eval.ps1` and it continues
with the papers that don't yet have a score — reusing any cached pipeline output
(artifact_a, conclusion), so only the missing steps are recomputed.

**Live progress:** after *every* paper the judge runs immediately and `scores.csv`,
`report.md` and `aggregate.json` are rewritten — watch `eval/out/scores.csv` grow.

## Compare the PDF parsers (PyMuPDF vs GROBID)

Before trusting PyMuPDF for related-work full text, eyeball it against GROBID:

```powershell
python eval/compare_parsers.py --n 3
python eval/compare_parsers.py --pdfs "data/<run>/related_work_data/pdfs" --n 5
```

Prints #sections / #chars / time / title-overlap per PDF and writes side-by-side
`*.pymupdf.md` / `*.grobid.md` dumps to `eval/parser_compare/` so you can read both
outputs and decide. (Needs GROBID up.)

## What it does per paper

1. Runs my full pipeline autonomously: GROBID doc processing → claim extraction →
   S2 retrieval → PDF download → per-claim agentic review → overall **conclusion**
   (the comparable prose artifact). Every step + token cost is logged.
2. Runs the two-stage judge (extract core judgments from the human assessment, then
   score each system's assessment) for **Afzal's summary** and **my conclusion**.

## Outputs (`eval/out/`)

- `report.md` — pipeline health table (GROBID ok? #claims? #PDFs? conclusion?), full
  cost breakdown, and the Afzal-vs-mine alignment scores across the four dimensions.
- `scores.csv` — one row per (paper, human-ref, system) for your own analysis.
- `results/{forum_id}.json` — everything per paper (steps, cost, conclusion, judge).
- `aggregate.json`, `run.log`.

## Dimensions (Afzal Fig 14)

Judgment similarity (0–1), Conclusion agreement (%), Prior-work engagement (NONE/
LIMITED/EXTENSIVE), Depth of analysis (SURFACE/MODERATE/DEEP), plus positive/negative
novelty shift (miscalibration vs the human, lower = better).

## Conclusion re-scoring experiment (does a better final paragraph fix the scores?)

The first run showed the agentic pipeline WINS on prior-work engagement + depth but loses
on conclusion agreement with a large positive shift (over-claims novelty) — the weakness is
the **final conclusion paragraph's calibration**, not the underlying Artifact A.
`rescore_conclusions.py` isolates that: it rebuilds ONLY the conclusion from each paper's
existing Artifact A (critical reviewer stance, faithfully carrying the agent's per-claim
`challenged`/overlap verdicts), then re-runs the identical Fig 13/14 judge on the new
conclusion vs Afzal vs the humans. The pipeline is NOT re-run (no GROBID needed).

```powershell
.\run-rescore.ps1                       # all papers in eval/out/results
.\run-rescore.ps1 -Ids "09JVxsEZPf"     # one paper
.\run-rescore.ps1 -N 3                   # first 3
.\run-rescore.ps1 -Force                 # redo already-scored
```

Writes to a SEPARATE `eval/out_v2/` (report.md with an OLD-vs-NEW "did it improve?" table +
per-paper verdict flips, scores.csv, conclusions/{id}.txt, results/{id}.json). **Never
touches** the original `eval/out/` conclusions. Same conclusion model (gpt-4.1) as the main
run, so only the PROMPT differs. Watch the trade-off: the tighter critical conclusion improves
calibration but can lower the prose-only prior-work/depth scores (a verbosity artifact).

## Notes / caveats

- **Model:** `run-eval.ps1` uses `gpt-5-mini` for the pipeline (a reasoning model — slow,
  minutes per claim; a full 18-paper run takes hours, so let it run overnight — it
  resumes), `gpt-4.1` for the conclusion synthesis, and `gpt-4.1` for the judge (as
  Afzal did). Tip: sanity-check with a small batch first (`.\run-eval.ps1 -N 3`).
- The judge sees **prose only** (my conclusion vs Afzal's summary vs human) to keep the
  comparison fair — the pipeline's richer per-claim verified evidence is not fed to the
  judge in this first run.
- Fair baseline: Afzal's own `ours/summary.txt` is re-judged here with the identical
  judge, rather than citing the paper's reported numbers.
