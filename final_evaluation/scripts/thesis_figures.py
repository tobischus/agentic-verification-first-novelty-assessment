"""Figures of the thesis, computed from the frozen result files of the evaluation."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "final_evaluation" / "results" / "main"
OUT = RES / "figures"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42,
})
CRIT = [("submission_fidelity", "Contribution extraction"),
        ("comparison_specificity", "Comparison specificity"),
        ("presented_evidence", "Presented evidence"),
        ("conclusion_warrant", "Conclusion warrant"),
        ("reviewer_usefulness", "Reviewer usefulness")]
NAMES = {"agent": "Agent", "linear": "Linear", "opennovelty": "OpenNovelty",
         "afzal": "Afzal et al.", "deepreviewer": "DeepReviewer 2.0"}
DARK, MID, LIGHT, PALE = "#1f3b73", "#7f97c4", "#c9c9c9", "#ededed"
CM = 1 / 2.54


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def agent_vs_linear(e1, title, out):
    crit = e1["by_paper_set"]["all"]["criteria"]
    fig, ax = plt.subplots(figsize=(15.5 * CM, 6.0 * CM))
    labels = []
    for i, (key, name) in enumerate(CRIT):
        row = next(p for p in crit[key]["pairs"] if p["pair"] == ["agent", "linear"])
        parts = [(row["agent_wins"], DARK, "Agent preferred"),
                 (row["tie"], LIGHT, "Tie"),
                 (row["inconsistent"], "white", "Order-dependent"),
                 (row["linear_wins"], MID, "Linear preferred")]
        left = 0
        for n, col, lab in parts:
            ax.barh(i, n, left=left, color=col, edgecolor="#555555", linewidth=0.5,
                    label=lab if i == 0 else None, hatch="///" if col == "white" else None)
            if n:
                ax.text(left + n / 2, i, str(n), ha="center", va="center", fontsize=7.5,
                        color="white" if col in (DARK,) else "black")
            left += n
        labels.append(name)
    ax.set_yticks(range(len(CRIT)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("Papers")
    ax.set_title(title, loc="left")
    fig.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 0.0), frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(OUT / out)
    plt.close(fig)


def pair_endings(al, out):
    ag, li = al["reentry"]["agent"], al["reentry"]["linear"]
    rows = [("Agent", [ag["dismissed"], ag["compared"] - ag["first_check_failed"],
                       ag["resolved_by_reentry"], ag["unresolved"]]),
            ("Linear", [li["dismissed"], li["compared"] - li["first_check_failed"],
                        li["resolved_by_reentry"], li["unresolved"]])]
    cols = [(PALE, "Set aside after reading"), (MID, "Passed the first evidence check"),
            (DARK, "Resolved after re-entry"), ("#b5452f", "Unresolved")]
    fig, ax = plt.subplots(figsize=(15.5 * CM, 5.0 * CM))
    for i, (name, vals) in enumerate(rows):
        left = 0
        for n, (col, lab) in zip(vals, cols):
            ax.barh(i, n, left=left, color=col, edgecolor="#555555", linewidth=0.5,
                    label=lab if i == 0 else None)
            if n:
                ax.text(left + n / 2, i, f"{n:,}", ha="center", va="center", fontsize=7.5,
                        color="white" if col in (DARK, "#b5452f") else "black")
            left += n
    ax.set_yticks([0, 1])
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1695)
    ax.set_xlabel("Claim-paper pairs (n = 1,695)")
    fig.legend(ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.0), frameon=False)
    fig.tight_layout(rect=(0, 0.22, 1, 1))
    fig.savefig(OUT / out)
    plt.close(fig)


def elo(e1, out):
    r = e1["by_paper_set"]["all"]["elo_all_criteria"]["ratings"]
    order = sorted(r, key=lambda s: -r[s]["elo"])
    fig, ax = plt.subplots(figsize=(15.5 * CM, 5.0 * CM))
    for i, s in enumerate(order):
        lo, hi = r[s]["ci95"]
        col = DARK if s in ("agent", "linear") else "#888888"
        ax.plot([lo, hi], [i, i], color=col, linewidth=2.2, alpha=0.55, solid_capstyle="round")
        ax.plot(r[s]["elo"], i, "o", color=col, markersize=6)
        ax.text(hi + 15, i, f"{r[s]['elo']:.0f}  (rank {r[s]['rank']})", va="center", fontsize=7.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([NAMES[s] for s in order])
    ax.invert_yaxis()
    ax.axvline(1000, color="#bbbbbb", linewidth=0.6, linestyle="--")
    ax.set_xlim(400, 1900)
    ax.set_xlabel("Elo (Bradley–Terry, 1000 = mean of the five systems; +400 = odds of 10:1)")
    fig.tight_layout()
    fig.savefig(OUT / out)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    e1 = load(RES / "e1" / "e1_analysis.json")
    al = load(RES / "agent_linear" / "agent_linear.json")
    agent_vs_linear(e1, "LLM judge: GPT-6.1 Sol", "fig_agent_linear.pdf")
    pair_endings(al, "fig_pair_endings.pdf")
    elo(e1, "fig_elo.pdf")
    print("written:", sorted(p.name for p in OUT.glob("fig_*.pdf")))
