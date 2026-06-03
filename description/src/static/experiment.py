"""Monte-Carlo performance evaluation (MODEL.md §7) — a standalone, runnable module.

Estimates the mean matching fraction ``(1/N) E[L_N(alpha)]`` by averaging over many random
problem instances. The replication count ``reps`` is the explicit statistical-accuracy vs
execution-time knob (the paper uses 1000). Each result reports the mean, a confidence
interval, and quartiles (Q1, median, Q3).

Run directly::

    python -m static.experiment                       # default DB(0) on N=144, d=8
    python -m static.experiment --selection greedy --thinning max_k --k 2 --reps 2000
    python -m static.experiment --sweep-alpha -3,-2,-1.4,-1,0 --distribution binomial
"""

from __future__ import annotations

import argparse
import math
import warnings
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace

import numpy as np

from . import selection as sel
from . import thinning as thin
from .degree import make_sampler
from .generate import generate_feasible_graph
from .rng import spawn_rngs
from .round import MatchingRound
from .selection import SelectionStrategy
from .thinning import ThinningStrategy


@dataclass(frozen=True)
class ExperimentConfig:
    """A single Monte-Carlo experiment point."""

    N: int = 144
    mean_degree: float = 8.0
    distribution: str = "binomial"  # deterministic | binomial | poisson
    thinning: ThinningStrategy = field(default_factory=thin.none)
    selection: SelectionStrategy = field(default_factory=sel.db_uniform)
    reps: int = 1000  # accuracy/time knob
    seed: int = 42
    n_workers: int = 1
    ci_level: float = 0.95

    def __post_init__(self) -> None:
        if self.N <= 0:
            raise ValueError(f"N must be positive, got {self.N}")
        if self.reps < 1:
            raise ValueError(f"reps must be >= 1, got {self.reps}")
        if self.n_workers < 1:
            raise ValueError(f"n_workers must be >= 1, got {self.n_workers}")
        if not 0.0 < self.ci_level < 1.0:
            raise ValueError(f"ci_level must be in (0, 1), got {self.ci_level}")
        if self.distribution not in {"deterministic", "binomial", "poisson"}:
            raise ValueError(f"unknown distribution {self.distribution!r}")


@dataclass(frozen=True)
class ExperimentResult:
    """Aggregated statistics over ``reps`` independent replications."""

    fractions: np.ndarray  # per-rep L_N / N, shape (reps,)
    mean: float
    ci_low: float
    ci_high: float
    q1: float
    median: float
    q3: float
    config: ExperimentConfig

    def summary(self) -> str:
        return (
            f"mean={self.mean:.4f}  "
            f"CI{int(self.config.ci_level * 100)}%=[{self.ci_low:.4f}, {self.ci_high:.4f}]  "
            f"Q1={self.q1:.4f} med={self.median:.4f} Q3={self.q3:.4f}  "
            f"(reps={self.config.reps})"
        )


# A worker-friendly free function: returns one replication's matching fraction.
def _one_rep(args: tuple[ExperimentConfig, np.random.Generator]) -> float:
    config, rng = args
    sampler = make_sampler(config.distribution, config.N, config.mean_degree)
    feasible = generate_feasible_graph(config.N, sampler, rng)
    round_ = MatchingRound(config.thinning, config.selection)
    return round_.run(feasible, rng).matching_fraction


def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    """Run ``config.reps`` independent replications and aggregate the statistics.

    With ``n_workers > 1`` replications run in a process pool. Because each rep is seeded from
    an independent spawned stream, results are identical to (and reproducible regardless of)
    the worker count. If the platform forbids multiprocessing (e.g. a restricted sandbox), the
    run transparently falls back to serial execution with a warning rather than crashing.
    """
    rngs = spawn_rngs(config.seed, config.reps)
    work = [(config, rng) for rng in rngs]

    if config.n_workers > 1:
        try:
            with ProcessPoolExecutor(max_workers=config.n_workers) as pool:
                results = list(pool.map(_one_rep, work))
            return _aggregate(np.asarray(results, dtype=np.float64), config)
        except (PermissionError, NotImplementedError, OSError) as exc:
            warnings.warn(
                f"parallel workers unavailable on this platform ({exc!r}); "
                "running serially instead",
                RuntimeWarning,
                stacklevel=2,
            )

    fractions = np.fromiter(map(_one_rep, work), dtype=np.float64, count=config.reps)
    return _aggregate(fractions, config)


def _aggregate(fractions: np.ndarray, config: ExperimentConfig) -> ExperimentResult:
    mean = float(fractions.mean())
    # Normal-approximation CI on the mean (sound for large reps).
    z = _z_score(config.ci_level)
    sem = float(fractions.std(ddof=1) / math.sqrt(fractions.size)) if fractions.size > 1 else 0.0
    q1, median, q3 = (float(x) for x in np.quantile(fractions, [0.25, 0.5, 0.75]))
    return ExperimentResult(
        fractions=fractions,
        mean=mean,
        ci_low=mean - z * sem,
        ci_high=mean + z * sem,
        q1=q1,
        median=median,
        q3=q3,
        config=config,
    )


def _z_score(ci_level: float) -> float:
    # Inverse standard-normal CDF without a scipy dependency at runtime.
    # math.erfinv is unavailable; use the relation z = sqrt(2) * erfinv(2p-1) via a small approx.
    # For the few standard levels we just hard-code; otherwise fall back to a rational approx.
    table = {0.90: 1.6448536269514722, 0.95: 1.959963984540054, 0.99: 2.5758293035489004}
    if ci_level in table:
        return table[ci_level]
    p = 0.5 + ci_level / 2.0
    return _ppf_normal(p)


def _ppf_normal(p: float) -> float:
    # Acklam's rational approximation to the standard-normal quantile (abs error < 1.15e-9).
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


def sweep_alpha(base: ExperimentConfig, alphas: Sequence[float]) -> dict[float, ExperimentResult]:
    """Sweep the DB selection exponent ``alpha`` (with ``none`` thinning by default)."""
    return {a: run_experiment(replace(base, selection=sel.db_alpha(a))) for a in alphas}


def sweep_density(
    base: ExperimentConfig, mean_degrees: Sequence[float]
) -> dict[float, ExperimentResult]:
    """Sweep the mean degree ``d``."""
    return {d: run_experiment(replace(base, mean_degree=d)) for d in mean_degrees}


def find_optimal_alpha(base: ExperimentConfig, alphas: Sequence[float]) -> float:
    """Return the ``alpha`` maximizing the mean matching fraction over the swept values."""
    results = sweep_alpha(base, alphas)
    return max(results, key=lambda a: results[a].mean)


# --------------------------------------------------------------------------- CLI


def _build_selection(name: str, alpha: float) -> SelectionStrategy:
    if name == "uniform":
        return sel.db_uniform()
    if name == "greedy":
        return sel.db_greedy()
    if name == "alpha":
        return sel.db_alpha(alpha)
    raise ValueError(f"unknown selection {name!r}")


def _build_thinning(name: str, k: int, q: float) -> ThinningStrategy:
    if name == "none":
        return thin.none()
    if name == "max_k":
        return thin.max_k(k)
    if name == "bernoulli":
        return thin.bernoulli(q)
    raise ValueError(f"unknown thinning {name!r}")


def _parse_floats(text: str) -> list[float]:
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        out.append(-math.inf if tok in {"-inf", "-infinity"} else float(tok))
    return out


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Monte-Carlo matching-fraction experiments.")
    p.add_argument("--N", type=int, default=144)
    p.add_argument("--mean-degree", "-d", type=float, default=8.0)
    p.add_argument(
        "--distribution", choices=["deterministic", "binomial", "poisson"], default="binomial"
    )
    p.add_argument("--selection", choices=["uniform", "greedy", "alpha"], default="uniform")
    p.add_argument("--alpha", type=float, default=0.0, help="exponent when --selection alpha")
    p.add_argument("--thinning", choices=["none", "max_k", "bernoulli"], default="none")
    p.add_argument("--k", type=int, default=2, help="cap for --thinning max_k")
    p.add_argument("--q", type=float, default=0.5, help="keep prob for --thinning bernoulli")
    p.add_argument("--reps", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--sweep-alpha", type=str, default=None, help="comma list, e.g. -3,-1.4,0")
    p.add_argument("--sweep-density", type=str, default=None, help="comma list, e.g. 2,3,4,8")
    args = p.parse_args(argv)

    config = ExperimentConfig(
        N=args.N,
        mean_degree=args.mean_degree,
        distribution=args.distribution,
        thinning=_build_thinning(args.thinning, args.k, args.q),
        selection=_build_selection(args.selection, args.alpha),
        reps=args.reps,
        seed=args.seed,
        n_workers=args.workers,
    )

    if args.sweep_alpha:
        print(f"alpha sweep (d={config.mean_degree}, {config.distribution}, N={config.N}):")
        for a, res in sweep_alpha(config, _parse_floats(args.sweep_alpha)).items():
            print(f"  alpha={a:>6}: {res.summary()}")
    elif args.sweep_density:
        print(f"density sweep ({config.distribution}, N={config.N}):")
        for d, res in sweep_density(config, _parse_floats(args.sweep_density)).items():
            print(f"  d={d:>5}: {res.summary()}")
    else:
        print(
            f"N={config.N} d={config.mean_degree} {config.distribution} "
            f"selection={args.selection} thinning={args.thinning}"
        )
        print(f"  {run_experiment(config).summary()}")


if __name__ == "__main__":
    main()
