# How each system's output was obtained

Kept out of the rated documents on purpose: a note explaining that a system produces a
full review would tell a rater which system they are reading.

- `__agentic.md` — own agentic pipeline, `battle_export.py` over Artifact A + B.
- `__linear.md` — own linear baseline, same export with `--variant linear`.
- `__afzal.md` — Afzal et al. step 6, run on this pipeline's GROBID output via
  `eval/afzal_adapter.py`. Their step 6 reads introductions written from Nougat MMD, which
  this tree does not produce, so the run is "their assessment method on our inputs" and not
  an end-to-end comparison. File = `summary.txt` + `novelty_delta_analysis.txt`.
- `__opennovelty.md` — the authors' own published report (lightweight variant), converted
  from PDF with `eval/pdf_to_md.py`. Not re-run locally: their Phase 2 depends on the
  WisPaper API, which is not public.
- `__deepreviewer.md` — DeepReviewer 2.0 run locally, MinerU v4 parse, DeepXiv search,
  `AGENT_MODEL` overridden from `gpt-4.1-mini` to `gpt-4.1` for parity with the other
  systems. It writes a complete review, so the file is its "Novelty Verification &
  Related-Work Matrix" section plus the reference list its `[n]` markers point into. That
  restriction is deliberate information loss and the only way to compare it against
  systems that assess novelty alone.
