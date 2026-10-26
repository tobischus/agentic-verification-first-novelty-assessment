# Towards Verification-First Agentic Novelty Assessment of Scientific Papers

Code of the master's thesis of the same title. The system extracts the claimed
contributions of a submission, retrieves prior work, and lets an agent compare each claim
with each prior paper. Every overlap it reports is backed by quotes that are verified
against the source texts. The linear baseline runs the same steps in a fixed order.

The repository builds on the code of Afzal et al., *Beyond "Not Novel Enough": Enriching
Scholarly Critique with LLM-Assisted Feedback* (UKP Lab, TU Darmstadt). Their pipeline
(`src/novelty_assessment/pipeline.py` and the modules it calls) serves as a baseline, and
their retrieval stage (`src/retrieval/`) is reused with changes. The original code is
licensed under Apache 2.0 (`LICENSE`, `NOTICE.txt`).

## Layout

```
src/preprocess/           PDF parsing with GROBID, metadata, submission date
src/retrieval/            prior-work retrieval, Semantic Scholar matching, version pinning
src/novelty_assessment/   claim extraction, agent and linear baseline, report, API
  agent/                  claim agent, linear baseline, tools, evidence check, run logs
eval/                     batch runs of agent, linear and baselines, E1 judge
final_evaluation/         rating dashboard (E2) and analyses (E1 to E3)
frontend/                 reviewer UI with the two checkpoints
docker/                   GROBID configuration
```

## Setup

Python 3.11 and Node 18 (tested with 3.11.2 and 18.15.0).

```bash
pip install -r requirements.txt
git clone https://github.com/sunnweiwei/RankGPT.git    # used at commit 0d62bc3
cp .env.example .env                                   # set OPENAI_API_KEY
```

GROBID runs in Docker, see `docker/README.md`.

## Usage

**Reviewer UI.** Start the API (`start-backend.ps1`, or `python src/novelty_assessment/api.py`)
and the frontend (`cd frontend && npm ci && npm run dev`). Upload a PDF, review the
claims and the prior-work pool at the two checkpoints, then run the claim review.

**Command line.** For a paper in `data/<id>/`:

```bash
# document processing, claim extraction, retrieval, PDF download
python src/novelty_assessment/orchestrator.py --data-dir data --submission-id <id> --pdf paper.pdf --no-hitl
# agent and linear baseline, with the paper-level summary
python eval/run_pilot.py --submission <id> --variant both
# baseline of Afzal et al.
python eval/afzal_adapter.py --data-dir data --submission-id <id>
python src/novelty_assessment/pipeline.py --data-dir data --submission-id <id> --model gpt-4.1
```

`eval/run_claim_assessment.py` adds the claim explanations to the reports.
`eval/run_e1_extra.py` runs all steps for the ten E1-only papers.

## Reproducing the evaluation

The analyses of Chapter 6 run offline from the data archive (`DATA.md`). Unpack it
into the repository root and run:

```bash
mkdir out
python -m final_evaluation.cli analyze-e1 --out out/e1_analysis.json
python -m final_evaluation.cli sensitivity-e1 --out out/e1_sensitivity.json
python -m final_evaluation.cli agent-linear --out out/agent_linear.json
python -m final_evaluation.cli source-audit --out out/source_audit.json
python -m final_evaluation.cli analyze-human --input final_evaluation/results/main/e2/main_study_v2_export.zip --out out/human_analysis.json
python -m final_evaluation.cli compare-e1 --input final_evaluation/results/main/e2/main_study_v2_export.zip \
  --e1 final_evaluation/results/main/e1/judge_calls.jsonl --out out/compare_e1.json
python final_evaluation/scripts/thesis_figures.py
```

The outputs in `out/` match the stored results in `final_evaluation/results/main/`.
Without `--out`, the commands overwrite the stored files.
New runs of the systems or the judge call paid APIs and give different outputs, since the
models are not deterministic. Each run log records the prompt and schema hashes it used.
