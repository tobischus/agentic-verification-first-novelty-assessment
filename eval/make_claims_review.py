"""Dump one Stage-A system's complete claim sets to a readable Markdown review.

Per paper: the metrics, every claim with its evidence quote and verification status,
and the silver reference beside it -- so the claims can be judged against the PAPER
first and the reference only second (the reference is silver and restates itself).

  python eval/make_claims_review.py fulltext_luna
  python eval/make_claims_review.py fulltext_sol
"""
import json
import sys
from pathlib import Path

MODELS = {"fulltext_luna": "gpt-5.6-luna", "fulltext_sol": "gpt-5.6-sol",
          "fulltext_terra": "gpt-5.6-terra"}


def build(system: str, results: str, data_dir: str, out_path: str) -> Path:
    res = json.load(open(results, encoding="utf-8"))
    rows = sorted((p for p in res["per_paper"] if system in p["systems"]),
                  key=lambda p: p["systems"][system]["f1"])

    def load(sid, name):
        f = Path(data_dir) / sid / f"{sid}_{name}"
        return json.load(open(f, encoding="utf-8")) if f.exists() else None

    key = system.replace("fulltext_", "")
    L = [f"# Claim Extraction — vollstaendige {key.capitalize()}-Ausgaben\n",
         f"System `{system}` · Modell **{MODELS.get(system, '?')}**, reasoning_effort=high · "
         f"ganzes Paper in EINEM freien Call, keine Realization (Stage A wertet nur Claim-TEXT).\n",
         f"{len(rows)} Paper · Silber-Referenz von **gpt-4.1** (bewusst ein anderes Modell als der "
         f"Extraktor, gegen Self-Preference-Bias) · Judge **{res['judge_model']}**.\n",
         "Sortiert nach F1 **aufsteigend** — die schwaechsten Faelle stehen oben.\n",
         "\n> Die Referenz ist SILBER, nicht Gold: sie ist selbst modellerzeugt und nachweislich\n"
         "> unvollstaendig, und sie wiederholt Beitraege. Ein Claim ohne Referenz-Entsprechung ist\n"
         "> also nicht automatisch falsch, und Recall < 100% nicht automatisch ein Fehler.\n",
         "\n## Ueberblick\n",
         "| # | Paper | Claims | Recall | Prec | F1 | Atomic | Redund | $ |",
         "|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(rows, 1):
        s = p["systems"][system]
        d = load(p["submission_id"], f"claims_{system}.json") or {}
        t = (d.get("title") or p["submission_id"])[:52]
        L.append(f"| {i} | {t} | {s['n_claims']} | {s['recall']*100:.0f}% "
                 f"({s['n_reference_covered']}/{s['n_reference']}) | {s['precision']*100:.0f}% | "
                 f"{s['f1']*100:.0f}% | {s['atomicity']*100:.0f}% | {s['redundancy']*100:.0f}% | "
                 f"{s['cost'].get('usd', 0):.4f} |")

    for i, p in enumerate(rows, 1):
        sid = p["submission_id"]
        s = p["systems"][system]
        d = load(sid, f"claims_{system}.json") or {}
        ref = load(sid, "reference_contributions.json") or {}
        L.append(f"\n---\n\n## {i}. {d.get('title') or sid}\n")
        L.append(f"`{sid}` · Recall **{s['recall']*100:.0f}%** ({s['n_reference_covered']}/"
                 f"{s['n_reference']} Referenzbeitraege) · Precision **{s['precision']*100:.0f}%** · "
                 f"F1 **{s['f1']*100:.0f}%** · Atomicity {s['atomicity']*100:.0f}% · "
                 f"Redundanz {s['redundancy']*100:.0f}% · Groundedness {s['groundedness']*100:.0f}% · "
                 f"${s['cost'].get('usd', 0):.4f}\n")
        L.append(f"### Claims ({len(d.get('claims', []))})\n")
        for j, c in enumerate(d.get("claims", []), 1):
            L.append(f"**{j}.** {c['claim_text']}\n")
            q = (c.get("evidence_quote") or "").strip().replace("\n", " ")
            mark = ("verifiziert woertlich im Paper" if c.get("evidence_verified")
                    else "NICHT verifiziert")
            L.append(f"> _{mark}:_ {q[:700]}{'…' if len(q) > 700 else ''}\n" if q
                     else "> _kein Belegzitat_\n")
        st = ref.get("statements", [])
        L.append(f"\n### Silber-Referenz ({len(st)} Beitraege, {ref.get('model', '?')})\n")
        for stx in st:
            txt = (stx.get("text") if isinstance(stx, dict) else str(stx)).strip().replace("\n", " ")
            L.append(f"- {txt[:500]}{'…' if len(txt) > 500 else ''}")

    out = Path(out_path)
    out.write_text("\n".join(L), encoding="utf-8")
    return out


if __name__ == "__main__":
    system = sys.argv[1] if len(sys.argv) > 1 else "fulltext_luna"
    out = build(system,
                sys.argv[2] if len(sys.argv) > 2 else "eval/out/stage_a_luna_vs_sol.json",
                sys.argv[3] if len(sys.argv) > 3 else "eval/out/data",
                sys.argv[4] if len(sys.argv) > 4 else f"eval/out/{system}_claims_review.md")
    print(f"geschrieben: {out} ({out.stat().st_size/1024:.0f} KB)")
