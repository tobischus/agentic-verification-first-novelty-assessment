"""Linear ablation of the agent (Section 4.9).

Only the per-paper loop is replaced: sections are selected once, the paper is compared
once and checked once. There is no further reading, no setting aside and no re-entry.
Everything else is inherited from `ClaimNoveltyAgent`.
"""

from typing import List

from .claim_agent import (
    ClaimNoveltyAgent,
    _PAPER_SECTION_PICK,
    _READ_CAP,
    _SectionPick,
    _fill,
    _fmt_sections_full,
    _fmt_sections_menu,
    _resolve_sections,
    _section_ids,
)

_LINEAR_MAX_SECTIONS = 12
_LINEAR_UNRESOLVED_REASON = "no_reentry_single_pass"


class LinearBaselineAgent(ClaimNoveltyAgent):
    control_flow = "linear_single_pass"

    def _new_run_log(self, claim: dict):
        log = super()._new_run_log(claim)
        log.config["control_flow"] = self.control_flow
        log.config["adaptivity_removed"] = ["read_more", "early_dismissal", "evidence_reentry"]
        return log

    def _select_sections(self, tb, claim: dict, pid: str, claim_ctx: str, trace: List[str]):
        """The single section selection. Returns (context, names, pt, ct)."""
        pt = ct = 0
        menu = tb.section_menu(pid) or []
        if not menu:
            trace.append("no section menu -- comparison runs on the document as parsed")
            return "", [], pt, ct

        sec_ids = _section_ids(menu)
        claim_s = self._claim_str(claim)[:1200]
        title = (tb.pool.get(pid, {}) or {}).get("title", "")

        parsed, a, b = self._struct(
            _SectionPick,
            _fill(
                _PAPER_SECTION_PICK,
                claim=claim_s,
                realization=claim_ctx,
                title=title,
                sections=_fmt_sections_menu(menu, ids=sec_ids),
            ),
            role="reading",
        )
        pt += a
        ct += b

        asked = [s for s in (getattr(parsed, "sections", None) or []) if s] if parsed else []
        wanted, unresolved = _resolve_sections(asked, menu, sec_ids)
        why = (getattr(parsed, "why", "") or "").strip() if parsed else ""

        got = (
            tb.read_sections(
                pid, wanted[:_LINEAR_MAX_SECTIONS], max_total=_READ_CAP, exact=True
            ).get("sections", [])
            or []
        )
        fallback = ""
        if not got:
            fallback = "no named section could be read"
            wanted = [m["name"] for m in sorted(menu, key=lambda m: -m.get("chars", 0))[:4]]
            got = (
                tb.read_sections(pid, wanted, max_total=_READ_CAP, exact=True).get("sections", [])
                or []
            )

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
        """Select, compare and check once. An open assessment is marked unresolved."""
        pt = ct = 0
        trace: List[str] = [
            "[linear] one pass: one section pick, one comparison, one evidence check; "
            "no read_more, no dismissal, no re-entry"
        ]

        context, names, a, b = self._select_sections(tb, claim, pid, claim_ctx, trace)
        pt += a
        ct += b

        comp, a, b = self._section_compare(tb, claim, pid, claim_ctx, context, turn=0)
        pt += a
        ct += b
        self._trace_raw(trace, 0, comp)

        comp, a, b = self._map_evidence(tb, claim, pid, comp, context, turn=0)
        pt += a
        ct += b
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
