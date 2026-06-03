"""Optional matplotlib plotting helpers.

This module is NOT imported by the core package; ``matplotlib`` is an optional dependency
(``pip install 'static[plot]'``). Importing the module without matplotlib raises a helpful
error. All helpers accept an existing ``Axes`` (or create one) and return it, so callers
compose figures freely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .analysis import DistributionSummary

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .experiment import ExperimentResult

try:
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
    raise ImportError(
        "plotting requires matplotlib; install with: pip install 'static[plot]'"
    ) from exc


def plot_distribution(summary: DistributionSummary, ax: Any = None, **bar_kwargs: Any) -> Any:
    """Bar plot of an empirical PMF (degree / grant distributions)."""
    if ax is None:
        _, ax = plt.subplots()
    values = sorted(summary.pmf)
    ax.bar(values, [summary.pmf[v] for v in values], **bar_kwargs)
    ax.set_xlabel("value")
    ax.set_ylabel("probability")
    ax.set_title(f"mean={summary.mean:.3f}, var={summary.var:.3f}, n={summary.n_samples}")
    return ax


def plot_sweep(results: Mapping[float, ExperimentResult], ax: Any = None, **kwargs: Any) -> Any:
    """Plot mean matching fraction with Q1-Q3 band against the swept parameter."""
    if ax is None:
        _, ax = plt.subplots()
    xs = sorted(results)
    means = [results[x].mean for x in xs]
    q1 = [results[x].q1 for x in xs]
    q3 = [results[x].q3 for x in xs]
    ax.plot(xs, means, marker="o", **kwargs)
    ax.fill_between(xs, q1, q3, alpha=0.2)
    ax.set_ylabel("mean matching fraction")
    return ax
