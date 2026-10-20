"""E3, automatic part: do the quotes a report shows stand in the sources it names?

Read-only, no API call, no model. Added 2026-09-27 (PROTOCOL 8c); descriptive, no
test. The midterm presentation announced two checkable metrics that need no
judge -- the grounding rate and the verifiability rate. This module reports them for the
agent and the linear baseline on the 20 E1 papers, and adds an audit that does not reuse
the pipeline's verifier: every quote a report SHOWS is looked up again in the source text
it was verified against, after that text's hash has been matched to the run log.

Inputs are the artifacts the frozen reports were rendered from (sha256-checked against the
manifests, `agent_linear._checked`) and, per quote, the source text:

  submission side   the submission's section texts + abstract, joined exactly as
                    `tools.py` builds the verification corpus; its sha256 must equal the
                    run log's `submission_selection.source_sha256`
  prior-work side   `related_work_data/<parsed_text_path>`, whose sha256 must equal the run
                    log's `parsed_text_sha256`. A source without a recorded parsed text
                    (abstract + introduction only) is reported as not auditable -- its text
                    cannot be tied to the run by a hash.

Metrics, per flow:

  grounding rate      overlap comparisons (partial / substantial / same, or refuting) that
                      show at least one quote pair
  verifiability rate  quote pairs the model proposed whose two sides the pipeline found in
                      the sources: (returned - unverified) / returned, from the recorded
                      map diagnostics of each comparison's final turn
  ownership rate      of those, the pairs the ownership check assigned to the prior paper's
                      own contribution -- the pairs a report shows
  quote audit         each shown quote against its source text: exact (case- and
                      whitespace-insensitive substring), near-verbatim (rapidfuzz
                      partial_ratio >= 90, the pipeline's documented threshold, e.g. a
                      dropped citation marker or a ligature), not found (< 90)
  source dates        shown pairs whose prior-work version is dated before the submission's
                      first public version

Only the agent and the linear baseline record quote pairs in machine-readable form. What
the external systems' free text says about prior work, and absence claims in any report
("paper X does not do Y"), need the prior-work papers read by a person: E3's manual part,
not implemented.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

from .. import agent_linear as al

NEAR = 90.0
EXAMPLES = 10


def norm(text: str) -> str:
    """Lowercase, whitespace collapsed -- the pipeline's own convention for 'exact'."""
    return " ".join((text or "").lower().split())


def classify(quote: str, source_norm: str | None) -> tuple[str, float]:
    """('exact' | 'near' | 'not_found' | 'no_source', similarity) for one shown quote."""
    if source_norm is None:
        return "no_source", 0.0
    q = norm(quote)
    if q and q in source_norm:
        return "exact", 100.0
    score = float(fuzz.partial_ratio(q, source_norm)) if q else 0.0
    return ("near" if score >= NEAR else "not_found"), score


def submission_text(sub_dir: Path, paper: str) -> str:
    """The verification corpus of the submission, joined as `tools.py` joins it."""
    meta = json.loads((sub_dir / f"{paper}.json").read_text(encoding="utf-8"))
    ft = json.loads((sub_dir / f"{paper}_fulltext.json").read_text(encoding="utf-8"))
    return "\n\n".join([s.get("text", "") for s in ft.get("sections", [])]
                       + [meta.get("abstract", "")])


def paper_text(sub_dir: Path, pw: dict) -> str | None:
    """The parsed prior-work text the run verified against, or None if it cannot be tied
    to the run by its recorded hash."""
    rel, want = pw.get("parsed_text_path"), pw.get("parsed_text_sha256")
    if not (rel and want):
        return None
    f = sub_dir / "related_work_data" / rel
    # Hash the bytes, as the writer did (see tools._load_fulltext_file).
    if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != want:
        return None
    return f.read_text(encoding="utf-8")


def audit_variant(artifact_a: dict, sub_dir: Path, paper: str, sub_date: str, vd,
                  sub_norm: str, sub_sha: str) -> tuple[Counter, list]:
    """Counts for one flow on one paper, and the quotes that were not found."""
    c, misses, cache = Counter(), [], {}
    for claim in artifact_a.get("claims") or []:
        rl = claim.get("run_log") or {}
        c["claims"] += 1
        c["submission_hash_ok"] += (rl.get("submission_selection") or {}).get("source_sha256") == sub_sha
        pws = {pw.get("paper_id"): pw for pw in rl.get("prior_work") or []}
        for comp in claim.get("comparisons") or []:
            pw = pws.get(comp.get("paper_id"), {})
            pairs = comp.get("evidence_pairs") or []
            if vd.is_overlap(comp):
                c["overlap"] += 1
                c["overlap_grounded"] += bool(pairs)
            if vd.degree(comp) in ("substantial", "same"):
                c["strong"] += 1
                c["strong_grounded"] += bool(pairs)
            if vd.challenges(comp):
                c["refuting"] += 1
                c["refuting_grounded"] += bool(pairs)
            diag = comp.get("map_diag") or {}
            ret, unver = diag.get("returned") or 0, diag.get("unverified") or 0
            c["pairs_proposed"] += ret
            c["pairs_both_sides_found"] += ret - unver
            c["pairs_shown"] += len(pairs)
            if not pairs:
                continue
            # Keyed by path AND recorded hash: a record naming the same file with another
            # hash must not inherit the verdict of the one that matched.
            key = (pw.get("parsed_text_path") or "", pw.get("parsed_text_sha256") or "")
            if key not in cache:
                txt = paper_text(sub_dir, pw)
                cache[key] = norm(txt) if txt is not None else None
            dated = pw.get("pinned_version_date") or ""
            for pr in pairs:
                c["pairs_source_dated"] += bool(dated)
                c["pairs_source_before_submission"] += bool(dated) and dated < sub_date
                for side, quote, src in (("submission", pr.get("claim_quote", ""), sub_norm),
                                         ("prior_work", pr.get("paper_quote", ""), cache[key])):
                    kind, score = classify(quote, src)
                    c[f"{side}_{kind}"] += 1
                    if kind == "not_found":
                        misses.append({"paper": paper, "claim_id": claim.get("claim_id"),
                                       "prior_paper": comp.get("paper_id"), "side": side,
                                       "similarity": round(score, 1),
                                       "quote": " ".join(quote.split())[:200]})
    return c, misses


def _rate(num: int, den: int):
    return round(num / den, 4) if den else None


def rates(c: Counter) -> dict:
    shown_quotes = 2 * c["pairs_shown"]
    audited = shown_quotes - c["prior_work_no_source"] - c["submission_no_source"]
    exact = c["submission_exact"] + c["prior_work_exact"]
    near = c["submission_near"] + c["prior_work_near"]
    return {
        "grounding_rate": _rate(c["overlap_grounded"], c["overlap"]),
        "grounding_rate_strong": _rate(c["strong_grounded"], c["strong"]),
        "grounding_rate_refuting": _rate(c["refuting_grounded"], c["refuting"]),
        "verifiability_rate": _rate(c["pairs_both_sides_found"], c["pairs_proposed"]),
        "ownership_rate": _rate(c["pairs_shown"], c["pairs_both_sides_found"]),
        "quotes_shown": shown_quotes,
        "quotes_audited": audited,
        "quotes_exact": exact,
        "quotes_near": near,
        "quotes_not_found": c["submission_not_found"] + c["prior_work_not_found"],
        "quotes_not_auditable": shown_quotes - audited,
        "share_exact": _rate(exact, audited),
        "share_exact_or_near": _rate(exact + near, audited),
        # Of the shown pairs whose prior-work version carries a date; an undated source is a
        # single-document record without version history (`version_status == single`).
        "sources_dated_before_submission": _rate(c["pairs_source_before_submission"],
                                                 c["pairs_source_dated"]),
        "pairs_source_undated": c["pairs_shown"] - c["pairs_source_dated"],
    }


def analyze(config: Path = al.E1_CONFIG) -> dict:
    rm = al._run_metrics()
    vd = rm.vd
    totals = {v: Counter() for v in al.VARIANTS}
    per_paper, misses = {}, {v: [] for v in al.VARIANTS}
    for _, paper, entry in al.paper_entries(config):
        sub_dir = al.ROOT / "data" / paper
        meta = json.loads((sub_dir / f"{paper}.json").read_text(encoding="utf-8"))
        sub = submission_text(sub_dir, paper)
        sub_sha = hashlib.sha256(sub.encode("utf-8")).hexdigest()
        sub_norm = norm(sub)
        per_paper[paper] = {}
        for v in al.VARIANTS:
            prov = entry["systems"][v]["provenance"]
            art = json.loads(al._checked(prov["artifact_a_path"], prov["artifact_a_sha256"])
                             .read_text(encoding="utf-8"))
            c, miss = audit_variant(art, sub_dir, paper, meta.get("publication_date") or "9999",
                                    vd, sub_norm, sub_sha)
            totals[v] += c
            misses[v] += miss
            per_paper[paper][v] = {"counts": dict(c), **rates(c)}

    def spread(v, key):
        vals = [r[v][key] for r in per_paper.values() if r[v][key] is not None]
        return {"min": min(vals), "median": round(statistics.median(vals), 4)} if vals else None

    return {
        "post_hoc": "added 2026-09-27; descriptive, no test (PROTOCOL 8c)",
        "papers": len(per_paper),
        "near_threshold": NEAR,
        "variants": {v: {"counts": dict(totals[v]), **rates(totals[v]),
                         "per_paper": {k: spread(v, k) for k in
                                       ("grounding_rate", "verifiability_rate", "share_exact_or_near")},
                         "not_found": misses[v]}
                     for v in al.VARIANTS},
        "per_paper": per_paper,
    }


def _pct(x) -> str:
    return "-" if x is None else f"{x:.1%}"


def print_report(res: dict) -> None:
    print(f"E3 automatic source audit -- {res['papers']} papers ({res['post_hoc']})")
    print()
    rows = [
        ("grounding rate (overlap comparisons with a quote pair)", "grounding_rate"),
        ("  substantial/same only", "grounding_rate_strong"),
        ("  refuting only", "grounding_rate_refuting"),
        ("verifiability rate (proposed pairs found on both sides)", "verifiability_rate"),
        ("ownership rate (found pairs owned by the prior paper)", "ownership_rate"),
        ("shown quotes: exact in the hash-pinned source", "share_exact"),
        (f"shown quotes: exact or near-verbatim (>= {res['near_threshold']:.0f})", "share_exact_or_near"),
        ("shown pairs with a dated source: dated before the submission", "sources_dated_before_submission"),
    ]
    print(f"{'':58s} {'agent':>9s} {'linear':>9s}")
    for label, key in rows:
        print(f"{label:58s} {_pct(res['variants']['agent'][key]):>9s} "
              f"{_pct(res['variants']['linear'][key]):>9s}")
    print()
    for v in al.VARIANTS:
        r = res["variants"][v]
        c = r["counts"]
        print(f"{v}: {r['quotes_shown']} quotes shown ({c.get('pairs_shown', 0)} pairs) -- "
              f"{r['quotes_exact']} exact, {r['quotes_near']} near-verbatim, "
              f"{r['quotes_not_found']} not found, {r['quotes_not_auditable']} not auditable "
              f"(no hash-recorded source text); submission hash matched on "
              f"{c.get('submission_hash_ok', 0)}/{c.get('claims', 0)} claims")
        pp = r["per_paper"]
        print(f"  per paper: grounding min {_pct(pp['grounding_rate']['min'])} / median "
              f"{_pct(pp['grounding_rate']['median'])}; verifiability min "
              f"{_pct(pp['verifiability_rate']['min'])} / median {_pct(pp['verifiability_rate']['median'])}")
        for m in r["not_found"][:EXAMPLES]:
            print(f"  not found: {m['paper']} {m['claim_id']} {m['side']} ({m['similarity']}): "
                  f"{m['quote'][:110]}")
