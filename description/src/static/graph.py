"""The bipartite-graph container (MODEL.md §3.1, §8.1).

A single sparse-adjacency backend: ``adj_sender[u]`` is the array of receiver ids that
sender ``u`` points to. Senders and receivers share the index space ``0..N-1`` but live in
disjoint vertex sets ``U`` and ``V`` (a sender id and a receiver id with the same integer
are different nodes). Receiver degrees are computed by a sparse scatter-add and cached.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BipartiteGraph:
    """A ``D``-out bipartite graph on senders ``U`` and receivers ``V``, ``|U| = |V| = N``.

    ``adj_sender[u]`` holds the (distinct) receiver ids of sender ``u``. The same structure
    represents both the *feasible* graph and, after thinning, the *intention* graph.
    """

    N: int
    adj_sender: list[np.ndarray]
    _deg_receiver: np.ndarray | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if len(self.adj_sender) != self.N:
            raise ValueError(f"expected {self.N} senders, got {len(self.adj_sender)}")

    @property
    def deg_receiver(self) -> np.ndarray:
        """Receiver in-degrees ``deg(v) = |{u : u ~ v}|``, shape ``(N,)`` (cached).

        This is the quantity senders learn from REQ replies and that the DB(alpha) rule
        consumes (MODEL.md §4, §5.2).
        """
        if self._deg_receiver is None:
            deg = np.zeros(self.N, dtype=np.int64)
            if self.num_edges() > 0:
                all_receivers = np.concatenate(self.adj_sender)
                np.add.at(deg, all_receivers, 1)
            self._deg_receiver = deg
        return self._deg_receiver

    def deg_sender(self) -> np.ndarray:
        """Sender out-degrees ``deg(u) = |N_u|``, shape ``(N,)``."""
        return np.fromiter((a.size for a in self.adj_sender), dtype=np.int64, count=self.N)

    def num_edges(self) -> int:
        return int(sum(a.size for a in self.adj_sender))

    def copy(self) -> BipartiteGraph:
        """Deep copy of the adjacency arrays (thinning is non-destructive on the input)."""
        return BipartiteGraph(self.N, [a.copy() for a in self.adj_sender])

    def invalidate_cache(self) -> None:
        """Drop the cached receiver-degree vector (call after mutating ``adj_sender``)."""
        self._deg_receiver = None

    def to_matrix(self) -> np.ndarray:
        """Dense ``N x N`` boolean adjacency view (for demos / small tests only)."""
        m = np.zeros((self.N, self.N), dtype=bool)
        for u, neighbors in enumerate(self.adj_sender):
            m[u, neighbors] = True
        return m
