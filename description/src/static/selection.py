"""Selection strategies — the GRANT-stage knob, the DB(alpha) family (MODEL.md §5.2).

When sender ``u`` grants, it picks neighbor ``v`` with probability proportional to
``deg(v)**alpha`` (Definition 2). A ``SelectionStrategy`` is a callable
``(neighbors, deg_receiver, rng) -> chosen receiver id``. Only ``alpha <= 0`` is of interest:

* ``alpha = 0``     uniform (the DB(0) baseline).
* ``alpha < 0``     favors low-degree receivers (spreads grants, fewer collisions).
* ``alpha = -inf``  greedy: grant only to a minimum-degree neighbor (ties broken uniformly).

``neighbors`` is the calling sender's post-thinning neighbor array and is assumed non-empty
(the round only calls selection for senders with at least one neighbor).

Strategies are small frozen dataclasses (picklable, so they cross ``ProcessPoolExecutor``
boundaries) built via factory functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SelectionStrategy(Protocol):
    """Callable choosing one receiver from a sender's neighbors given receiver degrees."""

    def __call__(
        self,
        neighbors: np.ndarray,
        deg_receiver: np.ndarray,
        rng: np.random.Generator,
    ) -> int: ...


@dataclass(frozen=True)
class _Uniform:
    def __call__(self, neighbors, deg_receiver, rng) -> int:
        return int(rng.choice(neighbors))


@dataclass(frozen=True)
class _Greedy:
    def __call__(self, neighbors, deg_receiver, rng) -> int:
        degs = deg_receiver[neighbors]
        candidates = neighbors[degs == degs.min()]
        return int(rng.choice(candidates))


@dataclass(frozen=True)
class _Alpha:
    alpha: float

    def __call__(self, neighbors, deg_receiver, rng) -> int:
        degs = deg_receiver[neighbors].astype(np.float64)
        # Work in log-space: log_w = alpha * log(deg). This keeps the relative ordering for
        # large |alpha| where deg**alpha would underflow to 0 and collapse to a uniform draw.
        with np.errstate(divide="ignore"):  # deg 0 -> log(0) = -inf, handled via m below
            log_w = self.alpha * np.log(degs)
        m = log_w.max()
        if m == np.inf:
            # A degree-0 neighbor with alpha < 0 is "infinitely" preferred (defensive: real
            # neighbors have deg >= 1). Pick uniformly among such receivers.
            return int(rng.choice(neighbors[np.isposinf(log_w)]))
        if not np.isfinite(m):
            return int(rng.choice(neighbors))  # all weights vanish -> uniform fallback
        weights = np.exp(log_w - m)  # max weight is exp(0)=1, so the sum is always >= 1
        return int(rng.choice(neighbors, p=weights / weights.sum()))


def db_uniform() -> SelectionStrategy:
    """DB(0): choose uniformly at random among neighbors."""
    return _Uniform()


def db_greedy() -> SelectionStrategy:
    """DB(-inf): choose uniformly among the minimum-degree neighbors.

    Implemented as the explicit min-degree special case (per the spec's implementation tip)
    rather than evaluating ``deg(v)**-inf``.
    """
    return _Greedy()


def db_alpha(alpha: float) -> SelectionStrategy:
    """DB(alpha): choose neighbor ``v`` with probability proportional to ``deg(v)**alpha``.

    ``alpha == 0`` and ``alpha == -inf`` delegate to the dedicated fast paths. For other
    ``alpha`` the weights ``deg**alpha`` are normalized; if every weight is zero or non-finite
    we fall back to a uniform choice. (``alpha > 0`` is permitted but discouraged: it favors
    high-degree receivers and is excluded from the paper's study because it causes collisions.)
    """
    if alpha == 0:
        return _Uniform()
    if alpha == -np.inf:
        return _Greedy()
    return _Alpha(alpha)
