# final_evaluation

Rating dashboard for the human study (E2) and the evaluation scripts (E1 to E3). The
dashboard makes no model calls. It serves report files frozen by `import-inputs` and
stores the ratings. All commands run from the repository root.

## Dashboard

```
python -m pip install -r final_evaluation/requirements.txt
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

The app runs at <http://127.0.0.1:8010>. Without further settings it uses SQLite and
local file storage under `final_evaluation/private/`. Access codes are stored as
HMAC-SHA256 only. `create-participants` and `create-admin` write them to files under
`private/` and print the paths.

| Command | Purpose |
|---|---|
| `import-inputs` | Freeze reports and submission texts into `inputs/` with a hash manifest |
| `validate-inputs` | Check hashes, systems per paper, quote anchors and task pairs |
| `init-db`, `seed-study` | Create the database and the study, papers, reports and tasks |
| `create-participants`, `create-admin` | Participants with their assignments, admin access |
| `build-frontend`, `serve` | Build the frontend and serve it with the API |
| `export` | Pseudonymized research export (ZIP) |
| `upload-assets`, `backup`, `restore` | Cloud storage upload and operational backups |

## Analyses

| Command | Thesis |
|---|---|
| `plan-e1` | E1 judge calls and cost estimate. `--execute` runs them (paid) |
| `analyze-e1` | E1 pairwise results and Bradley-Terry ranking |
| `sensitivity-e1` | E1 length-adjusted rankings |
| `agent-linear` | Agent vs linear run metrics with sign tests |
| `source-audit` | E3 quote and source checks for agent and linear |
| `analyze-human --input export.zip` | E2 tallies and agreement |
| `compare-e1 --input export.zip --e1 judge_calls.jsonl` | Human ratings vs the judge |

The commands in this table run offline on the result files and artifacts of the data
archive (see `DATA.md` in the repository root), except `plan-e1 --execute`.
`python -m final_evaluation.evaluation.e3.opennovelty_audit` checks the quotes of the
OpenNovelty reports and needs network access to Semantic Scholar and arXiv.
`python final_evaluation/scripts/thesis_figures.py` draws the thesis figures.

## Layout

```
config/      study and E1 configuration, source bindings
prompts/     judge rubric, rating criteria, participant instructions
dashboard/   FastAPI backend, Vite/React frontend, migrations
evaluation/  E1, E2 and E3 analyses
scripts/     input import and validation, seeding, figures
```

`inputs/`, `manifests/`, `results/` and `private/` are not in git. They are part of the
data archive, except `private/`.
