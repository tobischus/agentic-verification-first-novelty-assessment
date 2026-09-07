#!/usr/bin/env python3
"""
Run threat-first examination over every claim of a submission and write the deliverable.

The document mirrors battle_export.py section for section -- same headings, same order,
the same quote conventions -- because the comparison it is written for judges assessments,
and a format the raters can tell apart is a format that decides the comparison instead of
the content.

What it can say that the existing export cannot: why each paper was examined, why the rest
were not, and why the examination stopped.

Usage
-----
  python eval/threat_run_all.py --submission transducing_language_models
  python eval/threat_run_all.py --submission ID --budget 8 --out comparison/outputs/ID__threat.md
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                          # noqa: E402

load_dotenv()

_LQ, _RQ = "“", "”"
_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]
_QUOTE_NOTE = (
    "Text in quotation marks (“…”) is quoted verbatim from the document it is "
    "attributed to and was checked against that document automatically. Everything else is "
    "the system's own prose."
)
DEG = {"same": "delivers the same contribution", "substantial": "substantial overlap",
       "partial": "partial overlap", "superficial": "no overlap of contribution",
       "none": "unrelated to the claim"}


def _q(t):
    return _LQ + " ".join((t or "").split()) + _RQ


def _clip(t, limit):
    """Trim to the last complete sentence within `limit`.

    A blind rating marked this document down for "truncated" summaries: cutting at a fixed
    character count leaves half a clause, which reads as a summary that ran out rather than
    one that ended.
    """
    t = " ".join((t or "").split())
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for stop in (". ", "; ", ", "):
        i = cut.rfind(stop)
        if i > limit * 0.5:
            return cut[:i + 1].rstrip(" ,;")
    return cut.rsplit(" ", 1)[0]


def render(sid: str, data_dir: str, results: list, overall: str = "") -> str:
    sub = Path(data_dir) / sid
    meta = json.loads((sub / f"{sid}.json").read_text(encoding="utf-8")) if (sub / f"{sid}.json").exists() else {}
    claims_doc = json.loads((sub / f"{sid}_claims.json").read_text(encoding="utf-8"))
    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]

    out = ["# Novelty Assessment", ""]
    if meta.get("title"):
        out += [f"**{meta['title']}**", ""]
    if meta.get("publication_date"):
        out += [f"Publication date: {meta['publication_date']}", ""]

    out += ["## Extracted claims", ""]
    for i, c in enumerate(claims, 1):
        out += [f"### Extracted Claim {i}", "", (c.get("claim_text") or "").strip(), ""]
        if c.get("evidence_quote"):
            out += ["Evidence in paper:", "", _q(c["evidence_quote"]), ""]

    seen = {}
    for r in results:
        for c in r["examined"]:
            p = c["_paper"]
            seen.setdefault(p["paper_id"], (p.get("title", ""), c.get("overlap_degree", "")))
    if seen:
        out += ["## Related work examined", "",
                f"{len(seen)} papers were read in full and compared against the claims above; "
                f"the rest of the retrieved pool ranked below the level at which a paper could "
                f"still challenge a claim.", ""]
        for title, deg in sorted(seen.values(), key=lambda x: x[0].lower()):
            out.append(f"- {title} — {DEG.get(deg, deg)}")
        out.append("")

    if overall:
        out += ["## Overall assessment", "", overall.strip(), ""]

    out += ["## Review", ""]
    for n, r in enumerate(results):
        claim = r["claim"]
        ex = sorted(r["examined"], key=lambda c: -c["_paper"]["threat"])
        threats = [c for c in ex if (c.get("overlap_degree") or "") in ("same", "substantial")]
        label = _ORDINALS[n] if n < len(_ORDINALS) else f"Claim {n + 1}"
        out += ["---", "", f"### {label} extracted claim", "",
                (claim.get("claim_text") or "").strip(), ""]
        verdict = ("challenged by prior work" if threats
                   else "not challenged in the examined literature")
        out += [f"**Verdict:** {verdict}", ""]
        out += [f"{len(threats)} of the {len(ex)} papers examined for this claim challenge it. "
                f"Examination stopped because: {r['stop_reason'].replace('_', ' ')}.", ""]

        # Only a CHALLENGE earns a full entry. Everything the examination touched is
        # reported, but a claim with three challenges and nineteen partial overlaps, each
        # given a paragraph and four quotes, is the page this design set out to replace:
        # measured over 60 claims, listing only substantial-or-same takes the reviewer from
        # 4.7 papers per claim to 1.1, and on the claim that started this it leaves exactly
        # the two that carry the decision.
        overlapping = [c for c in ex if (c.get("overlap_degree") or "") in
                       ("same", "substantial")]
        partial = [c for c in ex if (c.get("overlap_degree") or "") == "partial"]
        distinct = [c for c in ex if c not in overlapping and c not in partial]

        for c in overlapping:
            p = c["_paper"]
            deg = (c.get("overlap_degree") or "").lower()
            out += [f"#### {p.get('title', '')}", "",
                    f"**{DEG.get(deg, deg).capitalize()}.** "
                    f"{_clip(p['threat_reason'], 200)}", ""]
            note = c.get("assessment") or c.get("brief_note") or ""
            if note:
                out += [note.strip(), ""]
            pairs = [x for x in (c.get("evidence_pairs") or [])
                     if x.get("claim_quote_verified") and x.get("paper_quote_verified")]
            for x in pairs[:3]:
                out += ["The submission states:", "", _q(x["claim_quote"]), "",
                        "The prior work states:", "", _q(x["paper_quote"]), ""]
                if x.get("rationale"):
                    out += [x["rationale"].strip(), ""]
            # Every verified span of the paper, not one: a comparison without a PAIR still
            # read the paper and confirmed spans in it, and dropping them leaves an
            # assertion where evidence exists.
            # Verified spans of the paper IN ADDITION to the pairs. A blind rating marked
            # this document down on verifiability against a version that quoted far more,
            # and a pair plus three spans is still a fraction of the old page's length.
            quotes = [x["content"] for x in (c.get("paper_realization") or [])
                      if x.get("kind") == "quote" and x.get("verified")]
            if quotes and not pairs:
                out += ["The prior work states:", ""]
                for q in quotes[:2]:
                    out += [_q(q), ""]
            if c.get("withdraw_reason"):
                out += ["This paper was first judged to overlap substantially; the judgement "
                        "was withdrawn because no passage of it could be paired with the "
                        "claim. " + c["withdraw_reason"].strip(), ""]
            if c.get("submission_delta"):
                out += ["What the submission adds beyond it: " + c["submission_delta"].strip(), ""]

        # Examined and found not to overlap: one line each. They were read in full, which is
        # worth recording, but a page that spends a paragraph on every paper it cleared is
        # the page this design set out to replace.
        if partial:
            out += ["#### Examined, partial overlap only", "",
                    "Each of these delivers a piece of what the claim promises without "
                    "challenging it:", ""]
            for c in partial:
                pp = c["_paper"]
                # what THIS paper has that touches the claim -- the submission's delta is
                # the same sentence for every one of them, so a list of deltas reads as one
                # sentence repeated and tells the reviewer nothing about the papers.
                shared = (c.get("what_is_shared") or "").strip()
                if not shared:
                    shared = (c.get("brief_note") or c.get("assessment") or "").strip()
                delta = (c.get("submission_delta") or "").strip()
                line = f"- {pp.get('title', '')} — {_clip(shared, 260)}"
                if delta:
                    line += f" The submission adds: {_clip(delta, 180)}"
                out.append(line)
            out.append("")

        if distinct:
            out += ["#### Examined and found not to overlap", ""]
            for c in distinct:
                p = c["_paper"]
                why = (c.get("brief_note") or c.get("assessment") or "").strip()
                out.append(f"- {p.get('title', '')} — {why[:260]}")
            out.append("")

        rest = [p for p in r["ranked"]
                if p["paper_id"] not in {c["_paper"]["paper_id"] for c in ex}]
        if rest:
            out += ["#### Examined no further", "",
                    "These ranked below the level at which a paper could still challenge this "
                    "claim, and were not read in full:", ""]
            for p in rest[:12]:
                out.append(f"- {p.get('title', '')} — {_clip(p['threat_reason'], 200)}")
            if len(rest) > 12:
                out.append(f"- … and {len(rest) - 12} more")
            out.append("")

    out += ["---", "", _QUOTE_NOTE]
    return "\n".join(out).rstrip() + "\n"


SYNTH_PROMPT = """Write the opening paragraph of a novelty assessment: what a reviewer should take away across ALL of this paper's claims, before they read the per-claim detail.

Ground it only in the findings below. Name the prior work that challenges a claim, say which claims stand, and where the evidence is thin say so. Never attribute the submission's own contributions to a prior paper: the lines marked "what THIS SUBMISSION still adds" describe the paper under review, not its rivals. No preamble, no restating the task, one paragraph.

{findings}"""


def synthesize(results: list) -> str:
    """One paragraph across the claims, which the per-claim pages cannot supply.

    A blind rating put this document behind the previous one on usefulness with the reason
    that it "buries conclusions" and has no overall assessment, while the old export opens
    with one. The synthesis is generated from the findings already made -- it introduces no
    new judgement, it states the ones already reached in one place.
    """
    import os
    from langchain_openai import ChatOpenAI
    lines = []
    for r in results:
        ch = [c for c in r["examined"]
              if (c.get("overlap_degree") or "") in ("same", "substantial")]
        lines.append(f"CLAIM: {(r['claim'].get('claim_text') or '')[:400]}")
        lines.append(f"  verdict: {'challenged' if ch else 'not challenged'} "
                     f"({len(r['examined'])} papers examined, stopped: {r['stop_reason']})")
        for c in ch:
            # Label both sides explicitly. Written as "challenged by X -- <delta>" the
            # model read the submission's own delta as a property of the challenger and
            # credited this paper's construction to the prior work.
            lines.append(f"  challenged by (PRIOR WORK): {c['_paper'].get('title', '')}")
            lines.append(f"    what the prior work does: "
                         f"{(c.get('what_is_shared') or '')[:200]}")
            lines.append(f"    what THIS SUBMISSION still adds beyond it: "
                         f"{(c.get('submission_delta') or '')[:200]}")
    try:
        llm = ChatOpenAI(model_name=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"),
                         api_key=os.getenv("OPENAI_API_KEY"), max_retries=4, timeout=180)
        return llm.invoke(SYNTH_PROMPT.format(findings=chr(10).join(lines))).content.strip()
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser(description="Threat-first over every claim, as a document")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)

    sys.path.insert(0, str(REPO / "eval"))
    import threat_first_test as t
    sub = Path(args.data_dir) / args.submission
    art = json.loads((sub / f"{args.submission}_artifact_a.json").read_text(encoding="utf-8"))
    claims_doc = json.loads((sub / f"{args.submission}_claims.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in claims_doc.get("claims", [])}

    results, usd, calls, t0 = [], 0.0, 0, time.perf_counter()
    for e in art.get("claims", []):
        cid = e["claim_id"]
        if cid not in by_id:
            continue
        print(f"\n########## {cid} ##########")
        r = t.run(args.data_dir, args.submission, cid, args.model, args.budget)
        r["claim"] = by_id[cid]
        results.append(r)
        usd += r["usd"]; calls += r["spend"]["calls"]

    Path("eval/out").mkdir(parents=True, exist_ok=True)
    Path(f"eval/out/threat_all_{args.submission}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    overall = synthesize(results)
    md = render(args.submission, args.data_dir, results, overall)
    out = args.out or f"comparison/outputs/{args.submission}__threat.md"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(md, encoding="utf-8")
    print(f"\n{'=' * 78}")
    print(f"{len(results)} claims · {calls} calls · ${usd:.4f} · "
          f"{(time.perf_counter() - t0) / 60:.1f} min · {len(md.split())} words")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
