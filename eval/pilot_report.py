#!/usr/bin/env python3
"""Turn the judge calls back into system-level statements, order bias included.

A/B is a position in one call, not a system, so the first thing that happens here is the
translation back to the internal system ids. After that, one rule decides everything, per
criterion and per pair:

    same winner in both orders          stable preference
    tie in both orders                  stable tie
    unclear in both orders              not decidable
    anything else                       UNSTABLE

"Anything else" includes A-wins-one-way and tie-the-other. That is not a near-tie to be
averaged: it means the outcome moved when only the presentation order moved, and the
honest report of it is that the pair was not separated. Averaging the two calls would
turn a position effect into half a win.

Nothing is aggregated across criteria and nothing is turned into a score or an Elo. With
two development papers, a single number would be read as a ranking it cannot support.

Technical failures are counted and named, never folded into `unclear`: a call that did
not come back says nothing about the reports.

Usage
-----
  python eval/pilot_report.py
  python eval/pilot_report.py --calls eval/out/pilot_v1/judge_calls.jsonl --md out.md
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
            "conclusion_warrant", "reviewer_usefulness")

# Judge pricing from the project's own table (claim_agent._PRICES), so a reported judge
# cost and a reported run cost are computed the same way. Tokens are printed beside it:
# a price table can go stale, a token count cannot.
USD_PER_M_IN = 2.00
USD_PER_M_OUT = 12.00


def load(path: Path) -> list:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def resolve(rec: dict, criterion: str) -> str:
    """The winner of one call as a SYSTEM id (or 'tie'/'unclear')."""
    w = (rec["parsed_result"]["criteria"][criterion]["winner"] or "").strip()
    if w == "A":
        return rec["system_a"]
    if w == "B":
        return rec["system_b"]
    return w


def outcome(first: str, second: str) -> str:
    if first == second:
        return {"tie": "stable tie", "unclear": "not decidable"}.get(first, "stable preference")
    return "unstable"


def main():
    ap = argparse.ArgumentParser(description="Report the pilot's pairwise outcomes")
    ap.add_argument("--calls", default="eval/out/pilot_v1/judge_calls.jsonl")
    ap.add_argument("--md", default="")
    args = ap.parse_args()

    recs = load(REPO / args.calls if not Path(args.calls).is_absolute() else Path(args.calls))
    ok = [r for r in recs if not r.get("failed") and r.get("parsed_result")]
    failed = [r for r in recs if r.get("failed")]
    retried = [r for r in ok if r.get("n_attempts", 1) > 1]

    # (paper, frozenset(pair), criterion) -> {orientation: system-or-tie}
    seen = defaultdict(dict)
    for r in ok:
        pair = frozenset((r["system_a"], r["system_b"]))
        for c in CRITERIA:
            seen[(r["paper_id"], pair, c)][(r["system_a"], r["system_b"])] = resolve(r, c)

    lines = ["# Pilot v1 — pairwise novelty-report judging", ""]
    lines += [f"- calls recorded: {len(recs)} ({len(ok)} usable, {len(failed)} technical "
              f"failures, {len(retried)} needed a retry)",
              f"- judge: {ok[0]['requested_model'] if ok else '-'} "
              f"(effort={ok[0]['effort'] if ok else '-'}), "
              f"returned: {sorted({r.get('returned_model','') for r in ok})}",
              f"- seed: {ok[0]['seed'] if ok else '-'}, "
              f"prompt: novelty_report_judge_v1 "
              f"({sorted({r['system_prompt_sha256'][:12] for r in ok})})", ""]

    for paper in sorted({p for p, _, _ in seen}):
        lines += [f"## {paper}", ""]
        pairs = sorted({pr for p, pr, _ in seen if p == paper}, key=lambda s: sorted(s))
        lines += ["| pair | " + " | ".join(c.replace("_", " ") for c in CRITERIA) + " |",
                  "|" + "---|" * (len(CRITERIA) + 1)]
        for pair in pairs:
            x, y = sorted(pair)
            cells = []
            for c in CRITERIA:
                d = seen[(paper, pair, c)]
                if len(d) < 2:
                    cells.append("one order only")
                    continue
                (o1, o2) = sorted(d.keys())
                res = outcome(d[o1], d[o2])
                if res == "stable preference":
                    cells.append(f"**{d[o1]}**")
                elif res == "stable tie":
                    cells.append("tie")
                elif res == "not decidable":
                    cells.append("unclear")
                else:
                    cells.append(f"unstable ({d[o1]} / {d[o2]})")
            lines.append(f"| {x} vs {y} | " + " | ".join(cells) + " |")
        lines.append("")

    # counts per criterion, so the stable signal is visible without reading the tables
    lines += ["## Stability per criterion", "",
              "| criterion | stable preference | stable tie | not decidable | unstable |",
              "|---|---|---|---|---|"]
    for c in CRITERIA:
        tally = defaultdict(int)
        for (p, pair, crit), d in seen.items():
            if crit != c or len(d) < 2:
                continue
            (o1, o2) = sorted(d.keys())
            tally[outcome(d[o1], d[o2])] += 1
        lines.append(f"| {c} | {tally['stable preference']} | {tally['stable tie']} | "
                     f"{tally['not decidable']} | {tally['unstable']} |")
    lines.append("")

    # stable wins per system, counted only where the swap held
    wins = defaultdict(lambda: defaultdict(int))
    for (p, pair, crit), d in seen.items():
        if len(d) < 2:
            continue
        (o1, o2) = sorted(d.keys())
        if outcome(d[o1], d[o2]) == "stable preference":
            wins[d[o1]][crit] += 1
    if wins:
        lines += ["## Stable preferences per system (count of pair-criterion cells won)", "",
                  "| system | " + " | ".join(c.replace('_', ' ') for c in CRITERIA) + " | total |",
                  "|" + "---|" * (len(CRITERIA) + 2)]
        for s in sorted(wins, key=lambda k: -sum(wins[k].values())):
            row = [str(wins[s].get(c, 0)) for c in CRITERIA]
            lines.append(f"| {s} | " + " | ".join(row) + f" | {sum(wins[s].values())} |")
        lines.append("")

    # Position check. The both-orders design catches instability per pair, but it cannot
    # say whether the judge has a general pull towards whichever report came first. That
    # is one number: the share of A-verdicts over all judgements. Near 50% means the
    # unstable cells above are genuinely close pairs; well above it would mean the whole
    # table is partly a reading of presentation order.
    pos = defaultdict(int)
    per_crit = defaultdict(lambda: defaultdict(int))
    for r in ok:
        for c, v in r["parsed_result"]["criteria"].items():
            pos[v["winner"]] += 1
            per_crit[c][v["winner"]] += 1
    tot = sum(pos.values()) or 1
    lines += ["## Position check", "",
              f"Over all {tot} judgements: A {pos['A']}, B {pos['B']}, tie {pos['tie']}, "
              f"unclear {pos['unclear']} — **{100 * pos['A'] / tot:.1f}% chose the report "
              f"shown first**.", "",
              "| criterion | A | B | tie | unclear | A share |", "|---|---|---|---|---|---|"]
    for c in CRITERIA:
        d = per_crit[c]
        n = sum(d.values()) or 1
        lines.append(f"| {c} | {d['A']} | {d['B']} | {d['tie']} | {d['unclear']} | "
                     f"{100 * d['A'] / n:.0f}% |")
    locs = sum(len(v["locators"]) for r in ok for v in r["parsed_result"]["criteria"].values())
    withloc = sum(1 for r in ok for v in r["parsed_result"]["criteria"].values() if v["locators"])
    lines += ["", f"Locators: {locs} cited, {withloc}/{tot} judgements carry at least one "
                  f"(all validated against the supplied line ids).", ""]

    # cost and context, reported next to the outcomes as the protocol requires
    tin = sum(r.get("input_tokens", 0) for r in ok)
    tout = sum(r.get("output_tokens", 0) for r in ok)
    treason = sum(r.get("reasoning_tokens", 0) for r in ok)
    tcache = sum(r.get("cache_tokens", 0) for r in ok)
    lat = [r.get("latency_s", 0) for r in ok]
    lines += ["## Cost and context", "",
              f"- judge tokens: {tin:,} in ({tcache:,} from cache), {tout:,} out "
              f"(of which {treason:,} reasoning)",
              f"- latency: {sum(lat)/len(lat):.0f}s mean, {max(lat):.0f}s max, "
              f"{sum(lat)/60:.0f} min total" if lat else "- latency: n/a"]
    if USD_PER_M_IN and USD_PER_M_OUT:
        lines.append(f"- judge cost: ${tin/1e6*USD_PER_M_IN + tout/1e6*USD_PER_M_OUT:.2f}")
    lines.append("")
    lines += ["| paper | report | chars | words |", "|---|---|---|---|"]
    seen_len = set()
    for r in ok:
        for role in ("a", "b"):
            key = (r["paper_id"], r[f"system_{role}"])
            if key in seen_len:
                continue
            seen_len.add(key)
            ch = r["context_chars"][f"report_{role}"]
            lines.append(f"| {key[0]} | {key[1]} | {ch:,} | ~{ch // 6:,} |")
    lines.append("")
    for r in ok[:1]:
        lines.append(f"Submission context: "
                     + ", ".join(f"{p} {n:,} chars" for p, n in sorted(
                         {(x['paper_id'], x['context_chars']['submission']) for x in ok})))
    if failed:
        lines += ["", "## Technical failures", ""]
        for r in failed:
            errs = [a.get("technical_error", "") for a in r.get("attempts", [])]
            lines.append(f"- {r['paper_id']} A={r['system_a']} B={r['system_b']}: "
                         f"{r['n_attempts']} attempts — {errs[-1][:140]}")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.md:
        Path(args.md).write_text(text, encoding="utf-8")
        print(f"written: {args.md}")


if __name__ == "__main__":
    main()
