"""Paper-level novelty summary."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import source_refs
import verdict as vd


PROMPT_VERSION = "paper_synthesis_v3_consistent_evidence_statements"

_RULES = """You are writing the paper-level novelty summary that opens a novelty report for a peer reviewer.

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
"""

_RULE_10 = """10. Keep evidence statements consistent throughout the summary.
   If a comparison's partial-overlap assessment was confirmed, do not
   later describe that same assessment as unsupported.

   When discussing an unsupported assessment, identify the specific
   claim and prior work. Distinguish it from other, confirmed comparisons.
   Do not change the recorded comparison results.
"""

_OUTPUT = """
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

PAPER_SYNTHESIS_PROMPT = _RULES + _RULE_10 + _OUTPUT

# paper_synthesis_v2_confirmed_vs_material: the same prompt without rule 10. It wrote the
# summaries of the ten human-study papers except the linear one of astabench.
PROMPT_V2 = _RULES + _OUTPUT

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


def _txt(x) -> str:
    return " ".join(str(x or "").split())


def _evidence_phrase(c: dict) -> str:
    """The evidence check's result, always stated explicitly."""
    status = vd.evidence_status(c)
    check = c.get("evidence_check") or {}
    if not status:
        return "no evidence check recorded"
    supporting = [i for i in (check.get("supporting_pair_indices") or []) if str(i).isdigit()]
    if status == "material":
        return f"material evidence (supporting pairs: {len(supporting)})"
    return {
        "nonmaterial": "examined passages did not support it",
        "insufficient": "evidence check inconclusive",
    }.get(status, status)


def _comparison_block(c: dict, ref: str, claim_label: str) -> List[str]:
    out = [
        f"- {ref} — {_txt(c.get('title')) or 'Untitled prior work'} [{claim_label}]",
        f"  Assessed overlap: {vd.degree(c) or 'not recorded'}",
        f"  Evidence check: {_evidence_phrase(c)}",
    ]
    for label, key in (
        ("Shared contribution", "what_is_shared"),
        ("Reported difference", "submission_delta"),
    ):
        if c.get(key):
            out.append(f"  {label}: {_txt(c[key])}")
    note = c.get("assessment") or c.get("brief_note")
    if note:
        out.append(f"  Novelty argument: {_txt(note)}")
    return out


def build_findings(
    artifact_a: dict, artifact_b: dict, claim_order: List[str], claim_names: dict, refs: dict
) -> str:
    """What the model sees: recorded results, no traces and no quotes."""
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
            (strong if vd.degree_confirmed(c) else proposed).append(block)

    out += ["## SUBSTANTIAL-OR-STRONGER OVERLAP, SUPPORTED BY THE EVIDENCE CHECK", ""]
    if strong:
        for block in strong:
            out += block + [""]
    else:
        out += [
            "None. No comparison reached substantial-or-stronger overlap with material evidence.",
            "",
        ]

    out += [
        "## SUBSTANTIAL-OR-STRONGER OVERLAP, PROPOSED BUT NOT SUPPORTED BY THE EVIDENCE CHECK",
        "",
        "These are proposals that the evidence check did not confirm. They are NOT "
        "established overlaps.",
        "",
    ]
    if proposed:
        for block in proposed:
            out += block + [""]
    else:
        out += ["None.", ""]

    out += [
        "## CONFIRMED SHARED ELEMENTS BELOW SUBSTANTIAL",
        "",
        "Shared elements the evidence check confirmed at `partial` degree. They are "
        "NOT anticipation of the claim, but they are real commonalities: a summary "
        "must not describe these claims as having no overlap with prior work.",
        "",
    ]
    partial_lines = []
    for cid in claim_order:
        comparisons = (a_by.get(cid) or {}).get("comparisons") or []
        confirmed = [c for c in comparisons if vd.degree(c) == "partial" and vd.degree_confirmed(c)]
        if confirmed:
            ids = ", ".join(refs.get(source_refs.paper_id(c), "R?") for c in confirmed)
            partial_lines.append(
                f"- {labels[cid]}: {len(confirmed)} confirmed partial overlap(s) ({ids})"
            )
    out += partial_lines or ["None recorded."]
    out.append("")

    out += ["## OPEN CONFLICTS AND EVIDENCE GAPS", ""]
    gaps = []
    for cid in claim_order:
        comparisons = (a_by.get(cid) or {}).get("comparisons") or []
        conflicting = [c for c in comparisons if vd.conflicts(c)]
        inconclusive = [c for c in comparisons if vd.evidence_status(c) == "insufficient"]
        unchecked = [c for c in comparisons if not vd.evidence_status(c)]
        unconfirmed = [
            c
            for c in comparisons
            if vd.evidence_status(c) == "material"
            and not vd.degree_confirmed(c)
            and vd.degree(c) in vd.OVERLAP_DEGREES
        ]
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
                    for c in group
                )
            gaps.append(line)
    out += gaps or ["None recorded."]
    out.append("")

    if not strong and not proposed:
        out += [
            "## STRONGEST COMPARISONS ACTUALLY FOUND",
            "",
            "No substantial-or-stronger overlap was proposed at all. These are the "
            "strongest comparisons on record, for orientation only.",
            "",
        ]
        best = []
        for cid in claim_order:
            comparisons = (a_by.get(cid) or {}).get("comparisons") or []
            ranked = sorted(comparisons, key=vd.sort_key)
            for c in ranked[:2]:
                if vd.degree(c):
                    best.append(
                        _comparison_block(c, refs.get(source_refs.paper_id(c), "R?"), labels[cid])
                    )
        if best:
            for block in best:
                out += block + [""]
        else:
            out += ["No comparison recorded an overlap degree.", ""]
    return "\n".join(out).rstrip() + "\n"


def fingerprint(findings: str) -> str:
    """Identifies the exact claim results this summary was derived from."""
    return hashlib.sha256(findings.encode("utf-8")).hexdigest()


def prompt_sha256() -> str:
    return hashlib.sha256(PAPER_SYNTHESIS_PROMPT.encode("utf-8")).hexdigest()


def is_stale(summary: Optional[dict], findings: str) -> bool:
    """True when the stored summary no longer describes the current claim results."""
    if not summary:
        return False
    return summary.get("inputs_fingerprint") != fingerprint(findings)


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
        kw = (
            {"reasoning_effort": os.getenv("NOVELTY_CONCLUSION_EFFORT", "low")}
            if model_name.startswith(("gpt-5", "o1", "o3", "o4"))
            else {"temperature": temperature}
        )
        self.model_name = model_name
        self.llm = ChatOpenAI(model_name=model_name, api_key=api_key, **kw)

    def _invoke(self, prompt: str):
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
            raw = self.llm.with_structured_output(_schema(), include_raw=True).invoke(prompt)
        parsed = raw["parsed"]
        if parsed is None:
            raise RuntimeError(f"structured output failed: {raw.get('parsing_error')}")
        usage = getattr(raw.get("raw"), "usage_metadata", None) or {}
        return parsed, usage

    def summarize(self, findings: str) -> dict:
        prompt = (
            PAPER_SYNTHESIS_PROMPT.replace("{lo}", str(WORDS_LO))
            .replace("{hi}", str(WORDS_HI))
            .replace("{findings}", findings)
        )
        parsed, usage = self._invoke(prompt)
        words = len(f"{parsed.main_novelty_concern} {parsed.remaining_contribution}".split())
        retried = False
        if not WORDS_LO <= words <= WORDS_HI:
            retried = True
            second, usage2 = self._invoke(
                prompt + f"\n\n# REVISION\nYour previous answer was {words} words across "
                f"both fields. Rewrite it within {WORDS_LO}-{WORDS_HI} words in total, "
                "keeping the same findings and the same sources. Cut detail, not content."
            )
            if abs(
                len(f"{second.main_novelty_concern} {second.remaining_contribution}".split())
                - (WORDS_LO + WORDS_HI) // 2
            ) < abs(words - (WORDS_LO + WORDS_HI) // 2):
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
            "usage": {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            },
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


def build(
    data_dir: str, submission_id: str, variant: str = "", model_name: str = "gpt-4.1"
) -> dict:
    """Generate the summary and store it in Artifact B next to the results it describes."""
    findings, b_path, artifact_b = context_for(data_dir, submission_id, variant)
    summary = PaperSynthesizer(model_name=model_name).summarize(findings)
    artifact_b["paper_summary"] = summary
    b_path.write_text(json.dumps(artifact_b, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
