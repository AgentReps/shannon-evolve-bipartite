"""static — degree-biased distributed bipartite matching simulator.

Implements the abstract model and distributed matching protocol from ``MODEL.md``:
generate D-out random bipartite graphs, run any member of the degree-biased (DB) algorithm
family — ``algorithm = (thinning rule) x (selection rule)`` — analyze the empirical
distributions at each stage, and evaluate performance by Monte-Carlo (see
:mod:`static.experiment`).

Quick start::

    from static import generate_feasible_graph, deterministic, MatchingRound, TWO_CGS, make_rng

    rng = make_rng(0)
    g = generate_feasible_graph(144, deterministic(8), rng)
    result = MatchingRound(*TWO_CGS).run(g, rng)
    print(result.matching_fraction)
"""

from __future__ import annotations

from .analysis import (
    DistributionSummary,
    accept_summary,
    grant_distribution,
    receiver_degree_distribution,
    sender_degree_distribution,
)
from .degree import binomial, deterministic, make_sampler, poisson
from .generate import generate_feasible_graph
from .graph import BipartiteGraph
from .rng import make_rng, spawn_rngs
from .round import MatchingRound, RoundResult
from .selection import db_alpha, db_greedy, db_uniform
from .thinning import bernoulli, max_k, none

# Named algorithms (MODEL.md §5.3) compose as (thinning, selection) pairs;
# splat into MatchingRound, e.g. MatchingRound(*TWO_CGS).
DB0 = (none(), db_uniform())  # 1r-dcPIM baseline
DB_GREEDY = (none(), db_greedy())  # best in sparse graphs
TWO_CGS = (max_k(2), db_greedy())  # recommended: robust across densities

__all__ = [
    "DB0",
    "DB_GREEDY",
    "TWO_CGS",
    "BipartiteGraph",
    "DistributionSummary",
    "MatchingRound",
    "RoundResult",
    "accept_summary",
    "bernoulli",
    "binomial",
    "db_alpha",
    "db_greedy",
    "db_uniform",
    "deterministic",
    "generate_feasible_graph",
    "grant_distribution",
    "make_rng",
    "make_sampler",
    "max_k",
    "none",
    "poisson",
    "receiver_degree_distribution",
    "sender_degree_distribution",
    "spawn_rngs",
]
