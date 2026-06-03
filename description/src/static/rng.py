"""Random-number-generator helpers.

Reproducibility rule (see MODEL.md): every function that consumes randomness takes an
explicit ``rng: numpy.random.Generator``. Only top-level entry points (e.g. the experiment
runner) ever call :func:`make_rng`. The module-global ``numpy.random.seed`` is never used.
"""

from __future__ import annotations

import numpy as np

SeedLike = int | np.random.SeedSequence | np.random.Generator | None


def make_rng(seed: SeedLike = None) -> np.random.Generator:
    """Return a fresh ``Generator``.

    Accepts an int seed, a ``SeedSequence``, an existing ``Generator`` (returned as-is), or
    ``None`` (nondeterministic). Passing a ``Generator`` through makes it easy to thread one
    stream into helpers that nominally accept a seed.
    """
    if isinstance(seed, np.random.Generator):
        return seed
    return np.random.default_rng(seed)


def spawn_rngs(seed: int, n: int) -> list[np.random.Generator]:
    """Return ``n`` independent, reproducible child generators.

    Uses ``SeedSequence.spawn`` so that Monte-Carlo replications (and parallel workers) get
    statistically independent streams whose results do not depend on scheduling order.
    """
    return [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(n)]
