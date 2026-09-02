#!/usr/bin/env python3
"""
Grounding and verifiability analysis over the evidence the pipeline already produced.

This is the JUDGE-FREE pillar of the evaluation. Everything here is deterministic string
matching against the source texts -- no model is asked for an opinion, so none of these
numbers depend on the LLM judge whose position bias decides 40% of pairwise outcomes.

It answers, over every artifact_a in the tree:
  * how many evidence quotes actually verify, split by side (claim vs. paper);
  * WHY the rest fail -- too short, absent from the source, or a near miss that is
    almost always parse noise rather than fabrication;
  * how the verification rate depends on how deeply the prior paper was read;
  * how often a `can_refute` was downgraded because it had no both-sides-verified pair,
    i.e. how load-bearing the evidence gate actually is.

Every pair is RE-VERIFIED offline with the current rule (evidence.verify_pair, the agent's
min_quote_tokens and fuzzy_threshold) instead of trusting the flags in the file. Older
artifacts were written when artifact_a checked only the paper side, by plain substring and
with no minimum length, so their stored flags are not comparable across runs. Re-verifying
puts every run on one footing and yields the old-rule/new-rule delta as a by-product.

Usage
-----
  python eval/verifiability_analysis.py
  python eval/verifiability_analysis.py --roots data eval/out/data --out eval/out/verifiability.json
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "novelty_assessment"
sys.path.insert(0, str(_SRC))
from agent import evidence as ev  # noqa: E402

# A failed check with a high fuzzy score is a near miss -- the quote is essentially in the
# source but the parse mangled it. Below this it is absent, which is the fabrication case.
NEAR_MISS_SCORE = 70.0


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class SubmissionSources:
    """Everything needed to re-verify one submission's evidence, loaded once."""

    def __init__(self, sub_dir: Path, sid: str):
        self.sub_dir, self.sid = sub_dir, sid
        # claim side: the submission's own body + abstract (same corpus the agent uses)
        parts = []
        ft = _load(sub_dir / f"{sid}_fulltext.json") or {}
        parts += [s.get("text", "") for s in ft.get("sections", [])]
        meta = _load(sub_dir / f"{sid}.json") or {}
        parts.append(meta.get("abstract", "") or "")
        self.submission_text = "\n\n".join(p for p in parts if p)

        # At run time the claim side is checked against the submission PLUS the claim's
        # own claim_text and description (agent/tools.py ClaimToolbox). artifact_a stores
        # claim_text but not description, so the claims doc is needed to rebuild the exact
        # corpus. It is only usable when it still holds the same claim -- the extractor was
        # replaced since the older runs, which rewrote these files.
        self.claim_extras = {}
        doc = _load(sub_dir / f"{sid}_claims.json") or {}
        for c in doc.get("claims", []) or []:
            if c.get("id"):
                self.claim_extras[c["id"]] = "\n\n".join(
                    x for x in (c.get("claim_text", ""), c.get("description", "")) if x)

        # paper side: pool abstracts, plus full text where it was actually fetched
        self.abstracts, self.titles = {}, {}
        for rel in ("related_work_data/ranked_papers.json",
                    "related_work_data/agent_retrieved_papers.json"):
            for p in _load(sub_dir / rel) or []:
                pid = p.get("paper_id")
                if pid:
                    self.abstracts.setdefault(pid, p.get("abstract") or "")
                    self.titles.setdefault(pid, p.get("title") or "")
        self._fulltext_cache = {}

    def paper_text(self, pid: str) -> tuple:
        """(text, source) -- full text when it was parsed for this paper, else the abstract."""
        if pid in self._fulltext_cache:
            return self._fulltext_cache[pid]
        text, src = "", "none"
        for rel in (f"related_work_data/grobid_fulltext/{pid}.txt",
                    f"related_work_data/nougat_output/{pid}.mmd",
                    f"related_work_data/mineru_output/{pid}.md"):
            p = self.sub_dir / rel
            if p.exists():
                try:
                    text, src = p.read_text(encoding="utf-8", errors="ignore"), "fulltext"
                    break
                except Exception:
                    pass
        if not text:
            ab = self.abstracts.get(pid) or ""
            text, src = ab, ("abstract" if ab else "none")
        self._fulltext_cache[pid] = (text, src)
        return text, src


def classify(chk) -> str:
    """QuoteCheck -> the failure bucket reported in the thesis."""
    if chk.verified:
        return chk.method                      # exact | fuzzy
    if chk.method in ("empty", "too_short"):
        return chk.method
    return "near_miss" if chk.score >= NEAR_MISS_SCORE else "absent"


def analyse(roots, min_tokens, fuzzy, out_path=None):
    files = []
    for r in roots:
        files += sorted(Path(r).glob("*/*_artifact_a.json"))
    if not files:
        print("keine artifact_a.json gefunden")
        return

    stats = {
        "files": 0, "agentic": 0, "linear": 0, "claims": 0, "comparisons": 0, "pairs": 0,
        "claims_corpus_drift": 0, "pairs_corpus_drift": 0,
        "claim_side": Counter(), "paper_side": Counter(),
        "by_depth": defaultdict(lambda: {"pairs": 0, "verified": 0}),
        "by_paper_source": defaultdict(lambda: {"pairs": 0, "verified": 0}),
        "fully_verified": 0, "no_source": 0,
        "can_refute_stored": 0, "can_refute_survives": 0,
        "downgraded_at_runtime": 0, "gate_violations": 0,
        "legacy_pairs": 0, "legacy_would_flip": Counter(),
    }
    per_run = []

    for f in files:
        a = _load(f)
        if not a:
            continue
        sub_dir = f.parent
        sid = a.get("submission_id") or sub_dir.name
        src = SubmissionSources(sub_dir, sid)
        agentic = bool(a.get("agentic"))
        stats["files"] += 1
        stats["agentic" if agentic else "linear"] += 1
        run = {"file": str(f), "submission_id": sid, "agentic": agentic,
               "pairs": 0, "fully_verified": 0}

        for entry in a.get("claims", []):
            stats["claims"] += 1
            cid = entry.get("claim_id", "")
            extras = src.claim_extras.get(cid)
            # Faithful only when the claims doc still holds the SAME claim under this id.
            # Matching ids are not enough: the extractor was replaced, so claim_1 in the
            # current file can be a different contribution than the claim_1 this artifact
            # was written for. Without the original text the run-time corpus cannot be
            # rebuilt, and a mismatch would measure our reconstruction, not the pipeline.
            stored_ct = ev.normalize(entry.get("claim_text", ""))
            faithful = bool(extras) and (
                not stored_ct or stored_ct in ev.normalize(extras))
            claim_corpus = "\n\n".join(x for x in (
                src.submission_text, entry.get("claim_text", ""),
                entry.get("claim_name", ""),
                extras if faithful else "") if x)
            if not faithful:
                stats["claims_corpus_drift"] += 1
            for comp in entry.get("comparisons", []) or []:
                stats["comparisons"] += 1
                pid = comp.get("paper_id", "")
                ptext, psrc = src.paper_text(pid)
                depth = comp.get("depth") or ("linear:" + (comp.get("content_source") or "?"))
                status = comp.get("refutation_status")
                # The artifacts store the status AFTER the gate ran, so a downgrade cannot
                # be re-derived from them -- it is read off the marker the gate leaves in
                # the note (agent/tools.py record_comparison).
                if faithful and (comp.get("brief_note") or "").startswith("[downgraded"):
                    stats["downgraded_at_runtime"] += 1
                if status == "can_refute" and faithful:
                    stats["can_refute_stored"] += 1
                any_full = False

                for pair in comp.get("evidence_pairs", []) or []:
                    cq, pq = pair.get("claim_quote", ""), pair.get("paper_quote", "")
                    c_chk = ev.verify_quote(cq, claim_corpus, min_tokens, fuzzy)
                    p_chk = ev.verify_quote(pq, ptext, min_tokens, fuzzy)
                    full = c_chk.verified and p_chk.verified
                    any_full |= full
                    if not faithful:
                        # cannot rebuild the run-time claim corpus -> not evidence about
                        # the pipeline, only about our reconstruction. Kept out of every
                        # headline number.
                        stats["pairs_corpus_drift"] += 1
                        continue
                    stats["pairs"] += 1
                    run["pairs"] += 1
                    if not ptext:
                        stats["no_source"] += 1
                    stats["claim_side"][classify(c_chk)] += 1
                    stats["paper_side"][classify(p_chk)] += 1
                    stats["fully_verified"] += full
                    run["fully_verified"] += full
                    stats["by_depth"][depth]["pairs"] += 1
                    stats["by_depth"][depth]["verified"] += full
                    stats["by_paper_source"][psrc]["pairs"] += 1
                    stats["by_paper_source"][psrc]["verified"] += full

                    # legacy pairs: written when only the paper side was checked, by
                    # substring and without a minimum length
                    if "fully_verified" not in pair:
                        stats["legacy_pairs"] += 1
                        old = bool(ev.normalize(pq)) and ev.normalize(pq) in ev.normalize(ptext)
                        if old != full:
                            stats["legacy_would_flip"][
                                "old accepted, now rejected" if old else
                                "old rejected, now accepted"] += 1

                if status == "can_refute" and faithful:
                    if any_full:
                        stats["can_refute_survives"] += 1
                    else:
                        # a can_refute that survived the run but does NOT hold up under the
                        # current rule -- an actual violation of the evidence invariant
                        stats["gate_violations"] += 1
        per_run.append(run)

    _report(stats, per_run, min_tokens, fuzzy)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps({
            "params": {"min_quote_tokens": min_tokens, "fuzzy_threshold": fuzzy,
                       "near_miss_score": NEAR_MISS_SCORE},
            "totals": {k: (dict(v) if isinstance(v, (Counter, defaultdict)) else v)
                       for k, v in stats.items()},
            "per_run": per_run,
        }, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
        print(f"\ngeschrieben: {out_path}")


def _pct(n, d):
    return f"{100.0 * n / d:5.1f}%" if d else "    --"


def _report(s, per_run, min_tokens, fuzzy):
    W = 78
    print("=" * W)
    print("GROUNDING & VERIFIABILITY  (judge-free; every pair re-verified offline)")
    print("=" * W)
    print(f"rule: min_quote_tokens={min_tokens}  fuzzy_threshold={fuzzy}  "
          f"near-miss cutoff={NEAR_MISS_SCORE}")
    print(f"artifacts: {s['files']}  ({s['agentic']} agentic, {s['linear']} linear)   "
          f"claims: {s['claims']}   comparisons: {s['comparisons']}")
    print(f"evidence pairs scored: {s['pairs']}"
          + (f"   EXCLUDED (corpus drift): {s['pairs_corpus_drift']} pairs "
             f"from {s['claims_corpus_drift']} claim(s)" if s["pairs_corpus_drift"] else ""))
    if s["pairs_corpus_drift"]:
        print("  A claim's quote is checked at run time against the submission PLUS that")
        print("  claim's own text and description. Where the claims file no longer holds the")
        print("  claim (the extractor was replaced), the run-time corpus cannot be rebuilt, so")
        print("  a mismatch would measure our reconstruction, not the pipeline. Excluded.")
    if s["no_source"]:
        print(f"NOTE: {s['no_source']} pair(s) had no reconstructable paper text "
              f"(counted as unverified)")

    print("\n--- verification rate by side " + "-" * (W - 30))
    print(f"{'':14}{'verified':>10}{'exact':>9}{'fuzzy':>9}{'near miss':>11}"
          f"{'absent':>9}{'too short':>11}{'empty':>8}")
    for name, c in (("claim side", s["claim_side"]), ("paper side", s["paper_side"])):
        ok = c["exact"] + c["fuzzy"]
        tot = sum(c.values())
        print(f"{name:14}{_pct(ok, tot):>10}{c['exact']:>9}{c['fuzzy']:>9}"
              f"{c['near_miss']:>11}{c['absent']:>9}{c['too_short']:>11}{c['empty']:>8}")
    print(f"{'BOTH sides':14}{_pct(s['fully_verified'], s['pairs']):>10}"
          f"   ({s['fully_verified']} of {s['pairs']} pairs fully verified)")

    print("\n--- how the prior paper was read " + "-" * (W - 34))
    print(f"{'depth':32}{'pairs':>8}{'fully verified':>17}")
    for d, v in sorted(s["by_depth"].items(), key=lambda kv: -kv[1]["pairs"]):
        print(f"{d[:32]:32}{v['pairs']:>8}{_pct(v['verified'], v['pairs']):>17}")
    print(f"\n{'paper text available as':32}{'pairs':>8}{'fully verified':>17}")
    for d, v in sorted(s["by_paper_source"].items(), key=lambda kv: -kv[1]["pairs"]):
        print(f"{d[:32]:32}{v['pairs']:>8}{_pct(v['verified'], v['pairs']):>17}")

    print("\n--- is the evidence gate load-bearing? " + "-" * (W - 40))
    tot = s["can_refute_stored"]
    attempted = tot + s["downgraded_at_runtime"]
    print(f"refutations the model proposed          : {attempted}")
    print(f"  downgraded at run time by the gate    : {s['downgraded_at_runtime']:>4}  "
          f"{_pct(s['downgraded_at_runtime'], attempted)}")
    print(f"  kept as can_refute                    : {tot:>4}  {_pct(tot, attempted)}")
    print(f"    of those, still hold under this rule: {s['can_refute_survives']:>4}  "
          f"{_pct(s['can_refute_survives'], tot)}")
    print(f"    VIOLATIONS (kept but unsupported)   : {s['gate_violations']:>4}  "
          f"{_pct(s['gate_violations'], tot)}")
    print("  The artifacts store the status AFTER the gate ran, so the downgrade count is")
    print("  read from the marker the gate writes into the note, not re-derived from them.")

    if s["legacy_pairs"]:
        print("\n--- old rule vs. current rule " + "-" * (W - 31))
        print(f"pairs written under the old artifact_a rule (paper side only, substring,")
        print(f"no minimum length): {s['legacy_pairs']}")
        if s["legacy_would_flip"]:
            for k, v in s["legacy_would_flip"].most_common():
                print(f"  {k:28}: {v:>4}  {_pct(v, s['legacy_pairs'])}")
        else:
            print("  no verdict changes")

    worst = sorted((r for r in per_run if r["pairs"]),
                   key=lambda r: r["fully_verified"] / r["pairs"])[:5]
    if worst:
        print("\n--- weakest runs (lowest share of fully verified pairs) " + "-" * 22)
        for r in worst:
            print(f"  {r['submission_id'][:44]:44} "
                  f"{r['fully_verified']:>3}/{r['pairs']:<3} "
                  f"{_pct(r['fully_verified'], r['pairs'])}")
    print("=" * W)


def main():
    ap = argparse.ArgumentParser(description="Grounding + verifiability analysis")
    ap.add_argument("--roots", nargs="+", default=["data", "eval/out/data"])
    ap.add_argument("--min-quote-tokens", type=int, default=ev.DEFAULT_MIN_QUOTE_TOKENS)
    ap.add_argument("--fuzzy-threshold", type=float, default=ev.DEFAULT_FUZZY_THRESHOLD)
    ap.add_argument("--out", default="eval/out/verifiability.json")
    args = ap.parse_args()
    analyse(args.roots, args.min_quote_tokens, args.fuzzy_threshold, args.out)


if __name__ == "__main__":
    main()
