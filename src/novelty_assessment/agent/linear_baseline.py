#!/usr/bin/env python3
"""The linear baseline: the same reviewer, without the ability to go back.

RQ1 asks what the AGENTIC control flow adds. That question is only answered if the
control flow is the single difference, so this baseline is not a second implementation
of the review -- it is `ClaimNoveltyAgent` with one method replaced. Everything a
comparison actually rests on is inherited, by construction rather than by agreement:

    submission            the same parsed document, the same claim extraction
    candidate pool        `tb._ranked()` -- the whole retrieval snapshot both systems
                          get, never a SPECTER2 top-k slice of it
    sources               the same version-pinned PDFs and hash-verified parsed text
                          (agent/tools.py), so neither system can read a document the
                          other could not
    submission context    the same `_build_submission_basis` selection per claim
    models                the same per-role model and reasoning effort
    comparison            the same `_PAPER_COMPARE` prompt and `_SectionComparison`
                          schema, through the same `_section_compare`
    grounding             the same evidence map: text verification, ownership, and
                          `check_evidence` -- through the same `_map_evidence`
    aggregation           the same ledger, the same `refutation_status` invariant, the
                          same deterministic claim verdict, the same renderer

What is removed is exactly the adaptivity:

    NO read_more          sections are chosen once, before anything has been compared
    NO early exit         no paper is dismissed from a partial reading; every candidate
                          goes through comparison, grounding and the evidence check
    NO re-entry           a failed evidence check does not send the paper back to read
                          again and be compared a second time

"Linear" is a property of the DECISION flow, not of execution: nothing here depends on
another paper's result, so the papers still run concurrently (`deep_dive_workers`), the
same way the agent's independent dives do.

One asymmetry is deliberate and stated rather than hidden. The agent reads three
sections first and may then ask for more, several times, up to `_READ_CAP`. Giving the
baseline three sections and no second chance would compare adaptivity against a smaller
budget instead of against a single pass, so its ONE selection may fill the whole cap --
the same 50,000 characters, chosen all at once. What it cannot do is choose the second
half after seeing what the first half produced.

The agent may still spend more model calls in total. Quality, cost and wall-clock time
therefore have to be reported together: this design isolates the control flow, not the
token budget.
"""
from typing import List, Optional

from .claim_agent import (
    ClaimNoveltyAgent,
    _PAPER_SECTION_PICK,
    _READ_CAP,
    _SectionPick,
    _USE_EVIDENCE_MAP,
    _fill,
    _fmt_sections_full,
    _fmt_sections_menu,
    _resolve_sections,
    _section_ids,
)

# How many sections the single pick may name before the character cap does the limiting.
# Not a third of `_READ_CAP`'s worth: the point of one pass is that the pick is
# unconstrained in WHAT it takes, only in WHEN it is made.
_LINEAR_MAX_SECTIONS = 12

# Why a paper ended without its evidence question settled. The agent has two such
# reasons (`read_cap_exhausted`, `comparison_budget_exhausted`); the baseline has this
# one, and it is not a budget -- nothing ran out. Keeping it as its own value stops a
# pilot's numbers from reading as though the baseline had been cut short.
_LINEAR_UNRESOLVED_REASON = "no_reentry_single_pass"


class LinearBaselineAgent(ClaimNoveltyAgent):
    """`ClaimNoveltyAgent` whose per-paper loop makes exactly one pass.

    Only `_paper_loop` is overridden. `run()` is inherited untouched, so the pool, the
    submission understanding, the per-paper `ensure_fulltext`, `_record`, the claim-level
    verdict, the run log and the artifact entry are literally the agent's own -- there is
    no second copy of any of them to drift.
    """

    #: Marks every artifact and run log this class produces, so a pilot cannot mistake a
    #: baseline result for an agent result after the files have been moved around.
    control_flow = "linear_single_pass"

    #: `_deep_dive` must enter through `_paper_loop` -- the method this class replaces --
    #: whatever NOVELTY_PAPER_LOOP is set to in the environment. Without this, forgetting
    #: the variable would silently run the agent's older two-round reading path and the
    #: baseline would not be linear at all.
    _use_paper_loop = True

    #: Every candidate is processed by the fixed flow. An abstract triage would be an
    #: early exit decided before anything was read -- the very thing under test -- so the
    #: baseline never screens, regardless of NOVELTY_NO_TRIAGE.
    _no_triage = True

    def _new_run_log(self, claim: dict):
        log = super()._new_run_log(claim)
        log.config["control_flow"] = self.control_flow
        log.config["adaptivity_removed"] = ["read_more", "early_dismissal", "evidence_reentry"]
        return log

    # ------------------------------ the one pass ------------------------------ #

    def _select_sections(self, tb, claim: dict, pid: str, claim_ctx: str,
                         trace: List[str]):
        """The one and only reading decision: which sections, chosen from the menu.

        The same prompt and schema the agent uses for its own first pick
        (`_PAPER_SECTION_PICK` / `_SectionPick`) on the same `reading` role, and the same
        handle resolution (`_resolve_sections`) so a named section that exists is found
        the same way. The difference is what happens afterwards: nothing.

        Returns (context, names, pt, ct).
        """
        pt = ct = 0
        menu = tb.section_menu(pid) or []
        if not menu:
            # No parsed sections at all. `_section_compare` falls back to the document (or
            # the abstract passages) on an empty context, exactly as it does for the agent.
            trace.append("no section menu -- comparison runs on the document as parsed")
            return "", [], pt, ct

        sec_ids = _section_ids(menu)
        claim_s = self._claim_str(claim)[:1200]
        title = (tb.pool.get(pid, {}) or {}).get("title", "")

        parsed, a, b = self._struct(
            _SectionPick,
            _fill(_PAPER_SECTION_PICK, claim=claim_s, realization=claim_ctx,
                  title=title, sections=_fmt_sections_menu(menu, ids=sec_ids)),
            role="reading",
        )
        pt += a; ct += b

        asked = [s for s in (getattr(parsed, "sections", None) or []) if s] if parsed else []
        wanted, unresolved = _resolve_sections(asked, menu, sec_ids)
        why = (getattr(parsed, "why", "") or "").strip() if parsed else ""

        got = tb.read_sections(pid, wanted[:_LINEAR_MAX_SECTIONS],
                               max_total=_READ_CAP, exact=True).get("sections", []) or []
        fallback = ""
        if not got:
            # Nothing the model named could be read. An empty context would quietly hand
            # the whole document to the comparison, which would make this paper's context
            # incomparable to every other one -- so fall back the way the agent does, to
            # the biggest sections, and say so in the trace.
            fallback = "no named section could be read"
            wanted = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:4]]
            got = tb.read_sections(pid, wanted, max_total=_READ_CAP,
                                   exact=True).get("sections", []) or []

        names = [s["name"] for s in got]
        used = sum(len(s.get("text", "")) for s in got)

        trace.append(f"turn 0: single section pick -> {len(names)} of {len(menu)} sections")
        trace.extend(f"  - {n}" for n in names)
        trace.append(f"  requested: {len(asked)}")
        trace.append(f"  loaded: {len(names)}")
        trace.append(f"  total chars: {used:,}/{_READ_CAP:,}")
        if unresolved:
            trace.append(f"  unresolved: {', '.join(unresolved[:6])}")
        if why:
            trace.append(f"  reason: {' '.join(why.split())}")
        if fallback:
            trace.append(f"  FALLBACK: {fallback} -- read the {len(names)} biggest instead")
        trace.append("  no read_more available: this is the only reading of this paper")

        tb._log("linear_read", f"{pid}: {len(names)} of {len(menu)} sections, {used:,} chars")
        return _fmt_sections_full(got, max_total=_READ_CAP), names, pt, ct

    def _paper_loop(self, tb, claim: dict, pid: str, claim_ctx: str):
        """Select once, compare once, ground once, check once, stop.

        Same signature and same return shape as the agent's `_paper_loop`
        ((comp, pt, ct, trace)), because `_deep_dive` calls this and then does the
        version-pinned fetch bookkeeping, the record and the timing for both systems.

        A standing evidence deficit is handled by the SAME rule the agent applies when
        its budget is spent: the last semantic comparison is kept as the best available
        assessment, the paper is marked unresolved, and `can_refute` is withdrawn -- an
        unresolved paper must not become a verified strong refuter in either system. What
        differs is only that the agent had the option to read again first, and this did
        not. The reason is recorded as `no_reentry_single_pass` rather than as a budget so
        the two endings stay distinguishable in the results.
        """
        pt = ct = 0
        trace: List[str] = [
            "[linear] one pass: one section pick, one comparison, one evidence check; "
            "no read_more, no dismissal, no re-entry"
        ]

        context, names, a, b = self._select_sections(tb, claim, pid, claim_ctx, trace)
        pt += a; ct += b

        comp, a, b = self._section_compare(tb, claim, pid, claim_ctx, context, turn=0)
        pt += a; ct += b
        self._trace_raw(trace, 0, comp)

        if _USE_EVIDENCE_MAP:
            comp, a, b = self._map_evidence(tb, claim, pid, comp, context, turn=0)
            pt += a; ct += b
            self._trace_grounding(trace, 0, comp)

        deficit = self._evidence_deficit(comp) or ""
        if not deficit:
            trace.append("[0] compared, evidence gate passed")
            return comp, pt, ct, trace

        comp = dict(comp)
        comp["unresolved_deficit"] = deficit
        comp["paper_state"] = "unresolved_single_pass"
        comp["insufficient"] = True
        comp["unresolved"] = True
        comp["unresolved_reason"] = _LINEAR_UNRESOLVED_REASON
        comp["refutation_status"] = "cannot_refute"
        trace.append(
            f"[0] evidence gate would have refused -- the linear baseline has no "
            f"re-entry, so the last semantic assessment "
            f"({comp.get('overlap_degree', '')}) stands as the best available "
            f"assessment; UNRESOLVED: {deficit}"
        )
        return comp, pt, ct, trace
