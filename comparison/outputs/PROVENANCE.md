# How each system's output was obtained

Kept out of the rated documents on purpose: a note explaining that a system produces a
full review would tell a rater which system they are reading.

Internal ids (`agent`, `linear`, `opennovelty`, `deepreviewer`, `afzal`) appear in file
names only. The judge and the human rater see "report A" and "report B".

## Pilot v1 (2026-09-12)

Both papers here are DEVELOPMENT papers: the pipeline was built and debugged against them,
so any ranking read off this pilot is an upper bound on this system's standing, not an
estimate of it. That is why the pilot reports stability per criterion and no overall score.

- `*__agent.md` — this project's agentic pipeline. Fresh run, `eval/run_pilot.py
  --variant agent`, gpt-5.6-luna at low effort for all three roles, whole retrieval
  snapshot (no abstract screen), then `battle_export.py --variant agent`.
- `*__linear.md` — this project's linear baseline: the SAME agent with its per-paper loop
  replaced by a single pass (`agent/linear_baseline.py`) -- one section selection, one
  comparison, one evidence check, no re-reading and no re-entry. Same models, same pool,
  same sources, same verification, same exporter. Fresh run in the same process as the
  agent's (`--variant both`), so the two differ in control flow and nothing else.
- `*__afzal.md` — Afzal et al.'s assessment stage (`src/novelty_assessment/pipeline.py`,
  gpt-4.1) on this pipeline's inputs. Their steps read introductions written by their own
  Nougat-based extractor, which this tree does not produce, so `eval/afzal_adapter.py`
  writes them from the GROBID output first. It is therefore "their assessment method on
  our inputs", not an end-to-end system comparison, and has to be reported as such.
  File = `summary.txt` + `novelty_delta_analysis.txt`, both verbatim, in that order.
- `*__deepreviewer.md` — DeepReviewer 2.0, run locally (MinerU v4 parse, DeepXiv search,
  `AGENT_MODEL` raised from `gpt-4.1-mini` to `gpt-4.1` for parity). It writes a complete
  peer review, so `eval/extract_deepreviewer.py` applies one rule, fixed before either
  paper was extracted and applied identically to both: the whole `## Novelty Verification
  & Related-Work Matrix` section up to the next `## ` heading, plus the `## References`
  entries its `[n]` markers point into. Nothing rewritten, shortened or dropped. The
  restriction to one section is deliberate information loss and the only way to place a
  full-review system beside novelty-only systems. Verified by re-deriving the existing
  transducing file from the rule: 694 words, identical.
- `transducing_language_models__opennovelty.md` — the authors' own published report
  (lightweight variant), converted from PDF with `eval/pdf_to_md.py`. Not re-run locally:
  their Phase 2 depends on the WisPaper API, which needs an account and a browser login.

### Missing: OpenNovelty for GraphRAG

There is no OpenNovelty report for `graphrag_when_to_use`, and one cannot be produced
here: the authors published reports for five other papers, and running their pipeline
needs a WisPaper token obtained through an interactive login. The pilot therefore judges
five systems on `transducing_language_models` (10 pairs) and four on
`graphrag_when_to_use` (6 pairs). With a token, the four missing pairs add 8 calls and
the existing 32 stay valid -- the prompt and every other report are unchanged.

## Archived

`_pre_pilot_archive/` holds the outputs this pilot replaced: the earlier agentic run
(`__agentic.md`), the earlier linear baseline (`__linear.md`, the old `ArtifactABuilder`
rather than the current single-pass baseline), and `__threat.md`. They are kept for
traceability and must not be mixed into pilot v1 results.
