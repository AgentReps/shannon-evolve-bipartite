"""The distributed matching round — the four synchronous stages (MODEL.md §4, §8.2c).

```
Stage 0  NOTIFY   apply thinning  -> intention graph
Stage 1  REQ      receivers reply degree(v); senders now know neighbor degrees
Stage 2  GRANT    each sender with >=1 neighbor picks one via the selection rule
Stage 3  ACCEPT   each receiver with >=1 grant accepts one sender uniformly
```

By the realization identity (§6.3) the matching size equals the number of granted-to
receivers, so ACCEPT does not change ``L_N`` — but we run it explicitly because the accept
analysis (which sender each receiver picked) is a first-class output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .graph import BipartiteGraph
from .rng import make_rng
from .selection import SelectionStrategy
from .thinning import ThinningStrategy


@dataclass
class RoundResult:
    """Everything one matching round produces, ready for analysis."""

    matched_pairs: list[tuple[int, int]]
    grants_per_receiver: np.ndarray  # int64 (N,): number of grants each receiver received
    chosen_receiver: np.ndarray  # int64 (N,): receiver each sender granted to, -1 if none
    accept_sender: np.ndarray  # int64 (N,): sender each receiver accepted, -1 if unmatched
    intention_graph: BipartiteGraph  # post-thinning graph (target of degree analysis)
    N: int = field(init=False)

    def __post_init__(self) -> None:
        self.N = self.intention_graph.N

    @property
    def matching_size(self) -> int:
        """``L_N``: the number of matched pairs."""
        return len(self.matched_pairs)

    @property
    def matching_fraction(self) -> float:
        """``L_N / N`` — the primary quality metric."""
        return self.matching_size / self.N


class MatchingRound:
    """One round of the distributed protocol, parameterized by the two algorithm knobs.

    Named algorithms compose directly, e.g. ``MatchingRound(max_k(2), db_greedy())`` is 2CGS.
    """

    def __init__(self, thinning: ThinningStrategy, selection: SelectionStrategy) -> None:
        self.thinning = thinning
        self.selection = selection

    def run(self, feasible: BipartiteGraph, rng: np.random.Generator | int | None) -> RoundResult:
        rng = make_rng(rng)
        N = feasible.N

        # Stage 0 NOTIFY: thin the feasible graph into the intention graph.
        intention = self.thinning(feasible, rng)

        # Stage 1 REQ: receivers reply with their degree (senders now know neighbor degrees).
        deg_receiver = intention.deg_receiver

        # Stage 2 GRANT: each sender with >=1 neighbor selects exactly one receiver.
        chosen_receiver = np.full(N, -1, dtype=np.int64)
        grants_in: list[list[int]] = [[] for _ in range(N)]
        for u, neighbors in enumerate(intention.adj_sender):
            if neighbors.size:
                v = self.selection(neighbors, deg_receiver, rng)
                chosen_receiver[u] = v
                grants_in[v].append(u)

        grants_per_receiver = np.fromiter((len(g) for g in grants_in), dtype=np.int64, count=N)

        # Stage 3 ACCEPT: each receiver with >=1 grant accepts one sender uniformly.
        accept_sender = np.full(N, -1, dtype=np.int64)
        matched_pairs: list[tuple[int, int]] = []
        for v, senders in enumerate(grants_in):
            if senders:
                u = int(rng.choice(senders)) if len(senders) > 1 else senders[0]
                accept_sender[v] = u
                matched_pairs.append((u, v))

        return RoundResult(
            matched_pairs=matched_pairs,
            grants_per_receiver=grants_per_receiver,
            chosen_receiver=chosen_receiver,
            accept_sender=accept_sender,
            intention_graph=intention,
        )
