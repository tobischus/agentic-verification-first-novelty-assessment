# Towards Verification-First Agentic Novelty Assessment of Scientific Papers

Code of the master's thesis. An agent compares each claimed contribution of a submission
with retrieved prior work and backs every reported overlap with quotes verified in both
papers. The code builds on Afzal et al., *Beyond "Not Novel Enough"* (Apache 2.0, see
`LICENSE` and `NOTICE.txt`).

## Contents

1. [Reproduce the results](#reproduce-the-results)
2. [Run the system](#run-the-system)
3. [Run the evaluation](#run-the-evaluation)
4. [Layout](#layout)
5. [Data archive](#data-archive)

## Reproduce the results

Needs Python 3.11 and the data archive `thesis_data_archive.tar.xz` (sent separately,
see [Data archive](#data-archive)). No API key or network access is needed after
installation. Run from the repository root:

```bash
python3.11 -m venv .venv               # Windows: py -3.11 -m venv .venv
source .venv/bin/activate              # Windows (cmd): .venv\Scripts\activate
pip install -r requirements.txt        # about 4 GB with PyTorch
tar -xJf thesis_data_archive.tar.xz
mkdir out
python -m final_evaluation.cli analyze-e1 --out out/e1_analysis.json
python -m final_evaluation.cli sensitivity-e1 --out out/e1_sensitivity.json
python -m final_evaluation.cli agent-linear --out out/agent_linear.json
python -m final_evaluation.cli source-audit --out out/source_audit.json
python -m final_evaluation.cli analyze-human --input final_evaluation/results/main/e2/main_study_v2_export.zip --out out/human_analysis.json
python -m final_evaluation.cli compare-e1 --input final_evaluation/results/main/e2/main_study_v2_export.zip --e1 final_evaluation/results/main/e1/judge_calls.jsonl --out out/compare_e1.json
python final_evaluation/scripts/thesis_figures.py
```

The commands compute E1 (`analyze-e1`, `sensitivity-e1`), agent vs linear baseline
(`agent-linear`), E3 (`source-audit`) and E2 (`analyze-human`, `compare-e1`). The last
command redraws the figures in `final_evaluation/results/main/figures/`. The files in
`out/` are identical to the stored results in `final_evaluation/results/main/`. On Linux,
two bootstrap shares in `e1_analysis.json` that the thesis does not report differ in the
third decimal because of floating-point rounding.

## Run the system

Uses the environment installed above and needs an OpenAI API key and Docker for
GROBID. Model calls are billed.

```bash
git clone https://github.com/sunnweiwei/RankGPT.git
git -C RankGPT checkout 0d62bc3
cp .env.example .env                   # set OPENAI_API_KEY
docker create -p 8070:8070 --name grobid grobid/grobid:0.9.0-crf
docker cp docker/grobid.yaml grobid:/opt/grobid/grobid-home/config/grobid.yaml  # less memory
docker start grobid
```

On Windows, set `PYTHONUTF8=1` before the following commands.

**Reviewer UI** (Section 4.8). Start the API and, in a second terminal, the frontend
(Node 18), then open <http://localhost:5173>, upload a PDF and approve the two checkpoints:

```bash
python src/novelty_assessment/api.py
cd frontend
npm ci
npm run dev
```

**Batch run** as in the evaluation, without checkpoints, for a submission `paper.pdf`
under a chosen id `<id>`:

```bash
python src/novelty_assessment/orchestrator.py --data-dir data --submission-id <id> --pdf paper.pdf --no-hitl
python eval/run_pilot.py --submission <id>
python eval/afzal_adapter.py --data-dir data --submission-id <id>
python src/novelty_assessment/pipeline.py --data-dir data --submission-id <id>
```

These extract the claims and retrieve the prior work, run the agent and the linear
baseline, and run the baseline of Afzal et al. All results are written to `data/<id>/`.

## Run the evaluation

The rules of the evaluation are in `final_evaluation/PROTOCOL.md`. Besides the analyses
above, `python -m final_evaluation.cli plan-e1 --execute` runs the 400 E1 judge calls
(billed), and `python -m final_evaluation.evaluation.e3.opennovelty_audit` checks the
quotes of the OpenNovelty reports against the cited papers (needs network access).

**Baselines.** OpenNovelty's reports are the published PDFs listed in
`final_evaluation/config/sources.*.yaml`. DeepReviewer 2.0 runs locally:

```bash
git clone https://github.com/ResearAI/DeepReviewer-v2.git
git -C DeepReviewer-v2 checkout 1c19a23
```

Install it into `DeepReviewer-v2/.venv` as its README describes, with `openai>=2.36.0` in its
`pyproject.toml`, and set `AGENT_MODEL=gpt-4.1-mini`, `PAPER_SEARCH_PROVIDER=deepxiv` and
`MINERU_MODEL_VERSION=vlm` in its `.env`. `python eval/deepreviewer_run.py --all` then
reviews the submissions of `final_evaluation/config/main.yaml`.

**Rating dashboard** of the human study, in the environment installed above. It needs the
original PDFs of the submissions and reports, which are not part of the data archive:

```bash
pip install -r final_evaluation/requirements.txt
cp final_evaluation/.env.example final_evaluation/.env    # set the two secrets
python -m final_evaluation.cli import-inputs
python -m final_evaluation.cli validate-inputs --study main_study_v2
python -m final_evaluation.cli init-db
python -m final_evaluation.cli seed-study
python -m final_evaluation.cli create-participants --study main_study_v2 --count 3 --prefix M --not-test
python -m final_evaluation.cli create-admin --study main_study_v2
python -m final_evaluation.cli build-frontend
python -m final_evaluation.cli serve
```

The dashboard runs at <http://127.0.0.1:8010>. Access codes are written to
`final_evaluation/private/`. `export`, `backup`, `restore` and `upload-assets` handle the
research export, backups and cloud storage.

## Layout

```
src/               the system: PDF parsing, retrieval, claim extraction, agent, linear baseline
eval/              batch runs of all systems and the E1 judge
final_evaluation/  E1 to E3 analyses and the rating dashboard of the human study
frontend/          reviewer UI
```

## Data archive

The archive unpacks into the repository root. `SHA256SUMS.txt` lists the hash of every
file. Not included: PDFs, the study database, access codes and API keys. Files are JSON,
Markdown and plain text. A `.diff` next to a run log holds the uncommitted code changes at
run time. The export of the human study is a ZIP of CSV and JSONL files, and the schema of
the study database is `final_evaluation/dashboard/backend/models.py`.

| Path | Content |
|---|---|
| `data/<paper>/` | Per paper: claims, prior-work pool and texts, results of agent, linear baseline and Afzal et al., one log per claim run |
| `final_evaluation/inputs/`, `manifests/` | The report and submission texts the judge and the raters read, with hashes |
| `final_evaluation/results/main/` | Judge calls, the export of the human study, all analyses and figures |
| `data/oec_rejected/`, `eval/out/rejected_case/` | The rejected submission of Section 7.4 |
| `eval/out/` | Metadata of the batch runs |
