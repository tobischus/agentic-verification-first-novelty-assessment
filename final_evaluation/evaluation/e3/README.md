# E3 -- source-fidelity verification (schema + directory only, NOT implemented)

This directory is a placeholder by design (PROTOCOL.md section 12): "Ein vollständiges
Quellenprüfungsdashboard ... sind nicht Voraussetzung für den lauffähigen Human-Pilot."
Nothing under `evaluation/e3/` is wired into `cli.py`, the dashboard backend, or E2's
analysis. Do not treat the schema below as an implemented feature.

## What E3 is for

E1 and E2 (the LLM judge and the human raters) both evaluate reports against the
submission alone -- neither ever sees the ORIGINAL prior-work papers a report cites.
E3 is the later, separate step that checks a report's claims about prior work against
those prior-work papers themselves: does a quoted "paper_quote" actually stand in the
cited paper, does a stated absence hold up, does an ownership claim ("this is the cited
paper's OWN contribution, not something it cites in turn") hold.

## Why it is a separate package, not a mode of E2

Prior-work papers are the one category of PDF this dashboard's study mode must NEVER
serve to a participant mid-E2 (see PROTOCOL.md section 5, "Welche PDFs dürfen aufgehen?").
Keeping E3's inputs, manifest, and importer in their own directory -- never read by
`dashboard/backend/routers/assets.py` -- is what makes that boundary structural rather
than a filter someone has to remember to apply. `evaluation/e3/` has no import path from
`dashboard/`, and that absence is the point, not an oversight to fix later by wiring one.

## Planned input schema (not implemented)

```json
{
  "paper_id": "graphrag_when_to_use",
  "system_id": "agent",
  "claim_id": "claim_1",
  "prior_work_paper_id": "...",
  "prior_work_source": {"path": "...", "sha256": "...", "version": "...", "version_date": "..."},
  "checks": [
    {"kind": "quote_exists", "quoted_text": "...", "located_at": {"page": 4, "span": [120, 340]}},
    {"kind": "ownership", "verdict": "own_contribution|cited_work|unclear"},
    {"kind": "absence_claim", "claim_text": "...", "verdict": "supported|contradicted|unresolved"}
  ]
}
```

## Planned output schema (not implemented)

```json
{
  "paper_id": "...", "system_id": "...",
  "n_claims_checked": 0, "n_quote_verified": 0, "n_quote_failed": 0,
  "n_absence_supported": 0, "n_absence_contradicted": 0,
  "per_claim": []
}
```

## Import path (not implemented)

A future `python -m final_evaluation.cli import-e3-sources --manifest
final_evaluation/manifests/pilot/e3_sources.json` would materialise prior-work PDFs into
`final_evaluation/inputs/e3/` (a directory E2's asset router does not read) and produce
`final_evaluation/manifests/pilot/e3_manifest.json` in the shape above.
