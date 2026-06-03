"""Sender out-degree distributions (MODEL.md §3.4).

A ``DegreeSampler`` draws all ``N`` sender out-degrees at once given an rng. The three
supported families share the same mean degree ``d`` so they are interchangeable in sweeps:

* ``deterministic(d)`` — every sender has exactly ``d`` neighbors.
* ``binomial(N, d)``   — ``Bin(N, d/N)`` (the bipartite Erdos-Renyi graph).
* ``poisson(d)``       — ``Pois(d)`` (the ``N -> inf`` limit).

The generator clips draws to ``N`` (Assumption 1/2); samplers do not, so a sampler can be
reused for any ``N``.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class DegreeSampler(Protocol):
    """Callable drawing ``size`` i.i.d. out-degrees as a non-negative integer array."""

    def __call__(self, rng: np.random.Generator, size: int) -> np.ndarray: ...


def deterministic(d: int) -> DegreeSampler:
    """Fixed degree ``D = d`` for every sender (Cor. 1a)."""
    if d < 0:
        raise ValueError("d must be non-negative")

    def sample(rng: np.random.Generator, size: int) -> np.ndarray:
        return np.full(size, d, dtype=np.int64)

    return sample


def binomial(N: int, d: float) -> DegreeSampler:
    """``D ~ Bin(N, d/N)`` with mean degree ``d`` (line 199)."""
    if not 0 <= d <= N:
        raise ValueError("mean degree d must satisfy 0 <= d <= N")
    p = d / N

    def sample(rng: np.random.Generator, size: int) -> np.ndarray:
        return rng.binomial(N, p, size=size).astype(np.int64)

    return sample


def poisson(d: float) -> DegreeSampler:
    """``D ~ Pois(d)`` with mean degree ``d`` (lines 719, 779)."""
    if d < 0:
        raise ValueError("mean degree d must be non-negative")

    def sample(rng: np.random.Generator, size: int) -> np.ndarray:
        return rng.poisson(d, size=size).astype(np.int64)

    return sample


_FAMILIES = {"deterministic", "binomial", "poisson"}


def make_sampler(distribution: str, N: int, d: float) -> DegreeSampler:
    """Build a sampler by name — convenience for config-driven experiments.

    ``deterministic`` requires an integer ``d``.
    """
    if distribution == "deterministic":
        if d != int(d):
            raise ValueError("deterministic degree must be an integer")
        return deterministic(int(d))
    if distribution == "binomial":
        return binomial(N, d)
    if distribution == "poisson":
        return poisson(d)
    raise ValueError(f"unknown distribution {distribution!r}; expected one of {_FAMILIES}")
