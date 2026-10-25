#!/usr/bin/env python3
"""Get the human-study papers ready for the review runs, and say what still needs a human.

`human_study/paper/*.pdf` are the submissions, `human_study/OpenNovelty/*.pdf` the
authors' own reports for the same papers. This script does the deterministic part:

  1. assigns each PDF a stable submission id (and paper_key for the study config),
  2. matches each OpenNovelty report to its paper by title, reporting anything ambiguous
     rather than picking by mtime -- the same rule `inventory.py` applies,
  3. runs the orchestrator's four preparation stages per paper
     (document_processing -> claim_extraction -> retrieval -> fetch_pdfs),
  4. prints a readiness table.

It deliberately STOPS before the agent and linear runs. Two things have to be looked at by
a person first, and both are cheap to fix now and expensive to discover afterwards:

  publication date   Retrieval's cutoff is the submission's FIRST-disclosure date. A paper
                     whose date fell back to today admits later work as "prior work", which
                     silently corrupts every comparison for it. Flagged as DATE? below.
  claims             Everything downstream is per claim. `--no-hitl` auto-approves the
                     extraction, so the claim count and wording are worth reading once
                     before spending the agent budget on them.

Then, per paper:

    python eval/run_pilot.py --submission <id> --variant both

Usage
-----
  python eval/human_study_prep.py --status          # table only, runs nothing
  python eval/human_study_prep.py --run             # prepare every paper not yet done
  python eval/human_study_prep.py --run --only astabench,hubble
  python eval/human_study_prep.py --write-sources final_evaluation/config/sources.main.yaml

The ten E1-only papers live elsewhere; every call above takes
  --papers-dir "<dir>/paper" --opennovelty-dir "<dir>/opennovelty"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HS = REPO / "human_study"
PAPERS = HS / "paper"
OPENNOVELTY = HS / "OpenNovelty"
DATA = REPO / "data"

#: Long enough to stay readable, short enough for a path and a config key.
_KEY_MAX = 46


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if len(s) <= _KEY_MAX:
        return s
    # Cut on a word boundary rather than mid-token, so the key stays recognisable.
    return s[:_KEY_MAX].rsplit("_", 1)[0]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def opennovelty_index() -> dict:
    """{stem-of-title: path} for the authors' reports, from their filename convention."""
    out = {}
    for p in sorted(OPENNOVELTY.glob("*.pdf")):
        m = re.match(r"novelty_report_(?:lightweight_)?(.+?)_\d{8}", p.stem)
        out[_norm(m.group(1) if m else p.stem)] = p
    return out


def match_opennovelty(paper_pdf: Path, index: dict) -> tuple[Path | None, str]:
    """(report, note). Their filename carries a TRUNCATED title, so this matches on the
    shorter of the two normalised strings -- and reports every tie instead of choosing."""
    want = _norm(paper_pdf.stem)
    hits = []
    for key, path in index.items():
        n = min(len(key), len(want))
        if key[:n] == want[:n]:
            hits.append(path)
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, "no OpenNovelty report matched this title"
    return None, f"AMBIGUOUS: {len(hits)} reports match ({', '.join(h.name for h in hits)})"


def plan() -> list[dict]:
    rows = []
    index = opennovelty_index()
    for pdf in sorted(PAPERS.glob("*.pdf")):
        report, note = match_opennovelty(pdf, index)
        rows.append({"key": slug(pdf.stem), "pdf": pdf, "opennovelty": report,
                     "opennovelty_note": note})
    return rows


# ------------------------------------------------------------------- status --

def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


#: orchestrator.STAGES, by the output each one leaves behind.
_STAGE_OUTPUT = (
    ("document_processing", "{k}_quality.json"),
    ("claim_extraction", "{k}_claims.json"),
    ("retrieval", "related_work_data/ranked_papers.json"),
    ("fetch_pdfs", "{k}_pdf_status.json"),
)


def status_of(key: str) -> dict:
    sub = DATA / key
    meta = _load(sub / f"{key}.json") or {}
    quality = _load(sub / f"{key}_quality.json") or {}
    claims_doc = _load(sub / f"{key}_claims.json") or {}
    pool = _load(sub / "related_work_data" / "ranked_papers.json") or []
    claims = [c for c in claims_doc.get("claims", []) or [] if c.get("status") != "rejected"]
    # "Prepared" means all FOUR stages left their output -- not merely that document
    # processing wrote {key}.json. A paper that parsed and then died in claim extraction
    # would otherwise look done and be skipped on every resume, silently entering the
    # agent runs with no claims. GROBID dying mid-batch makes that a likely shape of
    # failure, not a hypothetical one.
    done = [n for n, rel in _STAGE_OUTPUT if (sub / rel.format(k=key)).exists()]
    state = _load(sub / f"{key}_pipeline_state.json") or {}
    gates = quality.get("gates") or quality
    failed = [g for g, ok in gates.items() if isinstance(ok, bool) and not ok]
    return {
        "processed": len(done) == len(_STAGE_OUTPUT),
        "stages_done": done,
        "partial": bool(done) and len(done) < len(_STAGE_OUTPUT),
        "last_error": (state.get("last_error") or "")[:70],
        "title": (meta.get("title") or "")[:44],
        "date": meta.get("publication_date") or "",
        "date_source": meta.get("date_source") or "",
        "date_needs_review": bool(meta.get("date_needs_review")),
        "title_needs_review": bool(meta.get("title_needs_review")),
        "failed_gates": failed,
        "n_claims": len(claims),
        "pool": len(pool),
        "agent": (sub / f"{key}_artifact_a_agent.json").is_file(),
        "linear": (sub / f"{key}_artifact_a_linear.json").is_file(),
        "afzal": (sub / "novelty_delta_analysis.txt").is_file() and (sub / "summary.txt").is_file(),
    }


def print_table(rows: list[dict]) -> None:
    print(f"{'paper_key':<46} {'ON':<3} {'prep':<5} {'date':<12} {'cl':>3} {'pool':>5} "
          f"{'A':<2}{'L':<2}{'Az':<3} flags")
    print("-" * 118)
    todo_prep, needs_human = [], []
    for r in rows:
        st = status_of(r["key"])
        flags = []
        if r["opennovelty"] is None:
            flags.append("NO-OPENNOVELTY" if not r["opennovelty_note"].startswith("AMB")
                         else "ON-AMBIGUOUS")
        if st["processed"]:
            if st["date_needs_review"] or st["date_source"] == "today_fallback":
                flags.append("DATE?")
            if st["title_needs_review"]:
                flags.append("TITLE?")
            if st["failed_gates"]:
                flags.append("GATES:" + ",".join(st["failed_gates"]))
            if st["n_claims"] == 0:
                flags.append("NO-CLAIMS")
        else:
            todo_prep.append(r["key"])
            if st["partial"]:
                flags.append("PARTIAL:" + "+".join(x[:5] for x in st["stages_done"]))
            if st["last_error"]:
                flags.append("err(" + st["last_error"].split(":")[0] + ")")
        if any(f in flags for f in ("DATE?", "TITLE?", "NO-CLAIMS")) or \
                any(f.startswith("GATES") for f in flags):
            needs_human.append(r["key"])
        print(f"{r['key']:<46} {'ok' if r['opennovelty'] else '--':<3} "
              f"{('ok' if st['processed'] else (str(len(st['stages_done'])) + '/4' if st['partial'] else '--')):<5} "
              f"{(st['date'] or '-'):<12} {st['n_claims']:>3} {st['pool']:>5} "
              f"{'A' if st['agent'] else '.':<2}{'L' if st['linear'] else '.':<2}"
              f"{'Az' if st['afzal'] else '.':<3} {' '.join(flags)}")
    print("-" * 118)
    print(f"{len(rows)} papers | prep outstanding: {len(todo_prep)} | "
          f"needs a look before the agent runs: {len(needs_human)}")
    if needs_human:
        print("  ->", ", ".join(needs_human))
    print("\nLegend: ON=OpenNovelty report found, prep=stages 1-4 done, cl=claims, "
          "A/L/Az=agent/linear/afzal artifacts present.")
    print("DATE? means retrieval's prior-work cutoff is unreliable for that paper -- fix "
          "the date before running the agent, or its comparisons are not trustworthy.")


# --------------------------------------------------------------------- run --

def grobid_alive(url: str, timeout: float = 4.0) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(url.rstrip("/") + "/api/isalive", timeout=timeout).read()
        return True
    except Exception:
        return False


def wait_for_grobid(url: str, seconds: int) -> bool:
    """GROBID dying mid-batch cost seven papers once. With `--restart unless-stopped`
    Docker brings it back in a few seconds, so waiting beats aborting the run."""
    import time
    if grobid_alive(url):
        return True
    print(f"  GROBID is down -- waiting up to {seconds}s for it to come back", flush=True)
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(5)
        if grobid_alive(url):
            print("  GROBID is back", flush=True)
            return True
    return False


def prepare(row: dict, model: str, grobid: str, k: int, wait: int = 0) -> bool:
    key, pdf = row["key"], row["pdf"]
    cmd = [sys.executable, str(REPO / "src" / "novelty_assessment" / "orchestrator.py"),
           "--data-dir", str(DATA), "--submission-id", key, "--pdf", str(pdf),
           "--model", model, "--grobid-server", grobid, "--no-hitl"]
    for attempt in (1, 2):
        if not wait_for_grobid(grobid, wait if attempt == 1 else max(wait, 60)):
            print(f"\n=== {key} === SKIPPED: GROBID unreachable at {grobid}", flush=True)
            return False
        print(f"\n=== {key} ==={'  (retry)' if attempt == 2 else ''}\n"
              f"{' '.join(cmd[-12:])}", flush=True)
        if subprocess.run(cmd, cwd=str(REPO)).returncode == 0:
            return True
        # The orchestrator is resumable and idempotent, so a second attempt picks up at
        # the stage that failed rather than redoing the ones that succeeded. Only worth
        # it when GROBID is what went away; a real parse failure fails the same way twice.
        if attempt == 1 and not grobid_alive(grobid):
            print(f"  {key} failed and GROBID is gone -- retrying once", flush=True)
            continue
        return False
    return False


def write_sources(rows: list[dict], out_path: Path) -> None:
    """A starting sources.yaml: what is unambiguous is filled in, the rest is left as a
    TODO with the reason. Never invents a resolution -- same contract as the pilot's."""
    lines = [
        "# Source resolution for the human study. Generated by eval/human_study_prep.py;",
        "# every TODO below needs a human decision, and nothing here was picked by mtime.",
        "#",
        "# deepreviewer: point `file` at final_report_review_only.pdf (produced by",
        "#   eval/deepreviewer_review_pdf.py) -- DeepReviewer's own final_report.pdf",
        "#   appends the full annotated submission and is ~4x longer than every other",
        "#   report in the study.",
        "",
    ]
    for r in rows:
        key = r["key"]
        lines.append(f"{key}:")
        lines.append(f"  submission:")
        # `pdf:` and `text:` are the key names import_pilot._import_submission reads.
        lines.append(f"    pdf: \"{r['pdf'].relative_to(REPO).as_posix()}\"")
        lines.append(f"    # TODO: text: the frozen submission text the E1 judge reads.")
        lines.append(f"    #   The pilot took MinerU's markdown from the DeepReviewer job")
        lines.append(f"    #   dir, because GROBID's section text drops display equations")
        lines.append(f"    #   and table bodies and the judge checks claims about the")
        lines.append(f"    #   submission against the submission. Same parser for every")
        lines.append(f"    #   paper, so resolve this only once DeepReviewer has run.")
        for variant in ("agent", "linear"):
            # Rendered fresh at import time from these two artifacts; their hashes and the
            # renderer's own go into the frozen content_version, so the paths belong here.
            lines.append(f"  {variant}:")
            lines.append(f"    kind: rendered")
            lines.append(f"    renderer: battle_export.build")
            lines.append(f"    variant: {variant}")
            lines.append(f"    artifact_a: data/{key}/{key}_artifact_a_{variant}.json")
            lines.append(f"    artifact_b: data/{key}/{key}_artifact_b_{variant}.json")
        lines.append(f"  opennovelty:")
        if r["opennovelty"]:
            lines.append(f"    kind: native_pdf")
            lines.append(f"    path: \"{r['opennovelty'].relative_to(REPO).as_posix()}\"")
            lines.append(f"    resolution_note: matched by title against the authors' filename")
        else:
            lines.append(f"    # TODO: {r['opennovelty_note']}")
        lines.append(f"  deepreviewer:")
        lines.append(f"    kind: deepreviewer_job")
        lines.append(f"    # TODO: job_dir: DeepReviewer-v2/data/jobs/<id>")
        lines.append(f"    file: final_report_review_only.pdf")
        lines.append(f"  afzal:")
        lines.append(f"    kind: concat_text")
        lines.append(f"    parts:")
        lines.append(f"      - data/{key}/summary.txt")
        lines.append(f"      - \"---\"")
        lines.append(f"      - data/{key}/novelty_delta_analysis.txt")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes("\n".join(lines).encode("utf-8"))
    print(f"written: {out_path.relative_to(REPO)}  ({len(rows)} papers, "
          f"{sum(1 for r in rows if not r['opennovelty'])} OpenNovelty TODOs, "
          f"{len(rows)} DeepReviewer TODOs)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true", help="print the table and exit")
    ap.add_argument("--run", action="store_true", help="prepare every paper not yet processed")
    ap.add_argument("--only", default="", help="comma-separated paper_keys")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--grobid-server", default="http://localhost:8070")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--write-sources", default="", help="write a sources.yaml skeleton here")
    ap.add_argument("--papers-dir", default="", help="submission PDFs (default human_study/paper)")
    ap.add_argument("--opennovelty-dir", default="",
                    help="OpenNovelty reports (default human_study/OpenNovelty)")
    args = ap.parse_args()
    global PAPERS, OPENNOVELTY
    if args.papers_dir:
        PAPERS = (REPO / args.papers_dir).resolve()
    if args.opennovelty_dir:
        OPENNOVELTY = (REPO / args.opennovelty_dir).resolve()

    if not PAPERS.is_dir():
        print(f"missing {PAPERS.relative_to(REPO)}")
        return 2
    rows = plan()
    if not rows:
        print("no PDFs found")
        return 1
    if args.only:
        want = {k.strip() for k in args.only.split(",") if k.strip()}
        rows = [r for r in rows if r["key"] in want]
        if not rows:
            print(f"no paper matched --only {args.only}")
            return 1

    if args.write_sources:
        write_sources(plan(), REPO / args.write_sources)
        return 0
    if not args.run:
        print_table(rows)
        return 0

    if not grobid_alive(args.grobid_server):
        # NOT --rm: the container that died mid-batch was removed along with its logs, so
        # nothing was left to say why. --restart brings it back on its own, which is what
        # --wait-grobid then waits for.
        print(f"GROBID is not answering at {args.grobid_server}.\n"
              "  docker run -d --init --ulimit core=0 -p 8070:8070 "
              "--restart unless-stopped --name grobid grobid/grobid:0.9.0-crf")
        return 2

    failed = []
    for r in rows:
        if status_of(r["key"])["processed"]:
            print(f"\n=== {r['key']} === already prepared, skipping")
            continue
        if not prepare(r, args.model, args.grobid_server, args.k):
            failed.append(r["key"])
    print()
    print_table(rows)
    if failed:
        print("\nFAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
