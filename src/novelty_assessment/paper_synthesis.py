#!/usr/bin/env python3
"""Step 5b: the paper-level novelty summary.

Final claim reviews -> THIS STEP -> stored in Artifact B -> rendered by battle_export.

The report already answers "what happened to each claim". It does not answer the question a
reviewer actually opens it with: does this submission, as a whole, have a novelty problem?
Reading fifteen per-claim sections to find out is the work this step does once.

What it is NOT allowed to do:

- change any claim verdict or any paper-pair judgement. It summarises decisions that are
  already fixed in Artifact A/B; the deterministic controller owns them.
- treat a PROPOSED overlap degree as an established one. The context below separates
  "substantial and supported by the evidence check" from "substantial but not supported"
  STRUCTURALLY, not just in prose, so the two cannot be blurred by a careless reading:
  a proposed `substantial` whose evidence check came back insufficient is exactly the
  case that must not be summarised as a secured overlap.
- recommend acceptance or rejection, or mention literature that is not in the artifacts.

Why it lives here and not in battle_export: the export renders, it does not decide, and it
makes no model calls -- it is the artifact the system comparison uses. The summary is
generated once, stored beside the claim results it was derived from, and fingerprinted
against them, so a later change to those results marks it stale instead of leaving a
confident paragraph standing over a report that no longer says that (see `is_stale`).

The agent and the linear baseline run the SAME step with the same prompt and model, so a
difference between their reports stays a difference in their reviews rather than in how
their reviews were summarised.

Usage
-----
  python paper_synthesis.py --data-dir data --submission-id <id> [--variant agent]
  python paper_synthesis.py --data-dir data --submission-id <id> --check   # no model call
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import source_refs
import verdict as vd

# pydantic and langchain are imported only where the model is actually called. Everything
# above that -- the findings context, the fingerprint, the staleness test -- is pure, so
# battle_export can import this module to decide whether a stored summary is still current
# without dragging the model stack into the renderer.

#: v2 separates "the evidence check confirmed this overlap" from "a shared element was
#: found": v1 split its findings on `material` alone, so comparisons the check had
#: declined were summarised as established overlap, and it gave the model nothing below
#: `substantial`, so "no supported substantial overlap" came out as "no overlap at all".
#: v3 adds rule 10. v2 could name a claim's confirmed partial overlaps in one section and
#: then, in the other, describe the same comparisons as not establishing their proposed
#: degree -- taking the confirmation back in a sentence that was really about a DIFFERENT
#: comparison (one substantial proposal the check declined). The two statements were each
#: defensible in isolation and contradictory together.
PROMPT_VERSION = "paper_synthesis_v3_consistent_evidence_statements"

# Deliberately without a worked example. A single example of a filled-in summary would be
# copied in shape and in emphasis by every run, and the pilot papers are the ones whose
# examples were at hand -- so the rules are stated instead, and the model writes from the
# evidence it is given rather than from a template it has seen.
PAPER_SYNTHESIS_PROMPT = """You are writing the paper-level novelty summary that opens a novelty report for a peer reviewer.

Everything you need is in FINDINGS below. It is a condensed view of decisions that have
already been made and are FIXED.

## WHAT YOU ARE DOING
Summarise the findings. You are not re-reviewing the paper.

## RULES
1. Summarise the recorded judgements. Do not change, strengthen, or weaken any claim
   verdict or any paper-comparison judgement, and do not add a comparison of your own.
2. Prioritise strong overlaps that the evidence check supported. A comparison listed under
   "PROPOSED BUT NOT SUPPORTED BY THE EVIDENCE CHECK" is NOT an established overlap and
   must never be summarised as one; name it as proposed-but-unsupported or leave it out.
   The same holds for anything listed as "shared element found but proposed degree NOT
   confirmed" or as an inconclusive evidence check: a shared element was found, the
   overlap it was proposed to establish was not. Never merge such a comparison into a
   statement that an overlap is supported -- if you mention it, say it remains unresolved.
3. Distinguish "one claim is affected" from "the contribution as a whole is anticipated".
   These are different statements and the second needs far more than the first.
4. Do not count overlapping claims as independent votes. Several claims can describe the
   same underlying contribution; if they do, say so instead of adding them up.
5. Do not invent an importance weighting of the claims. If the findings do not say how
   much a claim matters to the overall contribution, write within that limit rather than
   assuming it is central or peripheral.
6. If the SUPPORTED section of FINDINGS is empty -- no substantial-or-stronger overlap
   anywhere in the submission is backed by the evidence check -- write exactly this
   sentence in the first section: "No adequately supported substantial overlap was
   identified in the examined literature." Use it only in that case, and never write that
   the paper is novel.
   That sentence is about ANTICIPATION, not about commonality. It ends with a full stop
   and is never altered. Whenever "CONFIRMED SHARED ELEMENTS BELOW SUBSTANTIAL" is not
   empty, the NEXT sentence must name the claims concerned, as its own sentence and in as
   few words as possible -- e.g. "Confirmed partial overlaps were found for Claim 2 and
   Claim 4." Never write, in any wording, that no overlap, no shared element or no related
   prior work was found for a claim that appears in that section -- "not anticipated" and
   "nothing in common" are different findings, and only the first was established.
7. No acceptance or rejection recommendation. No claim about literature that is not in
   FINDINGS.
8. Refer to prior work by its source id exactly as FINDINGS gives it (R1, R2, ...), and to
   claims as "Claim 1", "Claim 2", ... Naming a title as well is fine; inventing or
   renumbering an id is not.
9. Do not list every partial overlap, and do not enumerate their source ids. Naming the
   CLAIMS that carry confirmed partial overlaps (rule 6) is required; listing the sources
   behind them is not, and a long id list is what pushes this summary over its budget.
   Mention an individual partial finding only where it changes what a reviewer would
   conclude.
10. Keep evidence statements consistent throughout the summary.
   If a comparison's partial-overlap assessment was confirmed, do not
   later describe that same assessment as unsupported.

   When discussing an unsupported assessment, identify the specific
   claim and prior work. Distinguish it from other, confirmed comparisons.
   Do not change the recorded comparison results.

## OUTPUT
Two short sections. {lo}-{hi} words IN TOTAL across both fields together -- a hard limit,
not a target. Count your words and cut before answering; a reviewer reads this first and a
long summary defeats its purpose. Prefer naming the decisive comparisons over listing
every detail of them.

main_novelty_concern:
  Which claims are materially touched by which prior work -- or, if none is supported,
  rule 6's sentence. State the evidence status where it qualifies what you are saying.

remaining_contribution:
  Which contributions remain distinguishable according to the comparisons that were made.
  Do not assert that what remains is scientifically significant or sufficiently novel;
  the findings do not establish that. Where findings about one claim do not settle the
  submission as a whole, say so.

Write plain prose. No headings, no bullet lists, no markdown inside the two fields.

# FINDINGS
{findings}
"""

WORDS_LO, WORDS_HI = 120, 180


def _schema():
    """The structured-output schema, built on demand so importing this module stays cheap."""
    from pydantic import BaseModel, Field

    class PaperSummary(BaseModel):
        main_novelty_concern: str = Field(
            description="Which claims are materially touched by which prior work, or the "
                        "no-supported-overlap sentence. Plain prose."
        )
        remaining_contribution: str = Field(
            description="What remains distinguishable according to the comparisons made, "
                        "without asserting significance or sufficiency. Plain prose."
        )

    return PaperSummary


# --------------------------------------------------------------------- context --

def _txt(x) -> str:
    return " ".join(str(x or "").split())


def _evidence_phrase(c: dict) -> str:
    """The evidence check's result, always stated -- never left to be inferred."""
    status = vd.evidence_status(c)
    check = c.get("evidence_check") or {}
    if not status:
        return "no evidence check recorded"
    supporting = [i for i in (check.get("supporting_pair_indices") or []) if str(i).isdigit()]
    if status == "material":
        return f"material evidence (supporting pairs: {len(supporting)})"
    return {"nonmaterial": "examined passages did not support it",
            "insufficient": "evidence check inconclusive"}.get(status, status)


def _comparison_block(c: dict, ref: str, claim_label: str) -> List[str]:
    out = [f"- {ref} — {_txt(c.get('title')) or 'Untitled prior work'} [{claim_label}]",
           f"  Assessed overlap: {vd.degree(c) or 'not recorded'}",
           f"  Evidence check: {_evidence_phrase(c)}"]
    for label, key in (("Shared contribution", "what_is_shared"),
                       ("Reported difference", "submission_delta")):
        if c.get(key):
            out.append(f"  {label}: {_txt(c[key])}")
    note = c.get("assessment") or c.get("brief_note")
    if note:
        out.append(f"  Novelty argument: {_txt(note)}")
    return out


def build_findings(artifact_a: dict, artifact_b: dict, claim_order: List[str],
                   claim_names: dict, refs: dict) -> str:
    """The only thing the model sees: recorded results, no traces and no quotes.

    Every comparison carries its assessed degree AND its evidence status on adjacent
    lines, and the strong comparisons are split into supported and unsupported groups, so
    the two cannot be read as one. That split is the reason this is built in code rather
    than handed over as raw JSON.
    """
    b_by = {v.get("claim_id"): v for v in (artifact_b or {}).get("per_claim", []) or []}
    a_by = {e.get("claim_id"): e for e in (artifact_a or {}).get("claims", []) or []}
    labels = {cid: f"Claim {i}" for i, cid in enumerate(claim_order, 1)}

    out = ["## CLAIMS AND THEIR FINAL VERDICTS", ""]
    for cid in claim_order:
        entry, rec = a_by.get(cid) or {}, b_by.get(cid) or {}
        name = claim_names.get(cid) or entry.get("claim_name") or ""
        out.append(f"### {labels[cid]}{(' — ' + _txt(name)) if name else ''}")
        text = entry.get("claim_text") or ""
        if text:
            out.append(f"Claimed contribution: {_txt(text)}")
        out.append(f"Final verdict: {rec.get('verdict') or 'not recorded'}")
        if rec.get("rationale"):
            out.append(f"Rationale: {_txt(rec['rationale'])}")
        comparisons = entry.get("comparisons") or []
        out.append(f"Prior papers compared for this claim: {len(comparisons)}")
        out.append("")

    strong, proposed = [], []
    for cid in claim_order:
        for c in (a_by.get(cid) or {}).get("comparisons") or []:
            if vd.degree(c) not in ("same", "substantial"):
                continue
            block = _comparison_block(c, refs.get(source_refs.paper_id(c), "R?"), labels[cid])
            # `material` alone is not confirmation: it says a shared element was found,
            # not that the element carries the overlap at the proposed degree. Splitting
            # on it put comparisons the check had explicitly declined into the SUPPORTED
            # section, where the summary then reported them as established overlap.
            (strong if vd.degree_confirmed(c) else proposed).append(block)

    out += ["## SUBSTANTIAL-OR-STRONGER OVERLAP, SUPPORTED BY THE EVIDENCE CHECK", ""]
    if strong:
        for block in strong:
            out += block + [""]
    else:
        out += ["None. No comparison reached substantial-or-stronger overlap with material "
                "evidence.", ""]

    out += ["## SUBSTANTIAL-OR-STRONGER OVERLAP, PROPOSED BUT NOT SUPPORTED BY THE "
            "EVIDENCE CHECK", "",
            "These are proposals that the evidence check did not confirm. They are NOT "
            "established overlaps.", ""]
    if proposed:
        for block in proposed:
            out += block + [""]
    else:
        out += ["None.", ""]

    # Without this section the findings say nothing at all about claims whose overlaps
    # stayed below `substantial`, and a summary written from them cannot tell "not
    # anticipated" from "nothing in common was found". These are confirmed shared
    # elements -- the check backed both the evidence and the proposed partial degree.
    out += ["## CONFIRMED SHARED ELEMENTS BELOW SUBSTANTIAL", "",
            "Shared elements the evidence check confirmed at `partial` degree. They are "
            "NOT anticipation of the claim, but they are real commonalities: a summary "
            "must not describe these claims as having no overlap with prior work.", ""]
    partial_lines = []
    for cid in claim_order:
        comparisons = (a_by.get(cid) or {}).get("comparisons") or []
        confirmed = [c for c in comparisons
                     if vd.degree(c) == "partial" and vd.degree_confirmed(c)]
        if confirmed:
            ids = ", ".join(refs.get(source_refs.paper_id(c), "R?") for c in confirmed)
            partial_lines.append(f"- {labels[cid]}: {len(confirmed)} confirmed partial "
                                 f"overlap(s) ({ids})")
    out += partial_lines or ["None recorded."]
    out.append("")

    out += ["## OPEN CONFLICTS AND EVIDENCE GAPS", ""]
    gaps = []
    for cid in claim_order:
        comparisons = (a_by.get(cid) or {}).get("comparisons") or []
        conflicting = [c for c in comparisons if vd.conflicts(c)]
        inconclusive = [c for c in comparisons if vd.evidence_status(c) == "insufficient"]
        unchecked = [c for c in comparisons if not vd.evidence_status(c)]
        # Material evidence, proposed degree declined. Neither an established overlap nor
        # an absence of one -- so it belongs here, named, rather than silently joining
        # either side.
        unconfirmed = [c for c in comparisons
                       if vd.evidence_status(c) == "material" and not vd.degree_confirmed(c)
                       and vd.degree(c) in vd.OVERLAP_DEGREES]
        for label, group, note in (
            ("degree and evidence check disagree", conflicting, True),
            ("shared element found but proposed degree NOT confirmed", unconfirmed, False),
            ("evidence check inconclusive", inconclusive, False),
            ("no evidence check recorded", unchecked, False),
        ):
            if not group:
                continue
            ids = ", ".join(refs.get(source_refs.paper_id(c), "R?") for c in group)
            line = f"- {labels[cid]}: {len(group)}/{len(comparisons)} {label} ({ids})"
            if note:
                line += "".join(
                    f"\n    {refs.get(source_refs.paper_id(c), 'R?')}: "
                    f"{vd.degree(c) or 'unspecified degree'} vs. {vd.evidence_status(c)} evidence"
                    for c in group)
            gaps.append(line)
    out += gaps or ["None recorded."]
    out.append("")

    # Only when there is nothing strong to summarise: the best that WAS found, so the
    # summary can place the submission rather than saying nothing at all.
    if not strong and not proposed:
        out += ["## STRONGEST COMPARISONS ACTUALLY FOUND", "",
                "No substantial-or-stronger overlap was proposed at all. These are the "
                "strongest comparisons on record, for orientation only.", ""]
        best = []
        for cid in claim_order:
            comparisons = (a_by.get(cid) or {}).get("comparisons") or []
            ranked = sorted(comparisons, key=vd.sort_key)
            for c in ranked[:2]:
                if vd.degree(c):
                    best.append(_comparison_block(
                        c, refs.get(source_refs.paper_id(c), "R?"), labels[cid]))
        if best:
            for block in best:
                out += block + [""]
        else:
            out += ["No comparison recorded an overlap degree.", ""]
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------ staleness --

def fingerprint(findings: str) -> str:
    """Identifies the exact claim results this summary was derived from.

    Taken over the findings text rather than the whole artifact: it changes if and only if
    something the summary was allowed to see changed, so an unrelated edit elsewhere in
    Artifact A does not flag a summary that is in fact still accurate.
    """
    return hashlib.sha256(findings.encode("utf-8")).hexdigest()


def prompt_sha256() -> str:
    return hashlib.sha256(PAPER_SYNTHESIS_PROMPT.encode("utf-8")).hexdigest()


def is_stale(summary: Optional[dict], findings: str) -> bool:
    """True when the stored summary no longer describes the current claim results."""
    if not summary:
        return False
    return summary.get("inputs_fingerprint") != fingerprint(findings)


# ----------------------------------------------------------------- the builder --

def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _claim_order(sub_dir: Path, submission_id: str, artifact_a: dict):
    """The claim order the report displays, so "Claim 2" means the same everywhere."""
    doc = _load(sub_dir / f"{submission_id}_claims.json") or {}
    claims = [c for c in doc.get("claims", []) or [] if c.get("status") != "rejected"]
    a_ids = [e.get("claim_id") for e in (artifact_a or {}).get("claims", []) or []]
    order = [c["id"] for c in claims] or a_ids
    names = {c["id"]: c.get("claim_name") or c.get("name") or "" for c in claims}
    return [cid for cid in order if cid in set(a_ids)], names


class PaperSynthesizer:
    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        from langchain_openai import ChatOpenAI
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        # Same switch artifact_b.py uses: the reasoning models reject `temperature`.
        kw = ({"reasoning_effort": os.getenv("NOVELTY_CONCLUSION_EFFORT", "low")}
              if model_name.startswith(("gpt-5", "o1", "o3", "o4")) else
              {"temperature": temperature})
        self.model_name = model_name
        self.llm = ChatOpenAI(model_name=model_name, api_key=api_key, **kw)

    def _invoke(self, prompt: str):
        import warnings
        with warnings.catch_warnings():
            # LangChain serialises the parsed object back into the AIMessage, and pydantic
            # warns because the field is typed as None there. Cosmetic, and unrelated to
            # our own parse, which is checked right below -- but it buries real output.
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            raw = self.llm.with_structured_output(_schema(), include_raw=True).invoke(prompt)
        parsed = raw["parsed"]
        if parsed is None:
            raise RuntimeError(f"structured output failed: {raw.get('parsing_error')}")
        usage = getattr(raw.get("raw"), "usage_metadata", None) or {}
        return parsed, usage

    def summarize(self, findings: str) -> dict:
        prompt = (PAPER_SYNTHESIS_PROMPT
                  .replace("{lo}", str(WORDS_LO)).replace("{hi}", str(WORDS_HI))
                  .replace("{findings}", findings))
        parsed, usage = self._invoke(prompt)
        words = len(f"{parsed.main_novelty_concern} {parsed.remaining_contribution}".split())
        retried = False
        if not WORDS_LO <= words <= WORDS_HI:
            # One bounded retry, told the actual count. The budget is part of what was
            # specified, so a single correction is worth its cost; a loop is not, and a
            # silent overrun would quietly turn the opening summary into another section
            # to skim. If the retry also misses, the recorded word_count says so.
            retried = True
            second, usage2 = self._invoke(
                prompt + f"\n\n# REVISION\nYour previous answer was {words} words across "
                f"both fields. Rewrite it within {WORDS_LO}-{WORDS_HI} words in total, "
                "keeping the same findings and the same sources. Cut detail, not content.")
            if abs(len(f"{second.main_novelty_concern} {second.remaining_contribution}"
                       .split()) - (WORDS_LO + WORDS_HI) // 2) < abs(words - (WORDS_LO + WORDS_HI) // 2):
                parsed = second
            for k in ("input_tokens", "output_tokens"):
                usage[k] = (usage.get(k) or 0) + ((usage2 or {}).get(k) or 0)
        text = f"{parsed.main_novelty_concern} {parsed.remaining_contribution}"
        return {
            "retried_for_length": retried,
            "main_novelty_concern": parsed.main_novelty_concern.strip(),
            "remaining_contribution": parsed.remaining_contribution.strip(),
            "word_count": len(text.split()),
            "word_budget": [WORDS_LO, WORDS_HI],
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": prompt_sha256(),
            "model": self.model_name,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "inputs_fingerprint": fingerprint(findings),
            "usage": {"prompt_tokens": usage.get("input_tokens"),
                      "completion_tokens": usage.get("output_tokens")},
        }


def context_for(data_dir: str, submission_id: str, variant: str = ""):
    """(findings, artifact_b_path, artifact_b) -- everything but the model call."""
    from source_refs import variant_path
    sub_dir = Path(data_dir) / submission_id
    a_path = variant_path(sub_dir, submission_id, "artifact_a", variant)
    b_path = variant_path(sub_dir, submission_id, "artifact_b", variant)
    artifact_a = _load(a_path)
    if artifact_a is None:
        raise FileNotFoundError(f"{a_path.name} not found")
    artifact_b = _load(b_path)
    if artifact_b is None:
        raise FileNotFoundError(f"{b_path.name} not found -- run Artifact B first")
    order, names = _claim_order(sub_dir, submission_id, artifact_a)
    refs = source_refs.refs_for(artifact_a, order)
    findings = build_findings(artifact_a, artifact_b, order, names, refs)
    return findings, b_path, artifact_b


def build(data_dir: str, submission_id: str, variant: str = "",
          model_name: str = "gpt-4.1") -> dict:
    """Generate the summary and store it in Artifact B next to the results it describes."""
    findings, b_path, artifact_b = context_for(data_dir, submission_id, variant)
    summary = PaperSynthesizer(model_name=model_name).summarize(findings)
    artifact_b["paper_summary"] = summary
    b_path.write_text(json.dumps(artifact_b, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser(description="Step 5b: paper-level novelty summary")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--variant", default="", help="read/write the {variant}-suffixed artifacts")
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--check", action="store_true",
                    help="build and print the context, report staleness; NO model call")
    ap.add_argument("--print-context", action="store_true", help="with --check, print it in full")
    args = ap.parse_args()

    if args.check:
        findings, _b_path, artifact_b = context_for(args.data_dir, args.submission_id, args.variant)
        stored = artifact_b.get("paper_summary")
        print(f"findings: {len(findings.split())} words, fingerprint {fingerprint(findings)[:12]}")
        if not stored:
            print("stored summary: none")
        elif is_stale(stored, findings):
            print(f"stored summary: STALE (was {str(stored.get('inputs_fingerprint'))[:12]}, "
                  f"generated {stored.get('generated_at')})")
        else:
            print(f"stored summary: current ({stored.get('word_count')} words, "
                  f"{stored.get('prompt_version')}, {stored.get('generated_at')})")
        if args.print_context:
            print("\n" + findings)
        return

    summary = build(args.data_dir, args.submission_id, args.variant, args.model)
    print(f"[{args.variant or 'default'}] {summary['word_count']} words "
          f"(budget {WORDS_LO}-{WORDS_HI})")
    print("\nMain novelty concern:\n" + summary["main_novelty_concern"])
    print("\nRemaining contribution:\n" + summary["remaining_contribution"])
    u = summary.get("usage") or {}
    if u.get("prompt_tokens"):
        print(f"\ntokens: {u['prompt_tokens']} in / {u.get('completion_tokens')} out")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
