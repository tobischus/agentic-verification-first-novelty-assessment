#!/usr/bin/env python3
"""
Advanced claim-extraction methods, evaluated against the `fulltext_luna` baseline.

The baseline is a single unconstrained call over the whole paper. It is strong but has
MEASURED failure modes (Stage-A evaluation): occasional missing contributions, occasional
inflated or non-contribution claims, and instability across papers. Each method below is
an established inference-time technique aimed at one of those, so a win is attributable to
a named technique rather than to prompt tinkering.

  SelfConsistencyExtractor  -- Self-Consistency (Wang et al., ICLR 2023) with the
      LLM-based aggregation of Universal Self-Consistency (Chen et al., 2023). Several
      independent extractions are produced and reconciled into the set they agree on.
      Targets: instability, sampling-noise claims, recall gaps that one sample misses.
      Diversity note: reasoning models take no temperature, so the samples are drawn with
      DIFFERENT ENTRY POINTS into the paper (prompt ensembling) instead of by sampling
      noise alone -- explicit, and reported as a deviation from vanilla self-consistency.

  CoVeExtractor  -- Chain-of-Verification (Dhuliawala et al., 2023). Draft, then plan and
      answer verification questions about each drafted claim AGAINST THE PAPER, then
      revise using the answers. The verification step deliberately does not see the other
      claims, so it cannot rationalise the draft.
      Targets: inflated / invented / non-contribution claims (precision).

  SelfRefineExtractor  -- Self-Refine (Madaan et al., NeurIPS 2023). Draft, critique
      against an explicit rubric, revise. Same model throughout, no supervision.
      Targets: redundancy, atomicity, completeness.

All methods use the SAME whole-paper input as the baseline (load_paper_for_extraction) and
the SAME verbatim-evidence requirement, so a comparison isolates the method. Token/USD
accounting is recorded per run for the cost table.
"""
import json
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claim_extraction import (  # noqa: E402
    _Claims,
    _cost_block,
    _fill,
    _make_llm,
    _usage,
    claims_to_doc,
    load_paper_for_extraction,
)

# The baseline task definition, shared verbatim by every method so that what differs is
# the INFERENCE TECHNIQUE, not the task description.
_TASK = """Identify this paper's NOVELTY CLAIMS: the contributions the AUTHORS THEMSELVES put forward as their own, which together capture what this paper adds to the research literature.

What this is for, so you can judge what belongs in the set: every claim will afterwards be checked INDIVIDUALLY against prior work to decide whether that contribution is actually new. A claim therefore earns its place only if it is

- REALLY THE AUTHORS' OWN: something they present as their contribution -- not background, motivation, a problem statement, or work by others;
- SUBSTANTIAL: a contribution whose novelty is worth checking against the literature at all -- not a minor detail, an incidental experiment, or routine practice;
- STANDALONE: it stands on its own, rather than being a component, feature, design choice, implementation detail, intermediate result, or a rephrasing of another claim in your set.

Taken together, the set should represent the paper's contribution completely and without duplication: nothing important left out, nothing padded in, and no two claims that a reader would regard as the same contribution.

Where exactly those lines fall differs from paper to paper -- use your own judgement for THIS one, including how many claims that turns out to be and how to phrase each. Stay faithful to what the authors actually claim; do not strengthen or generalise it."""

_OUTPUT_SPEC = """For each claim give:
- claim: one clear sentence.
- evidence: an exact CONTIGUOUS verbatim passage from the paper text, copied character-for-character, that states this contribution."""


# --------------------------------------------------------------------------- #
# Self-Consistency  (Wang et al. 2023 + Universal Self-Consistency, Chen et al. 2023)
# --------------------------------------------------------------------------- #

# Three entry points into the same paper. Reasoning models reject a temperature setting,
# so diversity is induced by WHERE the model starts reading rather than by sampling noise;
# the task itself is identical in all three.
_SC_VIEWS = [
    "",
    "\n\nApproach it by first locating where the authors state their contributions explicitly (e.g. an abstract summary or a contributions paragraph), then verifying each against the body of the paper.",
    "\n\nApproach it by first working out from the body of the paper what was actually built, proved or discovered, then checking which of those the authors themselves put forward as their contributions.",
]

_SC_AGGREGATE = """Several independent analyses of the SAME paper each produced a candidate set of the paper's novelty claims. They disagree in places. Produce the FINAL claim set.

{task}

How to reconcile the candidates:
- A contribution that MOST candidates identify is very likely real -- keep it.
- A contribution that only ONE candidate identifies may be either a genuine find that the others missed, or an over-extraction. Decide by checking the paper text below: keep it only if the paper really presents it as a standalone, substantial contribution of the authors.
- Where candidates state the same contribution differently, keep ONE claim with the clearest, most faithful phrasing.
- Do not simply take the union, and do not simply take the intersection: judge each contribution on the paper.

{output_spec}

## Paper title
{title}

## Candidate claim sets
{candidates}

## Full text
{content}"""


class SelfConsistencyExtractor:
    """k independent extractions, reconciled by an LLM aggregation step (USC)."""

    MODE = "self_consistency"

    def __init__(self, model_name: str = "gpt-5.6-luna", reasoning_effort: str = "high",
                 k: int = 3):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.k = max(2, k)
        self.llm = _make_llm(model_name, reasoning_effort=reasoning_effort)
        self._pt = self._ct = self._calls = 0

    def _struct(self, schema, prompt):
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    def extract(self, data_dir: str, submission_id: str, out_name: Optional[str] = None) -> dict:
        self._pt = self._ct = self._calls = 0
        meta, title, content, source_text = load_paper_for_extraction(data_dir, submission_id)

        samples = []
        for i in range(self.k):
            view = _SC_VIEWS[i % len(_SC_VIEWS)]
            prompt = _fill(
                "Below is the complete text of a scientific paper.\n\n{task}{view}\n\n{output_spec}\n\n## Paper title\n{title}\n\n## Full text\n{content}",
                task=_TASK, view=view, output_spec=_OUTPUT_SPEC, title=title, content=content)
            parsed = self._struct(_Claims, prompt)
            got = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                   for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
            if got:
                samples.append(got)

        if not samples:
            return self._write(data_dir, submission_id, meta, title, [], source_text, out_name, 0)
        if len(samples) == 1:
            final = samples[0]
        else:
            cand = "\n\n".join(
                f"### Candidate {i + 1}\n" + "\n".join(f"- {c['claim']}" for c in s)
                for i, s in enumerate(samples))
            parsed = self._struct(_Claims, _fill(
                _SC_AGGREGATE, task=_TASK, output_spec=_OUTPUT_SPEC, title=title,
                candidates=cand, content=content))
            final = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                     for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
            if not final:                      # aggregation failed -> fall back to the largest sample
                final = max(samples, key=len)
        return self._write(data_dir, submission_id, meta, title, final, source_text, out_name, len(samples))

    def _write(self, data_dir, sid, meta, title, final, source_text, out_name, n_samples):
        doc = claims_to_doc(sid, meta, title, final, source_text, self.MODE, extra={
            "model": self.model_name, "reasoning_effort": self.reasoning_effort,
            "k_samples": self.k, "n_samples_used": n_samples,
            "technique": "self-consistency (Wang et al. 2023) + USC aggregation (Chen et al. 2023)",
            "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls),
        })
        return _persist(doc, data_dir, sid, out_name)


# --------------------------------------------------------------------------- #
# Chain-of-Verification  (Dhuliawala et al. 2023)
# --------------------------------------------------------------------------- #


class _VQ(BaseModel):
    claim_index: int = Field(description="0-based index of the drafted claim this question checks")
    question: str = Field(description="a question answerable from the paper alone")


class _VQuestions(BaseModel):
    questions: List[_VQ] = Field(default_factory=list)


class _VAnswer(BaseModel):
    claim_index: int
    answer: str = Field(description="the answer, grounded in the paper text")
    supported: bool = Field(description="does the paper support keeping this as a standalone, substantial contribution of the authors?")


class _VAnswers(BaseModel):
    answers: List[_VAnswer] = Field(default_factory=list)


_COVE_PLAN = """A first pass produced the draft claim set below for this paper. Your job is to PLAN THE VERIFICATION -- not to judge yet.

For EACH drafted claim, write one focused question that can be answered from the paper alone and that would expose the claim if it were wrong. Good questions test whether the paper really presents this as the authors' OWN contribution, whether it is SUBSTANTIAL rather than a minor detail or incidental experiment, and whether it is STANDALONE rather than a component or restatement of another drafted claim.

Ask exactly one question per claim, referencing its index.

## Paper title
{title}

## Draft claims
{draft}"""


_COVE_ANSWER = """Answer each verification question using ONLY the paper text below.

Answer each question INDEPENDENTLY and strictly from the paper. Do not assume a question's premise is true because it was asked, and do not let the other questions influence your answer.

For each question also decide `supported`: true if the paper genuinely presents this as a standalone, substantial contribution of the authors; false if it is background, motivation, someone else's work, a minor or incidental detail, or merely a component/restatement of another contribution.

## Questions
{questions}

## Full text
{content}"""


_COVE_REVISE = """Produce the FINAL claim set for this paper, using the verification results.

{task}

You are given a draft claim set and, for each claim, a verification question answered directly from the paper. Use them as follows:
- Drop claims whose verification came back unsupported.
- Merge claims that the verification shows are the same contribution.
- Fix phrasing that the verification shows to be inflated or unfaithful.
- If the verification answers reveal a contribution of the paper that the draft missed, add it.

{output_spec}

## Paper title
{title}

## Draft claims
{draft}

## Verification
{verification}

## Full text
{content}"""


class CoVeExtractor:
    """Draft -> plan verification questions -> answer them from the paper -> revise."""

    MODE = "chain_of_verification"

    def __init__(self, model_name: str = "gpt-5.6-luna", reasoning_effort: str = "high"):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.llm = _make_llm(model_name, reasoning_effort=reasoning_effort)
        self._pt = self._ct = self._calls = 0

    def _struct(self, schema, prompt):
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    def extract(self, data_dir: str, submission_id: str, out_name: Optional[str] = None) -> dict:
        self._pt = self._ct = self._calls = 0
        meta, title, content, source_text = load_paper_for_extraction(data_dir, submission_id)

        # 1. draft (identical to the baseline)
        parsed = self._struct(_Claims, _fill(
            "Below is the complete text of a scientific paper.\n\n{task}\n\n{output_spec}\n\n## Paper title\n{title}\n\n## Full text\n{content}",
            task=_TASK, output_spec=_OUTPUT_SPEC, title=title, content=content))
        draft = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                 for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
        if not draft:
            return _persist(claims_to_doc(submission_id, meta, title, [], source_text, self.MODE,
                                          extra=self._extra(0)),
                        data_dir, submission_id, out_name)

        draft_txt = "\n".join(f"{i}. {c['claim']}" for i, c in enumerate(draft))

        # 2. plan verification questions
        qs = self._struct(_VQuestions, _fill(_COVE_PLAN, title=title, draft=draft_txt))
        questions = [q for q in (getattr(qs, "questions", None) or []) if (q.question or "").strip()]
        if not questions:   # planning failed -> keep the draft rather than degrade it
            return _persist(claims_to_doc(submission_id, meta, title, draft, source_text,
                                          self.MODE, extra=self._extra(0)),
                        data_dir, submission_id, out_name)

        # 3. answer them against the paper (draft NOT shown -> no rationalising)
        q_txt = "\n".join(f"[claim {q.claim_index}] {q.question}" for q in questions)
        ans = self._struct(_VAnswers, _fill(_COVE_ANSWER, questions=q_txt, content=content))
        answers = getattr(ans, "answers", None) or []
        ver_txt = "\n".join(
            f"[claim {a.claim_index}] supported={a.supported} :: {a.answer}" for a in answers
        ) or "(verification produced no answers)"

        # 4. revise
        parsed = self._struct(_Claims, _fill(
            _COVE_REVISE, task=_TASK, output_spec=_OUTPUT_SPEC, title=title,
            draft=draft_txt, verification=ver_txt, content=content))
        final = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                 for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
        if not final:
            final = draft
        n_dropped = sum(1 for a in answers if not a.supported)
        return _persist(claims_to_doc(submission_id, meta, title, final, source_text, self.MODE,
                                      extra=self._extra(n_dropped, len(draft))),
                        data_dir, submission_id, out_name)

    def _extra(self, n_unsupported: int, n_draft: int = 0) -> dict:
        return {"model": self.model_name, "reasoning_effort": self.reasoning_effort,
                "technique": "chain-of-verification (Dhuliawala et al. 2023)",
                "n_draft_claims": n_draft, "n_verification_unsupported": n_unsupported,
                "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls)}


# --------------------------------------------------------------------------- #
# Self-Refine  (Madaan et al. 2023)
# --------------------------------------------------------------------------- #


class _Critique(BaseModel):
    missing: List[str] = Field(default_factory=list, description="contributions of the paper the set fails to cover")
    not_contributions: List[int] = Field(default_factory=list, description="indices of claims that are not standalone substantial contributions")
    duplicates: List[List[int]] = Field(default_factory=list, description="index pairs stating the same contribution")
    inflated: List[int] = Field(default_factory=list, description="indices whose wording overstates what the authors claim")
    verdict: str = Field(default="", description="one sentence: is the set already good, and if not, what is the main problem?")


_REFINE_CRITIQUE = """Critique a candidate set of a paper's novelty claims. Be a demanding reviewer: your job is to find what is WRONG with the set, using the paper text below as the only authority.

A good set states, exactly once each, every contribution the authors put forward as their own -- each of them standalone and substantial -- and nothing else.

Report:
- missing: contributions the paper presents that the set does not cover (quote or name them).
- not_contributions: indices of claims that are background, motivation, other people's work, incidental detail, or otherwise not a standalone substantial contribution.
- duplicates: index pairs that state the same contribution (note: building an artifact and using it for its intended purpose is ONE contribution).
- inflated: indices whose wording claims more than the authors actually do.
- verdict: one sentence. If the set is already good, say so and leave the lists empty -- do not invent problems.

## Paper title
{title}

## Candidate claims
{draft}

## Full text
{content}"""


_REFINE_REVISE = """Produce the FINAL claim set for this paper by applying the critique to the candidate set.

{task}

Apply the critique: add what it reports as missing, remove what it reports as not a contribution, merge each reported duplicate pair into one claim, and reword what it reports as inflated. Where you disagree with the critique, follow the paper -- the paper is the authority, not the critique.

{output_spec}

## Paper title
{title}

## Candidate claims
{draft}

## Critique
{critique}

## Full text
{content}"""


class SelfRefineExtractor:
    """Draft -> rubric critique against the paper -> revise (one iteration)."""

    MODE = "self_refine"

    def __init__(self, model_name: str = "gpt-5.6-luna", reasoning_effort: str = "high"):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.llm = _make_llm(model_name, reasoning_effort=reasoning_effort)
        self._pt = self._ct = self._calls = 0

    def _struct(self, schema, prompt):
        try:
            res = self.llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        except Exception:
            return None
        pt, ct = _usage(res.get("raw"))
        self._pt += pt; self._ct += ct; self._calls += 1
        return res.get("parsed")

    def extract(self, data_dir: str, submission_id: str, out_name: Optional[str] = None) -> dict:
        self._pt = self._ct = self._calls = 0
        meta, title, content, source_text = load_paper_for_extraction(data_dir, submission_id)

        parsed = self._struct(_Claims, _fill(
            "Below is the complete text of a scientific paper.\n\n{task}\n\n{output_spec}\n\n## Paper title\n{title}\n\n## Full text\n{content}",
            task=_TASK, output_spec=_OUTPUT_SPEC, title=title, content=content))
        draft = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                 for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
        if not draft:
            return _persist(claims_to_doc(submission_id, meta, title, [], source_text, self.MODE,
                                          extra=self._extra({})),
                        data_dir, submission_id, out_name)

        draft_txt = "\n".join(f"{i}. {c['claim']}" for i, c in enumerate(draft))
        crit = self._struct(_Critique, _fill(_REFINE_CRITIQUE, title=title,
                                             draft=draft_txt, content=content))
        if crit is None:
            return _persist(claims_to_doc(submission_id, meta, title, draft, source_text,
                                          self.MODE, extra=self._extra({})),
                        data_dir, submission_id, out_name)

        stats = {"n_missing": len(crit.missing or []),
                 "n_not_contributions": len(crit.not_contributions or []),
                 "n_duplicate_pairs": len(crit.duplicates or []),
                 "n_inflated": len(crit.inflated or [])}
        # Nothing to fix -> keep the draft instead of paying for a rewrite that can only drift.
        if not any(stats.values()):
            return _persist(claims_to_doc(submission_id, meta, title, draft, source_text,
                                          self.MODE, extra=self._extra(stats, revised=False)),
                        data_dir, submission_id, out_name)

        crit_txt = json.dumps({
            "missing": crit.missing, "not_contributions": crit.not_contributions,
            "duplicates": crit.duplicates, "inflated": crit.inflated, "verdict": crit.verdict,
        }, ensure_ascii=False, indent=2)
        parsed = self._struct(_Claims, _fill(
            _REFINE_REVISE, task=_TASK, output_spec=_OUTPUT_SPEC, title=title,
            draft=draft_txt, critique=crit_txt, content=content))
        final = [{"claim": (c.claim or "").strip(), "evidence": (c.evidence or "").strip()}
                 for c in (getattr(parsed, "claims", None) or []) if (c.claim or "").strip()]
        if not final:
            final = draft
        return _persist(claims_to_doc(submission_id, meta, title, final, source_text, self.MODE,
                                      extra=self._extra(stats, revised=True)),
                        data_dir, submission_id, out_name)

    def _extra(self, stats: dict, revised: bool = False) -> dict:
        return {"model": self.model_name, "reasoning_effort": self.reasoning_effort,
                "technique": "self-refine (Madaan et al. 2023)", "revised": revised,
                **stats,
                "cost": _cost_block(self.model_name, self._pt, self._ct, self._calls)}


# --------------------------------------------------------------------------- #


def _persist(doc: dict, data_dir: str, submission_id: str, out_name: Optional[str]) -> dict:
    """Write the claim artifact next to the submission."""
    out = Path(data_dir) / submission_id / (out_name or f"{submission_id}_claims.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
