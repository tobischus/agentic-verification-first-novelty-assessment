"""Slide figures for the E1 and agent-vs-linear results -- read-only, no API call.

Reads the analysis outputs, never the raw judge calls, so a figure cannot show a number the
thesis does not report:

  results/main/e1/e1_analysis.json             analyze-e1
  results/main/e1/e1_sensitivity.json          sensitivity-e1 (backup figure only)
  results/main/agent_linear/agent_linear.json  agent-linear
  results/main/e3/source_audit.json            source-audit (figure 6, if present)

Writes one PNG (300 dpi) and one SVG per figure into results/main/figures/. Sized for a
16:9 slide (13.33 x 7.5 in): inserted without scaling, the fonts appear at their nominal
size (labels 16-18 pt). Colours and font follow the presentation template (navy #1E2761,
Calibri). No figure carries a title: the slide title says what the figure shows.

  1_elo_ranking               E1 main result: Elo with 95% CI, shared ranks
  2_agent_vs_existing         agent vs each existing system, per criterion
  3_agent_vs_linear_judge     RQ1: the judge's agent-vs-linear verdicts per criterion
  4_open_questions            RQ1: what re-entry changes on the same claim-paper pairs
  5_backup_breadth            backup: P(agent preferred) measured vs at equal coverage
  6_source_audit              E3 automatic part: grounding, verifiability, every shown quote re-checked
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "final_evaluation" / "results" / "main"

NAVY, LINEAR, GREY, GREY_DARK = "#1E2761", "#8E9BD6", "#A7AEB8", "#5A6472"
GREEN, RED, ORANGE, TEXT = "#2E7D5B", "#B3382C", "#B45309", "#333A45"
TIE, INCONS, BAND, GRID = "#C9CED6", "#E6E9EE", "#EFF3FB", "#E3E7EE"

LABEL = {"agent": "Agent (ours)", "linear": "Linear (ablation)", "opennovelty": "OpenNovelty",
         "afzal": "Afzal et al.", "deepreviewer": "DeepReviewer 2.0"}
COLOR = {"agent": NAVY, "linear": LINEAR, "opennovelty": GREY, "afzal": GREY, "deepreviewer": GREY}
ROLE = ["agent", "linear", "opennovelty", "afzal", "deepreviewer"]
EXISTING = ["opennovelty", "afzal", "deepreviewer"]
CRIT = {"submission_fidelity": "Contribution extraction",
        "comparison_specificity": "Comparison specificity",
        "presented_evidence": "Presented evidence",
        "conclusion_warrant": "Conclusion warrant",
        "reviewer_usefulness": "Reviewer usefulness"}


def _style():
    plt.rcParams.update({
        "font.family": ["Calibri", "DejaVu Sans"],
        "font.size": 17, "axes.labelsize": 17, "xtick.labelsize": 16, "ytick.labelsize": 17,
        "axes.edgecolor": GREY_DARK, "axes.labelcolor": TEXT, "text.color": TEXT,
        "xtick.color": TEXT, "ytick.color": TEXT, "axes.spines.top": False,
        "axes.spines.right": False, "svg.fonttype": "none", "figure.dpi": 100,
    })


def _save(fig, out: Path, name: str) -> list:
    paths = []
    for ext in ("png", "svg"):
        p = out / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", facecolor="white")
        paths.append(p)
    plt.close(fig)
    return paths


def _pair(crit_block: dict, x: str, y: str) -> dict:
    """The pair table for (x, y) as {x_wins, y_wins, tie, inconsistent, p}, whatever order
    analyze-e1 stored it in."""
    for p in crit_block["pairs"]:
        if set(p["pair"]) == {x, y}:
            return {"x": p[f"{x}_wins"], "y": p[f"{y}_wins"], "tie": p["tie"],
                    "inconsistent": p["inconsistent"], "papers": p["papers"], "p": p["sign_test_p"]}
    raise KeyError((x, y))


# ------------------------------------------------------------------------ figures --

def fig_elo(e1: dict, out: Path, minimal: bool = False) -> list:
    e = e1["by_paper_set"]["all"]["elo_all_criteria"]
    r = e["ratings"]
    order = sorted(r, key=lambda s: (r[s]["rank"], ROLE.index(s)))
    ys = {s: len(order) - 1 - i for i, s in enumerate(order)}

    fig, ax = plt.subplots(figsize=(12, 4.9))
    top = [s for s in order if r[s]["rank"] == 1]
    ax.axhspan(min(ys[s] for s in top) - 0.42, max(ys[s] for s in top) + 0.42,
               color=BAND, zorder=0, lw=0)
    for s in order:
        lo, hi = r[s]["ci95"]
        y = ys[s]
        ax.hlines(y, lo, hi, color=COLOR[s], lw=5, alpha=0.45, zorder=2, capstyle="round")
        ax.plot(r[s]["elo"], y, "o", ms=15, color=COLOR[s], zorder=3,
                mec="white", mew=1.5)
        ax.text(hi + 18, y, f"{r[s]['elo']:.0f}", va="center", fontsize=18,
                fontweight="bold" if s in ("agent", "linear") else "normal", color=TEXT)
    ax.set_yticks([ys[s] for s in order])
    ax.set_yticklabels([f"#{r[s]['rank']}   {LABEL[s]}" for s in order])
    for lab, s in zip(ax.get_yticklabels(), order):
        if s == "agent":
            lab.set_fontweight("bold")

    best_existing = max(EXISTING, key=lambda s: r[s]["elo"])
    gap = r["agent"]["elo"] - r[best_existing]["elo"]
    # Low in the gap above the best existing system, so the label stays clear of the row above
    # it (the linear ablation's interval can lie right over the arrow's span).
    y_arrow = ys[best_existing] + 0.42
    ax.annotate("", xy=(r["agent"]["elo"], y_arrow), xytext=(r[best_existing]["elo"], y_arrow),
                arrowprops=dict(arrowstyle="<->", color=GREEN, lw=2.2))
    ax.text((r["agent"]["elo"] + r[best_existing]["elo"]) / 2, y_arrow + 0.06,
            f"+{gap:.0f} Elo over the best existing system", ha="center", va="bottom",
            color=GREEN, fontsize=17, fontweight="bold")
    x_max = max(1700, max(r[s]["ci95"][1] for s in order) + 90)
    if len(top) > 1:
        ax.text(x_max - 5, max(ys[s] for s in top) + 0.3, "shared rank 1: 95% CIs overlap",
                ha="right", va="center", fontsize=15, color=GREY_DARK, style="italic")

    ax.set_xlim(400, x_max)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("Elo (Bradley–Terry; 1000 = mean of the five systems; +400 = 10:1 preference odds)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    fig.text(0.0, -0.04,
             f"LLM judge, 5 criteria pooled · {e['papers']} papers · 95% CI from resampling papers"
             if minimal else
             f"LLM judge, pooled over 5 criteria · {e['papers']} papers · 400 calls (10 pairs × 2 orders) · "
             f"95% CI from resampling papers · rank: 1 + systems whose CI lies entirely above",
             fontsize=12.5, color=GREY_DARK, ha="left")
    return _save(fig, out, "1_elo_ranking")


def fig_existing(e1: dict, out: Path, minimal: bool = False) -> list:
    crit = e1["by_paper_set"]["all"]["criteria"]
    rows = list(CRIT)
    cells, losses, tot, p_max = {}, {}, {o: [0, 0, 0] for o in EXISTING}, 0.0
    for c in rows:
        for o in EXISTING:
            t = _pair(crit[c], "agent", o)
            cells[(c, o)] = (t["x"], t["papers"])
            p_max = max(p_max, t["p"])
            losses[(c, o)] = t["y"]
            tot[o][0] += t["x"]; tot[o][1] += t["papers"]; tot[o][2] += t["y"]

    cmap = LinearSegmentedColormap.from_list("g", ["#F3F7F5", GREEN])
    fig, ax = plt.subplots(figsize=(10, 5.6))
    n_r, n_c = len(rows) + 1, len(EXISTING)
    for i, c in enumerate(rows + ["__all__"]):
        for j, o in enumerate(EXISTING):
            if c == "__all__":
                w, n, lo = tot[o]
            else:
                (w, n), lo = cells[(c, o)], losses[(c, o)]
            share = w / n
            y = n_r - 1 - i
            ax.add_patch(plt.Rectangle((j, y), 0.96, 0.9, color=cmap((share - 0.5) / 0.5),
                                       ec="white", lw=2))
            txt = f"{w}/{n}"
            ax.text(j + 0.48, y + 0.45 + (0.1 if lo else 0), txt, ha="center", va="center",
                    fontsize=19 if c != "__all__" else 20, color="white",
                    fontweight="bold")
            if lo:
                ax.text(j + 0.48, y + 0.2, f"{lo} loss" + ("es" if lo > 1 else ""),
                        ha="center", va="center", fontsize=13, color="white")
    ax.axhline(1 - 0.05, color=GREY_DARK, lw=1.2, xmin=0.0, xmax=1.0)
    ax.set_xlim(0, n_c)
    ax.set_ylim(0, n_r)
    ax.set_xticks([j + 0.48 for j in range(n_c)])
    ax.set_xticklabels([f"vs {LABEL[o]}" for o in EXISTING], fontsize=17)
    ax.xaxis.tick_top()
    ax.set_yticks([n_r - 1 - i + 0.45 for i in range(n_r)])
    ax.set_yticklabels([CRIT[c] for c in rows] + ["All criteria"])
    ax.get_yticklabels()[-1].set_fontweight("bold")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    W = sum(t[0] for t in tot.values()); N = sum(t[1] for t in tot.values())
    L = sum(t[2] for t in tot.values())
    if minimal:
        fig.text(0.0, -0.01,
                 "Papers won by the agent in both A/B orders, out of 20"
                 + (" · exact sign test p < 0.001 in every cell" if p_max < 0.001 else ""),
                 fontsize=12.5, color=GREY_DARK, ha="left")
        return _save(fig, out, "2_agent_vs_existing")
    fig.text(0.0, -0.01,
             f"Cell: papers on which the judge preferred the agent in both A/B orders, out of 20.\n"
             f"Overall {W}/{N} won, {L} lost; the rest tied or order-inconsistent. "
             f"Every criterion cell p < 0.001 (exact sign test).",
             fontsize=12.5, color=GREY_DARK, ha="left")
    return _save(fig, out, "2_agent_vs_existing")


def fig_agent_linear(e1: dict, out: Path, minimal: bool = False) -> list:
    crit = e1["by_paper_set"]["all"]["criteria"]
    rows = list(CRIT)
    fig, ax = plt.subplots(figsize=(6.9, 4.9))
    segs = [("x", "Agent wins", NAVY, None, "white"),
            ("tie", "Tie", TIE, None, TEXT),
            ("inconsistent", "Order-inconsistent", INCONS, "///", GREY_DARK),
            ("y", "Linear wins", LINEAR, None, "white")]
    for i, c in enumerate(rows):
        t = _pair(crit[c], "agent", "linear")
        y = len(rows) - 1 - i
        left = 0
        for key, _, col, hatch, tc in segs:
            v = t[key]
            if v:
                ax.barh(y, v, left=left, color=col, hatch=hatch, edgecolor="white", lw=1.5,
                        height=0.66)
                ax.text(left + v / 2, y, str(v), ha="center", va="center", fontsize=16,
                        color=tc, fontweight="bold")
            left += v
        p_txt = ("p < 0.001" if t["p"] < 0.001 else f"p = {t['p']:.3f}" if t["p"] < 0.01
                 else f"p = {t['p']:.2f}".replace("p = 1.00", "p = 1.0"))
        ax.text(left + 0.4, y, p_txt,
                va="center", fontsize=15, color=GREY_DARK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([CRIT[c] for c in reversed(rows)])
    ax.set_xlim(0, 23.5)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("Papers (stable verdict = same winner in both A/B orders)", fontsize=15)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(handles=[Patch(facecolor=col, hatch=h, edgecolor="white", label=lab)
                       for _, lab, col, h, _ in segs],
              ncol=2, loc="lower left", bbox_to_anchor=(-0.02, 1.0), frameon=False,
              fontsize=14, handlelength=1.2, columnspacing=1.0)
    fig.text(0.0, -0.05, "p: exact sign test, 20 papers" if minimal else
             "No criterion differs significantly (exact sign test, 20 papers).",
             fontsize=12.5, color=GREY_DARK, ha="left")
    return _save(fig, out, "3_agent_vs_linear_judge")


def fig_open(al: dict, out: Path, minimal: bool = False) -> list:
    m = al["matched"]
    failed = {"agent": m["first_check_failed"]["agent"], "linear": m["first_check_failed"]["linear"]}
    open_ = {"agent": m["unresolved"]["agent"], "linear": m["unresolved"]["linear"]}
    pairs = m["pairs"]["agent"]
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    xs = {"agent": 0, "linear": 1}
    for s in ("agent", "linear"):
        o, res = open_[s], failed[s] - open_[s]
        ax.bar(xs[s], o, width=0.58, color=ORANGE, edgecolor="white", lw=1.5)
        ax.text(xs[s], o / 2, f"{o}\nleft open", ha="center", va="center", color="white",
                fontsize=17, fontweight="bold")
        if res:
            ax.bar(xs[s], res, bottom=o, width=0.58, color=GREEN, edgecolor="white", lw=1.5)
            ax.text(xs[s], o + res / 2, f"{res}\nresolved by\nre-reading", ha="center",
                    va="center", color="white", fontsize=15, fontweight="bold")
        ax.text(xs[s], failed[s] + 6, f"{failed[s]} failed\nfirst evidence check", ha="center",
                va="bottom", fontsize=14, color=GREY_DARK)
    red = 1 - open_["agent"] / open_["linear"]
    # Two guides at the "left open" heights and one vertical arrow between them.
    ax.hlines(open_["agent"], 0.29, 0.5, color=TEXT, lw=1.3, ls=(0, (3, 3)))
    ax.hlines(open_["linear"], 0.5, 0.71, color=TEXT, lw=1.3, ls=(0, (3, 3)))
    ax.annotate("", xy=(0.5, open_["agent"]), xytext=(0.5, open_["linear"]),
                arrowprops=dict(arrowstyle="->", color=TEXT, lw=2.2, shrinkA=0, shrinkB=0))
    ax.text(0.5, (open_["agent"] + open_["linear"]) / 2, f"−{red:.0%}",
            ha="center", va="center", fontsize=21, fontweight="bold", color=TEXT,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.set_xticks([0, 1])
    ax.set_xticklabels([LABEL["agent"], LABEL["linear"]], fontsize=17)
    ax.set_xlim(-0.55, 1.55)
    ax.set_ylim(0, max(failed.values()) * 1.32)
    ax.set_ylabel("Claim–paper pairs")
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    t = m["unresolved"]
    if minimal:
        # The slide header already names the pairs; the caption carries the one other run-record
        # fact the talk uses, the claim-level verdict agreement.
        v = al["verdicts"]
        fig.text(0.0, -0.06, f"Same verdict on {v['agree']} of {v['claims']} claims",
                 fontsize=12.5, color=GREY_DARK, ha="left")
        return _save(fig, out, "4_open_questions")
    fig.text(0.0, -0.06,
             f"Same {pairs:,} claim–paper pairs, compared by both. Fewer left open on "
             f"{t['agent_lower']}/{al['papers']} papers\n(sign test, Holm-adjusted p < 0.001). "
             f"Cost ×{al['tests']['usd']['agent'] / al['tests']['usd']['linear']:.1f} "
             f"(list-price estimate).",
             fontsize=12.5, color=GREY_DARK, ha="left")
    return _save(fig, out, "4_open_questions")


def fig_breadth(sens: dict, out: Path, minimal: bool = False) -> list:
    avl = sens["agent_vs_linear"]
    rows = list(CRIT) + ["all_criteria_pooled"]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    for i, c in enumerate(rows):
        d = avl[c]["coverage"]
        y = len(rows) - 1 - i
        a, b = d["p_agent_unadjusted"], d["p_agent_at_equal"]
        pooled = c == "all_criteria_pooled"
        if pooled:
            ax.axhspan(y - 0.45, y + 0.45, color=BAND, zorder=0, lw=0)
        ax.hlines(y - 0.13, *d["p_agent_unadjusted_ci95"], color=LINEAR, lw=3, alpha=0.6)
        ax.hlines(y + 0.13, *d["p_agent_at_equal_ci95"], color=NAVY, lw=3, alpha=0.5)
        ax.plot(a, y - 0.13, "o", ms=12, color=LINEAR, mec="white", zorder=3)
        ax.plot(b, y + 0.13, "o", ms=12, color=NAVY, mec="white", zorder=3)
        # minimal: right of the axis, where no point or interval can reach
        ax.text(1.02 if minimal else 1.0, y, f"{a:.2f} → {b:.2f}", va="center",
                ha="left" if minimal else "right", fontsize=15,
                fontweight="bold" if pooled else "normal")
    ax.axvline(0.5, color=GREY_DARK, ls="--", lw=1.3)
    ax.text(0.5, len(rows) - 0.35, "no preference", ha="center", fontsize=13, color=GREY_DARK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([("All criteria" if c == "all_criteria_pooled" else CRIT[c])
                        for c in reversed(rows)])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.6, len(rows) - 0.2)
    ax.set_xlabel("P(judge prefers the agent's report over the linear one)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=LINEAR, ms=11, label="as measured"),
                       plt.Line2D([], [], marker="o", ls="", color=NAVY, ms=11,
                                  label="at equal number of detailed comparisons")],
              loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False, fontsize=14)
    cov = sens["coverage"]["total"]
    if minimal:
        fig.text(0.0, -0.08,
                 "Post hoc · Bradley–Terry with the ratio of detailed comparisons as covariate · "
                 "95% CI from resampling papers",
                 fontsize=12.5, color=GREY_DARK, ha="left")
        return _save(fig, out, "5_backup_breadth")
    fig.text(0.0, -0.11,
             f"Post-hoc, exploratory: Bradley–Terry with the ratio of detailed comparisons as covariate; "
             f"95% CI from resampling papers.\nLinear shows more detailed comparisons "
             f"({cov['linear']} vs {cov['agent']}); no adjusted difference is significant.",
             fontsize=12.5, color=GREY_DARK, ha="left")
    return _save(fig, out, "5_backup_breadth")


def fig_source_audit(sa: dict, out: Path, minimal: bool = False) -> list:
    v = sa["variants"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.4, 4.4), gridspec_kw={"width_ratios": [1, 1.25]})

    # left: the two midterm metrics plus ownership, agent next to linear
    metrics = [("grounding_rate", "Grounding rate"), ("verifiability_rate", "Verifiability rate"),
               ("ownership_rate", "Ownership rate")]
    for i, (k, lab) in enumerate(metrics):
        y = len(metrics) - 1 - i
        for dy, s in ((0.19, "agent"), (-0.19, "linear")):
            val = v[s][k]
            a1.barh(y + dy, val * 100, height=0.34, color=COLOR[s])
            a1.text(val * 100 - 1.2, y + dy, f"{val:.0%}", ha="right", va="center", fontsize=15,
                    color="white", fontweight="bold")
    a1.set_yticks(range(len(metrics)))
    a1.set_yticklabels([lab for _, lab in reversed(metrics)])
    a1.set_xlim(0, 100)
    a1.set_xticks([0, 25, 50, 75, 100])
    a1.set_xlabel("Share (%)")
    a1.tick_params(axis="y", length=0)
    a1.spines["left"].set_visible(False)
    a1.legend(handles=[Patch(color=COLOR[s], label=LABEL[s]) for s in ("agent", "linear")],
              loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False, fontsize=14)

    # right: every shown quote looked up again in its hash-pinned source
    segs = [("quotes_exact", "exact", GREEN, "white"),
            ("quotes_near", "near-verbatim (≥ 90%)", "#8FC1A9", TEXT),
            ("quotes_not_found", "not found", RED, "white"),
            ("quotes_not_auditable", "no hashed source", TIE, TEXT)]
    for i, s in enumerate(("agent", "linear")):
        y = 1 - i
        total, left = v[s]["quotes_shown"], 0.0
        for key, _, col, tc in segs:
            share = 100 * v[s][key] / total
            a2.barh(y, share, left=left, height=0.5, color=col, edgecolor="white", lw=1)
            if share >= 6:
                a2.text(left + share / 2, y, f"{share:.1f}%", ha="center", va="center",
                        fontsize=15 if share >= 20 else 13, color=tc, fontweight="bold")
            left += share
        a2.text(104, y, f"{total:,} quotes\n{v[s]['quotes_not_found']} not found\n"
                        f"{v[s]['quotes_not_auditable']} without hashed source",
                va="center", fontsize=13, color=GREY_DARK)
    a2.set_yticks([1, 0])
    a2.set_yticklabels([LABEL["agent"], LABEL["linear"]])
    a2.set_xlim(0, 100)
    a2.set_xticks([0, 25, 50, 75, 100])
    a2.set_xlabel("% of quotes shown in the reports")
    a2.tick_params(axis="y", length=0)
    a2.spines["left"].set_visible(False)
    a2.legend(handles=[Patch(color=col, label=lab) for _, lab, col, _ in segs],
              loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False, fontsize=13.5)
    fig.subplots_adjust(wspace=0.55)
    if minimal:
        fig.text(0.0, -0.1,
                 "Grounding: overlap comparisons with a quote pair · Verifiability: proposed pairs "
                 "found on both sides · Ownership: found pairs that are the prior paper's own contribution",
                 fontsize=12, color=GREY_DARK, ha="left")
        return _save(fig, out, "6_source_audit")
    fig.text(0.0, -0.1,
             "Grounding: overlap comparisons with a quote pair · Verifiability: proposed pairs found on both sides · "
             "Ownership: found pairs that are the prior paper's own contribution.\n"
             "Audit: every shown quote re-checked in the source text whose hash the run log records; "
             f"all sources dated before the submission. No model, no judge · {sa['papers']} papers.",
             fontsize=12, color=GREY_DARK, ha="left")
    return _save(fig, out, "6_source_audit")


def build(out_dir: Path = RES / "figures", e1_dir: Path = RES / "e1", minimal: bool = False) -> list:
    """`e1_dir`: the E1 run whose analysis outputs are drawn.
    `minimal`: one short caption line per figure, built from the data only."""
    _style()
    out_dir.mkdir(parents=True, exist_ok=True)
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    e1 = load(e1_dir / "e1_analysis.json")
    sens = load(e1_dir / "e1_sensitivity.json")
    al = load(RES / "agent_linear" / "agent_linear.json")
    paths = []
    paths += fig_elo(e1, out_dir, minimal)
    paths += fig_existing(e1, out_dir, minimal)
    paths += fig_agent_linear(e1, out_dir, minimal)
    paths += fig_open(al, out_dir, minimal)
    paths += fig_breadth(sens, out_dir, minimal)
    audit = RES / "e3" / "source_audit.json"
    if audit.exists():
        paths += fig_source_audit(load(audit), out_dir, minimal)
    return paths
