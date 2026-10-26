# final_evaluation

Analyses of E1 to E3 and the rating dashboard of the human study (E2). The rules of the
evaluation are in `PROTOCOL.md`. All commands run from the repository root as
`python -m final_evaluation.cli <command>`.

| Command | Purpose |
|---|---|
| `analyze-e1`, `sensitivity-e1` | E1 results, ranking and length adjustment |
| `agent-linear` | Agent vs linear baseline from the run records |
| `source-audit` | E3 quote and source checks |
| `analyze-human`, `compare-e1` | E2 results and agreement with the judge |
| `plan-e1 --execute` | Runs the E1 judge calls (billed) |

`python -m final_evaluation.evaluation.e3.opennovelty_audit` checks the quotes of the
OpenNovelty reports against the cited papers and needs network access.

## Dashboard

The dashboard serves the frozen reports and stores the ratings. It makes no model calls
and needs the original PDFs of the submissions and reports, which are not part of the
data archive.

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

The app runs at <http://127.0.0.1:8010>. Access codes are written to
`final_evaluation/private/`. `export`, `backup`, `restore` and `upload-assets` handle the
research export, backups and cloud storage.
