"""Thinning strategies — the NOTIFY-stage knob (MODEL.md §5.1, Definition 1).

Thinning subsamples each sender's feasible neighbors *before* matching, shaping the
intention-graph degree distribution and capping control overhead. A ``ThinningStrategy`` is a
callable ``(graph, rng) -> graph``. The concrete strategies are small frozen dataclasses
(picklable, so they cross ``ProcessPoolExecutor`` boundaries) constructed via factory
functions, composing exactly like the spec (``thinning=max_k(2)``). Each returns a NEW graph
(operating on ``graph.copy()``) so one feasible graph can be reused across thinning configs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from .graph import BipartiteGraph


@runtime_checkable
class ThinningStrategy(Protocol):
    """Callable mapping a feasible graph to a (thinned) intention graph."""

    def __call__(self, graph: BipartiteGraph, rng: np.random.Generator) -> BipartiteGraph: ...


@dataclass(frozen=True)
class _None:
    def __call__(self, graph: BipartiteGraph, rng: np.random.Generator) -> BipartiteGraph:
        return graph.copy()


@dataclass(frozen=True)
class _MaxK:
    k: int

    def __call__(self, graph: BipartiteGraph, rng: np.random.Generator) -> BipartiteGraph:
        out = graph.copy()
        for u, neighbors in enumerate(out.adj_sender):
            if neighbors.size > self.k:
                out.adj_sender[u] = rng.choice(neighbors, size=self.k, replace=False)
        out.invalidate_cache()
        return out


@dataclass(frozen=True)
class _Bernoulli:
    q: float

    def __call__(self, graph: BipartiteGraph, rng: np.random.Generator) -> BipartiteGraph:
        out = graph.copy()
        for u, neighbors in enumerate(out.adj_sender):
            if neighbors.size:
                out.adj_sender[u] = neighbors[rng.random(neighbors.size) < self.q]
        out.invalidate_cache()
        return out


def none() -> ThinningStrategy:
    """Keep all feasible edges: intention graph == feasible graph."""
    return _None()


def max_k(k: int) -> ThinningStrategy:
    """``max(k)``: a sender with more than ``k`` edges keeps exactly ``k`` of them, chosen
    uniformly at random; senders with ``<= k`` keep all. Yields a ``k``-out graph.
    ``max(2)`` is the paper's recommended sweet spot (2CGS)."""
    if k < 0:
        raise ValueError("k must be non-negative")
    return _MaxK(k)


def bernoulli(q: float) -> ThinningStrategy:
    """``Bern(q)``: keep each edge independently with probability ``q`` (mean degree -> q*D)."""
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    return _Bernoulli(q)
