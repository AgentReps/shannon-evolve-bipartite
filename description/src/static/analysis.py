"""Empirical-distribution analysis of graphs and round outcomes (MODEL.md reqs 1,2,4,5).

These functions turn a graph or a round result into a plain :class:`DistributionSummary`
(or, for accepts, a small dict). They make no assumptions about the upstream model, so they
work equally on the feasible graph (left = senders, right = receivers) and on the thinned
intention graph.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .graph import BipartiteGraph
from .round import RoundResult


@dataclass(frozen=True)
class DistributionSummary:
    """Empirical distribution of a non-negative integer quantity over a sample."""

    counts: dict[int, int]  # value -> frequency
    pmf: dict[int, float]  # value -> relative frequency (sums to 1)
    mean: float
    var: float
    support_max: int
    n_samples: int

    @classmethod
    def from_values(cls, values: np.ndarray) -> DistributionSummary:
        values = np.asarray(values, dtype=np.int64)
        n = values.size
        if n == 0:
            return cls(counts={}, pmf={}, mean=0.0, var=0.0, support_max=0, n_samples=0)
        vals, freqs = np.unique(values, return_counts=True)
        counts = {int(v): int(c) for v, c in zip(vals, freqs, strict=True)}
        pmf = {v: c / n for v, c in counts.items()}
        return cls(
            counts=counts,
            pmf=pmf,
            mean=float(values.mean()),
            var=float(values.var()),
            support_max=int(values.max()),
            n_samples=n,
        )


def sender_degree_distribution(graph: BipartiteGraph) -> DistributionSummary:
    """Empirical out-degree distribution on the left (sender) side."""
    return DistributionSummary.from_values(graph.deg_sender())


def receiver_degree_distribution(graph: BipartiteGraph) -> DistributionSummary:
    """Empirical in-degree distribution on the right (receiver) side."""
    return DistributionSummary.from_values(graph.deg_receiver)


def grant_distribution(result: RoundResult) -> DistributionSummary:
    """Empirical distribution of the number of grants received per receiver (Stage 2)."""
    return DistributionSummary.from_values(result.grants_per_receiver)


def accept_summary(result: RoundResult) -> dict[str, float | int]:
    """Accept-stage outcome (Stage 3): how many receivers ended up matched."""
    matched = int((result.accept_sender >= 0).sum())
    return {
        "matched": matched,
        "unmatched": result.N - matched,
        "matching_size": result.matching_size,
        "matching_fraction": result.matching_fraction,
    }
