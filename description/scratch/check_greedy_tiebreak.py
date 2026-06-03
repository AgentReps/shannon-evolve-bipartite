"""Investigate the small systematic offset in Fig 3b (DB(-inf) greedy).

Hypothesis: the sub-percent gap (sim ~0.004 ABOVE the paper for small d) comes from greedy
TIE-BREAKING. static breaks ties among minimum-degree neighbors uniformly at random
(MODEL.md §5.2), which spreads grants and yields marginally more matches. A deterministic
tie-break (always the lowest receiver id) makes co-located senders collide more, lowering the
mean. We compare both tie-break rules against the paper's published Fig 3b means.

Run:  cd model && uv run python scratch/check_greedy_tiebreak.py
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from static.experiment import ExperimentConfig, run_experiment

N, REPS, SEED = 144, 2000, 7

PAPER_3B = {2: 0.6774, 3: 0.6905, 4: 0.6494, 5: 0.5942, 6: 0.5420, 8: 0.4546, 10: 0.3889}


def greedy_random(neighbors, deg_receiver, rng) -> int:
    degs = deg_receiver[neighbors]
    cands = neighbors[degs == degs.min()]
    return int(rng.choice(cands))


def greedy_lowest_id(neighbors, deg_receiver, rng) -> int:
    # deterministic tie-break: smallest receiver id among the min-degree neighbors
    degs = deg_receiver[neighbors]
    return int(neighbors[degs == degs.min()].min())


def panel(label, selection) -> None:
    base = ExperimentConfig(
        N=N, distribution="binomial", selection=selection, reps=REPS, seed=SEED
    )
    print(f"\n{label}")
    print(f"{'d':>3} | {'sim':>8} {'paper':>8} {'Δ':>8}")
    deltas = []
    for d in PAPER_3B:
        m = run_experiment(replace(base, mean_degree=d)).mean
        deltas.append(m - PAPER_3B[d])
        print(f"{d:>3} | {m:>8.4f} {PAPER_3B[d]:>8.4f} {m - PAPER_3B[d]:>+8.4f}")
    deltas = np.array(deltas)
    print(f"    mean Δ = {deltas.mean():+.4f}, rms Δ = {np.sqrt((deltas**2).mean()):.4f}")


if __name__ == "__main__":
    print(f"DB(-inf) greedy, binomial, N={N}, reps={REPS}, seed={SEED}")
    panel("uniform-random tie-break (static default, MODEL.md §5.2):", greedy_random)
    panel("deterministic lowest-id tie-break:", greedy_lowest_id)
