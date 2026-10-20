#!/usr/bin/env python3
"""Pilot v1: pairwise LLM judging of novelty reports, both orders, fully logged.

The protocol is fixed before the first call and is not adjusted afterwards -- a rubric or
a context chosen after seeing results measures the chooser. What it fixes:

CONTEXT PER CALL      the system prompt (eval/prompts/novelty_report_judge_v1.txt), the
                      submission, report A with its references, report B with its
                      references. Nothing else: no prior-work sources, no human
                      reference assessment, no traces, no earlier battle results. The
                      judge therefore rates REPORTS WITH SUBMISSION CONTEXT, which is
                      why criterion 1 is `submission_fidelity` and not "factuality":
                      without the prior-work sources, factual correctness about prior
                      work is not checkable and must not be claimed.

LINE IDS              every line of all three documents is prefixed S####/A####/B####,
                      so the judge can point at what decided a criterion. The prefix is
                      the only change; the text itself is untouched, never reformatted,
                      shortened or normalised. Length differences between systems are a
                      property of the systems and are reported, not edited away.

BOTH ORDERS           each pair is judged twice, X-as-A and X-as-B, in two independent
                      calls with no shared conversation. A preference only counts when it
                      survives the swap; anything else (including "A wins one way, tie the
                      other") is instability, not a result. Position bias decided 40% of
                      outcomes in an earlier experiment on this project.

SHUFFLED              the execution order of all calls is shuffled with a stored seed,
                      so a drift in the API over the session cannot align with one system
                      or one paper. The seed governs the experiment plan only -- nothing
                      about the model's generation.

VALIDATED             the response must be JSON with the five criteria, an allowed winner
                      value, and locators that actually exist in the supplied material.
                      A malformed or aborted call is a TECHNICAL ERROR: it is retried a
                      bounded number of times and every attempt is stored. It never
                      becomes an `unclear`, and retrying stops at the cap whether or not
                      the outcome is convenient.

Usage
-----
  python eval/pilot_judge.py --plan                       # show the call plan only
  python eval/pilot_judge.py --papers graphrag_when_to_use --pairs agent:linear
  python eval/pilot_judge.py                              # the whole pilot
"""
import argparse
import hashlib
import itertools
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                          # noqa: E402

load_dotenv()

PILOT_VERSION = "pilot_v1"
SEED = 42
JUDGE_MODEL = "gpt-5.6-terra"
JUDGE_EFFORT = "medium"
MAX_TOKENS = 16384
MAX_ATTEMPTS = 3

PROMPT_PATH = REPO / "eval" / "prompts" / "novelty_report_judge_v1.txt"
REPORT_DIR = REPO / "comparison" / "outputs"
OUT_DIR = REPO / "eval" / "out" / PILOT_VERSION

CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
            "conclusion_warrant", "reviewer_usefulness")
WINNERS = ("A", "B", "tie", "unclear")

# The `inventory` block rubric v5 asks for before the criteria (per report A and B).
INVENTORY_FIELDS = {
    "contributions_examined": ("all", "most", "some", "none"),
    "off_point_material": ("low", "medium", "high"),
    "repetition": ("low", "medium", "high"),
    "unsupported_or_contradicted": ("low", "medium", "high"),
}

# Internal ids only. The judge never sees them -- it sees "report A" and "report B".
SYSTEMS = ("agent", "linear", "opennovelty", "deepreviewer", "afzal")

USER_TEMPLATE = """Evaluate the two reports using the rubric in your system instructions.

<submission>
{submission}
</submission>

<report_a>
{report_a}
</report_a>

<report_b>
{report_b}
</report_b>"""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def with_line_ids(text: str, prefix: str) -> str:
    """Prefix every line with a running id. Content is not otherwise touched."""
    return "\n".join(f"{prefix}{i:04d} {ln}" for i, ln in enumerate(text.splitlines(), 1))


def report_path(paper: str, system: str) -> Path:
    return REPORT_DIR / f"{paper}__{system}.md"


def available_systems(paper: str) -> list:
    return [s for s in SYSTEMS if report_path(paper, s).exists()]


def build_plan(papers: list, pairs_filter: list) -> list:
    """Every unordered pair of the available systems, each in both orders, shuffled."""
    calls = []
    for paper in papers:
        systems = available_systems(paper)
        for x, y in itertools.combinations(systems, 2):
            if pairs_filter and {x, y} not in pairs_filter:
                continue
            calls.append({"paper_id": paper, "system_a": x, "system_b": y})
            calls.append({"paper_id": paper, "system_a": y, "system_b": x})
    random.Random(SEED).shuffle(calls)
    for i, c in enumerate(calls, 1):
        c["call_index"] = i
    return calls


def _locator_ids(*texts) -> set:
    ids = set()
    for t in texts:
        ids.update(re.findall(r"\b([SAB]\d{4})\b", t))
    return ids


def _inventory_problems(inv) -> list:
    if not isinstance(inv, dict):
        return ["no 'inventory' object"]
    problems = []
    cc = inv.get("central_contributions")
    if not (isinstance(cc, list) and cc and all(isinstance(x, str) and x.strip() for x in cc)):
        problems.append("inventory: central_contributions not a non-empty list of strings")
    for role in ("A", "B"):
        r = inv.get(role)
        if not isinstance(r, dict):
            problems.append(f"inventory: {role} missing")
            continue
        for field, allowed in INVENTORY_FIELDS.items():
            if r.get(field) not in allowed:
                problems.append(f"inventory: {role}.{field}={r.get(field)!r} not in {allowed}")
    return problems


def validate(parsed: dict, valid_ids: set, inventory: bool = False) -> list:
    """Structural problems, as a list of strings. Empty list = usable result.
    `inventory` (rubric v5): the response must also carry a well-formed inventory."""
    problems = _inventory_problems(parsed.get("inventory")) if inventory else []
    crit = parsed.get("criteria")
    if not isinstance(crit, dict):
        return problems + ["no 'criteria' object"]
    for name in CRITERIA:
        c = crit.get(name)
        if not isinstance(c, dict):
            problems.append(f"{name}: missing")
            continue
        w = c.get("winner")
        if w not in WINNERS:
            problems.append(f"{name}: winner={w!r} not in {WINNERS}")
        if not str(c.get("reason") or "").strip():
            problems.append(f"{name}: empty reason")
        locs = c.get("locators")
        if locs is None:
            problems.append(f"{name}: no locators field")
        elif not isinstance(locs, list):
            problems.append(f"{name}: locators not a list")
        else:
            # A locator that exists nowhere in the supplied material is a fabricated
            # reference to evidence; reported, not silently accepted.
            bad = [x for x in locs if isinstance(x, str)
                   and re.fullmatch(r"[SAB]\d{4}", x.strip()) and x.strip() not in valid_ids]
            if bad:
                problems.append(f"{name}: locators not in material: {bad[:5]}")
    extra = [k for k in crit if k not in CRITERIA]
    if extra:
        problems.append(f"unexpected criteria: {extra}")
    return problems


def _parse_json(text: str):
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t), ""
    except Exception as e:
        m = re.search(r"\{.*\}", t, re.S)      # a JSON object with prose around it
        if m:
            try:
                return json.loads(m.group(0)), f"recovered from surrounding text ({e})"
            except Exception as e2:
                return None, f"invalid JSON ({e2})"
        return None, f"invalid JSON ({e})"


def make_llm(service_tier: str | None = None, cache_breakpoints: bool = False,
             model: str | None = None, effort: str | None = None):
    """The judge model. Without arguments: exactly the pilot's request. `service_tier`
    ("flex") and `cache_breakpoints` change billing only: same model, effort, and token
    sequence (see `user_parts`). `model`/`effort` override JUDGE_MODEL/JUDGE_EFFORT (an E1
    config's judge_model/judge_effort)."""
    from langchain_openai import ChatOpenAI
    kw = {}
    if service_tier:
        kw["service_tier"] = service_tier
    if cache_breakpoints:
        # GPT-5.6+ writes the WHOLE prompt to the cache by default and bills that write at
        # 1.25x input. Explicit mode writes only up to the breakpoints set in user_parts.
        kw["extra_body"] = {"prompt_cache_options": {"mode": "explicit"}}
    return ChatOpenAI(model_name=model or JUDGE_MODEL, api_key=os.getenv("OPENAI_API_KEY"),
                      reasoning_effort=effort or JUDGE_EFFORT, max_tokens=MAX_TOKENS,
                      max_retries=0, timeout=900, **kw)


_BREAKPOINT = {"mode": "explicit"}


def user_parts(sub_txt: str, a_txt: str, b_txt: str) -> list:
    """USER_TEMPLATE as three text parts: [header + submission] [report A] [report B],
    with cache breakpoints after the first two. The parts concatenate to exactly the
    string USER_TEMPLATE.format(...) produces (asserted), and a message sent as text parts
    tokenizes identically to the single string -- measured 2026-09-24: same prompt token
    count, and the two forms hit each other's cache in full. So the judge reads the same
    tokens; only which prefix is cached (and billed as a cache read) changes."""
    pre, rest = USER_TEMPLATE.split("{submission}")
    mid_a, rest = rest.split("{report_a}")
    mid_b, end = rest.split("{report_b}")
    parts = [pre + sub_txt, mid_a + a_txt, mid_b + b_txt + end]
    assert "".join(parts) == USER_TEMPLATE.format(submission=sub_txt, report_a=a_txt, report_b=b_txt)
    return [{"type": "text", "text": parts[0], "prompt_cache_breakpoint": _BREAKPOINT},
            {"type": "text", "text": parts[1], "prompt_cache_breakpoint": _BREAKPOINT},
            {"type": "text", "text": parts[2]}]


def _is_capacity_429(e: Exception) -> bool:
    """Flex 'Resource Unavailable' or a rate limit: no model output was produced and
    nothing was billed. Not a quota error, which waiting cannot fix."""
    s = f"{type(e).__name__}: {e}"
    return ("429" in s or "RateLimit" in s) and "insufficient_quota" not in s


FLEX_WAITS = (30, 60, 120, 240, 480, 600, 600, 600, 600, 600)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def usage_counts(msg) -> dict:
    """Token counts of one response. Cache reads and writes come from the RAW usage
    (response_metadata.token_usage.prompt_tokens_details): langchain's usage_metadata has
    no cache writes, and on flex/priority it files the reads under `flex_cache_read` /
    `priority_cache_read` instead of `cache_read` -- which recorded 0 for the first flex
    calls (dreamphase, 2026-09-24; see billing_corrections.jsonl)."""
    meta = getattr(msg, "usage_metadata", None) or {}
    det = meta.get("input_token_details") or {}
    rmeta = getattr(msg, "response_metadata", {}) or {}
    ptd = (rmeta.get("token_usage") or {}).get("prompt_tokens_details") or {}
    read = ptd.get("cached_tokens")
    if read is None:
        read = next((v for k, v in det.items() if k.endswith("cache_read") and v), 0)
    reasoning = next((v for k, v in (meta.get("output_token_details") or {}).items()
                      if k.endswith("reasoning") and v), 0)
    return {"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0),
            "cache_tokens": read or 0, "cache_write_tokens": ptd.get("cache_write_tokens"),
            "reasoning_tokens": reasoning}


def run_call(llm, system_prompt: str, call: dict, docs: dict, cache_breakpoints: bool = False,
             cache_key: str | None = None, wait_on_429: bool = False,
             model: str | None = None, effort: str | None = None,
             inventory: bool = False) -> dict:
    """One judge call with its attempts. Returns the stored record.

    Defaults reproduce the pilot's request exactly. `cache_breakpoints` sends the same
    user text as three parts (see user_parts); `cache_key` routes the calls of one paper
    to the same cache; `wait_on_429` waits out flex capacity/rate-limit 429s (no output,
    not billed) instead of spending one of the MAX_ATTEMPTS on them. `model`/`effort` are
    what `llm` was built with (recorded; default JUDGE_MODEL/JUDGE_EFFORT); `inventory`
    makes a missing or malformed rubric-v5 inventory a technical error like any other."""
    from langchain_core.messages import HumanMessage, SystemMessage
    paper = call["paper_id"]
    sub_txt = docs[paper]["submission"]
    a_txt = docs[paper]["reports"][call["system_a"]]
    b_txt = docs[paper]["reports"][call["system_b"]]
    user = USER_TEMPLATE.format(submission=sub_txt, report_a=a_txt, report_b=b_txt)
    valid_ids = _locator_ids(sub_txt, a_txt, b_txt)
    if cache_breakpoints:
        messages = [SystemMessage(system_prompt), HumanMessage(content=user_parts(sub_txt, a_txt, b_txt))]
    else:
        messages = [("system", system_prompt), ("human", user)]
    invoke_kw = {"prompt_cache_key": cache_key} if cache_key else {}

    rec = {
        "pilot_version": PILOT_VERSION,
        "seed": SEED,
        "call_index": call["call_index"],
        "paper_id": paper,
        "system_a": call["system_a"],
        "system_b": call["system_b"],
        "submission_sha256": sha(sub_txt),
        "report_a_sha256": sha(a_txt),
        "report_b_sha256": sha(b_txt),
        "prompt_sha256": sha(system_prompt + "\n\n" + user),
        "system_prompt_sha256": sha(system_prompt),
        "requested_model": model or JUDGE_MODEL,
        "effort": effort or JUDGE_EFFORT,
        "thinking": "reasoning_effort",
        "max_tokens": MAX_TOKENS,
        "context_chars": {"submission": len(sub_txt), "report_a": len(a_txt),
                          "report_b": len(b_txt), "user_prompt": len(user)},
        "request_format": "text_parts_cache_breakpoints" if cache_breakpoints else "single_string",
        "attempts": [],
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        t0 = time.perf_counter()
        att = {"attempt": attempt, "started_at": _utc_now()}
        try:
            waits = 0
            while True:
                try:
                    msg = llm.invoke(messages, **invoke_kw)
                    break
                except Exception as e:  # noqa: BLE001
                    if not (wait_on_429 and _is_capacity_429(e) and waits < len(FLEX_WAITS)):
                        raise
                    print(f"    429 ({str(e)[:80]}) -- waiting {FLEX_WAITS[waits]}s, "
                          "not counted as an attempt", flush=True)
                    time.sleep(FLEX_WAITS[waits])
                    waits += 1
            if waits:
                att["capacity_waits"] = waits
            att["latency_s"] = round(time.perf_counter() - t0, 1)
            raw = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            rmeta = getattr(msg, "response_metadata", {}) or {}
            att.update({
                "raw_response": raw,
                "returned_model": rmeta.get("model_name", ""),
                "stop_reason": rmeta.get("finish_reason", ""),
                "service_tier": rmeta.get("service_tier"),
                "system_fingerprint": rmeta.get("system_fingerprint"),
                **usage_counts(msg),
            })
            parsed, note = _parse_json(raw)
            att["parse_note"] = note
            if parsed is None:
                att["technical_error"] = note or "unparseable response"
            else:
                problems = validate(parsed, valid_ids, inventory=inventory)
                att["validation_problems"] = problems
                if problems:
                    att["technical_error"] = "; ".join(problems)
                else:
                    att["parsed_result"] = parsed
        except Exception as e:
            att["latency_s"] = round(time.perf_counter() - t0, 1)
            att["technical_error"] = f"{type(e).__name__}: {e}"

        rec["attempts"].append(att)
        if "parsed_result" in att:
            rec["parsed_result"] = att["parsed_result"]
            rec["raw_response"] = att["raw_response"]
            rec["returned_model"] = att["returned_model"]
            rec["stop_reason"] = att["stop_reason"]
            rec["input_tokens"] = att["input_tokens"]
            rec["output_tokens"] = att["output_tokens"]
            rec["cache_tokens"] = att["cache_tokens"]
            rec["cache_write_tokens"] = att.get("cache_write_tokens")
            rec["service_tier"] = att.get("service_tier")
            rec["system_fingerprint"] = att.get("system_fingerprint")
            rec["reasoning_tokens"] = att.get("reasoning_tokens", 0)
            rec["latency_s"] = att["latency_s"]
            rec["n_attempts"] = attempt
            break
    else:
        # Out of attempts. Recorded as a technical failure with every attempt kept, and
        # excluded from the results rather than folded in as an "unclear" verdict.
        rec["failed"] = True
        rec["n_attempts"] = MAX_ATTEMPTS
    rec["started_at"] = rec["attempts"][0]["started_at"]
    rec["finished_at"] = _utc_now()
    return rec


def load_docs(papers: list) -> dict:
    """Submission and reports per paper, with line ids, hashed once.

    The submission text is identical for every battle on that paper: one file, read once,
    prefixed once. Reports are the systems' native outputs, unchanged.
    """
    docs = {}
    for paper in papers:
        sub_file = REPO / "eval" / "out" / PILOT_VERSION / f"{paper}__submission.txt"
        if not sub_file.exists():
            raise SystemExit(f"submission text missing: {sub_file}\n"
                             f"run eval/pilot_submission.py first")
        sub = with_line_ids(sub_file.read_text(encoding="utf-8"), "S")
        reports = {}
        for s in available_systems(paper):
            prefix = "A"        # replaced per call: the same report is A in one call, B in the other
            reports[s] = report_path(paper, s).read_text(encoding="utf-8")
        docs[paper] = {"submission": sub, "reports_raw": reports}
    return docs


def main():
    ap = argparse.ArgumentParser(description=f"{PILOT_VERSION}: pairwise report judging")
    ap.add_argument("--papers", default="graphrag_when_to_use,transducing_language_models")
    ap.add_argument("--pairs", default="", help="restrict to pairs, e.g. agent:linear,agent:afzal")
    ap.add_argument("--plan", action="store_true", help="print the call plan and exit")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N planned calls")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    papers = [p.strip() for p in args.papers.split(",") if p.strip()]
    pairs_filter = [set(p.split(":")) for p in args.pairs.split(",") if p.strip()]
    plan = build_plan(papers, pairs_filter)

    print(f"{PILOT_VERSION}: {len(plan)} calls, seed {SEED}, judge {JUDGE_MODEL} "
          f"(effort={JUDGE_EFFORT})")
    for paper in papers:
        print(f"  {paper}: systems = {', '.join(available_systems(paper))}")
    if args.plan:
        for c in plan:
            print(f"  #{c['call_index']:02d} {c['paper_id'][:28]:28} "
                  f"A={c['system_a']:12} B={c['system_b']}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    docs = load_docs(papers)
    llm = make_llm()

    if args.limit:
        plan = plan[:args.limit]

    out_path = Path(args.out) if args.out else OUT_DIR / "judge_calls.jsonl"
    done = set()
    if out_path.exists():
        for ln in out_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                if not r.get("failed"):
                    done.add((r["paper_id"], r["system_a"], r["system_b"]))
            except Exception:
                continue
        if done:
            print(f"  resuming: {len(done)} calls already recorded in {out_path.name}")

    with out_path.open("a", encoding="utf-8") as fh:
        for c in plan:
            key = (c["paper_id"], c["system_a"], c["system_b"])
            if key in done:
                continue
            # Line ids are per ROLE (A/B), so the same report gets A-ids in one order and
            # B-ids in the other -- the judge's locators then always name the role it saw.
            per_call = {c["paper_id"]: {
                "submission": docs[c["paper_id"]]["submission"],
                "reports": {
                    c["system_a"]: with_line_ids(
                        docs[c["paper_id"]]["reports_raw"][c["system_a"]], "A"),
                    c["system_b"]: with_line_ids(
                        docs[c["paper_id"]]["reports_raw"][c["system_b"]], "B"),
                },
            }}
            rec = run_call(llm, system_prompt, c, per_call)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if rec.get("failed"):
                print(f"  #{c['call_index']:02d} {c['paper_id'][:20]:20} "
                      f"{c['system_a']}/{c['system_b']}: TECHNICAL FAILURE after "
                      f"{rec['n_attempts']} attempts", flush=True)
            else:
                w = {k: v["winner"] for k, v in rec["parsed_result"]["criteria"].items()}
                print(f"  #{c['call_index']:02d} {c['paper_id'][:20]:20} "
                      f"A={c['system_a']:11} B={c['system_b']:11} "
                      f"{rec['input_tokens']:>7} in / {rec['output_tokens']:>5} out, "
                      f"{rec['latency_s']:>5}s | "
                      + " ".join(f"{k[:4]}={v}" for k, v in w.items()), flush=True)

    print(f"\nwritten: {out_path}")


if __name__ == "__main__":
    main()
