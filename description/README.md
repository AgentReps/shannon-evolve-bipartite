# static

A clean, tested Python framework for the **degree-biased distributed bipartite matching**
model and protocol specified in [`MODEL.md`](MODEL.md) (from the paper *Degree-Biased
Matching for Datacenter Transport*).

It lets you:

- **generate** the D-out random bipartite graphs the paper studies,
- **run** any member of the degree-biased (DB) algorithm family —
  `algorithm = (thinning rule) × (selection rule)` — over the 4-stage protocol,
- **analyze** the empirical distributions at each stage (sender/receiver degrees, grants,
  accepts), and
- **evaluate** the mean matching fraction by Monte-Carlo (its own module).

> Closed-form analytics (`MODEL.md` §6) are intentionally **not** shipped; the cheap formulas
> appear only as test oracles in [`tests/test_validation.py`](tests/test_validation.py).

## Install / run (uv)

```bash
cd model
uv sync                              # create env, install numpy + dev tools
uv run pytest -m "not slow" -q       # fast unit suite
uv run pytest -q                     # full suite incl. statistical validation (slow)
uv run python -m static.experiment  # Monte-Carlo summary (DB(0), N=144, d=8)
```

## Library usage

```python
from static import generate_feasible_graph, deterministic, MatchingRound, TWO_CGS, make_rng
from static import sender_degree_distribution, grant_distribution, accept_summary

rng = make_rng(0)
feasible = generate_feasible_graph(N=144, degree_sampler=deterministic(8), rng=rng)

result = MatchingRound(*TWO_CGS).run(feasible, rng)   # 2CGS = max(2) thinning + greedy select
print(result.matching_fraction)                       # ~0.74

print(sender_degree_distribution(feasible).mean)      # 8.0
print(grant_distribution(result).counts)              # grants-per-receiver histogram
print(accept_summary(result))                         # matched / unmatched counts
```

### The two algorithm knobs (easy to swap)

```python
from static import MatchingRound, none, max_k, bernoulli, db_uniform, db_alpha, db_greedy

MatchingRound(none(),   db_uniform())   # DB(0)  — 1r-dcPIM baseline
MatchingRound(none(),   db_greedy())    # DB(-∞) — greedy
MatchingRound(none(),   db_alpha(-1.4)) # DB(α)  — tuned exponent
MatchingRound(max_k(2), db_greedy())    # 2CGS   — recommended (preset: TWO_CGS)
```

- **Thinning** (`thinning.py`, NOTIFY stage): `none()`, `max_k(k)`, `bernoulli(q)`.
  Each is a `ThinningStrategy` callable `(graph, rng) -> graph`.
- **Selection** (`selection.py`, GRANT stage): `db_uniform()`, `db_alpha(α)`, `db_greedy()`.
  Each is a `SelectionStrategy` callable `(neighbors, deg_receiver, rng) -> receiver`.

Write your own by matching either `Protocol`.

## Monte-Carlo experiments

```python
from static.experiment import ExperimentConfig, run_experiment, sweep_alpha
from static import max_k, db_greedy

cfg = ExperimentConfig(N=144, mean_degree=8, distribution="binomial",
                       thinning=max_k(2), selection=db_greedy(),
                       reps=1000, seed=42)          # reps = accuracy/time knob
res = run_experiment(cfg)
print(res.summary())                                # mean, 95% CI, Q1/median/Q3

# sweep the DB exponent to locate α*
results = sweep_alpha(ExperimentConfig(mean_degree=8), [-3, -2, -1.4, -1, 0])
```

CLI:

```bash
uv run python -m static.experiment --selection greedy --thinning max_k --k 2 --reps 2000
# use the = form when a value starts with '-' (e.g. -inf, -1.4) so argparse doesn't
# mistake it for a flag:
uv run python -m static.experiment --sweep-alpha="-inf,-3,-1.4,0" --distribution binomial -d 8
uv run python -m static.experiment --sweep-density="2,3,4,8" --selection greedy
```

Set `--workers N` (or `n_workers`) for reproducible parallel replications.

## Design

| Module | Role |
|---|---|
| `rng` | seeded `Generator` helpers; `spawn_rngs` for independent reproducible reps |
| `graph` | `BipartiteGraph` (sparse adjacency, cached receiver degrees, `to_matrix()`) |
| `degree` | out-degree samplers: `deterministic`, `binomial`, `poisson` |
| `generate` | `generate_feasible_graph` (D-out, Assumption 1) |
| `thinning` | NOTIFY-stage strategies (pluggable) |
| `selection` | GRANT-stage DB(α) strategies (pluggable) |
| `round` | `MatchingRound` — the 4 synchronous stages → `RoundResult` |
| `analysis` | empirical degree / grant / accept distributions |
| `plotting` | optional matplotlib helpers (`pip install 'static[plot]'`) |
| `experiment` | Monte-Carlo runner, sweeps, CLI |

**Backend:** a single sparse adjacency representation (`list[np.ndarray]` of receiver ids).
Receiver degrees are a vectorized scatter-add — the matrix idiom expressed sparsely — so it
scales to the paper's `N=144`, `d∈{2..8}` without the O(N²) cost of a dense matrix. A
`to_matrix()` helper is provided for small demos.

**Reproducibility:** every randomized function takes an explicit `rng`; only top-level entry
points create one. Monte-Carlo reps use `SeedSequence.spawn`, so results are independent of
worker scheduling and reproducible from a single seed.

### Implementation notes

- **Numerically stable selection.** `db_alpha(α)` computes grant weights in log-space
  (`α·log(deg)`, max-shifted before exponentiating) rather than `deg**α` directly. This keeps
  the low-degree bias intact for large `|α|` — where `deg**α` would underflow to zero and
  collapse to a uniform draw — so `db_alpha` degrades smoothly toward `db_greedy` as `α → −∞`.
- **Validated configs.** `ExperimentConfig` checks its invariants on construction
  (`N > 0`, `reps ≥ 1`, `n_workers ≥ 1`, `0 < ci_level < 1`, known `distribution`) and raises
  `ValueError` with an actionable message, instead of failing deep inside NumPy later.
- **Graceful parallelism.** With `n_workers > 1`, replications run in a `ProcessPoolExecutor`.
  If the platform forbids multiprocessing (e.g. a restricted sandbox), the run emits a
  `RuntimeWarning` and falls back to serial execution — which yields identical numbers — rather
  than crashing. Custom strategies used with `n_workers > 1` must be picklable (top-level
  functions or frozen dataclasses, like the built-ins; not lambdas/closures).

## Validation (theory ↔ simulation)

`tests/test_validation.py` checks the simulator against `MODEL.md` §6:

- DB(0) mean fraction ≈ `1 − (1 − (1 − P{D=0})/N)^N` (≈ 0.633 at N=144, d≥2);
- DB(0) insensitivity (depends on `D` only through `P{D=0}`);
- greedy beats uniform when sparse (d=2);
- optimal `α*` non-decreasing in mean degree;
- 2CGS ≈ 0.737 (deterministic) roughly flat across densities;
- receiver-degree goodness-of-fit vs Poisson/Binomial.
