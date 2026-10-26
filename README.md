# Towards Verification-First Agentic Novelty Assessment of Scientific Papers

Code of the master's thesis. An agent compares each claimed contribution of a submission
with retrieved prior work and backs every reported overlap with quotes verified in both
papers. The code builds on Afzal et al., *Beyond "Not Novel Enough"* (Apache 2.0, see
`LICENSE` and `NOTICE.txt`).

## Reproduce the results

Needs Python 3.11 and the data archive `thesis_data_archive.tar.xz` (sent separately,
contents in `DATA.md`). No API key or network access is needed after installation.
Run from the repository root:

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

The files in `out/` are identical to the stored results in
`final_evaluation/results/main/`. On Linux, two bootstrap shares in `e1_analysis.json`
that the thesis does not report differ in the third decimal because of floating-point
rounding. The last command redraws the figures there.

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

## Layout

```
src/               the system: PDF parsing, retrieval, claim extraction, agent, linear baseline
eval/              batch runs of all systems and the E1 judge
final_evaluation/  E1 to E3 analyses and the rating dashboard of the human study
frontend/          reviewer UI
```
