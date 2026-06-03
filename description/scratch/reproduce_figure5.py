"""Reproduce Figure 5 of the paper with static and check statistical accuracy.

Figure 5 (tnet-2026.tex, fig:05): mean matching fraction vs DB exponent alpha in (-inf, 0],
for mean sender degrees d in {2,3,4,8}, N=144, 1000 replicates, NO thinning.
  - Fig 5a: Erdos-Renyi  D ~ Bin(N, d/N)
  - Fig 5b: deterministic D = d
Each d has a SOLID curve (DB(alpha) mean matching fraction, swept over integer alpha in
[-20, 0]) and a DOTTED horizontal line (the omniscient maximum-matching fraction, an upper
bound that does not depend on alpha).

We reproduce both:
  * the DB(alpha) sweep, using static's db_alpha selection (no thinning), and
  * the max-matching bound, using scipy's maximum_bipartite_matching on the same graph model.
Paper curves are parsed straight from the figure .tex (source of truth). This is a
statistical-accuracy check, not an exact match.

Run:  cd model && uv run --extra plot python scratch/reproduce_figure5.py
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

from static import binomial, db_alpha, deterministic, generate_feasible_graph, none, spawn_rngs
from static.experiment import ExperimentConfig, run_experiment

N = 144
REPS = 400  # accuracy/time knob; SEM ~ 0.025/sqrt(400) ~ 0.0013
SEED = 20260602
ALPHAS = list(range(-20, 1))  # integer grid [-20 .. 0], matching the paper

FIG_DIR = Path("../Articles/TNET-2026-00368/figures")
COLOR_TO_D = {"violet": 2, "blue": 3, "ForestGreen": 4, "red": 8}


def parse_paper(panel: str) -> dict:
    """Parse a figure-05x.tex into {d: {'db': {alpha: y}, 'max': y}} from active addplots."""
    text = "\n".join(
        ln for ln in (FIG_DIR / f"figure-05{panel}.tex").read_text().splitlines()
        if not ln.lstrip().startswith("%")
    )
    out: dict[int, dict] = {}
    for block in re.split(r"\\addplot", text)[1:]:
        head = block.split("coordinates")[0]
        cm = re.search(r"color\s*=\s*([A-Za-z]+)", head)
        if not cm or cm.group(1) not in COLOR_TO_D:
            continue
        d = COLOR_TO_D[cm.group(1)]
        coords = [(float(x), float(y)) for x, y in re.findall(r"\(([-\d.]+),\s*([-\d.]+)\)", block)]
        entry = out.setdefault(d, {})
        if "dotted" in head:
            entry["max"] = float(np.mean([y for _, y in coords]))  # constant line
        else:
            entry["db"] = {int(x): y for x, y in coords}
    return out


def max_matching_fraction(g) -> float:
    """Omniscient maximum bipartite matching fraction (centralized upper bound)."""
    rows, cols = [], []
    for u, nb in enumerate(g.adj_sender):
        rows.extend([u] * nb.size)
        cols.extend(nb.tolist())
    biadj = csr_matrix((np.ones(len(rows), bool), (rows, cols)), shape=(g.N, g.N))
    perm = maximum_bipartite_matching(biadj, perm_type="row")
    return int((perm >= 0).sum()) / g.N


def sim_db_sweep(distribution: str, d: int) -> dict[int, float]:
    base = ExperimentConfig(N=N, distribution=distribution, thinning=none(), reps=REPS, seed=SEED)
    return {
        a: run_experiment(replace(base, mean_degree=d, selection=db_alpha(float(a)))).mean
        for a in ALPHAS
    }


def sim_max_bound(distribution: str, d: int) -> float:
    sampler = binomial(N, d) if distribution == "binomial" else deterministic(d)
    rngs = spawn_rngs(SEED + 999, REPS)
    fracs = [max_matching_fraction(generate_feasible_graph(N, sampler, r)) for r in rngs]
    return float(np.mean(fracs))


def run_panel(label: str, distribution: str, paper: dict) -> dict:
    print(f"\n=== {label}  (N={N}, {distribution}, reps={REPS}) ===")
    results = {}
    for d in (2, 3, 4, 8):
        sim_db = sim_db_sweep(distribution, d)
        sim_max = sim_max_bound(distribution, d)
        p_db = paper[d]["db"]
        p_max = paper[d]["max"]
        # compare DB curve over the shared alpha grid
        diffs = np.array([sim_db[a] - p_db[a] for a in ALPHAS])
        # argmax (optimal alpha) for sim and paper
        sim_astar = max(sim_db, key=sim_db.get)
        p_astar = max(p_db, key=p_db.get)
        results[d] = dict(sim_db=sim_db, sim_max=sim_max, p_db=p_db, p_max=p_max)
        print(
            f" d={d}: DB curve rms Δ={np.sqrt((diffs**2).mean()):.4f} max|Δ|={np.abs(diffs).max():.4f}"
            f" | argmax α*: sim={sim_astar} paper={p_astar}"
            f" | peak: sim={max(sim_db.values()):.4f} paper={max(p_db.values()):.4f}"
            f" | MAXbound sim={sim_max:.4f} paper={p_max:.4f} Δ={sim_max - p_max:+.4f}"
        )
    return results


def plot(panels: dict) -> None:
    import matplotlib.pyplot as plt

    colors = {2: "violet", 3: "blue", 4: "forestgreen", 8: "red"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, (label, res) in zip(axes, panels.items(), strict=True):
        for d in (2, 3, 4, 8):
            c = colors[d]
            sim_db, p_db = res[d]["sim_db"], res[d]["p_db"]
            ax.plot(ALPHAS, [sim_db[a] for a in ALPHAS], "-", color=c, lw=1.5,
                    label=f"sim d={d}")
            ax.plot(ALPHAS, [p_db[a] for a in ALPHAS], "x", color=c, ms=4, alpha=0.7,
                    label=f"paper d={d}")
            ax.axhline(res[d]["sim_max"], color=c, ls=":", lw=1, alpha=0.6)
            ax.axhline(res[d]["p_max"], color=c, ls="--", lw=0.7, alpha=0.4)
        ax.set_title(label)
        ax.set_xlabel(r"exponent $\alpha$")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("mean matching fraction")
    axes[1].legend(fontsize=7, ncol=2, loc="center right")
    fig.suptitle("Figure 5 reproduction: lines=sim, x=paper DB, dotted=sim max, dashed=paper max")
    fig.tight_layout()
    out = "scratch/figure5_reproduction.png"
    fig.savefig(out, dpi=130)
    print(f"\nSaved overlay plot to {out}")


def main() -> None:
    panels = {
        "Fig 5a: Bin(N, d/N)": run_panel("Fig 5a", "binomial", parse_paper("a")),
        "Fig 5b: deterministic D=d": run_panel("Fig 5b", "deterministic", parse_paper("b")),
    }
    try:
        plot(panels)
    except ImportError:
        print("\n(matplotlib not available; skipping plot.)")


if __name__ == "__main__":
    main()
