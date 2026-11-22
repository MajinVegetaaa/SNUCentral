"""Figures for Section VI, drawn from the evaluation files (run from EndProject/):

    .venv/bin/python "report_md's/make_figures.py"

Writes fig2-fig5 as PDF (for LaTeX) and PNG (for preview) next to this script.
Palette: categorical slots 1-2 of the validated default palette (blue, orange); passes the CVD checks.
"""

import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

BLUE, ORANGE = "#2a78d6", "#eb6834"          # slot 1 = TF-IDF, slot 2 = BM25 (fixed order)
INK, MUTED, GRID = "#1f1f1e", "#6b6b68", "#e4e4e1"

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "savefig.dpi": 300, "savefig.bbox": "tight",
})
COL_W = 3.45                                    # IEEE single-column width in inches


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(HERE / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", name)


def latest_retrieval() -> str:
    files = sorted((ROOT / "eval/results").glob("retrieval-*.txt"))
    return files[-1].read_text(encoding="utf-8")


def per_query(text: str, ranker: str) -> dict[str, dict[str, float]]:
    block = text.split(f"== {ranker.upper()} ==")[1].split("==")[0]
    rows = {}
    for m in re.finditer(r"^\s+(Q\d+)\s+P@5=([\d.]+)\s+R@5=([\d.]+)\s+F1=([\d.]+)\s+RR=([\d.]+)\s+conf=([\d.]+)",
                         block, re.M):
        rows[m[1]] = dict(P=float(m[2]), R=float(m[3]), F1=float(m[4]), RR=float(m[5]), conf=float(m[6]))
    for m in re.finditer(r"^\s+(U\d+)\s+\(unanswerable\)\s+conf=([\d.]+)", block, re.M):
        rows[m[1]] = dict(conf=float(m[2]))
    return rows


def fig2_retrieval(text):
    """Grouped bars: P@5, R@5, F1@5, MRR for TF-IDF vs BM25."""
    tail = text.split("Ranker")[-1]
    vals = {r: [float(x) for x in re.search(rf"^{r}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", tail, re.M).groups()]
            for r in ("tfidf", "bm25")}
    labels = ["P@5", "R@5", "F1@5", "MRR"]
    fig, ax = plt.subplots(figsize=(COL_W, 2.1))
    x = range(len(labels))
    w = 0.36
    for off, (r, col, name) in zip((-w / 2 - 0.01, w / 2 + 0.01),
                                   (("tfidf", BLUE, "TF-IDF + cosine"), ("bm25", ORANGE, "BM25"))):
        bars = ax.bar([i + off for i in x], vals[r], w, color=col, label=name, zorder=2)
        for b, v in zip(bars, vals[r]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=6.5,
                    zorder=5, bbox=dict(fc="white", ec="none", pad=0.6))
    ax.plot([-0.45, 0.45], [0.6, 0.6], color=INK, lw=0.9, ls="--", zorder=4, label="Target (P@5 0.60, MRR 0.70)")
    ax.plot([2.55, 3.45], [0.7, 0.7], color=INK, lw=0.9, ls="--", zorder=4)
    ax.set_xticks(list(x), labels)
    ax.set_ylim(0, 1)
    ax.set_xlim(-0.6, 3.6)
    ax.set_ylabel("Score (mean over 20 queries)")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, 1.08)
    ax.legend(loc="upper left", frameon=False, ncol=2, columnspacing=1.0, handlelength=1.6)
    save(fig, "fig2_retrieval")


def fig3_per_query(text):
    """Dot plot: per-query reciprocal rank, TF-IDF vs BM25."""
    tf, bm = per_query(text, "tfidf"), per_query(text, "bm25")
    qs = [q for q in bm if q.startswith("Q")]
    fig, ax = plt.subplots(figsize=(COL_W, 2.2))
    for i, q in enumerate(qs):
        ax.plot([i, i], [tf[q]["RR"], bm[q]["RR"]], color=GRID, lw=1.6, zorder=1)
    ax.scatter(range(len(qs)), [tf[q]["RR"] for q in qs], s=18, color=BLUE, label="TF-IDF + cosine", zorder=3,
               edgecolors="white", linewidths=0.6)
    ax.scatter(range(len(qs)), [bm[q]["RR"] for q in qs], s=18, color=ORANGE, label="BM25", zorder=3,
               marker="D", edgecolors="white", linewidths=0.6)
    ax.set_xticks(range(len(qs)), [str(int(q[1:])) for q in qs], fontsize=6)
    ax.set_xlabel("Query")
    ax.set_ylabel("Reciprocal rank of first relevant passage")
    ax.set_ylim(-0.05, 1.08)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Reciprocal rank")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=2)
    save(fig, "fig3_per_query_rr")


def fig4_confidence(text):
    """Strip plot of BM25 confidence for answerable vs unanswerable questions, with the gate threshold."""
    import yaml
    tau = yaml.safe_load(open(ROOT / "config.yaml"))["retrieval"]["abstain_threshold"]
    bm = per_query(text, "bm25")
    ans = sorted(v["conf"] for q, v in bm.items() if q.startswith("Q"))
    un = {q: v["conf"] for q, v in bm.items() if q.startswith("U")}
    fig, ax = plt.subplots(figsize=(COL_W, 1.55))
    ax.scatter(ans, [1] * len(ans), s=22, color=ORANGE, alpha=0.85, edgecolors="white", linewidths=0.6, zorder=3)
    ax.scatter(list(un.values()), [0] * len(un), s=26, color=BLUE, marker="s", edgecolors="white",
               linewidths=0.6, zorder=3)
    groups: list[list[tuple[str, float]]] = []              # points closer than 0.03 share one label
    for q, c in sorted(un.items(), key=lambda x: x[1]):
        if groups and c - groups[-1][-1][1] < 0.03:
            groups[-1].append((q, c))
        else:
            groups.append([(q, c)])
    for i, g in enumerate(groups):
        x = sum(c for _, c in g) / len(g)
        ax.annotate(", ".join(sorted(q for q, _ in g)), (x, 0), xytext=(0, -10 if i % 2 == 0 else 9), textcoords="offset points",
                    ha="center", va="center", fontsize=5.5, color=MUTED)
    ax.axvline(tau, color=INK, lw=1, ls="--")
    ax.text(tau - 0.012, 1.42, f"τ = {tau:.2f}\n← declined before the LLM", fontsize=6, ha="right", va="top")
    ax.set_yticks([0, 1], ["Unanswerable /\noff-topic (5)", "Answerable (20)"])
    ax.set_ylim(-0.6, 1.5)
    ax.set_xlim(0, 0.8)
    ax.set_xlabel("BM25 confidence  (top score ÷ best reachable score)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig4_gate_confidence")


def fig5_ablation():
    """BM25 P@5 and MRR after each retrieval change (values recorded in system_design.md §12)."""
    steps = ["Baseline\n(b=0.75)", "Merge\nduplicates", "b = 0.5", "Heading\nfix"]
    p5 = [0.540, 0.560, 0.590, 0.580]
    mrr = [0.775, 0.783, 0.792, 0.792]
    fig, ax = plt.subplots(figsize=(COL_W, 2.0))
    ax.plot(steps, mrr, color=ORANGE, lw=2, marker="D", ms=5, label="MRR", zorder=3)
    ax.plot(steps, p5, color=BLUE, lw=2, marker="o", ms=5, label="P@5", zorder=3)
    for i, (a, b) in enumerate(zip(p5, mrr)):
        ax.text(i, b + 0.022, f"{b:.3f}", ha="center", fontsize=6.5)
        ax.text(i, a - 0.05, f"{a:.3f}", ha="center", fontsize=6.5)
    ax.set_ylim(0.45, 0.88)
    ax.set_xlim(-0.35, 3.35)
    ax.set_ylabel("BM25 score")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="center right", frameon=False)
    save(fig, "fig5_ablation")


if __name__ == "__main__":
    text = latest_retrieval()
    fig2_retrieval(text)
    fig3_per_query(text)
    fig4_confidence(text)
    fig5_ablation()
