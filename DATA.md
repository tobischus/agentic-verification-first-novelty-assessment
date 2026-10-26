# Data archive

The results of the thesis come from `thesis_data_archive.tar.xz`, which is distributed
separately from this repository. Unpack it into the repository root. `SHA256SUMS.txt`
lists every file with its hash.

| Path | Content |
|---|---|
| `data/<paper>/` | Per paper: parsed submission, claims, prior-work pool, parsed prior-work texts, artifacts of agent and linear, report summaries, output of Afzal et al. |
| `data/<paper>/run_logs/` | One log per claim run: model calls, decisions, prompt and schema hashes |
| `data/oec_rejected/`, `eval/out/rejected_case/` | The rejected submission of Section 7.4 |
| `final_evaluation/inputs/`, `final_evaluation/manifests/` | Frozen report and submission texts read by the E1 judge, with hashes |
| `final_evaluation/results/main/e1/` | E1 judge calls (`judge_calls.jsonl`) and their analyses |
| `final_evaluation/results/main/e2/` | Pseudonymized export of the human study and its analyses |
| `final_evaluation/results/main/agent_linear/`, `e3/` | Agent vs linear metrics, source audits |
| `final_evaluation/results/main/figures/` | Figures of the thesis |
| `eval/out/` | Run metadata of the batch runs and DeepReviewer jobs |

Not included: PDFs of submissions, prior work and external reports, access codes and
database of the study, and API keys. The ten papers per study and their sources are
listed in `final_evaluation/config/`.

The agent was run with `gpt-5.6-luna` (reasoning effort low, claim extraction high),
the E1 judge with `gpt-6.1-sol` (effort medium) and the baseline of Afzal et al. with
`gpt-4.1`.
