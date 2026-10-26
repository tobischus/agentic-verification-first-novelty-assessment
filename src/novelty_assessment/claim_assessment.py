"""Claim explanations: why each claim received its verdict."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import source_refs
import verdict as vd

PROMPT_VERSION = "claim_assessment_v1"

CLAIM_ASSESSMENT_PROMPT = """You are writing the claim-level assessment in a novelty report for a peer reviewer.

It explains why ONE claim of the submission received its verdict. Everything you need is
in FINDINGS below: the claim, its FIXED verdict, and the recorded comparisons with prior
work for this claim. These decisions have already been made.

## RULES
1. Explain the recorded verdict; never change it. Do not change, strengthen or weaken any
   overlap level or evidence-check result, and do not add a comparison of your own.
2. Say what the verdict rests on: name the decisive comparisons -- at most three -- by
   their source id (R1, R2, ... exactly as FINDINGS gives them) and state what the prior
   work already delivers and what the submission's claim adds beyond it, using the
   recorded "Shared contribution", "Reported difference" and "Novelty argument". If more
   comparisons share the same pattern, give their number instead of listing their ids --
   taken from COUNTS; when you name some and count the rest, the rest is the COUNTS number
   minus the ones you named.
   Mention OTHER COMPARISONS, if at all, only as a count.
3. Explain the level. For the strongest comparisons, say why the recorded level is what
   it is -- e.g. why an overlap is partial rather than substantial -- using only the
   recorded difference. If no comparison reached partial overlap, say that the recorded
   relations stay at a lower level and why, from the findings.
4. Keep the evidence status attached. An overlap whose evidence check confirmed the
   proposed level is "confirmed". A proposed overlap whose level the check did not
   support, whose check was inconclusive, or which has no check, is NOT established:
   if you mention it, say so for that specific source. Never describe the same comparison
   as both confirmed and unsupported. A CONFLICT between level and evidence check is an
   open disagreement: report it as such, in the direction FINDINGS states, and do not
   resolve it either way.
5. "Not challenged" means no comparison was recorded as anticipating the claim. It does
   not mean nothing is shared: if confirmed partial overlaps exist, say so. Never write
   that the claim is novel, and do not add the general caveat that the examined literature
   is limited -- the report states that right after your text.
6. A claim with no detailed comparison: say that the comparisons recorded for it stayed
   at superficial or no overlap, and name the evidence limits the findings list. Do not
   speculate about literature that was not examined.
7. No acceptance or rejection recommendation. No outside knowledge.

## OUTPUT
One paragraph of plain prose, {lo}-{hi} words -- a hard limit, not a target. No headings,
no bullet lists, no markdown. Prefer the decisive comparisons over listing every one.

# FINDINGS
{findings}
"""

WORDS_LO, WORDS_HI = 60, 130


def _txt(x) -> str:
    return " ".join(str(x or "").split())


def _check_phrase(c: dict) -> str:
    status = vd.evidence_status(c)
    if not status:
        return "no evidence check recorded (NOT established)"
    if status == "material":
        pds = (c.get("evidence_check") or {}).get("proposed_degree_supported")
        if vd.degree(c) in vd.OVERLAP_DEGREES:
            return (
                "material evidence; the proposed level is CONFIRMED"
                if pds is True
                else "material evidence, but the evidence check did NOT support the proposed "
                "level (NOT established at this level)"
            )
        return "material evidence of a shared element (no overlap level was proposed)"
    if status == "nonmaterial":
        return "the examined passages did not establish a shared element (NOT established)"
    return "evidence check inconclusive (NOT established)"


def build_claim_findings(
    entry: dict, claim_no: int, claim_text: str, verdict: str, refs: dict
) -> str:
    """What the model sees for one claim: recorded results only, no traces, no quotes."""
    comparisons = entry.get("comparisons") or []
    details = sorted(
        (c for c in comparisons if vd.is_overlap(c) or vd.conflicts(c)), key=vd.sort_key
    )
    rest = [c for c in comparisons if c not in details]

    def ref(c):
        return refs.get(source_refs.paper_id(c), "R?")

    out = [
        f"## Claim {claim_no}",
        f"Claimed contribution: {_txt(claim_text)}",
        f"FIXED VERDICT: {vd.verdict_label(verdict)}",
        "Comparisons recorded as anticipating (challenging) this claim: "
        + (", ".join(ref(c) for c in comparisons if vd.challenges(c)) or "none"),
        f"Prior papers compared for this claim: {len(comparisons)}",
        "",
    ]
    confirmed = [
        c for c in details if vd.degree(c) in vd.OVERLAP_DEGREES and vd.degree_confirmed(c)
    ]
    by_level = {}
    for c in confirmed:
        by_level[vd.degree(c)] = by_level.get(vd.degree(c), 0) + 1
    unconfirmed = [
        c
        for c in details
        if vd.degree(c) in vd.OVERLAP_DEGREES and not vd.degree_confirmed(c) and not vd.conflicts(c)
    ]
    conflicting = [c for c in details if vd.conflicts(c)]
    rest_levels = {}
    for c in rest:
        rest_levels[vd.degree(c) or "not recorded"] = (
            rest_levels.get(vd.degree(c) or "not recorded", 0) + 1
        )
    out += [
        "## COUNTS (exact -- use these numbers, never count yourself)",
        "",
        f"- detailed comparisons: {len(details)}",
        *(
            f"- confirmed {d} overlap: {n}"
            for d, n in sorted(by_level.items(), key=lambda kv: vd.degree_rank(kv[0]))
        ),
        f"- proposed overlap NOT established (level not supported, check inconclusive or "
        f"missing): {len(unconfirmed)}",
        f"- conflicts between level and evidence check: {len(conflicting)}",
        f"- other comparisons (no detailed section): {len(rest)}"
        + (
            " ("
            + ", ".join(
                f"{n} {d}"
                for d, n in sorted(rest_levels.items(), key=lambda kv: vd.degree_rank(kv[0]))
            )
            + ")"
            if rest
            else ""
        ),
        "",
    ]
    out += ["## DETAILED COMPARISONS (strongest first)", ""]
    if not details:
        out += [
            "None. No comparison for this claim reached partial overlap or recorded a "
            "conflict between its level and its evidence check.",
            "",
        ]
    for c in details:
        out.append(f"- {ref(c)} — {_txt(c.get('title')) or 'Untitled prior work'}")
        out.append(f"  Recorded overlap level: {vd.degree(c) or 'not recorded'}")
        out.append(f"  Evidence check: {_check_phrase(c)}")
        if vd.conflicts(c):
            if vd.degree(c) in vd.OVERLAP_DEGREES:
                out.append(
                    f"  CONFLICT: the recorded level ({vd.degree(c)}) was not borne out -- "
                    "the examined passages did not establish a shared element. The "
                    "disagreement is unresolved; the overlap is NOT established."
                )
            else:
                out.append(
                    f"  CONFLICT: the recorded level ({vd.degree(c) or 'none'}) is LOWER "
                    "than what the evidence check found -- it found material evidence of "
                    "a shared element. The disagreement is unresolved: neither the "
                    "recorded level nor a higher one is established."
                )
        for label, key in (
            ("Shared contribution", "what_is_shared"),
            ("Reported difference", "submission_delta"),
        ):
            if c.get(key):
                out.append(f"  {label}: {_txt(c[key])}")
        note = c.get("assessment") or c.get("brief_note")
        if note:
            out.append(f"  Novelty argument: {_txt(note)}")
        q = (c.get("evidence_check") or {}).get("unresolved_question") or c.get(
            "unresolved_deficit"
        )
        if q:
            out.append(f"  Open question recorded by the evidence check: {_txt(q)}")
        out.append("")
    if rest:
        inconclusive = sum(1 for c in rest if vd.evidence_status(c) == "insufficient")
        unchecked = sum(1 for c in rest if not vd.evidence_status(c))
        out += [
            "## OTHER COMPARISONS (no detailed section; numbers in COUNTS)",
            "",
            f"- of these, evidence check inconclusive: {inconclusive}",
            f"- of these, no evidence check recorded: {unchecked}",
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


def fingerprint(findings: str) -> str:
    return hashlib.sha256(findings.encode("utf-8")).hexdigest()


def prompt_sha256() -> str:
    return hashlib.sha256(CLAIM_ASSESSMENT_PROMPT.encode("utf-8")).hexdigest()


def is_stale(stored: Optional[dict], findings: str) -> bool:
    if not stored:
        return False
    return stored.get("inputs_fingerprint") != fingerprint(findings)


_NEG = re.compile(
    r"\b(not|no|never|without|nor|un(?:supported|confirmed|resolved)|"
    r"inconclusive|did not|does not|was not|were not)\b",
    re.I,
)


def consistency_problems(text: str, entry: dict, verdict: str, refs: dict) -> List[str]:
    """Deterministic checks on a generated text, each returned as a sentence for one revision."""
    problems = []
    comparisons = entry.get("comparisons") or []
    by_ref = {refs.get(source_refs.paper_id(c), "R?"): c for c in comparisons}
    cited = set(re.findall(r"\bR\d+\b", text))
    unknown = sorted(cited - set(by_ref), key=lambda r: int(r[1:]))
    if unknown:
        problems.append(
            f"Source id(s) {', '.join(unknown)} are not among this claim's "
            f"comparisons. Use only ids from FINDINGS."
        )
    if len(cited & set(by_ref)) > 5:
        problems.append(
            f"The text names {len(cited & set(by_ref))} source ids; name at most "
            "three decisive ones and give the others as a count."
        )
    words = len(text.split())
    if not WORDS_LO <= words <= WORDS_HI:
        problems.append(f"The text has {words} words; it must have {WORDS_LO}-{WORDS_HI}.")
    if re.search(r"\bnovel\b", text, re.I) and not re.search(r"\bnovelty\b", text, re.I):
        problems.append("Do not call the claim novel.")
    if verdict == "not_challenged" and re.search(
        r"\b(is|are|was|were)\s+(anticipated|challenged|refuted)\b", text, re.I
    ):
        for m in re.finditer(
            r"[^.]*\b(is|are|was|were)\s+(anticipated|challenged|refuted)\b[^.]*\.", text, re.I
        ):
            if not _NEG.search(m.group(0)):
                problems.append(
                    "The verdict is 'not challenged'; do not state that the claim "
                    f'is anticipated or challenged: "{m.group(0).strip()}"'
                )
    for sentence in re.split(r"(?<=[.;])\s+", text):
        ids = set(re.findall(r"\bR\d+\b", sentence)) & set(by_ref)
        if len(ids) != 1:
            continue
        c = by_ref[next(iter(ids))]
        confirmed = vd.degree_confirmed(c)
        if (
            not confirmed
            and vd.degree(c) in vd.OVERLAP_DEGREES
            and re.search(r"\bconfirmed\b", sentence, re.I)
            and not _NEG.search(sentence)
        ):
            problems.append(
                f"{next(iter(ids))}'s proposed level was NOT confirmed by the "
                f"evidence check, but this sentence calls it confirmed: "
                f'"{sentence.strip()}"'
            )
        if confirmed and re.search(
            r"\b(unsupported|not (?:been )?(?:supported|confirmed))\b", sentence, re.I
        ):
            problems.append(
                f"{next(iter(ids))}'s level WAS confirmed, but this sentence "
                f'calls it unsupported: "{sentence.strip()}"'
            )
    return problems


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def contexts_for(data_dir: str, submission_id: str, variant: str = ""):
    """[(claim_id, claim_no, entry, verdict, findings)], b_path, artifact_b, refs."""
    from source_refs import variant_path
    import paper_synthesis

    sub_dir = Path(data_dir) / submission_id
    a = _load(variant_path(sub_dir, submission_id, "artifact_a", variant))
    b_path = variant_path(sub_dir, submission_id, "artifact_b", variant)
    b = _load(b_path)
    if a is None or b is None:
        raise FileNotFoundError(f"{submission_id}/{variant}: artifact A or B missing")
    order, _names = paper_synthesis._claim_order(sub_dir, submission_id, a)
    refs = source_refs.refs_for(a, order)
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    b_by = {v.get("claim_id"): v for v in b.get("per_claim", [])}
    claims_doc = _load(sub_dir / f"{submission_id}_claims.json") or {}
    texts = {
        c["id"]: c.get("claim_text") for c in claims_doc.get("claims", []) or [] if c.get("id")
    }
    out = []
    for i, cid in enumerate(order, 1):
        entry = a_by[cid]
        verdict = (b_by.get(cid) or {}).get("verdict") or entry.get("agent_verdict") or "uncertain"
        text = entry.get("claim_text") or texts.get(cid) or entry.get("claim_name") or ""
        out.append((cid, i, entry, verdict, build_claim_findings(entry, i, text, verdict, refs)))
    return out, b_path, b, refs


class ClaimAssessor:
    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        from langchain_openai import ChatOpenAI
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.effort = (
            os.getenv("NOVELTY_CONCLUSION_EFFORT", "low")
            if model_name.startswith(("gpt-5", "o1", "o3", "o4"))
            else None
        )
        kw = {"reasoning_effort": self.effort} if self.effort else {"temperature": temperature}
        self.model_name = model_name
        self.llm = ChatOpenAI(model_name=model_name, api_key=api_key, **kw)

    def _invoke(self, prompt: str):
        msg = self.llm.invoke(prompt)
        usage = getattr(msg, "usage_metadata", None) or {}
        return " ".join(str(msg.content or "").split()), usage

    def assess(self, findings: str, entry: dict, verdict: str, refs: dict) -> dict:
        prompt = (
            CLAIM_ASSESSMENT_PROMPT.replace("{lo}", str(WORDS_LO))
            .replace("{hi}", str(WORDS_HI))
            .replace("{findings}", findings)
        )
        text, usage = self._invoke(prompt)
        problems = consistency_problems(text, entry, verdict, refs)
        revised = False
        if problems:
            revised = True
            text2, usage2 = self._invoke(
                prompt + "\n\n# YOUR PREVIOUS ANSWER\n" + text + "\n\n# REVISION\n"
                "Rewrite it. Fix exactly these problems and change nothing else:\n- "
                + "\n- ".join(problems)
            )
            problems2 = consistency_problems(text2, entry, verdict, refs)
            if len(problems2) <= len(problems):
                text, problems = text2, problems2
            for k in ("input_tokens", "output_tokens"):
                usage[k] = (usage.get(k) or 0) + ((usage2 or {}).get(k) or 0)
        return {
            "text": text,
            "word_count": len(text.split()),
            "word_budget": [WORDS_LO, WORDS_HI],
            "revised_after_check": revised,
            "open_check_problems": problems,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": prompt_sha256(),
            "model": self.model_name,
            "reasoning_effort": self.effort,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "inputs_fingerprint": fingerprint(findings),
            "usage": {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            },
        }


def build(
    data_dir: str,
    submission_id: str,
    variant: str = "",
    model_name: str = "gpt-4.1",
    workers: int = 6,
) -> List[dict]:
    """Generate the assessment of every claim and store it in Artifact B."""
    from concurrent.futures import ThreadPoolExecutor

    contexts, b_path, b, refs = contexts_for(data_dir, submission_id, variant)
    assessor = ClaimAssessor(model_name=model_name)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda x: assessor.assess(x[4], x[2], x[3], refs), contexts))
    by_id = {cid: r for (cid, *_), r in zip(contexts, results)}
    for v in b.get("per_claim", []):
        if v.get("claim_id") in by_id:
            v["claim_assessment"] = by_id[v["claim_id"]]
    b_path.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    return results
