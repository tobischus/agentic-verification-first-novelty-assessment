#!/usr/bin/env python3
"""Does every retrieved paper actually have a readable PDF? Report, then adopt.

WHY THIS EXISTS. A pool paper with no PDF does not stop the review. `tools.py`'s depth
ladder ranks `fulltext_unavailable` as level 1 and lists it in `_SUFFICIENT_DEPTHS`, so the
paper is compared on its abstract alone and the run reports itself complete. Measured on
the pilot: `transducing_language_models` had 3 of 24 pool papers without a PDF, and all
three were compared under EVERY one of its four claims -- twelve comparisons resting on an
abstract, with `fulltext_status` recorded as null, so the report could not show it either.
That is the failure this script is here to make impossible before a run rather than
discoverable after one.

TWO CHECKS, NOT ONE. "A file is present" is not the question. A zero-byte or unparseable
file is exactly as bad as a missing one and harder to notice, so every PDF is opened and
its extractable text measured.

ADOPTING A PDF YOU FETCHED BY HAND IS NOT JUST COPYING IT IN. Version pinning is on by
default, and `tools._prepare_pinned_pdf` compares the file's sha256 against the pinned
`doc_sha256`. A hand-placed file will not match, so it is discarded and re-downloaded --
failing again, silently. `--adopt` closes that: it validates the file, then records its
hash in `related_work_data/versions.json` via the pipeline's own `record_pdf_hash`, and
marks the entry as manually supplied so the provenance says where it came from.

Usage
-----
  python eval/check_pool_pdfs.py                       # every prepared submission
  python eval/check_pool_pdfs.py --submission <id>     # one
  python eval/check_pool_pdfs.py --submission <id> --links    # how to get the missing ones
  python eval/check_pool_pdfs.py --submission <id> --adopt    # after you dropped them in

Exit code is 1 while any paper is missing or unreadable, so it can gate a run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

DATA = REPO / "data"

#: Below this many extractable characters a "PDF" is not a paper -- a cover page, a
#: paywall interstitial or a scan with no text layer. The pilot's real parses are all
#: five figures; 1500 only catches the degenerate cases.
_MIN_TEXT_CHARS = 1500

#: tools.ClaimToolbox._USABLE_VERSION_STATUSES. A paper outside these is refused admission
#: to the pool by the temporal gate -- that is not a PDF problem, and no PDF fixes it.
_USABLE_STATUSES = ("pinned", "single")


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _pid(p: dict) -> str:
    return p.get("paper_id") or p.get("paperId") or p.get("id") or ""


def _ext(p: dict, *names) -> str:
    ext = p.get("externalIds") or {}
    for n in names:
        v = ext.get(n)
        if v:
            return str(v)
    return ""


def resolve_links(p: dict) -> list[str]:
    """Places this specific paper can actually be fetched from, best first."""
    out = []
    arx = _ext(p, "ArXiv", "arXiv", "arxiv")
    if arx:
        out.append(f"https://arxiv.org/pdf/{arx}")
    pmc = _ext(p, "PubMedCentral", "PMC")
    if pmc:
        out.append(f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc}/pdf/")
    doi = p.get("doi") or _ext(p, "DOI")
    if doi:
        out.append(f"https://doi.org/{doi}")
    acl = _ext(p, "ACL")
    if acl:
        out.append(f"https://aclanthology.org/{acl}.pdf")
    if _pid(p):
        out.append(f"https://www.semanticscholar.org/paper/{_pid(p)}")
    title = (p.get("title") or "").strip()
    if title:
        q = title.replace(" ", "+")
        out.append(f"https://scholar.google.com/scholar?q={q}")
    return out


def pdf_text_chars(path: Path) -> int:
    """Extractable characters, via the same parser the pipeline uses. -1 if unreadable."""
    try:
        import fitz
        with fitz.open(path) as d:
            return sum(len(d[i].get_text()) for i in range(min(d.page_count, 12)))
    except Exception:
        return -1


def audit(sid: str) -> dict:
    sub = DATA / sid
    pool = _load(sub / "related_work_data" / "ranked_papers.json")
    if pool is None:
        return {"submission": sid, "error": "no ranked_papers.json -- retrieval has not run"}
    pdf_dir = sub / "related_work_data" / "pdfs"
    versions = _load(sub / "related_work_data" / "versions.json") or {}

    ok, missing, broken, excluded = [], [], [], []
    for p in pool:
        pid = _pid(p)
        if not pid:
            continue
        pin = versions.get(pid) or {}
        status = pin.get("status") or ""
        f = pdf_dir / f"{pid}.pdf"
        # Checked FIRST, because it decides whether the PDF matters at all: a paper whose
        # version cannot be pinned is refused admission to the pool by
        # tools._add_pool_paper's version gate and is never compared, PDF or no PDF.
        if status not in _USABLE_STATUSES:
            excluded.append({**p, "_why": status or "unresolved",
                             "_has_pdf": f.is_file() and f.stat().st_size > 0})
            continue
        if not f.is_file() or f.stat().st_size == 0:
            missing.append(p)
            continue
        head = f.open("rb").read(4)
        chars = pdf_text_chars(f) if head == b"%PDF" else -1
        if chars < _MIN_TEXT_CHARS:
            broken.append({**p, "_why": "not a PDF" if head != b"%PDF"
                           else ("unreadable" if chars < 0 else f"only {chars} chars of text"),
                           "_path": f})
            continue
        # Not "is a hash recorded" but "does the recorded hash match THIS file". A pin
        # left over from an earlier download, with a different file now sitting in its
        # place, passes the first test and fails at review time exactly like an unpinned
        # one: _prepare_pinned_pdf compares sha256 and discards on mismatch.
        recorded = pin.get("doc_sha256") or ""
        ok.append({**p, "_pinned": bool(recorded) and recorded == _sha256(f),
                   "_status": status, "_path": f})
    unpinned = [p for p in ok if not p["_pinned"]]
    return {"submission": sid, "n_pool": len(pool), "n_ok": len(ok),
            "missing": missing, "broken": broken, "excluded": excluded,
            "unpinned": unpinned, "pdf_dir": pdf_dir}


def funnel(sid: str) -> dict:
    """Every place a candidate can be lost between the bibliography and the review.

    "Is every paper there?" is a different question from "does every pooled paper have a
    PDF", and this answers the first. The chain:

      references parsed out of the submission by GROBID
        -> matched to a Semantic Scholar record     (unmatched ones never become candidates)
        + papers found by the search queries
        -> all retrieved
        -> ranked into the pool                     (intended top-k selection, not loss)
        -> admitted by the version gate             (see audit(): `excluded`)
        -> full text available                      (see audit(): `missing`/`broken`)

    Only the first step is reported here; the rest is what audit() covers. The unmatched
    references are listed rather than counted, because in practice most of them are not
    papers at all -- software repositories, product pages, a URL GROBID mangled -- and
    that is a judgement to make by looking, not by a heuristic that would quietly file a
    real paper under "probably a tool".
    """
    sub = DATA / sid
    meta = _load(sub / f"{sid}.json") or {}
    cited = meta.get("cited_papers") or []
    unmatched = [r for r in cited if not r.get("ss_paper_obj")]
    results = _load(sub / "related_work_data" / "complete_results.json") or {}
    rwmeta = _load(sub / "related_work_data" / "metadata.json") or {}
    return {
        "n_references": len(cited),
        "n_matched": len(cited) - len(unmatched),
        "unmatched": unmatched,
        # GROBID could not even read a title here, so nothing could have been looked up.
        "n_no_title": sum(1 for r in unmatched if not (r.get("title") or "").strip()),
        "n_query": len(results.get("query_papers") or []),
        "n_retrieved": len(results.get("all_retrieved_papers") or [])
                       or rwmeta.get("num_all_retrieved") or 0,
    }


def print_funnel(sid: str, f: dict, verbose: bool) -> None:
    rate = (100.0 * f["n_matched"] / f["n_references"]) if f["n_references"] else 0.0
    print(f"     references in the bibliography: {f['n_references']:>3}  "
          f"-> matched to a record: {f['n_matched']:>3} ({rate:.0f}%)  "
          f"unmatched: {len(f['unmatched']):>2}"
          + (f" ({f['n_no_title']} unreadable by GROBID)" if f["n_no_title"] else ""))
    print(f"     + {f['n_query']} from the search queries  -> {f['n_retrieved']} candidates "
          f"retrieved in total")
    if verbose and f["unmatched"]:
        print("     unmatched entries (look for a real paper among them):")
        for r in f["unmatched"]:
            t = (r.get("title") or "").strip()
            print(f"       - {t[:72] if t else '(no title -- GROBID could not parse this entry)'}")


#: Version statuses that mean "the lookup failed", as opposed to "the answer is no".
#: paper_versions.py: `unresolved` = version history could not be READ (network, API,
#: malformed id); `unavailable` = every version is too recent to be prior work. The first
#: is a transient failure worth retrying; the second is a finding and must be left alone.
_RETRYABLE_STATUSES = ("unresolved", "")


def reresolve(sid: str) -> int:
    """Retry the version lookups that failed for a reason unrelated to the answer.

    An `unresolved` pin is not a verdict -- it is the absence of one, recorded because
    arXiv could not be reached. But `tools._add_pool_paper` gates on the status alone, and
    `_pin_is_stale` only re-resolves when the CUTOFF changed, so an unresolved pin from a
    rate-limited batch run is permanent: the paper is refused as evidence on every
    subsequent run, silently and forever. Measured after one such run: agentgym_rl would
    have reviewed 2 of its 19 pooled papers, astabench 7 of 20.

    Re-resolving with force=True fixes it when the source is reachable again, and then the
    newly pinned papers still need their PDF, which was never fetched for them either.
    """
    from fetch_fulltext import FullTextFetcher
    versions = _load(DATA / sid / "related_work_data" / "versions.json") or {}
    stuck = [pid for pid, e in versions.items()
             if (e.get("status") or "") in _RETRYABLE_STATUSES]
    if not stuck:
        print(f"{sid}: nothing to re-resolve")
        return 0
    print(f"{sid}: re-resolving {len(stuck)} version lookup(s) that had failed")
    fetcher = FullTextFetcher()
    out = fetcher.resolve_versions(str(DATA), sid, paper_ids=stuck, force=True)
    fixed = [pid for pid in stuck if (out.get(pid) or {}).get("status") in _USABLE_STATUSES]
    still = len(stuck) - len(fixed)
    print(f"  pinned now: {len(fixed)}   still unresolved: {still}")
    if fixed:
        print(f"  fetching the {len(fixed)} PDF(s) that were never downloaded for them")
        fetcher.download_pdfs(str(DATA), sid, paper_ids=fixed)
    return len(fixed)


def adopt(sid: str, report: dict) -> int:
    """Bind hand-placed PDFs to their manifest entry so version pinning accepts them."""
    from fetch_fulltext import FullTextFetcher
    fetcher = FullTextFetcher()
    adopted = 0
    for p in report["unpinned"]:
        pid = _pid(p)
        digest = fetcher.record_pdf_hash(str(DATA), sid, pid, p["_path"])
        if not digest:
            print(f"  ! {pid[:12]} has no versions.json entry -- cannot pin "
                  f"({(p.get('title') or '')[:50]})")
            continue
        # Say in the manifest that this document did not come from the resolver, so the
        # provenance in the report is not silently upgraded to an automatic match.
        vpath = DATA / sid / "related_work_data" / "versions.json"
        man = _load(vpath) or {}
        if pid in man:
            man[pid]["doc_source"] = "manual"
            vpath.write_bytes(json.dumps(man, ensure_ascii=False, indent=1).encode("utf-8"))
        adopted += 1
        print(f"  + {pid[:12]} pinned to the file on disk ({digest[:12]})  "
              f"{(p.get('title') or '')[:46]}")
    return adopted


def print_report(r: dict, links: bool) -> None:
    if r.get("error"):
        print(f"{r['submission']}: {r['error']}")
        return
    bad = len(r["missing"]) + len(r["broken"])
    mark = "OK " if bad == 0 and not r["unpinned"] else "!! "
    reviewed = r["n_pool"] - len(r["excluded"])
    print(f"{mark}{r['submission']:<46} retrieved={r['n_pool']:>3}  "
          f"reviewed={reviewed:>3}  full text={r['n_ok']:>3}  "
          f"missing={len(r['missing']):>2}  unreadable={len(r['broken']):>2}  "
          f"unpinned={len(r['unpinned']):>2}  excluded={len(r['excluded']):>2}")
    for p in r["broken"]:
        print(f"     UNREADABLE  {_pid(p)[:12]}  {p['_why']:<22} {(p.get('title') or '')[:52]}")
    for p in r["unpinned"]:
        print(f"     UNPINNED    {_pid(p)[:12]}  PDF present but its hash is not recorded "
              f"-- it will be re-downloaded, and the paper drops to abstract-only if that "
              f"fails. Fix with --adopt.")
    for p in r["missing"]:
        print(f"     MISSING     {_pid(p)[:12]}  {(p.get('title') or '')[:64]}")
        if links:
            print(f"                 save as: {(r['pdf_dir'] / (_pid(p) + '.pdf')).relative_to(REPO)}")
            for u in resolve_links(p):
                print(f"                 {u}")
            print()
    if r["excluded"]:
        with_pdf = sum(1 for p in r["excluded"] if p["_has_pdf"])
        # Every single paper excluded, all for the same unresolved reason, is not a finding
        # about this pool -- it is a directory whose pins were never resolved at all (an
        # older run, or one that predates version pinning). Listing twenty titles for that
        # buries the submissions that have something real to report.
        if len(r["excluded"]) == r["n_pool"] and all(p["_why"] == "unresolved"
                                                     for p in r["excluded"]):
            print(f"     NOT RESOLVED  no version pin was ever recorded for any of the "
                  f"{r['n_pool']} pooled papers. If this is a live submission, run "
                  f"--reresolve; if it is a leftover directory from an earlier run, "
                  f"ignore it.")
            return
        print(f"     EXCLUDED    {len(r['excluded'])} retrieved paper(s) never enter the "
              f"review at all ({with_pdf} of them even have a PDF on disk): their version "
              f"could not be pinned, so the temporal gate in tools._add_pool_paper refuses "
              f"them as evidence.")
        for p in r["excluded"]:
            print(f"                 {_pid(p)[:12]}  [{p['_why']}] {(p.get('title') or '')[:48]}")
        print("                 Getting a PDF does NOT fix these -- the version has to "
              "resolve. Either accept the smaller pool or re-run retrieval for them.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--submission", default="", help="one submission id")
    ap.add_argument("--human-study", action="store_true",
                    help="only the submissions that belong to human_study/paper/ "
                         "(data/ also holds dozens of leftover directories from earlier "
                         "runs, and scanning those buries the ones that matter)")
    ap.add_argument("--links", action="store_true", help="print where to fetch what is missing")
    ap.add_argument("--funnel", action="store_true",
                    help="also show where candidates are lost BEFORE the pool: how many "
                         "of the submission's references matched a record at all")
    ap.add_argument("--list-unmatched", action="store_true",
                    help="with --funnel, list every unmatched reference so you can see "
                         "whether a real paper is among them")
    ap.add_argument("--reresolve", action="store_true",
                    help="retry version lookups that failed for network reasons "
                         "(status `unresolved`), then fetch the PDFs that unlocks. "
                         "Leaves `unavailable` alone -- that one is a real finding.")
    ap.add_argument("--adopt", action="store_true",
                    help="bind hand-placed PDFs to their manifest entry (run after adding them)")
    args = ap.parse_args()

    if args.submission:
        sids = [args.submission]
    elif args.human_study:
        sys.path.insert(0, str(REPO / "eval"))
        from human_study_prep import plan
        sids = [r["key"] for r in plan()
                if (DATA / r["key"] / "related_work_data" / "ranked_papers.json").is_file()]
    else:
        sids = sorted(d.name for d in DATA.glob("*")
                      if d.is_dir() and (d / "related_work_data" / "ranked_papers.json").is_file())
        print(f"scanning all {len(sids)} submissions under data/ -- most are leftovers "
              f"from earlier runs. Use --human-study to see only the ten.\n")
    if not sids:
        print("no submission with a retrieval pool found")
        return 1

    worst = 0
    for sid in sids:
        r = audit(sid)
        if args.reresolve and not r.get("error"):
            if reresolve(sid):
                r = audit(sid)
        if args.adopt and not r.get("error") and r["unpinned"]:
            print(f"{sid}: adopting {len(r['unpinned'])} hand-placed PDF(s)")
            adopt(sid, r)
            r = audit(sid)
        print_report(r, args.links)
        if args.funnel and not r.get("error"):
            print_funnel(sid, funnel(sid), args.list_unmatched)
        if r.get("error") or r["missing"] or r["broken"] or r["unpinned"]:
            worst = 1
    if worst:
        print("\nNot every reviewable paper has a readable, pinned PDF. Fetch what is "
              "missing (--links shows where), drop it in as <paper_id>.pdf, then re-run "
              "with --adopt so version pinning binds the file instead of discarding it.")
    else:
        print("\nEvery paper that enters the review has a readable, pinned PDF.")
        print("(EXCLUDED papers, where listed above, are a separate matter: they never "
              "enter the review, so their full text is not consulted either way.)")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
