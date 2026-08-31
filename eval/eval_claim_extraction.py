#!/usr/bin/env python3
"""
STAGE-A EVALUATION: how well does a system extract the paper's claimed contributions?

This is the first of the thesis's three comparison stages (A: claims only, B: fixed
claims injected, C: end-to-end). It isolates EXTRACTION quality -- before any prior-work
comparison happens -- and is the stage where the pipeline's canonical claim artifact has
to hold up against the other systems.

WHAT COUNTS AS TRUTH
--------------------
The reference is the AUTHORS' OWN CONTRIBUTION STATEMENTS: the verbatim sentences in
which the authors say what they contribute. A claim set is good when it (i) covers all of
them, (ii) invents nothing beyond them, and (iii) is grounded in the paper's text.

Three reference sources, in order of preference (every result is labelled with the one
actually used -- the distinction is never hidden):
  1. GOLD   (--gold eval/gold_contributions.json): human-checked. The defensible
            reference for a thesis headline number.
  2. SILVER (--build-reference): extracted by an INDEPENDENT extractor implemented in
            this file, run with a DIFFERENT model from the systems under test, seeing
            MORE of the paper than either of them. Fair to all systems, but model-made.
  3. AUTO   the deep extractor's own anchor statements. *** CIRCULAR *** -- it measures
            internal consistency, NOT correctness, and flatters the deep extractor by
            construction. Regression testing only; never a comparison number.

FAIRNESS RULES BUILT INTO THIS HARNESS
--------------------------------------
* The reference is never an artifact of a system under test (silver/gold above).
* The judge model differs from the extraction model, so no system is scored by the model
  that produced it (self-preference bias).
* The judge only produces an ALIGNMENT (which claim covers which statement, how many
  contributions a claim bundles, which claims duplicate each other). Every number is then
  computed deterministically from that alignment -- the judge never emits a score.
* Groundedness is re-verified here with the deterministic matcher; a system's own
  `evidence_verified` flag is ignored, so a system cannot self-report it.
* Compared systems must be run with the SAME model, otherwise the comparison measures the
  model, not the method.
* The blind pairwise comparison (--battle) is reference-free and judged in BOTH
  orientations; a win counts only if it survives the swap, and order-dependent verdicts
  are reported as position bias rather than quietly resolved.

Known asymmetry, by design, not a defect: the deep extractor reads more of the paper
(targeted sections) than the one-shot baseline (introduction). That IS the treatment being
evaluated -- but it also means the comparison is method-vs-method, not prompt-vs-prompt.

METRICS (per system, macro-averaged over papers)
------------------------------------------------
  groundedness  % of claims whose evidence quote is verbatim in the paper. Computed
                WITHOUT the judge, by re-running the deterministic matcher against the
                paper text -- a system cannot self-report this.
  recall        % of reference contributions covered by >= 1 claim   (completeness)
  precision     % of claims that correspond to some reference contribution (no invention)
  f1            harmonic mean of the two
  atomicity     % of claims stating exactly ONE contribution
  redundancy    % of claim pairs that state the SAME contribution (0 is best; this is the
                metric that catches the "two phrasings of one contribution" failure)
  n_claims      mean number of claims

Alignment (which claim covers which reference statement, atomicity, redundancy) is done
by an LLM judge in ONE structured call per paper per system; all metrics are then computed
deterministically from that alignment, so the judge never reports a score itself.

SYSTEMS
-------
  deep     {id}_claims_deep.json     -- the agentic anchored extractor (this thesis)
  oneshot  {id}_claims_oneshot.json  -- the previous one-shot extractor (ablation)
  current  {id}_claims.json          -- whatever the pipeline last wrote
  afzal    structured_representation.json -> novelty_claims[]   (baseline system)
  opennovelty  phase1_extracted.json -> contributions[]         (comparison system)

Usage
-----
  # 1. produce the two own-system claim sets on the eval corpus
  python eval/eval_claim_extraction.py --data-dir eval/out/data --extract deep,oneshot
  # 2. score them
  python eval/eval_claim_extraction.py --data-dir eval/out/data --systems deep,oneshot
  # with a human reference:
  python eval/eval_claim_extraction.py --data-dir eval/out/data --systems deep,oneshot \
      --gold eval/gold_contributions.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

_SRC = Path(__file__).resolve().parents[1] / "src" / "novelty_assessment"
sys.path.insert(0, str(_SRC))
from agent import evidence as ev  # noqa: E402
from claim_extraction import _usd as _price_usd  # noqa: E402

load_dotenv()


# --------------------------------------------------------------------------- #
# Judge schema + prompt
# --------------------------------------------------------------------------- #


class _RefMatch(BaseModel):
    reference_index: int = Field(description="0-based index of the reference contribution")
    claim_indices: List[int] = Field(
        default_factory=list,
        description="0-based indices of the claims that state THIS contribution (empty if none)")


class _ClaimJudgement(BaseModel):
    claim_index: int
    states_a_reference_contribution: bool = Field(
        description="true if this claim corresponds to one of the reference contributions")
    n_contributions: int = Field(
        description="how many DISTINCT contributions this single claim bundles (1 = atomic)")


class _Alignment(BaseModel):
    reference_matches: List[_RefMatch] = Field(default_factory=list)
    claim_judgements: List[_ClaimJudgement] = Field(default_factory=list)
    redundant_pairs: List[List[int]] = Field(
        default_factory=list,
        description="pairs [i,j] of claim indices that state the SAME contribution")


_JUDGE_PROMPT = """You are evaluating how well an automatic system extracted the CLAIMED CONTRIBUTIONS of a scientific paper.

You are given (1) the REFERENCE contributions -- what the authors themselves state they contribute -- and (2) the CLAIMS a system extracted. Judge only whether the claims correspond to the reference contributions. Do NOT judge whether the contributions are good, novel, or well-written.

Decide three things:

1. reference_matches: for EACH reference contribution, list the indices of the claims that state that same contribution. A claim matches if it refers to the SAME contribution, even if worded differently or at a different level of detail. Leave the list empty if no claim covers it (a coverage gap).

2. claim_judgements: for EACH claim,
   - states_a_reference_contribution: true if it corresponds to one of the reference contributions. false means the system produced something the authors do not state as a contribution (an invention, a piece of background/motivation, an auxiliary experiment, or a sub-part of another contribution presented as its own).
   - n_contributions: how many DISTINCT contributions that single claim bundles. 1 = atomic (the desired case). Describing ONE artifact together with its parts/features counts as 1. Two genuinely different contributions joined by "and" counts as 2.

3. redundant_pairs: pairs of claim indices that state the SAME contribution as each other (two phrasings of one contribution, or one claim being a restatement/sub-part of another). Building an artifact and using that same artifact for its intended purpose is ONE contribution -- unless the authors present the findings obtained with it as a separate contribution. List each pair once, smaller index first. Empty list if all claims are distinct.

## Paper title
{title}

## REFERENCE contributions (index: the authors' own statement)
{references}

## Extracted CLAIMS (index: claim)
{claims}"""


# --------------------------------------------------------------------------- #
# Independent (silver) reference extraction
#
# Fairness: the reference must NOT be an artifact of a system under test. This
# extractor is deliberately independent of the pipeline --
#   * its own prompt, implemented here, not imported from claim_extraction.py;
#   * a DIFFERENT model from the one that produced the claim sets (self-preference);
#   * it sees MORE of the paper (abstract + intro + conclusion) than either system,
#     so it is not biased toward what one of them happens to read;
#   * it only LOCATES verbatim sentences -- it never judges, merges or rewrites.
# It is still model-made: that is a SILVER reference. A human-checked GOLD file
# (--gold) overrides it wherever available.
# --------------------------------------------------------------------------- #


class _RefStatement(BaseModel):
    text: str = Field(description="EXACT verbatim sentence(s) from the paper, copied character-for-character")


class _RefOut(BaseModel):
    statements: List[_RefStatement] = Field(default_factory=list)


_REFERENCE_PROMPT = """Locate the sentences in which the AUTHORS of this paper state their CONTRIBUTIONS -- what this paper ADDS to the literature.

COPY ONLY. Do not summarize, rephrase, merge, split, rank or judge. You are building a reference list of the authors' own words.

A CONTRIBUTION answers "what does this paper contribute to the field?" -- a proposed method, model, framework, task, benchmark, dataset, theoretical result, a headline empirical finding, or practical guidelines the authors present as an outcome of their work.

It is NOT how the work was carried out. EXCLUDE, even though they are phrased with "we":
- experimental setup and procedure: "we use/select/adopt/train/fine-tune/evaluate on/measure/set/compare", choices of datasets, models, baselines, hyperparameters;
- section roadmaps and pointers: "In this section we outline ...", "Details are in Appendix A";
- individual analyses or figures: "In Figure 3 we examine ...", "we then investigate the impact of ...";
- background, motivation, problem statements, other people's work, and bare result numbers.

Papers state FEW contributions -- typically 2 to 6, rarely more than 8. If your list is longer than that, you are including methodology or analysis steps: keep only the sentences a reader would cite as "this paper's contributions".

PREFER the paper's own summary of its contributions: the explicit contributions list or paragraph in the introduction ("Our contributions are ...", "(1) ... (2) ...", bullets) if one exists, otherwise the contribution sentences of the abstract and the end of the introduction.

CRITICAL -- an enumeration is not automatically a list of contributions:
- If the items are DIFFERENT THINGS THE AUTHORS DID ("we propose X; we show Y"), return one statement per item.
- If the items are the PARTS, FEATURES or COMPONENTS OF ONE ARTIFACT ("our benchmark features (i) diverse corpora, (ii) harder tasks, (iii) pipeline-wide evaluation"; "our method consists of ..."), that is ONE contribution: return the WHOLE sentence as a SINGLE statement.
  Test: are the items things the artifact HAS, or things the authors DID?

Each statement must be copyable character-for-character from the text below, must start at a sentence boundary, and must NOT overlap another statement (never return the same sentence cut at two different points).

## Paper title
{title}

## Paper text
{content}"""


def _dedupe_spans(texts: List[str], source_text: str) -> List[str]:
    """Keep only non-overlapping statements (longest first), in document order.

    Same deterministic guard the extractor uses, re-implemented here so the reference
    does not inherit a bug -- or a fix -- from the system under test."""
    src = ev.normalize(source_text)
    located, unlocated = [], []
    for t in texts:
        n = ev.normalize(t)
        pos = src.find(n) if n else -1
        (located if pos >= 0 else unlocated).append((pos, pos + len(n), t) if pos >= 0 else t)
    kept = []
    for start, end, t in sorted(located, key=lambda x: -(x[1] - x[0])):
        if any(start < ke and ks < end for ks, ke, _ in kept):
            continue
        kept.append((start, end, t))
    return [t for _, _, t in sorted(kept, key=lambda x: x[0])] + unlocated


def build_reference(sub: Path, sid: str, model: str, force: bool = False) -> dict:
    """Extract + verify the silver reference for one paper; cached in its own file."""
    out = sub / f"{sid}_reference_contributions.json"
    if out.exists() and not force:
        return _load_json(out) or {}

    from langchain_openai import ChatOpenAI

    meta = _load_json(sub / f"{sid}.json") or {}
    ft = _load_json(sub / f"{sid}_fulltext.json") or {}
    sections = ft.get("sections", [])
    abstract = (meta.get("abstract") or "").strip()
    # Leading region = "the introduction": stop at the first section that is clearly
    # PAST the introduction. Running blindly to a character budget leaked method and
    # experiment text in, and the model then returned setup sentences ("we evaluate on
    # ...", "we set rank=8") as if they were contributions.
    lead, used = [], 0
    for s in sections:
        head = (s.get("section") or "").strip().lower()
        if any(k in head for k in ("related work", "background", "preliminar", "method",
                                   "approach", "experiment", "evaluation", "setup",
                                   "result", "analysis", "conclusion", "discussion")):
            break
        t = (s.get("text") or "").strip()
        if not t:
            continue
        lead.append(t)
        used += len(t)
        if used >= 20000:
            break
    concl = "\n".join((s.get("text") or "") for s in sections
                      if any(k in (s.get("section") or "").lower()
                             for k in ("conclusion", "discussion")))[:6000]
    content = "\n\n".join(p for p in (
        f"Abstract:\n{abstract}" if abstract else "",
        "Introduction:\n" + "\n\n".join(lead) if lead else "",
        f"Conclusion / Discussion:\n{concl}" if concl.strip() else "",
    ) if p)
    source_text = paper_text(sub, sid)

    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    llm = ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                     max_retries=4, timeout=180, **kw)
    try:
        parsed = llm.with_structured_output(_RefOut, include_raw=True).invoke(
            _REFERENCE_PROMPT.replace("{title}", paper_title(sub, sid)).replace("{content}", content)
        ).get("parsed")
    except Exception as e:
        return {"submission_id": sid, "error": repr(e)[:200], "statements": []}

    raw = [(s.text or "").strip() for s in (getattr(parsed, "statements", None) or [])]
    raw = [t for t in raw if t]
    kept = _dedupe_spans(raw, source_text)
    statements = []
    for t in kept:
        chk = ev.verify_quote(t, source_text)
        statements.append({"text": ev.expand_to_sentence(t, source_text) if chk.verified else t,
                           "verified": chk.verified})
    doc = {"submission_id": sid, "source": "silver", "model": model,
           "n_raw": len(raw), "n_dropped_as_fragments": len(raw) - len(kept),
           "statements": statements,
           "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


# --------------------------------------------------------------------------- #
# Loading: papers, references, system claim sets
# --------------------------------------------------------------------------- #


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def paper_text(sub: Path, sid: str) -> str:
    """Abstract + full body -- what a claim's evidence quote is verified against."""
    meta = _load_json(sub / f"{sid}.json") or {}
    ft = _load_json(sub / f"{sid}_fulltext.json") or {}
    return "\n\n".join([s.get("text", "") for s in ft.get("sections", [])]
                       + [meta.get("abstract", "") or ""])


def paper_title(sub: Path, sid: str) -> str:
    return ((_load_json(sub / f"{sid}.json") or {}).get("title") or "").strip()


# system name -> (filename template, loader). A loader returns
# [{"claim_text":..., "evidence_quote":...}, ...]
def _load_ours(doc: dict) -> List[dict]:
    return [{"claim_text": c.get("claim_text") or c.get("name", ""),
             "evidence_quote": c.get("evidence_quote", "")}
            for c in (doc.get("claims") or []) if c.get("status") != "rejected"]


def _load_afzal(doc: dict) -> List[dict]:
    """Afzal baseline: claims are a flat string list inside the structured representation
    (no evidence quotes exist in that format -> groundedness is reported as n/a)."""
    parsed = (doc.get("main_paper") or {}).get("parsed") or doc.get("parsed") or doc
    return [{"claim_text": c, "evidence_quote": ""} for c in (parsed.get("novelty_claims") or [])]


def _load_opennovelty(doc: dict) -> List[dict]:
    return [{"claim_text": c.get("author_claim_text") or c.get("description") or c.get("name", ""),
             "evidence_quote": c.get("author_claim_text", "")}
            for c in (doc.get("contributions") or [])]


SYSTEMS = {
    "deep":        ("{id}_claims_deep.json", _load_ours),
    # free full-text extractor: whole paper, ONE unconstrained call to a strong reasoning
    # model. Two variants so method and model stay separable:
    #   fulltext      -- the strong model (--free-model, default gpt-5)
    #   fulltext_mini -- the SAME model as deep/oneshot, i.e. the method-only control
    "fulltext":      ("{id}_claims_fulltext.json", _load_ours),
    "fulltext_mini": ("{id}_claims_fulltext_mini.json", _load_ours),
    "fulltext_luna": ("{id}_claims_fulltext_luna.json", _load_ours),
    # advanced inference-time methods, all on gpt-5.6-luna (see claim_methods.py)
    "sc_luna":     ("{id}_claims_sc_luna.json", _load_ours),      # self-consistency + USC
    "cove_luna":   ("{id}_claims_cove_luna.json", _load_ours),    # chain-of-verification
    "refine_luna": ("{id}_claims_refine_luna.json", _load_ours),  # self-refine
    "oneshot":     ("{id}_claims_oneshot.json", _load_ours),
    "current":     ("{id}_claims.json", _load_ours),
    "afzal":       ("structured_representation.json", _load_afzal),
    "opennovelty": ("phase1_extracted.json", _load_opennovelty),
}


def load_system_claims(sub: Path, sid: str, system: str) -> Optional[List[dict]]:
    tmpl, loader = SYSTEMS[system]
    doc = _load_json(sub / tmpl.format(id=sid))
    return loader(doc) if doc is not None else None


def load_system_cost(sub: Path, sid: str, system: str) -> dict:
    """Token/USD accounting the extractor recorded for this paper (empty if absent).
    `usd` is None for models whose price is not in the extractor's table -- reported as
    n/a rather than guessed."""
    tmpl, _ = SYSTEMS[system]
    doc = _load_json(sub / tmpl.format(id=sid)) or {}
    cost = dict(((doc.get("extraction") or {}).get("cost") or {}))
    if cost:
        # Recompute from the token counts with the CURRENT price table: a stored `usd`
        # may come from an older/incorrect table (gpt-5.6-* was briefly mispriced as
        # gpt-5 via prefix matching). Token counts are exact and are trusted as-is.
        cost["usd"] = _price_usd(cost.get("model") or "",
                                 int(cost.get("prompt_tokens") or 0),
                                 int(cost.get("completion_tokens") or 0))
    return cost


def load_reference(sub: Path, sid: str, gold: Optional[dict]) -> tuple:
    """(statements, source), best available first:
        gold    human-checked            -- the defensible thesis reference
        silver  independent extractor    -- fair to all systems (see build_reference)
        auto    the deep extractor's own anchors -- CIRCULAR, last resort only"""
    if gold and sid in gold and gold[sid]:
        return list(gold[sid]), "gold"
    silver = _load_json(sub / f"{sid}_reference_contributions.json") or {}
    stmts = [s.get("text", "") for s in (silver.get("statements") or []) if s.get("text")]
    if stmts:
        return stmts, "silver"
    for name in (f"{sid}_claims_deep.json", f"{sid}_claims.json"):
        doc = _load_json(sub / name) or {}
        stmts = [s.get("text", "") for s in
                 ((doc.get("extraction") or {}).get("anchor_statements") or [])
                 if s.get("text")]
        if stmts:
            return stmts, "auto(anchor)"
    return [], "none"


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def groundedness(claims: List[dict], text: str) -> Optional[float]:
    """Fraction of claims whose evidence quote verifies verbatim in the paper.

    Re-verified here with the deterministic matcher rather than trusting any flag the
    system stored. None when the format carries no quotes at all (e.g. Afzal)."""
    if not claims:
        return None
    quotes = [(c.get("evidence_quote") or "").strip() for c in claims]
    if not any(quotes):
        return None
    ok = sum(1 for q in quotes if q and ev.verify_quote(q, text).verified)
    return ok / len(claims)


def score_paper(judge, title: str, refs: List[str], claims: List[dict]) -> Optional[dict]:
    """One judge call -> deterministic metrics for this (paper, system)."""
    if not claims:
        return {"n_claims": 0, "recall": 0.0 if refs else None, "precision": None,
                "atomicity": None, "redundancy": None}
    prompt = _JUDGE_PROMPT.format(
        title=title,
        references="\n".join(f"{i}: {s}" for i, s in enumerate(refs)) or "(none)",
        claims="\n".join(f"{i}: {c['claim_text']}" for i, c in enumerate(claims)),
    )
    try:
        res = judge.with_structured_output(_Alignment, include_raw=True).invoke(prompt)
        al = res.get("parsed")
    except Exception:
        al = None
    if al is None:
        return None

    n = len(claims)
    covered = sum(1 for m in al.reference_matches
                  if 0 <= m.reference_index < len(refs) and m.claim_indices)
    recall = covered / len(refs) if refs else None

    judged = {j.claim_index: j for j in al.claim_judgements if 0 <= j.claim_index < n}
    matched = sum(1 for j in judged.values() if j.states_a_reference_contribution)
    precision = matched / n if judged else None
    atomic = sum(1 for j in judged.values() if (j.n_contributions or 1) <= 1)
    atomicity = atomic / n if judged else None

    pairs = {tuple(sorted(p[:2])) for p in al.redundant_pairs
             if len(p) >= 2 and all(0 <= x < n for x in p[:2]) and p[0] != p[1]}
    total_pairs = n * (n - 1) / 2
    redundancy = (len(pairs) / total_pairs) if total_pairs else 0.0

    return {"n_claims": n, "recall": recall, "precision": precision,
            "atomicity": atomicity, "redundancy": redundancy,
            "n_reference": len(refs), "n_reference_covered": covered}


# --------------------------------------------------------------------------- #
# Blind pairwise comparison (battle mode) -- REFERENCE-FREE
#
# Sidesteps the reference question entirely: the judge sees the PAPER (title, abstract,
# introduction) and the two claim sets anonymised as A and B, with no hint of which
# system produced which. Every pair is judged TWICE with the positions swapped; only a
# verdict that survives the swap counts as a win. Disagreement between the two runs is
# position bias and is reported as a tie AND counted, so the judge's reliability is
# visible instead of assumed.
# --------------------------------------------------------------------------- #


class _BattleVerdict(BaseModel):
    winner: str = Field(description='"A", "B", or "tie"')
    reason: str = Field(default="", description="one sentence")


_BATTLE_PROMPT = """Two systems each extracted the CLAIMED CONTRIBUTIONS of the same paper. Decide which set better represents what the AUTHORS of this paper state as their own contributions.

Judge on, in order of importance:
1. FAITHFULNESS -- does every claim correspond to something the authors actually present as their contribution? Penalise invented, inflated or generalised claims, and claims that are really background, motivation, or an auxiliary experiment.
2. COMPLETENESS -- are all of the authors' contributions covered?
3. ATOMICITY -- does each claim state exactly one contribution?
4. NON-REDUNDANCY -- do two claims state the same contribution twice? Building an artifact and using that artifact for its intended purpose is ONE contribution.

More claims is NOT better, and fewer is not better either -- only the match to what the authors actually claim counts. Ignore wording, style and ordering.

Answer "tie" only if the two sets are genuinely equivalent in quality.

## Paper title
{title}

## Paper (abstract + introduction)
{paper}

## Claim set A
{set_a}

## Claim set B
{set_b}"""


def _fmt_claims(claims: List[dict]) -> str:
    return "\n".join(f"{i + 1}. {c['claim_text']}" for i, c in enumerate(claims)) or "(no claims)"


def battle_once(judge, title: str, paper: str, set_a: List[dict], set_b: List[dict]) -> Optional[str]:
    try:
        res = judge.with_structured_output(_BattleVerdict, include_raw=True).invoke(
            _BATTLE_PROMPT.replace("{title}", title).replace("{paper}", paper)
            .replace("{set_a}", _fmt_claims(set_a)).replace("{set_b}", _fmt_claims(set_b)))
        v = (res.get("parsed").winner or "").strip().upper()
        return v if v in ("A", "B", "TIE") else None
    except Exception:
        return None


def battle_pair(judge, title: str, paper: str, claims_x: List[dict], claims_y: List[dict]) -> dict:
    """Judge X vs Y in BOTH orientations. A verdict counts only if it survives the swap."""
    v1 = battle_once(judge, title, paper, claims_x, claims_y)   # X as A
    v2 = battle_once(judge, title, paper, claims_y, claims_x)   # X as B
    if v1 is None or v2 is None:
        return {"winner": None, "consistent": False, "raw": [v1, v2]}
    x_won = (v1 == "A") and (v2 == "B")
    y_won = (v1 == "B") and (v2 == "A")
    if x_won:
        return {"winner": "x", "consistent": True, "raw": [v1, v2]}
    if y_won:
        return {"winner": "y", "consistent": True, "raw": [v1, v2]}
    both_tie = v1 == "TIE" and v2 == "TIE"
    # not a genuine tie -> the two orientations disagreed = position bias
    return {"winner": "tie", "consistent": both_tie, "raw": [v1, v2]}


def paper_context(sub: Path, sid: str, limit: int = 6000) -> str:
    """Title-free abstract + leading text, for the reference-free battle judge."""
    meta = _load_json(sub / f"{sid}.json") or {}
    ft = _load_json(sub / f"{sid}_fulltext.json") or {}
    parts = [(meta.get("abstract") or "").strip()]
    used = len(parts[0])
    for s in ft.get("sections", []):
        t = (s.get("text") or "").strip()
        if not t:
            continue
        parts.append(t)
        used += len(t)
        if used >= limit:
            break
    return "\n\n".join(parts)[:limit]


def _f1(p, r):
    if p is None or r is None or (p + r) == 0:
        return None
    return 2 * p * r / (p + r)


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _fmt(v, pct=True):
    if v is None:
        return "   n/a"
    return f"{v * 100:5.1f}%" if pct else f"{v:5.2f}"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def discover_ids(data_dir: Path) -> List[str]:
    return sorted(d.name for d in data_dir.iterdir()
                  if d.is_dir() and not d.name.startswith("_")
                  and (d / f"{d.name}.json").exists())


def run_extraction(data_dir: Path, ids: List[str], which: List[str], model: str,
                   free_model: str = "gpt-5", reasoning_effort: str = "high"):
    """Produce the own-system claim sets to be compared.

    `model` is used for deep / oneshot / fulltext_mini -- keeping those on ONE model is
    what makes the method comparison valid. `free_model` is the deliberately stronger
    model for `fulltext`, so that run varies method AND model and must be read with the
    fulltext_mini control alongside it."""
    from claim_extraction import (DeepClaimExtractor, FullTextClaimExtractor,
                                  ShallowClaimExtractor)

    for sid in ids:
        sub = data_dir / sid
        for system in which:
            out = sub / SYSTEMS[system][0].format(id=sid)
            if out.exists():
                print(f"  [{sid}] {system}: exists, skip")
                continue
            t0 = time.time()
            try:
                if system == "deep":
                    DeepClaimExtractor(model_name=model).extract(
                        str(data_dir), sid, out_name=out.name)
                elif system == "oneshot":
                    ShallowClaimExtractor(model_name=model).extract(
                        str(data_dir), sid, out_name=out.name)
                elif system == "fulltext":
                    FullTextClaimExtractor(model_name=free_model, realize=False,
                                           reasoning_effort=reasoning_effort).extract(
                        str(data_dir), sid, out_name=out.name)
                elif system == "fulltext_mini":
                    FullTextClaimExtractor(model_name=model, realize=False,
                                           reasoning_effort=reasoning_effort).extract(
                        str(data_dir), sid, out_name=out.name)
                elif system == "fulltext_luna":
                    # realize=False: Stage A scores claim TEXT only, so the per-claim
                    # realization would add cost without affecting any metric.
                    FullTextClaimExtractor(model_name="gpt-5.6-luna", realize=False,
                                           reasoning_effort=reasoning_effort).extract(
                        str(data_dir), sid, out_name=out.name)
                elif system in ("sc_luna", "cove_luna", "refine_luna"):
                    from claim_methods import (CoVeExtractor, SelfConsistencyExtractor,
                                               SelfRefineExtractor)
                    cls = {"sc_luna": SelfConsistencyExtractor,
                           "cove_luna": CoVeExtractor,
                           "refine_luna": SelfRefineExtractor}[system]
                    cls(model_name="gpt-5.6-luna",
                        reasoning_effort=reasoning_effort).extract(
                        str(data_dir), sid, out_name=out.name)
                else:
                    print(f"  [{sid}] {system}: not an own system, skip")
                    continue
                print(f"  [{sid}] {system}: done in {time.time() - t0:.0f}s")
            except Exception as e:
                print(f"  [{sid}] {system}: FAILED {repr(e)[:140]}")


def main():
    ap = argparse.ArgumentParser(description="Stage-A evaluation: claim extraction quality")
    ap.add_argument("--data-dir", default="eval/out/data")
    ap.add_argument("--ids", default="", help="comma-separated submission ids (default: all)")
    ap.add_argument("--limit", type=int, default=0, help="evaluate only the first N papers")
    ap.add_argument("--systems", default="deep,oneshot",
                    help=f"comma-separated: {', '.join(SYSTEMS)}")
    ap.add_argument("--extract", default="",
                    help="run these extractors first (deep,oneshot), then exit")
    ap.add_argument("--model", default=os.getenv("NOVELTY_MODEL", "gpt-4.1"),
                    help="model for deep / oneshot / fulltext_mini (kept identical on purpose)")
    ap.add_argument("--free-model", default="gpt-5",
                    help="strong reasoning model for the `fulltext` system")
    ap.add_argument("--reasoning-effort", default="high")
    ap.add_argument("--judge-model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
    ap.add_argument("--gold", default="", help="human reference JSON {id: [statement,...]}")
    ap.add_argument("--build-reference", action="store_true",
                    help="build the independent SILVER reference per paper, then exit")
    ap.add_argument("--reference-model", default="gpt-4.1",
                    help="model for the silver reference -- MUST differ from the model that "
                         "produced the claim sets (self-preference bias)")
    ap.add_argument("--force-reference", action="store_true", help="rebuild existing references")
    ap.add_argument("--battle", default="",
                    help="blind position-swapped pairwise comparison, e.g. 'deep,oneshot'")
    ap.add_argument("--out", default="eval/out/stage_a_claim_extraction.json")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    ids = [s.strip() for s in args.ids.split(",") if s.strip()] or discover_ids(data_dir)
    if args.limit:
        ids = ids[: args.limit]
    if not ids:
        print(f"no submissions found in {data_dir}")
        return

    if args.extract:
        which = [s.strip() for s in args.extract.split(",") if s.strip()]
        print(f"extracting {which} for {len(ids)} paper(s) with {args.model} ...")
        run_extraction(data_dir, ids, which, args.model,
                       free_model=args.free_model, reasoning_effort=args.reasoning_effort)
        print("\ndone. now run the same command with --systems to score.")
        return

    if args.build_reference:
        print(f"building SILVER references for {len(ids)} paper(s) with "
              f"{args.reference_model} (independent of the systems under test) ...")
        for sid in ids:
            d = build_reference(data_dir / sid, sid, args.reference_model, args.force_reference)
            stmts = d.get("statements") or []
            nv = sum(1 for s in stmts if s.get("verified"))
            drop = d.get("n_dropped_as_fragments", 0)
            err = f"  ERROR {d['error']}" if d.get("error") else ""
            print(f"  [{sid}] {len(stmts)} statements ({nv} verbatim-verified)"
                  + (f", {drop} fragment(s) dropped" if drop else "") + err)
        print("\ndone. now run with --systems to score against it.")
        return

    systems = [s.strip() for s in args.systems.split(",") if s.strip() in SYSTEMS]
    gold = _load_json(Path(args.gold)) if args.gold else None
    if args.gold and gold is None:
        print(f"WARNING: gold file not readable: {args.gold}")

    from langchain_openai import ChatOpenAI
    jm = args.judge_model
    kw = {} if jm.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    judge = ChatOpenAI(model_name=jm, api_key=os.getenv("OPENAI_API_KEY"),
                       max_retries=4, timeout=180, **kw)

    per_paper, ref_sources = [], {}
    for sid in ids:
        sub = data_dir / sid
        refs, src = load_reference(sub, sid, gold)
        ref_sources[src] = ref_sources.get(src, 0) + 1
        if not refs:
            print(f"[{sid}] no reference contributions -> skipped")
            continue
        text, title = paper_text(sub, sid), paper_title(sub, sid)
        row = {"submission_id": sid, "reference_source": src, "n_reference": len(refs),
               "systems": {}}
        for system in systems:
            claims = load_system_claims(sub, sid, system)
            if claims is None:
                continue
            m = score_paper(judge, title, refs, claims)
            if m is None:
                print(f"[{sid}] {system}: judge failed")
                continue
            m["groundedness"] = groundedness(claims, text)
            m["f1"] = _f1(m.get("precision"), m.get("recall"))
            m["cost"] = load_system_cost(sub, sid, system)
            row["systems"][system] = m
        per_paper.append(row)
        got = " ".join(f"{s}:{row['systems'][s]['n_claims']}c" for s in row["systems"])
        print(f"[{sid}] ref={len(refs)} ({src})  {got}")

    # ---- aggregate ----
    summary = {}
    for system in systems:
        rows = [p["systems"][system] for p in per_paper if system in p["systems"]]
        if not rows:
            continue
        costs = [r.get("cost") or {} for r in rows]
        usds = [c.get("usd") for c in costs if c.get("usd") is not None]
        summary[system] = {
            "n_papers": len(rows),
            "extract_model": next((c.get("model") for c in costs if c.get("model")), None),
            "usd_per_paper": (sum(usds) / len(usds)) if usds else None,
            "usd_total": (sum(usds)) if usds else None,
            "prompt_tokens": _mean([c.get("prompt_tokens") for c in costs]),
            "completion_tokens": _mean([c.get("completion_tokens") for c in costs]),
            "n_calls": _mean([c.get("n_calls") for c in costs]),
            "n_claims": _mean([r["n_claims"] for r in rows]),
            "groundedness": _mean([r.get("groundedness") for r in rows]),
            "recall": _mean([r.get("recall") for r in rows]),
            "precision": _mean([r.get("precision") for r in rows]),
            "f1": _mean([r.get("f1") for r in rows]),
            "atomicity": _mean([r.get("atomicity") for r in rows]),
            "redundancy": _mean([r.get("redundancy") for r in rows]),
        }

    # ---- blind, position-swapped pairwise comparison (reference-free) ----
    battle = None
    if args.battle:
        bx = [s.strip() for s in args.battle.split(",") if s.strip() in SYSTEMS][:2]
        if len(bx) == 2:
            x, y = bx
            print(f"\nbattle: {x} vs {y} (blind, both orientations) ...")
            res = {"x": x, "y": y, "papers": [], "x_wins": 0, "y_wins": 0,
                   "ties": 0, "position_inconsistent": 0}
            for sid in [p["submission_id"] for p in per_paper]:
                sub = data_dir / sid
                cx, cy = load_system_claims(sub, sid, x), load_system_claims(sub, sid, y)
                if not cx or not cy:
                    continue
                r = battle_pair(judge, paper_title(sub, sid), paper_context(sub, sid), cx, cy)
                r["submission_id"] = sid
                res["papers"].append(r)
                if r["winner"] == "x":
                    res["x_wins"] += 1
                elif r["winner"] == "y":
                    res["y_wins"] += 1
                elif r["winner"] == "tie":
                    res["ties"] += 1
                    if not r["consistent"]:
                        res["position_inconsistent"] += 1
                print(f"  [{sid}] {r['raw']} -> "
                      + {"x": x, "y": y}.get(r["winner"], "tie"
                         + ("" if r["consistent"] else " (position-inconsistent)")))
            battle = res

    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "data_dir": str(data_dir), "n_papers": len(per_paper),
           "judge_model": jm, "reference_sources": ref_sources,
           "summary": summary, "battle": battle, "per_paper": per_paper}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- per-paper detail ----
    if systems:
        print("\n" + "=" * 78)
        print("PER-PAPER METRICS")
        print("=" * 78)
        head = f"{'paper':<13}{'ref':>4}{'sys':>9}{'clm':>5}{'grnd':>7}{'rec':>7}{'prec':>7}{'F1':>7}{'atom':>7}{'red':>7}"
        print(head)
        print("-" * 78)
        for p in per_paper:
            first = True
            for system in systems:
                m = p["systems"].get(system)
                if not m:
                    continue
                label = p["submission_id"][:12] if first else ""
                nref = str(p["n_reference"]) if first else ""
                first = False
                print(f"{label:<13}{nref:>4}{system:>9}{m['n_claims']:>5}"
                      f"{_fmt(m.get('groundedness')):>7}{_fmt(m.get('recall')):>7}"
                      f"{_fmt(m.get('precision')):>7}{_fmt(m.get('f1')):>7}"
                      f"{_fmt(m.get('atomicity')):>7}{_fmt(m.get('redundancy')):>7}")
            print("-" * 78)

    print("\n" + "=" * 78)
    print(f"STAGE-A: CLAIM EXTRACTION  ({len(per_paper)} papers, judge={jm})")
    if ref_sources.get("auto(anchor)"):
        print("!! reference is AUTO (the deep extractor's own anchors) for "
              f"{ref_sources['auto(anchor)']} paper(s): this measures internal consistency,")
        print("   NOT correctness. Use --gold with human-checked statements for a "
              "thesis-grade number.")
    print("=" * 78)
    print(f"{'system':<12}{'claims':>8}{'ground':>9}{'recall':>9}{'prec':>9}"
          f"{'F1':>9}{'atomic':>9}{'redund':>9}")
    print("-" * 78)
    for system, s in summary.items():
        print(f"{system:<12}{_fmt(s['n_claims'], pct=False):>8}"
              f"{_fmt(s['groundedness']):>9}{_fmt(s['recall']):>9}{_fmt(s['precision']):>9}"
              f"{_fmt(s['f1']):>9}{_fmt(s['atomicity']):>9}{_fmt(s['redundancy']):>9}")
    print("-" * 78)
    print("ground=evidence quote verbatim in paper · recall=reference contributions covered")
    print("prec=claims matching a reference · atomic=claims stating exactly one contribution")
    print("redund=claim pairs stating the same contribution (lower is better)")

    print()
    print("=" * 88)
    print("COST PER PAPER (extraction only; judge/eval cost not included)")
    print("=" * 88)
    print(f"{'system':<15}{'model':<16}{'calls':>7}{'in-tok':>10}{'out-tok':>10}{'USD/paper':>12}{'USD total':>12}")
    print("-" * 88)
    for system, s_ in summary.items():
        usdp = f"${s_['usd_per_paper']:.4f}" if s_.get("usd_per_paper") is not None else "n/a"
        usdt = f"${s_['usd_total']:.4f}" if s_.get("usd_total") is not None else "n/a"
        print(f"{system:<15}{(s_.get('extract_model') or '?'):<16}"
              f"{(s_.get('n_calls') or 0):>7.1f}{(s_.get('prompt_tokens') or 0):>10,.0f}"
              f"{(s_.get('completion_tokens') or 0):>10,.0f}{usdp:>12}{usdt:>12}")
    print("-" * 88)
    print("n/a = model price not in the extractor's table; token counts are still exact.")

    if battle:
        n = len(battle["papers"])
        print("\n" + "=" * 78)
        print(f"BLIND PAIRWISE COMPARISON (reference-free, both orientations)  n={n}")
        print("=" * 78)
        print(f"  {battle['x']:<12} wins: {battle['x_wins']}")
        print(f"  {battle['y']:<12} wins: {battle['y_wins']}")
        print(f"  {'tie':<12}     : {battle['ties']}"
              + (f"  (of which {battle['position_inconsistent']} only because the two "
                 f"orientations disagreed = position bias)" if battle["position_inconsistent"] else ""))
        print("  a win counts only if it survives swapping the presentation order.")
    print(f"\nwritten: {args.out}")


if __name__ == "__main__":
    main()
