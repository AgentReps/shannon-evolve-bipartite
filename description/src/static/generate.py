"""The D-out random bipartite graph generator (MODEL.md §3.3, Assumption 1)."""

from __future__ import annotations

import numpy as np

from .degree import DegreeSampler
from .graph import BipartiteGraph


def generate_feasible_graph(
    N: int,
    degree_sampler: DegreeSampler,
    rng: np.random.Generator,
) -> BipartiteGraph:
    """Sample a feasible graph.

    Each sender ``u`` independently draws an out-degree ``D_u`` from ``degree_sampler``, then
    picks ``min(D_u, N)`` receiver-neighbors uniformly at random without replacement
    (Assumption 1). The result is the *feasible* graph ``G-tilde``; apply a thinning strategy
    to obtain the *intention* graph.
    """
    if N <= 0:
        raise ValueError("N must be positive")
    degrees = np.minimum(degree_sampler(rng, N), N)
    adj = [rng.choice(N, size=int(d), replace=False).astype(np.int64) for d in degrees]
    return BipartiteGraph(N=N, adj_sender=adj)
