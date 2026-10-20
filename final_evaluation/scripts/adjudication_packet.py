"""Adjudication packet for the claims on which agent and linear reach different verdicts.

Read-only, no API call. Writes, into one directory:

  divergent_claims.md   Part A per case: the claim, where the submission states it, the
                        prior paper in question, and every quote pair EITHER flow
                        grounded for that paper -- pooled and deduplicated, with no degree,
                        strength or verdict attached. Part B per case: the two flows'
                        assessments side by side as "X" and "Y".
  decisions.csv         one row per case, to be filled in: Part A first, then Part B
  key.json              which of X/Y is the agent (seeded, per case) -- opened only after
                        decisions.csv is filled in

The prior paper in question is the one that makes the challenged side challenged
(`refutation_status == can_refute`). Every other paper that either flow rated substantial or
same for that claim is listed in Part B, so a decision on the claim is not made from one
paper alone.

Blinding is partial and the packet says so: the adjudicator knows the direction of the
divergence (in the main study the agent challenged in every case), and an unresolved
paper is recognisable as a single-pass ending. Part A is where the blinding does its work:
the adjudicator forms a judgment from the passages before seeing either flow's reading.

Inputs are sha256-checked against the frozen manifests (`agent_linear._checked`).
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from final_evaluation.evaluation import agent_linear as al

SEED = 2026
DEGREES = "same / substantial / partial / superficial / none"


def _cell(s) -> str:
    return " ".join(str(s or "").split()).replace("|", "\\|") or "–"


def _quote(s: str) -> str:
    return "> " + " ".join(str(s or "").split())


def _load(entry: dict, v: str) -> tuple[dict, dict]:
    prov = entry["systems"][v]["provenance"]
    a = al._checked(prov["artifact_a_path"], prov["artifact_a_sha256"])
    b = al._checked(prov["artifact_b_path"], prov["artifact_b_sha256"])
    return (json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8")))


def _claim(art: dict, cid: str) -> dict:
    return next(c for c in art["claims"] if c["claim_id"] == cid)


def _prior(claim: dict, pid: str) -> tuple[dict, dict]:
    comp = next((c for c in claim["comparisons"] if c["paper_id"] == pid), {})
    pw = next((p for p in claim["run_log"]["prior_work"] if p["paper_id"] == pid), {})
    return comp, pw


def divergent_cases(config: Path = al.E1_CONFIG) -> list:
    """[{paper, claim_id, challenger variant, prior paper ids, ...}] for every claim whose
    verdicts differ, in manifest order."""
    cases = []
    for _, paper, entry in al.paper_entries(config):
        arts = {v: _load(entry, v) for v in al.VARIANTS}
        verdicts = {v: {c["claim_id"]: c.get("verdict") for c in arts[v][1].get("per_claim") or []}
                    for v in al.VARIANTS}
        for cid, va in verdicts["agent"].items():
            vl = verdicts["linear"].get(cid)
            if vl is None or va == vl:
                continue
            side = "agent" if va == "challenged" else "linear"
            claim = _claim(arts[side][0], cid)
            pids = [c["paper_id"] for c in claim["comparisons"]
                    if c.get("refutation_status") == "can_refute"]
            cases.append({"paper": paper, "claim_id": cid, "verdicts": {"agent": va, "linear": vl},
                          "challenger": side, "prior_papers": pids, "arts": arts})
    return cases


def _pairs_pooled(comps: list) -> list:
    seen, out = set(), []
    for comp in comps:
        for p in comp.get("evidence_pairs") or []:
            k = (" ".join(p.get("claim_quote", "").split()), " ".join(p.get("paper_quote", "").split()))
            if k not in seen and all(k):
                seen.add(k)
                out.append(k)
    return out


def _yesno(x) -> str:
    return {True: "yes", False: "no"}.get(x, "–")


def _ending(pw: dict) -> str:
    st = pw.get("final_state", "")
    if st == "checked":
        return "evidence check passed"
    if st == "budget_exhausted":
        return "evidence check's objection stood at the end (left unresolved)"
    return st or "–"


def build(out_dir: Path, config: Path = al.E1_CONFIG) -> dict:
    cases = divergent_cases(config)
    rng = random.Random(SEED)
    key, part_a, part_b, rows = {}, [], [], []
    for i, case in enumerate(cases, 1):
        paper, cid = case["paper"], case["claim_id"]
        labels = ["agent", "linear"]
        rng.shuffle(labels)
        xy = {"X": labels[0], "Y": labels[1]}
        key[f"case_{i}"] = {"paper": paper, "claim_id": cid, **xy,
                            "verdicts": case["verdicts"]}

        sub_dir = al.ROOT / "data" / paper
        meta = json.loads((sub_dir / f"{paper}.json").read_text(encoding="utf-8"))
        claims_doc = json.loads((sub_dir / f"{paper}_claims.json").read_text(encoding="utf-8"))
        anchor = next((c for c in claims_doc["claims"] if c.get("id") == cid), {})
        pool = {p["paper_id"]: p for p in json.loads(
            (sub_dir / "related_work_data" / "ranked_papers.json").read_text(encoding="utf-8"))}
        claims = {v: _claim(case["arts"][v][0], cid) for v in al.VARIANTS}
        claim_text = claims["agent"].get("claim_text") or claims["agent"].get("claim_name", "")

        # ---------------- Part A: the evidence, without anyone's reading of it ----------
        a = [f"## Case {i} — {meta.get('title', paper)}, {cid.replace('_', ' ')}", "",
             f"Submission first public version: {meta.get('publication_date', '–')} "
             f"({meta.get('date_source', '')}). Prior work must predate it.", "",
             "**Claim**", "", _quote(claim_text), ""]
        if anchor.get("evidence_quote"):
            a += ["**Where the submission states it**", "", _quote(anchor["evidence_quote"]), ""]
        real = [r for r in claims["agent"].get("claim_realization") or [] if r.get("kind") == "quote"]
        if real:
            a += ["**How the submission realises it** (verified passages)", ""]
            a += [f"- \"{' '.join(r['content'].split())}\"" for r in real]
            a += [""]
        for pid in case["prior_papers"]:
            comps = [_prior(claims[v], pid)[0] for v in al.VARIANTS]
            pw = _prior(claims[case["challenger"]], pid)[1]
            pe = pool.get(pid, {})
            au = pe.get("authors") or []
            authors = au if isinstance(au, str) else ", ".join(
                x.get("name", "") if isinstance(x, dict) else str(x) for x in au[:8])
            a += [f"### Prior paper: {pe.get('title') or comps[0].get('title', pid)}", "",
                  f"- Version compared: {pw.get('pinned_version', '–')} of "
                  f"{pw.get('pinned_version_date', '–')} — {pw.get('pinned_url', '–')}",
                  f"- Authors: {authors or '–'}",
                  f"- Cited by the submission: {_yesno(comps[0].get('cited_by_submission'))}", ""]
            if pe.get("abstract"):
                a += ["**Abstract**", "", _quote(pe["abstract"]), ""]
            pairs = _pairs_pooled(comps)
            a += [f"**Passage pairs either flow grounded for this paper** ({len(pairs)}, "
                  f"verbatim-verified on both sides, pooled, order not meaningful)", ""]
            for j, (sq, pq) in enumerate(pairs, 1):
                a += [f"{j}. Submission: \"{sq}\"", f"   Prior paper: \"{pq}\"", ""]
        a += ["**Your decision, Part A** (decisions.csv, before reading Part B): the degree "
              f"to which this prior paper already delivers the claimed contribution ({DEGREES}), "
              "and whether the claim should therefore be marked challenged (yes / no / unsure).",
              "", "---", ""]
        part_a += a

        # ---------------- Part B: the two readings side by side ------------------------
        b = [f"## Case {i} — {paper}, {cid.replace('_', ' ')}", ""]
        for pid in case["prior_papers"]:
            cp = {lab: _prior(claims[v], pid) for lab, v in xy.items()}
            title = cp["X"][0].get("title") or cp["Y"][0].get("title") or pid
            b += [f"### {title}", "", "| | Assessment X | Assessment Y |", "|---|---|---|"]
            rowdefs = [
                ("Overlap degree", lambda c, p: c.get("overlap_degree")),
                ("Evidence check", lambda c, p: (c.get("evidence_check") or {}).get("status")),
                ("Check confirms the proposed degree",
                 lambda c, p: _yesno((c.get("evidence_check") or {}).get("proposed_degree_supported"))),
                ("Counts as challenging the claim",
                 lambda c, p: _yesno(c.get("refutation_status") == "can_refute")),
                ("How the paper ended", lambda c, p: _ending(p)),
                ("Sections read", lambda c, p: "; ".join(c.get("sections_used") or [])),
                ("What is shared", lambda c, p: c.get("what_is_shared")),
                ("What the submission adds", lambda c, p: c.get("submission_delta")),
                ("Assessment", lambda c, p: c.get("assessment")),
                ("Evidence check reasoning",
                 lambda c, p: (c.get("evidence_check") or {}).get("reasoning")),
                ("Open question named by the check",
                 lambda c, p: (c.get("evidence_check") or {}).get("unresolved_question")),
            ]
            for label, f in rowdefs:
                b.append(f"| {label} | {_cell(f(*cp['X']))} | {_cell(f(*cp['Y']))} |")
            b.append("")
            for lab in ("X", "Y"):
                pairs = cp[lab][0].get("evidence_pairs") or []
                b += [f"**Quote pairs in Assessment {lab}** ({len(pairs)})", ""]
                for j, p in enumerate(pairs, 1):
                    b += [f"{j}. [{p.get('strength', '–')}] {_cell(p.get('relation') or p.get('rationale'))}",
                          f"   - Submission: \"{' '.join(p.get('claim_quote', '').split())}\"",
                          f"   - Prior paper: \"{' '.join(p.get('paper_quote', '').split())}\""]
                b.append("")
        others = []
        for lab, v in xy.items():
            for c in claims[v]["comparisons"]:
                if c["paper_id"] not in case["prior_papers"] and \
                        (c.get("overlap_degree") or "") in ("same", "substantial"):
                    others.append(c["paper_id"])
        if others:
            b += ["**Other prior papers either assessment rated substantial or same for this claim**",
                  "", "| Prior paper | X: degree / evidence / challenges | Y: degree / evidence / challenges |",
                  "|---|---|---|"]
            for pid in dict.fromkeys(others):
                cells = []
                for lab in ("X", "Y"):
                    c = _prior(claims[xy[lab]], pid)[0]
                    cells.append("not compared" if not c else
                                 f"{c.get('overlap_degree', '–')} / "
                                 f"{(c.get('evidence_check') or {}).get('status', '–')} / "
                                 f"{_yesno(c.get('refutation_status') == 'can_refute')}")
                title = (pool.get(pid) or {}).get("title", pid)
                b.append(f"| {_cell(title)} | {cells[0]} | {cells[1]} |")
            b.append("")
        b += ["**Your decision, Part B**: which assessment reads this prior paper more "
              "accurately (X / Y / equal / neither), and why.", "", "---", ""]
        part_b += b

        rows.append({"case": i, "submission": paper, "claim_id": cid,
                     "prior_paper": "; ".join((pool.get(p) or {}).get("title", p)
                                              for p in case["prior_papers"]),
                     "A_degree_you_assign": "", "A_challenged": "", "A_notes": "",
                     "B_more_accurate": "", "B_notes": ""})

    head = [
        "# Divergent claim verdicts — adjudication packet", "",
        f"{len(cases)} claims on which the agent and the linear baseline reach different verdicts "
        "(E1 papers). Generated by `python -m final_evaluation.cli adjudication-packet` from the "
        "frozen artifacts (sha256-checked); no model call.", "",
        "**How to use it**", "",
        "1. Read **Part A** for every case and fill in the `A_` columns of `decisions.csv`. "
        "Part A shows only the claim, the prior paper and the passages — no degree, no verdict. "
        "Open the prior paper's PDF (link given) wherever the passages are not enough.",
        "2. Only then read **Part B** (the two assessments side by side as X and Y) and fill in "
        "the `B_` columns. Do not change the `A_` columns afterwards.",
        "3. Open `key.json` last.", "",
        "Blinding is partial: you know that one side challenged the claim and the other did not, "
        "and an assessment left unresolved is recognisable. You built the system, so this is an "
        "author adjudication, not an independent one, and is reported as such.", "",
        "The rule both flows apply: a prior paper challenges a claim only if its overlap degree is "
        "substantial or same, the evidence check calls the grounded passages material, and the "
        "check confirms the proposed degree.", "",
        "# Part A — the evidence", "",
    ]
    text = "\n".join(head + part_a + ["# Part B — the two assessments", ""] + part_b)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "divergent_claims.md").write_text(text, encoding="utf-8")
    dec = out_dir / "decisions.csv"
    if dec.exists():
        # Never overwrite decisions that may already be filled in.
        dec = out_dir / "decisions.template.csv"
    with dec.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["case"])
        w.writeheader()
        w.writerows(rows)
    (out_dir / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return {"cases": len(cases), "out_dir": str(out_dir), "decisions": str(dec)}
