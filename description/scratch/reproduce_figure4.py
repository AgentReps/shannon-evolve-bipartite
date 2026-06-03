"""Reproduce Figure 4 of the paper with the static framework and check statistical accuracy.

Figure 4 (tnet-2026.tex, fig:04): fraction of nodes matched vs mean degree d, for D-out random
bipartite graphs with DETERMINISTIC sender degree D = d, N=144, 1000 replicates, NO thinning.
  - Fig 4a: DB(0)   = uniform selection  (should be flat ~0.633, insensitive to d)
  - Fig 4b: DB(-inf)= greedy selection
Same structure as Figure 3, but deterministic degrees instead of Bin(N, d/N). We reproduce the
empirical mean, Q1, Q3 by Monte-Carlo and compare to the paper's published points (statistical
accuracy, not an exact match). Quartiles are quantiles of integer match counts => multiples of
1/144 ~ 0.00694.

Run:  cd model && uv run --extra plot python scratch/reproduce_figure4.py
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from static import db_greedy, db_uniform, none
from static.experiment import ExperimentConfig, run_experiment

N = 144
REPS = 1000
SEED = 20260602

# ---- Paper's published Figure 4 points (mean, Q1=lower quartile, Q3=upper quartile) --------
# figures/figure-04a.tex (DB(0), deterministic)
FIG4A = {
    "d": [2, 4, 6, 8, 10],
    "mean": [0.6339, 0.6334, 0.6332, 0.6325, 0.6329],
    "q1": [0.6181, 0.6181, 0.6181, 0.6181, 0.6181],
    "q3": [0.6528, 0.6528, 0.6528, 0.6528, 0.6528],
}
# figures/figure-04b.tex (DB(-inf), deterministic)
FIG4B = {
    "d": [2, 3, 4, 5, 6, 8, 10],
    "mean": [0.7257, 0.6847, 0.6222, 0.5624, 0.5128, 0.4285, 0.3694],
    "q1": [0.7083, 0.6736, 0.6111, 0.5486, 0.4931, 0.4097, 0.3542],
    "q3": [0.7431, 0.7014, 0.6389, 0.5764, 0.5208, 0.4375, 0.3819],
}

QUANTUM = 1.0 / N  # match counts are integers; fractions are multiples of 1/144


def run_panel(name: str, selection, paper: dict) -> list[dict]:
    base = ExperimentConfig(
        N=N, distribution="deterministic", thinning=none(), selection=selection,
        reps=REPS, seed=SEED,
    )
    rows = []
    print(f"\n=== {name}  (N={N}, deterministic, reps={REPS}, seed={SEED}) ===")
    header = f"{'d':>3} | {'sim mean':>9} {'paper':>7} {'Δmean':>7} {'SEM':>7} {'z':>5} "
    header += f"| {'simQ1':>7} {'paperQ1':>7} | {'simQ3':>7} {'paperQ3':>7}"
    print(header)
    print("-" * len(header))
    for i, d in enumerate(paper["d"]):
        res = run_experiment(replace(base, mean_degree=d))
        sim_mean, sim_q1, sim_q3 = res.mean, res.q1, res.q3
        p_mean, p_q1, p_q3 = paper["mean"][i], paper["q1"][i], paper["q3"][i]
        sem = float(res.fractions.std(ddof=1) / math.sqrt(REPS))
        dmean = sim_mean - p_mean
        z = dmean / sem if sem > 0 else 0.0
        rows.append(
            dict(d=d, sim_mean=sim_mean, p_mean=p_mean, dmean=dmean, sem=sem, z=z,
                 sim_q1=sim_q1, p_q1=p_q1, sim_q3=sim_q3, p_q3=p_q3)
        )
        print(
            f"{d:>3} | {sim_mean:>9.4f} {p_mean:>7.4f} {dmean:>+7.4f} {sem:>7.4f} {z:>+5.1f} "
            f"| {sim_q1:>7.4f} {p_q1:>7.4f} | {sim_q3:>7.4f} {p_q3:>7.4f}"
        )
    return rows


def assess(name: str, rows: list[dict]) -> None:
    dmean = np.array([r["dmean"] for r in rows])
    zs = np.array([r["z"] for r in rows])
    q1_off = np.array([abs(r["sim_q1"] - r["p_q1"]) for r in rows]) / QUANTUM
    q3_off = np.array([abs(r["sim_q3"] - r["p_q3"]) for r in rows]) / QUANTUM
    print(f"\n--- {name} accuracy ---")
    print(f"  mean |Δ|: max={np.abs(dmean).max():.4f}, rms={np.sqrt((dmean**2).mean()):.4f}")
    print(f"  mean |z| (Δ in SEMs): max={np.abs(zs).max():.2f}  "
          f"(|z|<=~3 => within Monte-Carlo noise)")
    print(f"  Q1 offset in 1/N quanta: max={q1_off.max():.2f}")
    print(f"  Q3 offset in 1/N quanta: max={q3_off.max():.2f}")


def main() -> None:
    rows_a = run_panel("Fig 4a: DB(0) uniform", db_uniform(), FIG4A)
    rows_b = run_panel("Fig 4b: DB(-inf) greedy", db_greedy(), FIG4B)
    assess("Fig 4a", rows_a)
    assess("Fig 4b", rows_b)

    try:
        plot(rows_a, rows_b)
    except ImportError:
        print("\n(matplotlib not available; skipping plot. Use: uv run --extra plot ...)")


def plot(rows_a: list[dict], rows_b: list[dict]) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, rows, title in (
        (axes[0], rows_a, "Fig 4a: DB(0) — deterministic D=d"),
        (axes[1], rows_b, "Fig 4b: DB(-inf) — deterministic D=d"),
    ):
        d = [r["d"] for r in rows]
        ax.plot(d, [r["p_mean"] for r in rows], "k--", marker="s", label="paper mean")
        ax.plot(d, [r["sim_mean"] for r in rows], "b-", marker="o", label="sim mean")
        ax.fill_between(d, [r["sim_q1"] for r in rows], [r["sim_q3"] for r in rows],
                        color="b", alpha=0.15, label="sim Q1-Q3")
        ax.plot(d, [r["p_q1"] for r in rows], color="green", ls=":", marker=".",
                label="paper Q1")
        ax.plot(d, [r["p_q3"] for r in rows], color="violet", ls=":", marker=".",
                label="paper Q3")
        ax.set_title(title)
        ax.set_xlabel("mean degree d")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    axes[0].set_ylabel("matching fraction")
    fig.tight_layout()
    out = "scratch/figure4_reproduction.png"
    fig.savefig(out, dpi=130)
    print(f"\nSaved overlay plot to {out}")


if __name__ == "__main__":
    main()
