# static — User Guide

A task-oriented guide to the degree-biased distributed bipartite matching framework. For the
*why* (the model and protocol), see [`../MODEL.md`](../MODEL.md); for a one-page overview see
[`../README.md`](../README.md). This guide walks through the framework end to end.

## Contents

1. [Install & verify](#1-install--verify)
2. [Core concepts in 60 seconds](#2-core-concepts-in-60-seconds)
3. [Generate a graph](#3-generate-a-graph)
4. [Run one matching round](#4-run-one-matching-round)
5. [The two algorithm knobs](#5-the-two-algorithm-knobs)
6. [Analyze the empirical distributions](#6-analyze-the-empirical-distributions)
7. [Monte-Carlo experiments](#7-monte-carlo-experiments)
8. [The command-line interface](#8-the-command-line-interface)
9. [Plotting (optional)](#9-plotting-optional)
10. [Reproducibility & seeding](#10-reproducibility--seeding)
11. [Extending the framework](#11-extending-the-framework)
12. [Recipes](#12-recipes)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Install & verify

The project is managed with [`uv`](https://docs.astral.sh/uv/). From the `model/` directory:

```bash
cd model
uv sync                              # create .venv, install numpy + dev tools
uv run pytest -m "not slow" -q       # fast unit suite (~2s)
uv run pytest -q                     # full suite incl. statistical validation (~30s)
uv run python -m static.experiment  # prints a Monte-Carlo summary
```

Prefix any Python command with `uv run` so it uses the project environment. (System Python is
not used — `uv` provisions an interpreter that satisfies `requires-python >=3.11`.)

---

## 2. Core concepts in 60 seconds

One **round** of the protocol matches **senders** `U` to **receivers** `V` (both indexed
`0..N-1`) in a bipartite graph, subject to: each sender grants to one receiver, each receiver
accepts one sender. The framework models a round in four stages:

```
Stage 0 NOTIFY   apply a THINNING rule  -> intention graph
Stage 1 REQ      receivers report deg(v); senders learn neighbor degrees
Stage 2 GRANT    each sender picks one neighbor via a SELECTION rule
Stage 3 ACCEPT   each receiver with >=1 grant accepts one sender (uniformly)
```

An **algorithm** is fully specified by two pluggable knobs:

```
algorithm = (thinning rule at NOTIFY) x (selection rule at GRANT)
```

The headline quality metric is the **mean matching fraction** `L_N / N` — the share of nodes
that get matched.

---

## 3. Generate a graph

A *feasible graph* is a D-out random bipartite graph: each sender independently draws an
out-degree, then picks that many distinct receivers uniformly at random.

```python
from static import generate_feasible_graph, deterministic, binomial, poisson, make_rng

rng = make_rng(42)                                       # seeded generator

# Pick a degree distribution (all parameterized by mean degree d):
g = generate_feasible_graph(N=144, degree_sampler=deterministic(8), rng=rng)
# g = generate_feasible_graph(144, binomial(144, 8), rng)   # Bin(N, d/N)
# g = generate_feasible_graph(144, poisson(8), rng)         # Pois(d)
```

The resulting `BipartiteGraph` exposes:

```python
g.N                  # 144
g.adj_sender[u]      # numpy array of receiver ids for sender u
g.deg_sender()       # out-degrees, shape (N,)
g.deg_receiver       # in-degrees (cached), shape (N,)
g.num_edges()        # total edges
g.to_matrix()        # dense N x N boolean adjacency (for small demos)
```

| Distribution | Factory | Notes |
|---|---|---|
| Deterministic | `deterministic(d)` | every sender has exactly `d` neighbors (`d` must be an int) |
| Binomial | `binomial(N, d)` | `Bin(N, d/N)` — the bipartite Erdős–Rényi graph |
| Poisson | `poisson(d)` | `Pois(d)` — the large-`N` limit |

---

## 4. Run one matching round

Compose an algorithm and run it on a feasible graph:

```python
from static import MatchingRound, max_k, db_greedy

round_ = MatchingRound(thinning=max_k(2), selection=db_greedy())   # this is 2CGS
result = round_.run(g, rng)

result.matching_fraction     # L_N / N, e.g. 0.74
result.matching_size         # L_N (number of matched pairs)
result.matched_pairs         # list of (sender, receiver)
result.chosen_receiver       # per sender: receiver granted to, or -1
result.grants_per_receiver   # per receiver: number of grants received
result.accept_sender         # per receiver: sender accepted, or -1
result.intention_graph       # the post-thinning graph (for degree analysis)
```

Named algorithms ship as presets — splat them into `MatchingRound`:

```python
from static import DB0, DB_GREEDY, TWO_CGS, MatchingRound

MatchingRound(*DB0)        # none thinning + uniform selection  (1r-dcPIM baseline)
MatchingRound(*DB_GREEDY)  # none thinning + greedy selection
MatchingRound(*TWO_CGS)    # max(2) thinning + greedy selection (recommended)
```

---

## 5. The two algorithm knobs

### Thinning (NOTIFY stage) — `static.thinning`

Subsamples each sender's neighbors before matching, shaping the intention-graph degree
distribution.

| Factory | Rule |
|---|---|
| `none()` | keep all feasible edges (intention = feasible) |
| `max_k(k)` | cap each sender at `k` edges (uniform subsample); yields a `k`-out graph |
| `bernoulli(q)` | keep each edge independently with probability `q` |

### Selection (GRANT stage) — `static.selection`

When a sender grants, it picks neighbor `v` with probability proportional to `deg(v)^α`.

| Factory | Behavior | When it wins |
|---|---|---|
| `db_uniform()` | α = 0, uniform over neighbors | the baseline |
| `db_alpha(α)` | favors low-degree receivers for α < 0 | tuned per density |
| `db_greedy()` | α = −∞, picks a minimum-degree neighbor | sparse graphs |

> Only `α ≤ 0` is of interest. `db_alpha(0)` and `db_alpha(-inf)` automatically dispatch to
> the uniform and greedy fast paths. Weights are computed in log-space (`α·log(deg)`), so even
> large-magnitude exponents like `db_alpha(-50)` keep the intended low-degree bias and degrade
> smoothly toward greedy — they do not underflow into a uniform draw.

Mix and match freely:

```python
from static import MatchingRound, none, max_k, bernoulli, db_uniform, db_alpha, db_greedy

MatchingRound(none(),        db_alpha(-1.4))   # tuned exponent, no thinning
MatchingRound(bernoulli(0.5), db_uniform())    # dilute, then uniform
MatchingRound(max_k(3),      db_greedy())      # 3-out greedy
```

---

## 6. Analyze the empirical distributions

Every analysis helper returns a plain `DistributionSummary` (`counts`, `pmf`, `mean`, `var`,
`support_max`, `n_samples`) — except `accept_summary`, which returns a small dict.

```python
from static import (
    sender_degree_distribution, receiver_degree_distribution,
    grant_distribution, accept_summary,
)

# Feasible graph (left = senders, right = receivers):
sd = sender_degree_distribution(g)
rd = receiver_degree_distribution(g)
print(sd.mean, sd.pmf)        # e.g. 8.0, {8: 1.0} for deterministic(8)

# Intention graph (after thinning) — pass result.intention_graph:
sender_degree_distribution(result.intention_graph)
receiver_degree_distribution(result.intention_graph)

# Round outcomes:
grant_distribution(result)    # how many grants each receiver got (Stage 2)
accept_summary(result)        # {'matched', 'unmatched', 'matching_size', 'matching_fraction'}
```

The same degree helpers work on both the feasible and intention graphs, so you can compare the
degree distributions before and after thinning.

---

## 7. Monte-Carlo experiments

The `experiment` module estimates the mean matching fraction over many random instances. It is
self-contained and runnable on its own. **`reps` is the accuracy-vs-time knob** (the paper uses
1000); results report the mean, a confidence interval, and quartiles.

```python
from static.experiment import ExperimentConfig, run_experiment
from static import max_k, db_greedy

cfg = ExperimentConfig(
    N=144, mean_degree=8, distribution="binomial",
    thinning=max_k(2), selection=db_greedy(),
    reps=1000, seed=42, n_workers=1, ci_level=0.95,
)
res = run_experiment(cfg)
print(res.summary())          # mean=0.7321  CI95%=[...]  Q1=.. med=.. Q3=..
res.mean, res.ci_low, res.ci_high, res.q1, res.median, res.q3
res.fractions                 # raw per-rep L_N/N array, shape (reps,)
```

Set `n_workers > 1` to parallelize replications across processes. The result is identical to a
serial run for the same `seed` (each rep draws from its own spawned stream), and if the
platform forbids multiprocessing the run warns and falls back to serial rather than crashing.

`ExperimentConfig` validates its arguments on construction — `N > 0`, `reps ≥ 1`,
`n_workers ≥ 1`, `0 < ci_level < 1`, and a known `distribution` — raising `ValueError` early
with a clear message rather than failing deep inside the run.

### Sweeps

```python
from static.experiment import sweep_alpha, sweep_density, find_optimal_alpha

base = ExperimentConfig(N=144, mean_degree=8, distribution="binomial", reps=500)

by_alpha = sweep_alpha(base, [-float("inf"), -3, -2, -1.4, -1, 0])  # dict: alpha -> result
by_d     = sweep_density(base, [2, 3, 4, 8])                        # dict: d -> result
best     = find_optimal_alpha(base, [-float("inf"), -2, -1.4, -1, 0])  # argmax mean
```

---

## 8. The command-line interface

Same runner, from the shell:

```bash
# single config (defaults: DB(0), N=144, d=8, binomial, 1000 reps)
uv run python -m static.experiment

# 2CGS
uv run python -m static.experiment --selection greedy --thinning max_k --k 2 --reps 2000

# sweeps — NOTE the = form when a value starts with '-' (e.g. -inf, -1.4),
# otherwise argparse mistakes it for a flag:
uv run python -m static.experiment --sweep-alpha="-inf,-3,-1.4,0" -d 8 --distribution binomial
uv run python -m static.experiment --sweep-density="2,3,4,8" --selection greedy
```

Key flags: `--N`, `--mean-degree/-d`, `--distribution {deterministic,binomial,poisson}`,
`--selection {uniform,greedy,alpha}` (with `--alpha`), `--thinning {none,max_k,bernoulli}`
(with `--k` / `--q`), `--reps`, `--seed`, `--workers`. Run with `--help` for the full list.

---

## 9. Plotting (optional)

Plotting lives in `static.plotting` and requires matplotlib (an optional extra):

```bash
uv run --extra plot python your_script.py     # or: pip install 'static[plot]'
```

```python
from static.plotting import plot_distribution, plot_sweep
import matplotlib.pyplot as plt

plot_distribution(grant_distribution(result))         # bar chart of an empirical PMF
plot_sweep(by_alpha)                                  # mean fraction + Q1–Q3 band vs parameter
plt.show()
```

The core package never imports matplotlib, so experiments stay dependency-light.

---

## 10. Reproducibility & seeding

The framework never touches the global NumPy RNG. Instead, every randomized function takes an
explicit `rng`:

```python
from static import make_rng, spawn_rngs

rng = make_rng(42)               # a seeded numpy Generator (or pass an existing one through)
rngs = spawn_rngs(seed=42, n=1000)   # 1000 independent, reproducible child streams
```

Experiments seed each replication from `SeedSequence.spawn`, so results are **identical across
runs and independent of worker count** — `run_experiment(cfg)` with `n_workers=1` and
`n_workers=8` produce the same numbers for the same `seed`.

---

## 11. Extending the framework

Both knobs are simple callables defined by a `Protocol`. Write your own and pass it straight to
`MatchingRound` — no registration needed.

**Custom thinning** — `(graph, rng) -> graph` (return a *new* graph; copy before mutating):

```python
from static.graph import BipartiteGraph

def thin_top_half(graph: BipartiteGraph, rng) -> BipartiteGraph:
    out = graph.copy()
    for u, nbrs in enumerate(out.adj_sender):
        out.adj_sender[u] = nbrs[: max(1, nbrs.size // 2)]
    out.invalidate_cache()        # degrees changed -> drop the cache
    return out

MatchingRound(thin_top_half, db_greedy()).run(g, rng)
```

**Custom selection** — `(neighbors, deg_receiver, rng) -> int`:

```python
import numpy as np

def select_least_loaded(neighbors, deg_receiver, rng) -> int:
    # e.g. break greedy ties toward the smallest receiver id
    degs = deg_receiver[neighbors]
    return int(neighbors[degs == degs.min()].min())

MatchingRound(none(), select_least_loaded).run(g, rng)
```

> If you plan to run with `n_workers > 1`, make strategies picklable (top-level functions or
> small frozen dataclasses, like the built-ins) rather than lambdas/closures.

---

## 12. Recipes

**Compare three algorithms at one density:**

```python
from static import DB0, DB_GREEDY, TWO_CGS
from static.experiment import ExperimentConfig, run_experiment

base = dict(N=144, mean_degree=8, distribution="binomial", reps=1000, seed=0)
for name, (thin, sel) in {"DB0": DB0, "greedy": DB_GREEDY, "2CGS": TWO_CGS}.items():
    res = run_experiment(ExperimentConfig(thinning=thin, selection=sel, **base))
    print(f"{name:7s} {res.summary()}")
```

**Locate the optimal exponent and see it shift with density:**

```python
from static.experiment import ExperimentConfig, find_optimal_alpha

alphas = [-float("inf"), -3, -2, -1.4, -1, -0.5, 0]
for d in (2, 4, 8):
    base = ExperimentConfig(N=144, mean_degree=d, distribution="binomial", reps=500)
    print(d, "-> alpha* =", find_optimal_alpha(base, alphas))
# expect alpha* near -inf at d=2, moving toward 0 as d grows.
```

**Inspect how thinning reshapes the receiver-degree distribution:**

```python
from static import receiver_degree_distribution, MatchingRound, max_k, db_greedy

g = generate_feasible_graph(144, deterministic(8), make_rng(1))
result = MatchingRound(max_k(2), db_greedy()).run(g, make_rng(1))
print("feasible  recv-deg mean:", receiver_degree_distribution(g).mean)               # ~8
print("intention recv-deg mean:", receiver_degree_distribution(result.intention_graph).mean)  # ~2
```

---

## 13. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `error: unrecognized arguments: -inf,...` | A sweep value starts with `-`. Use the `=` form: `--sweep-alpha="-inf,-1.4,0"`. |
| `ImportError: plotting requires matplotlib` | Install the extra: `uv run --extra plot ...` or `pip install 'static[plot]'`. |
| `ValueError: deterministic degree must be an integer` | `deterministic(d)` needs an int `d`; use `binomial`/`poisson` for fractional mean degree. |
| `ValueError` from `ExperimentConfig(...)` | Invalid config (e.g. `reps=0`, `ci_level=1.5`). The validator caught it at construction; fix the offending field. |
| `RuntimeWarning: parallel workers unavailable ...` | The platform forbids multiprocessing; the run already fell back to serial and the numbers are correct. Set `n_workers=1` to silence it. |
| `PicklingError` with `n_workers > 1` | A custom strategy is a lambda/closure. Make it a top-level function or frozen dataclass. |
| Results differ between runs | A fresh `make_rng(seed)` per run gives identical output; reusing one advancing generator does not. Pass a seed for reproducibility. |
| `VIRTUAL_ENV does not match` warning | Harmless; `uv` is ignoring a stale active venv and using `.venv`. |

---

### See also

- [`../MODEL.md`](../MODEL.md) — the mathematical model and protocol specification.
- [`../README.md`](../README.md) — quickstart and module map.
- [`../tests/test_validation.py`](../tests/test_validation.py) — the simulator checked against
  the paper's closed-form predictions.
