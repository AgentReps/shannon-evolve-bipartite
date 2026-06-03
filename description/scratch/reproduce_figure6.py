"""Reproduce Figure 6 (thinning) and Tables 1-2 of the paper with static.

Figure 6 (fig:06): mean matching fraction vs DB exponent alpha for thinned D-out graphs,
N=144, (d,k) in {4,8} x {2,3,4}.
  - Fig 6a: Binomial D ~ Bin(N, d/N)  with  max(k) thinning
  - Fig 6b: Deterministic D = d        with  Bern(k/d) thinning
(Per the paper: Bern(q) of G(n,n,p) is G(n,n,pq); max(k) of a d-out graph is a min(d,k)-out
graph -- so these two thinning/graph combos are the non-redundant ones.)

Tables 1-2 (tab:ER, tab:Det): mean matching fraction for Uniform DB(0), Optimal DB(alpha*),
Greedy DB(-inf), the optimal exponent alpha*, and the headline 2CGS = max(2) + DB(-inf), for
d in {2,3,4,8}.

We reproduce the figure curves and both tables by Monte-Carlo and compare to the paper's
published values (statistical accuracy, not exact match). Paper figure curves are parsed from
the figure .tex; table values are embedded from tnet-2026.tex.

Run:  cd model && uv run --extra plot python scratch/reproduce_figure6.py
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from pathlib import Path

import numpy as np

from static import bernoulli, binomial, db_alpha, db_greedy, db_uniform, deterministic, max_k, none
from static.experiment import ExperimentConfig, run_experiment

N = 144
SEED = 20260602
FIG_DIR = Path("../Articles/TNET-2026-00368/figures")

# ---------------------------------------------------------------- Figure 6 curves
FIG_REPS = 400
FIG_ALPHAS = list(range(-20, 1))
# legend order: (4,2),(4,3),(4,4),(8,2),(8,3),(8,4); color green=d4 red=d8; style solid/dash/dot=k2/3/4
DK_BY_COLOR_STYLE = {
    ("ForestGreen", "solid"): (4, 2), ("ForestGreen", "dashed"): (4, 3),
    ("ForestGreen", "dotted"): (4, 4), ("red", "solid"): (8, 2),
    ("red", "dashed"): (8, 3), ("red", "dotted"): (8, 4),
}


def parse_fig6(panel: str) -> dict:
    text = "\n".join(
        ln for ln in (FIG_DIR / f"figure-06{panel}.tex").read_text().splitlines()
        if not ln.lstrip().startswith("%")
    )
    out = {}
    for block in re.split(r"\\addplot", text)[1:]:
        head = block.split("coordinates")[0]
        cm = re.search(r"color\s*=\s*([A-Za-z]+)", head)
        if not cm:
            continue
        style = "dotted" if "dotted" in head else ("dashed" if "dashed" in head else "solid")
        key = DK_BY_COLOR_STYLE.get((cm.group(1), style))
        if key is None:
            continue
        coords = [(int(float(x)), float(y))
                  for x, y in re.findall(r"\(([-\d.]+),\s*([-\d.]+)\)", block)]
        out[key] = dict(coords)
    return out


def fig_panel(label: str, distribution: str, thinning_for, paper: dict) -> dict:
    print(f"\n=== {label}  (N={N}, {distribution}, reps={FIG_REPS}) ===")
    base = ExperimentConfig(N=N, distribution=distribution, reps=FIG_REPS, seed=SEED)
    results = {}
    for (d, k) in [(4, 2), (4, 3), (4, 4), (8, 2), (8, 3), (8, 4)]:
        p_curve = paper[(d, k)]
        thin = thinning_for(d, k)
        sim = {a: run_experiment(replace(base, mean_degree=d, thinning=thin,
                                         selection=db_alpha(float(a)))).mean
               for a in p_curve}
        diffs = np.array([sim[a] - p_curve[a] for a in p_curve])
        results[(d, k)] = dict(sim=sim, paper=p_curve)
        print(f"  (d,k)=({d},{k}): rms Δ={np.sqrt((diffs**2).mean()):.4f} "
              f"max|Δ|={np.abs(diffs).max():.4f} "
              f"peak sim={max(sim.values()):.4f} paper={max(p_curve.values()):.4f}")
    return results


# ---------------------------------------------------------------- Tables 1 & 2
TAB_REPS = 1000
OPT_REPS = 500
OPT_ALPHAS = [-math.inf] + [round(-6 + 0.2 * i, 1) for i in range(31)]  # -inf, -6.0..0.0 step .2

# paper tables: d -> (uniform, optimal, greedy, alpha_star, twocgs)
TAB_ER = {
    2: (0.581, 0.681, 0.681, "-inf", 0.678),
    3: (0.618, 0.704, 0.694, -3.9, 0.716),
    4: (0.626, 0.695, 0.655, -2.4, 0.728),
    8: (0.633, 0.661, 0.455, -1.4, 0.731),
}
TAB_DET = {
    2: (0.633, 0.737, 0.729, -4.4, 0.737),
    3: (0.633, 0.722, 0.688, -2.7, 0.737),
    4: (0.633, 0.700, 0.625, -2.0, 0.737),
    8: (0.633, 0.661, 0.431, -1.3, 0.737),
}


def reproduce_table(label: str, distribution: str, paper: dict) -> None:
    print(f"\n=== {label}  (N={N}, {distribution}, reps={TAB_REPS}; optimal grid reps={OPT_REPS}) ===")
    base = ExperimentConfig(N=N, distribution=distribution, seed=SEED)
    hdr = (f"{'d':>2} | {'uniform':>15} | {'greedy':>15} | {'optimal (a*)':>22} | "
           f"{'2CGS max(2)+greedy':>22}")
    print(hdr)
    print("-" * len(hdr))
    for d in (2, 3, 4, 8):
        p_uni, p_opt, p_grd, p_astar, p_2cgs = paper[d]
        uni = run_experiment(replace(base, mean_degree=d, reps=TAB_REPS,
                                     thinning=none(), selection=db_uniform())).mean
        grd = run_experiment(replace(base, mean_degree=d, reps=TAB_REPS,
                                     thinning=none(), selection=db_greedy())).mean
        twocgs = run_experiment(replace(base, mean_degree=d, reps=TAB_REPS,
                                        thinning=max_k(2), selection=db_greedy())).mean
        # optimal: argmax over the alpha grid (unthinned)
        opt_vals = {a: run_experiment(replace(base, mean_degree=d, reps=OPT_REPS,
                                              thinning=none(), selection=db_alpha(float(a)))).mean
                    for a in OPT_ALPHAS}
        a_star = max(opt_vals, key=opt_vals.get)
        opt = opt_vals[a_star]
        a_star_s = "-inf" if a_star == -math.inf else f"{a_star:g}"
        print(
            f"{d:>2} | {uni:.3f} vs {p_uni:.3f} {uni - p_uni:+.3f} | "
            f"{grd:.3f} vs {p_grd:.3f} {grd - p_grd:+.3f} | "
            f"{opt:.3f} vs {p_opt:.3f} {opt - p_opt:+.3f} (a*={a_star_s} vs {p_astar}) | "
            f"{twocgs:.3f} vs {p_2cgs:.3f} {twocgs - p_2cgs:+.3f}"
        )


def plot(panels: dict) -> None:
    import matplotlib.pyplot as plt

    cmap = {4: "forestgreen", 8: "red"}
    smap = {2: "-", 3: "--", 4: ":"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, (label, res) in zip(axes, panels.items(), strict=True):
        for (d, k), r in res.items():
            xs = sorted(r["sim"])
            ax.plot(xs, [r["sim"][a] for a in xs], smap[k], color=cmap[d], lw=1.4)
            ax.plot(xs, [r["paper"][a] for a in xs], "x", color=cmap[d], ms=3, alpha=0.6)
        ax.set_title(label)
        ax.set_xlabel(r"exponent $\alpha$")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("mean matching fraction")
    handles = [
        plt.Line2D([], [], color="forestgreen", label="d=4"),
        plt.Line2D([], [], color="red", label="d=8"),
        plt.Line2D([], [], color="gray", ls="-", label="k=2 (max/Bern)"),
        plt.Line2D([], [], color="gray", ls="--", label="k=3"),
        plt.Line2D([], [], color="gray", ls=":", label="k=4"),
        plt.Line2D([], [], color="gray", marker="x", ls="", label="paper"),
    ]
    axes[1].legend(handles=handles, fontsize=7, loc="lower right")
    fig.suptitle("Figure 6 reproduction: lines=sim, x=paper")
    fig.tight_layout()
    out = "scratch/figure6_reproduction.png"
    fig.savefig(out, dpi=130)
    print(f"\nSaved overlay plot to {out}")


def main() -> None:
    panels = {
        "Fig 6a: Binomial + max(k)": fig_panel(
            "Fig 6a", "binomial", lambda d, k: max_k(k), parse_fig6("a")),
        "Fig 6b: Deterministic + Bern(k/d)": fig_panel(
            "Fig 6b", "deterministic", lambda d, k: bernoulli(k / d), parse_fig6("b")),
    }
    print("\n" + "#" * 70 + "\n# Tables 1 & 2 (includes the headline 2CGS column)\n" + "#" * 70)
    reproduce_table("Table 1 (Erdos-Renyi)", "binomial", TAB_ER)
    reproduce_table("Table 2 (deterministic)", "deterministic", TAB_DET)
    try:
        plot(panels)
    except ImportError:
        print("\n(matplotlib not available; skipping plot.)")


if __name__ == "__main__":
    main()
