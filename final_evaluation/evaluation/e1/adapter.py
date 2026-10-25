"""E1: the LLM judge over the study's FROZEN inputs -- plan first, run only on request."""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import random
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
FE_ROOT = REPO_ROOT / "final_evaluation"

SYSTEMS = ("agent", "linear", "opennovelty", "deepreviewer", "afzal")

CHARS_PER_TOKEN = 3.45
OUTPUT_TOKENS_PER_CALL = 1200
PRICE_PER_1K = {"gpt-5.6-terra": (0.0020, 0.0120), "gpt-6.1-sol": (0.0020, 0.0100)}

CACHE_WRITE_X, CACHE_READ_X, LONG_CONTEXT = 1.25, 0.10, 272_000
CACHE_READ_X_BY_MODEL = {"gpt-6.1-sol": 0.05}


def billed_usd(rec: dict, model: str = "gpt-5.6-terra") -> float | None:
    """What one recorded call was billed, from its own usage counts. Needs the cache_write_tokens the judge records since 2026-09-24; None for older records."""
    if rec.get("failed") or rec.get("cache_write_tokens") is None or model not in PRICE_PER_1K:
        return None
    pin, pout = (p * 1000 for p in PRICE_PER_1K[model])
    if rec.get("service_tier") in ("flex", "batch"):
        pin, pout = pin / 2, pout / 2
    t, read, write = rec["input_tokens"], rec.get("cache_tokens") or 0, rec["cache_write_tokens"]
    m_in, m_out = (2.0, 1.5) if t > LONG_CONTEXT else (1.0, 1.0)
    plain = t - read - write
    read_x = CACHE_READ_X_BY_MODEL.get(model, CACHE_READ_X)
    return ((plain + write * CACHE_WRITE_X + read * read_x) * pin * m_in
            + rec["output_tokens"] * pout * m_out) / 1e6


def cache_order(calls: list) -> list:
    """The execution order for prompt caching: all calls of a paper back to back, and within a paper the calls that share report A back to back (they share the cached prefix rubric + submission + report A). No new randomness: papers, A-groups and the calls inside a group keep the relative order of the seeded shuffle. A drift of the API can then align with a paper -- all ten pairs of which run within minutes under the same conditions -- but not with a system."""
    papers, groups = {}, {}
    for c in calls:
        papers.setdefault(c["paper_id"], len(papers))
        groups.setdefault((c["paper_id"], c["system_a"]), len(groups))
    return sorted(calls, key=lambda c: (papers[c["paper_id"]], groups[(c["paper_id"], c["system_a"])]))


def _judge():
    """eval/pilot_judge.py -- the one judge implementation. Importing it makes no call."""
    if str(REPO_ROOT / "eval") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "eval"))
    import pilot_judge
    return pilot_judge


def _yaml(path: str) -> dict:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8")) or {}


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _report_file(input_dir: str, paper: str, system: str) -> Path:
    d = FE_ROOT / "inputs" / input_dir / paper
    md = d / f"{system}.md"
    if md.is_file():
        return md
    e1 = d / f"{system}.e1_text.md"
    if e1.is_file():
        return e1
    raise FileNotFoundError(f"no text input for {input_dir}/{paper}/{system} -- run import-pilot first")


def _submission_file(input_dir: str, paper: str) -> Path:
    return FE_ROOT / "inputs" / input_dir / paper / "submission.txt"


def _content_versions(input_dir: str) -> dict:
    """{(paper, system): content_version} from the import manifest -- the same string the dashboard stores on each report and the admin export writes to manifest.json."""
    p = FE_ROOT / "manifests" / input_dir / "reports.json"
    if not p.is_file():
        return {}
    m = json.loads(p.read_text(encoding="utf-8"))
    return {(paper, s): r.get("content_version")
            for paper, e in (m.get("papers") or {}).items()
            for s, r in (e.get("systems") or {}).items() if not r.get("blocker")}


def _prompt_chars(input_dir: str, paper: str, a: str, b: str, rubric_chars: int) -> int:
    """Characters the judge receives: rubric + the three documents with their line ids (`S0001 ` = 6 extra characters per line)."""
    n = rubric_chars
    for p in (_submission_file(input_dir, paper), _report_file(input_dir, paper, a),
              _report_file(input_dir, paper, b)):
        t = p.read_text(encoding="utf-8")
        n += len(t) + 6 * (t.count("\n") + 1)
    return n


def _call(input_dir, paper, a, b, role, human_task, versions, rubric_chars) -> dict:
    problems = []
    if not _submission_file(input_dir, paper).is_file():
        problems.append(f"no submission.txt for {input_dir}/{paper}")
    for s in (a, b):
        try:
            _report_file(input_dir, paper, s)
        except FileNotFoundError as e:
            problems.append(str(e))
    return {
        "paper_id": paper, "system_a": a, "system_b": b, "input_dir": input_dir,
        "paper_set": role, "human_task": human_task,
        "content_version_a": versions.get((paper, a)), "content_version_b": versions.get((paper, b)),
        "ready": not problems, "problems": problems,
        "prompt_chars": (_prompt_chars(input_dir, paper, a, b, rubric_chars)
                         if not problems else 0),
    }


def _plan_pilot(config_path: str, cfg: dict) -> dict:
    input_dir = cfg.get("inputs_dir") or "pilot"
    rubric_version = cfg["study"]["rubric_version"]
    rubric_chars = len((FE_ROOT / "prompts" / f"{rubric_version}.txt").read_text(encoding="utf-8"))
    versions = _content_versions(input_dir)
    calls = []
    for t in cfg["tasks"]:
        paper, (x, y) = t["paper"], t["pair"]
        for a, b in ((x, y), (y, x)):
            calls.append(_call(input_dir, paper, a, b, input_dir, True, versions, rubric_chars))
    for i, c in enumerate(calls, 1):
        c["call_index"] = i
    return {"mode": "pilot", "e1_id": "dashboard_pilot_v1_e1", "config_path": config_path,
            "rubric_version": rubric_version, "seed": None, "problems": [],
            "paper_sets": [{"config": config_path, "role": input_dir, "input_dir": input_dir,
                            "papers": list(cfg["papers"])}],
            "expected_papers": len(cfg["papers"]), "calls": calls,
            "default_out_dir": "final_evaluation/results/pilot/e1"}


def _plan_main(config_path: str, cfg: dict) -> dict:
    e1 = cfg["e1"]
    rubric_version = e1["rubric_version"]
    rubric_chars = len((FE_ROOT / "prompts" / f"{rubric_version}.txt").read_text(encoding="utf-8"))
    systems = list(e1.get("systems") or SYSTEMS)
    problems, sets, seen, calls = [], [], {}, []

    for ps in cfg["paper_sets"]:
        scfg = _yaml(ps["config"])
        input_dir = scfg.get("inputs_dir") or "pilot"
        role = ps.get("role") or input_dir
        study_rubric = (scfg.get("study") or {}).get("rubric_version")
        if study_rubric and study_rubric != rubric_version:
            problems.append(f"{ps['config']}: its study uses {study_rubric}, E1 uses "
                            f"{rubric_version} -- judge and raters would not read the same rubric")
        human_pairs = {(t["paper"], frozenset(t["pair"])) for t in (scfg.get("tasks") or [])}
        versions = _content_versions(input_dir)
        papers = list(scfg.get("papers") or {})
        sets.append({"config": ps["config"], "role": role, "input_dir": input_dir,
                     "papers": papers})
        for paper in papers:
            if paper in seen:
                problems.append(f"{paper}: listed in {seen[paper]} and {ps['config']}")
                continue
            seen[paper] = ps["config"]
            for x, y in itertools.combinations(systems, 2):
                human = (paper, frozenset((x, y))) in human_pairs
                for a, b in ((x, y), (y, x)):
                    calls.append(_call(input_dir, paper, a, b, role, human, versions, rubric_chars))

    expected = e1.get("expected_papers")
    if expected and len(seen) != expected:
        problems.append(f"{len(seen)} of {expected} papers configured")
    random.Random(int(e1.get("seed", 42))).shuffle(calls)
    for i, c in enumerate(calls, 1):
        c["call_index"] = i
    return {"mode": "main", "e1_id": e1["id"], "config_path": config_path,
            "rubric_version": rubric_version,
            "seed": int(e1.get("seed", 42)),
            "model": e1.get("judge_model"), "effort": e1.get("judge_effort"),
            "inventory": bool(e1.get("inventory")),
            "problems": problems, "paper_sets": sets, "expected_papers": expected,
            "calls": calls,
            "default_out_dir": e1.get("out_dir") or "final_evaluation/results/main/e1"}


def build_plan(config_path: str, papers: str = "", pairs: str = "") -> dict:
    """`papers` ("a,b") and `pairs` ("agent:linear,agent:afzal") narrow the plan, e.g. for a smoke run; call indices stay those of the full plan."""
    cfg = _yaml(config_path)
    plan = _plan_main(config_path, cfg) if "e1" in cfg else _plan_pilot(config_path, cfg)
    plan["rubric_path"] = f"final_evaluation/prompts/{plan['rubric_version']}.txt"
    pj = _judge()
    plan["model"] = plan.get("model") or pj.JUDGE_MODEL
    plan["effort"] = plan.get("effort") or pj.JUDGE_EFFORT
    plan.setdefault("inventory", False)
    plan["n_calls_full"] = len(plan["calls"])
    want_p = {p.strip() for p in papers.split(",") if p.strip()}
    want_s = [frozenset(p.split(":")) for p in pairs.split(",") if p.strip()]
    if want_p:
        plan["calls"] = [c for c in plan["calls"] if c["paper_id"] in want_p]
    if want_s:
        plan["calls"] = [c for c in plan["calls"]
                         if frozenset((c["system_a"], c["system_b"])) in want_s]
    plan["filtered"] = bool(want_p or want_s)
    return plan


def _estimate(plan: dict, calls: list) -> dict:
    tin = sum(c["prompt_chars"] for c in calls) / CHARS_PER_TOKEN
    tout = OUTPUT_TOKENS_PER_CALL * len(calls)
    pin, pout = PRICE_PER_1K.get(plan["model"], (None, None))
    usd = (tin / 1000 * pin + tout / 1000 * pout) if pin is not None else None
    biggest = max(calls, key=lambda c: c["prompt_chars"], default=None)
    return {"input_tokens": round(tin), "output_tokens": tout, "usd": usd,
            "largest_call": biggest}


def print_plan(plan: dict, verbose: bool = False) -> None:
    calls = plan["calls"]
    print(f"E1 plan ({plan['mode']}, {plan['e1_id']}): {len(calls)} calls"
          + (f" of {plan['n_calls_full']} (filtered)" if plan["filtered"] else "")
          + f", rubric={plan['rubric_path']}, model={plan['model']} (effort={plan['effort']})"
          + (f", seed={plan['seed']}" if plan["seed"] is not None else ""))
    if plan["inventory"]:
        print("  the response must carry an inventory")
    for s in plan["paper_sets"]:
        print(f"  paper set {s['role']:12} {len(s['papers']):2} papers  "
              f"(inputs/{s['input_dir']}/, {s['config']})")
    n_papers = len({c["paper_id"] for c in calls})
    print(f"  papers in plan: {n_papers}"
          + (f" of {plan['expected_papers']} planned" if plan.get("expected_papers") else ""))

    by_paper = {}
    for c in calls:
        d = by_paper.setdefault(c["paper_id"], {"n": 0, "ready": 0, "human": 0,
                                                "set": c["paper_set"], "problems": set()})
        d["n"] += 1
        d["ready"] += c["ready"]
        d["human"] += c["human_task"]
        d["problems"].update(c["problems"])
    print()
    for paper, d in sorted(by_paper.items()):
        status = "ready" if d["ready"] == d["n"] else f"{d['n'] - d['ready']} NOT READY"
        print(f"  {paper[:44]:44} {d['set']:12} {d['n']:3} calls, "
              f"{d['human']:2} on human tasks, {status}")
        for p in sorted(d["problems"]):
            print(f"      - {p}")
    if verbose:
        print()
        for c in calls:
            status = "ready" if c["ready"] else "NOT READY: " + "; ".join(c["problems"])
            print(f"  #{c['call_index']:03d} {c['paper_id'][:34]:34} A={c['system_a']:12} "
                  f"B={c['system_b']:12} {'H' if c['human_task'] else ' '} {status}")

    ready = [c for c in calls if c["ready"]]
    print(f"\n  ready: {len(ready)}/{len(calls)}; on human tasks: "
          f"{sum(c['human_task'] for c in calls)} (both orders)")
    if ready:
        est = _estimate(plan, ready)
        big = est["largest_call"]
        print(f"  estimate for the ready calls: ~{est['input_tokens'] / 1e6:.1f}M input + "
              f"~{est['output_tokens'] / 1e3:.0f}k output tokens"
              + (f" = ~${est['usd']:.0f}" if est["usd"] is not None else "")
              + f"  (largest call: ~{big['prompt_chars'] / CHARS_PER_TOKEN / 1e3:.0f}k tokens, "
                f"{big['paper_id']} {big['system_a']}/{big['system_b']})")
        print("  (estimate from the pilot's measured characters-per-token and output length, at "
              "the standard list price without cache effects; --execute runs on flex with cache "
              "breakpoints, which bills roughly a fifth of it. The run records the real counts "
              "and the billed USD per call.)")
    if plan["problems"]:
        print(f"\n  {len(plan['problems'])} PROBLEM(S):")
        for p in plan["problems"]:
            print(f"    - {p}")


def _load_done(out_path: Path, plan: dict) -> set:
    done = set()
    if not out_path.exists():
        return done
    for ln in out_path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("e1_id") != plan["e1_id"] or r.get("rubric_version") != plan["rubric_version"]:
            raise SystemExit(
                f"{out_path} holds calls of {r.get('e1_id')!r} / {r.get('rubric_version')!r}, "
                f"not {plan['e1_id']!r} / {plan['rubric_version']!r} -- results are never mixed "
                "or overwritten. Pass a different --out-dir.")
        if not r.get("failed"):
            done.add((r["paper_id"], r["system_a"], r["system_b"]))
    return done


def execute_plan(plan: dict, out_dir: str | None = None, limit: int = 0,
                 service_tier: str = "flex", cache: bool = True) -> None:
    """Runs the calls for real. Never called by the web app -- only by this CLI with --execute. Every call goes through eval/pilot_judge.run_call, so the same JSON-shape and locator checks and the same bounded retries apply as in the original pilot run."""
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set -- refusing to execute E1 calls. "
                         "(Plan mode needs no key; this message only appears with --execute.)")
    if plan["problems"] and not plan["filtered"]:
        raise SystemExit("plan has problems -- fix them, or narrow the run with --papers/--pairs:\n  "
                         + "\n  ".join(plan["problems"]))
    pj = _judge()
    rubric_path = REPO_ROOT / plan["rubric_path"]
    rubric = rubric_path.read_text(encoding="utf-8")
    llm = pj.make_llm(service_tier=service_tier or None, cache_breakpoints=cache,
                      model=plan["model"], effort=plan["effort"])

    out_path = REPO_ROOT / (out_dir or plan["default_out_dir"]) / "judge_calls.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _load_done(out_path, plan)
    todo = [c for c in plan["calls"] if c["ready"]
            and (c["paper_id"], c["system_a"], c["system_b"]) not in done]
    if cache:
        todo = cache_order(todo)
    skipped = [c for c in plan["calls"] if not c["ready"]]
    if limit:
        todo = todo[:limit]
    print(f"{len(done)} already recorded, {len(todo)} to run, {len(skipped)} not ready "
          f"-> {out_path}  [tier={service_tier or 'standard'}, cache breakpoints={cache}]")
    usd_total = 0.0

    with out_path.open("a", encoding="utf-8") as fh:
        for c in todo:
            paper, d = c["paper_id"], c["input_dir"]
            sub_p = _submission_file(d, paper)
            a_p, b_p = _report_file(d, paper, c["system_a"]), _report_file(d, paper, c["system_b"])
            call = {"paper_id": paper, "system_a": c["system_a"], "system_b": c["system_b"],
                    "call_index": c["call_index"]}
            docs = {paper: {
                "submission": pj.with_line_ids(sub_p.read_text(encoding="utf-8"), "S"),
                "reports": {c["system_a"]: pj.with_line_ids(a_p.read_text(encoding="utf-8"), "A"),
                            c["system_b"]: pj.with_line_ids(b_p.read_text(encoding="utf-8"), "B")}}}
            rec = pj.run_call(llm, rubric, call, docs, cache_breakpoints=cache,
                              cache_key=f"{plan['e1_id']}:{d}:{paper}" if cache else None,
                              wait_on_429=service_tier == "flex",
                              model=plan["model"], effort=plan["effort"],
                              inventory=plan["inventory"])
            rec.pop("pilot_version", None)
            usd = billed_usd(rec, plan["model"])
            usd_total += usd or 0.0
            rec.update({
                "service_tier_requested": service_tier or "standard",
                "execution_order": "cache_order(seed shuffle)" if cache else "seed shuffle",
                "billed_usd": None if usd is None else round(usd, 5),
                "e1_id": plan["e1_id"], "rubric_version": plan["rubric_version"],
                "rubric_file_sha256": _sha_file(rubric_path), "plan_seed": plan["seed"],
                "input_dir": d, "paper_set": c["paper_set"], "human_task": c["human_task"],
                "content_version_a": c["content_version_a"],
                "content_version_b": c["content_version_b"],
                "submission_file": sub_p.name, "submission_file_sha256": _sha_file(sub_p),
                "report_a_file": a_p.name, "report_a_file_sha256": _sha_file(a_p),
                "report_b_file": b_p.name, "report_b_file_sha256": _sha_file(b_p),
            })
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if rec.get("failed"):
                print(f"#{c['call_index']:03d} {paper[:28]} {c['system_a']}/{c['system_b']}: "
                      f"TECHNICAL FAILURE after {rec['n_attempts']} attempts", flush=True)
            else:
                w = {k: v["winner"] for k, v in rec["parsed_result"]["criteria"].items()}
                print(f"#{c['call_index']:03d} {paper[:28]:28} A={c['system_a']:12} "
                      f"B={c['system_b']:12} {rec['input_tokens']:>7} in "
                      f"(read {rec.get('cache_tokens') or 0:>6}, write {rec.get('cache_write_tokens') or 0:>6}) "
                      f"{rec.get('service_tier') or '?':7} ${usd or 0:.3f} | "
                      + " ".join(f"{k[:4]}={v}" for k, v in w.items()), flush=True)
    print(f"\nwritten: {out_path}  (billed this session: ${usd_total:.2f})")
