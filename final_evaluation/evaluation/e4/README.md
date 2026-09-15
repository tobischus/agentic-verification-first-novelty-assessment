# E4 -- usage / runtime robustness across repeated runs (schema + directory only, NOT implemented)

Placeholder by design, same status as `evaluation/e3/` -- see that directory's README for
why "schema and plan, not a built feature" is the deliberate scope for this task
(PROTOCOL.md section 12: "neue Robustheitsruns oder Elo-Fits sind nicht Voraussetzung").

## What E4 is for

The agent and linear-baseline systems are non-deterministic across repeated runs on the
same paper (different model samples, different section choices). E4 is the later step
that imports SEVERAL runs of the same system on the same paper, and reports how much a
report's content -- and, transitively, a human or judge preference about it -- varies
run to run, versus how much it varies system to system. A single frozen run (what E2
compares) cannot distinguish "system A is genuinely better" from "this run of system A
happened to go well."

## Planned input schema (not implemented)

```json
{
  "paper_id": "...", "system_id": "agent",
  "runs": [
    {"run_id": "...", "content_version": "...", "prompt_tokens": 0, "completion_tokens": 0,
     "usd": 0.0, "wall_clock_s": 0.0, "report_path": "..."}
  ]
}
```

## Planned output schema (not implemented)

```json
{
  "paper_id": "...", "system_id": "...", "n_runs": 0,
  "degree_agreement_across_runs": null,
  "cost_stats": {"mean_usd": null, "stdev_usd": null},
  "runtime_stats": {"mean_s": null, "stdev_s": null}
}
```

## Import path (not implemented)

A future `python -m final_evaluation.cli import-e4-runs --manifest
final_evaluation/manifests/pilot/e4_runs.json` would read multiple
`eval/out/pilot_v1`-style run artifacts (or fresh `eval/run_pilot.py` outputs) for the
same (paper, system) and write `final_evaluation/manifests/pilot/e4_manifest.json` in the
shape above. Nothing in `cli.py` currently calls this.
