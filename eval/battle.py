#!/usr/bin/env python3
"""
Blind pairwise comparison of the normalised assessments, one criterion at a time.

Every pair is judged in BOTH orders and a win only counts when it survives the swap. That
is not a nicety: on this project the judge's position bias decided 40% of outcomes in an
earlier experiment, so a single-orientation result says as much about presentation order as
about the systems.

The rubric is fixed here rather than passed in, because criteria chosen after seeing results
are worthless. It deliberately mixes:

  * criteria any system can win (accuracy, specificity, calibration),
  * one that encodes this thesis's premise (verifiability) -- reported SEPARATELY, so a
    reader can see whether the ranking survives without the criterion that was designed to
    favour an evidence-first system,
  * one that rewards brevity (usefulness), as a counterweight to the previous one.

Length is recorded, never scored. It spans a factor of 25 across these systems, and a
ranking that tracks it is a ranking of length.

This is an LLM pre-pass. It does not replace the human rating; it narrows down which pairs
are worth a person's time and gives a kappa baseline to check that rating against.

Usage
-----
  python eval/battle.py --paper transducing_language_models
  python eval/battle.py --paper ID --judge-model gpt-4.1 --out eval/out/battle_ID.json
"""
import argparse
import itertools
import json
import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

CRITERIA = {
    "accuracy": (
        "Factual accuracy about prior work",
        "Are the statements about what a cited prior paper does correct and fairly "
        "represented? Penalise misattribution, invented findings, and papers described in a "
        "way their own summary would not support."),
    "verifiability": (
        "Verifiability",
        "Could a reader check the claims without redoing the work? Named papers, locatable "
        "evidence, quoted or precisely referenced passages rather than assertions."),
    "specificity": (
        "Specificity of the delta",
        "Does it state concretely WHAT overlaps and WHAT the submission adds beyond it, or "
        "does it stay at the level of topics and generalities?"),
    "calibration": (
        "Calibration",
        "Does confidence match evidence? Reward stating the limits of the search and "
        "hedging where the evidence is thin; penalise both unearned certainty (\"no overlap "
        "risk\", \"clearly novel\") and vagueness that avoids committing to anything."),
    "usefulness": (
        "Usefulness to a reviewer",
        "Would this help someone write a review? Organisation, actionability, and getting "
        "to the point at a length proportionate to what it says."),
}

_PROMPT = """You are comparing two automated novelty assessments of the SAME paper, on ONE criterion.

Judge ONLY the criterion given. Ignore formatting, house style, and which assessment is longer -- length is not quality in either direction. Do not reward an assessment for agreeing with your own view of the paper; judge the assessment as a piece of work.

## Criterion: {criterion_name}
{criterion_detail}

## The paper under assessment
Title: {title}
Abstract: {abstract}

## Assessment 1
{doc1}

## Assessment 2
{doc2}

Answer with `winner` = "1", "2" or "tie", and one sentence of `reason` naming the concrete difference that decided it."""


class _Verdict(BaseModel):
    winner: str = Field(description='"1", "2" or "tie"')
    reason: str = Field(description="one sentence naming the concrete difference")


def _load_docs(paper: str, norm_dir: str) -> Dict[str, str]:
    d = Path(norm_dir) / paper
    return {p.stem: p.read_text(encoding="utf-8")
            for p in sorted(d.glob("[A-Z].md"))}


def _paper_meta(paper: str, data_dir: str) -> tuple:
    meta_path = Path(data_dir) / paper / f"{paper}.json"
    if not meta_path.exists():
        return paper, ""
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    return m.get("title", paper), (m.get("abstract", "") or "")[:2500]


def _judge(llm, crit_key: str, title: str, abstract: str, d1: str, d2: str) -> dict:
    name, detail = CRITERIA[crit_key]
    prompt = _PROMPT.format(criterion_name=name, criterion_detail=detail,
                            title=title, abstract=abstract, doc1=d1, doc2=d2)
    try:
        r = llm.with_structured_output(_Verdict).invoke(prompt)
        return {"winner": (r.winner or "tie").strip().lower(), "reason": r.reason}
    except Exception as e:
        return {"winner": "tie", "reason": f"[judge failed: {repr(e)[:120]}]"}


def run(paper: str, norm_dir: str, data_dir: str, judge_model: str, out_path: str) -> dict:
    docs = _load_docs(paper, norm_dir)
    if len(docs) < 2:
        raise SystemExit(f"need at least two assessments in {norm_dir}/{paper}")
    title, abstract = _paper_meta(paper, data_dir)
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set")
    llm = ChatOpenAI(model_name=judge_model, temperature=0.0,
                     api_key=os.getenv("OPENAI_API_KEY"), max_retries=6, timeout=300)

    letters = sorted(docs)
    results = {"paper": paper, "judge_model": judge_model,
               "words": {k: len(v.split()) for k, v in docs.items()},
               "criteria": {}, "comparisons": []}

    for crit in CRITERIA:
        wins = {k: 0 for k in letters}
        ties = inconsistent = 0
        for x, y in itertools.combinations(letters, 2):
            a = _judge(llm, crit, title, abstract, docs[x], docs[y])   # x first
            b = _judge(llm, crit, title, abstract, docs[y], docs[x])   # y first
            # translate each verdict into a letter, then require agreement
            first = {"1": x, "2": y}.get(a["winner"])
            second = {"1": y, "2": x}.get(b["winner"])
            if first and first == second:
                wins[first] += 1
                outcome = first
            else:
                ties += 1
                outcome = "tie"
                if first and second and first != second:
                    inconsistent += 1
            results["comparisons"].append(
                {"criterion": crit, "pair": [x, y], "outcome": outcome,
                 "raw": [a["winner"], b["winner"]],
                 "reasons": [a["reason"], b["reason"]]})
            print(f"  [{crit:13}] {x} vs {y}: {a['winner']}/{b['winner']} -> {outcome}")
        results["criteria"][crit] = {"wins": wins, "ties": ties,
                                     "position_inconsistent": inconsistent}

    _report(results, letters)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\nwritten: {out_path}")
    return results


def _report(res: dict, letters: List[str]) -> None:
    print("\n" + "=" * 78)
    print(f"BLIND PAIRWISE, both orders, wins count only if the swap agrees  ({res['paper']})")
    print("=" * 78)
    head = f"{'criterion':16}" + "".join(f"{l:>6}" for l in letters) + f"{'ties':>7}{'pos.incons.':>13}"
    print(head)
    print("-" * len(head))
    total = {l: 0 for l in letters}
    for crit, d in res["criteria"].items():
        row = f"{crit:16}" + "".join(f"{d['wins'][l]:>6}" for l in letters)
        print(row + f"{d['ties']:>7}{d['position_inconsistent']:>13}")
        for l in letters:
            total[l] += d["wins"][l]
    print("-" * len(head))
    print(f"{'TOTAL':16}" + "".join(f"{total[l]:>6}" for l in letters))
    # the premise-laden criterion, removed
    wo = {l: total[l] - res["criteria"]["verifiability"]["wins"][l] for l in letters}
    print(f"{'without verif.':16}" + "".join(f"{wo[l]:>6}" for l in letters))
    print(f"{'words':16}" + "".join(f"{res['words'][l]:>6}" for l in letters))
    print("=" * 78)
    print("`without verif.` drops the criterion written to favour an evidence-first system.")
    print("If the ranking tracks `words`, the ranking is of length.")


def main():
    ap = argparse.ArgumentParser(description="Blind pairwise battle over normalised outputs")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--norm-dir", default="comparison/normalized")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--judge-model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out = args.out or f"eval/out/battle_{args.paper}.json"
    run(args.paper, args.norm_dir, args.data_dir, args.judge_model, out)


if __name__ == "__main__":
    main()
