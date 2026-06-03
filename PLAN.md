# Plan: Adapt shannon-evolve to Distributed Bipartite Matching

## Context

The repo root is a generic `shannon-evolve` evolutionary-search template currently
configured for the LABS / merit-factor placeholder problem. `description/` (read-only)
specifies a different problem: **distributed bipartite matching** — match as many
sender–receiver pairs as possible in a single 4-stage message round where every node acts
only on local information.

Goal: re-target the root project at this problem so branches evolve a matching algorithm,
scored by a Monte-Carlo estimate of the **mean matching fraction**, with the
distributed-information ("no leakage") constraint enforced *structurally* by the interface,
and known solution paths (DB(0), DB(−∞), DB(α), 2CGS / `max(2)`) available as seeds.

Locked decisions (from user):
- **Objective:** robustness sweep — score = mean matching fraction averaged over a FIXED
  set of mean degrees **d ∈ {2,3,4,5,6,8,10}**, at **N = 144**.
- **Feasible graph:** **Binomial** D-out model (`D_u ~ Bin(N, d/N)`, then `D_u` distinct
  receivers chosen uniformly).
- **Monte-Carlo:** **~200 reps per density**, using **common random numbers** (fixed master
  seed) so every attempt is scored on byte-identical feasible graphs → paired, low-noise
  comparison and monotone search progress.

## The problem (verified from `description/MODEL.md`, `round.py`, `selection.py`)

One round, four synchronous stages on a bipartite graph of N senders / N receivers:
`NOTIFY` (sender thins, notifies a subset) → `REQ` (receivers reply, piggybacking their
intention-graph degree) → `GRANT` (each sender picks ONE neighbor) → `ACCEPT` (receiver keeps
one). Matching size = number of receivers that got ≥1 grant (ACCEPT doesn't change the count).
Reference points (N=144): DB(0) uniform ≈ **0.63**, 2CGS (`max(2)`+greedy) ≈ **0.73**
(robust, the bar to beat). Optimal α is non-decreasing in density: greedy (−∞) wins when
sparse, moderate α (≈ −1.3) when dense.

## The "no information leakage" design (core requirement)

Enforced by the function signatures themselves — a solution is *never handed the global graph*,
so it physically cannot leak. The EVOLVE-BLOCK exposes exactly two pure-local decision functions:

- `thin(degree, rng) -> indices` — NOTIFY stage. Receives ONLY this sender's own feasible
  out-degree (an int). Returns a subset of `range(degree)` (indices of neighbors to notify).
  Justification: at NOTIFY no degrees are known yet and neighbors are exchangeable uniform-random
  receivers, so out-degree is the *only* locality-respecting information. (`max(k)`, `Bern(q)`,
  `none` all express cleanly here.)
- `select(neighbor_degrees, rng) -> index` — GRANT stage. Receives ONLY the intention-graph
  degrees of *this sender's own* (post-thinning) neighbors (the REQ piggyback). Returns the
  index of the neighbor to grant to. This is exactly the DB(α) information set.

Tunable constants (e.g. `ALPHA`, `K`) chosen and **fixed for the network** live inside the
EVOLVE-BLOCK. `evaluate.py` validates outputs (indices in range, unique/subset) and marks any
violation `stage="invalid"`, `score=0` — so cheating or buggy locality fails closed.

## Files to create / modify (root only; `description/` untouched)

1. **`solution.py`** (rewrite) — module docstring stating the locality contract; one
   `# EVOLVE-BLOCK-START` / `# EVOLVE-BLOCK-END` region containing `ALPHA`/`K` constants plus
   `thin(...)` and `select(...)`. **Baseline = DB(0)**: `thin` keeps all (`np.arange(degree)`),
   `select` returns a uniform-random index (≈0.63, leaves clear headroom). Include the known
   seeds as clearly-labelled commented bodies right below: **DB(−∞) greedy**, **DB(α)**
   (log-space weights `α·log(deg)`, max-shifted — mirror `description/.../selection.py`), and
   **2CGS** (`thin` cap at `K=2` via `rng.choice(degree, min(degree,2), replace=False)` +
   greedy `select`). `__main__` prints a quick local mean-fraction sanity line.

2. **`evaluate.py`** (rewrite) — self-contained Monte-Carlo sampler (no runtime dependency on
   read-only `description/`; logic mirrors its verified pseudocode). Fixed constants:
   `N=144`, `DIST="binomial"`, `DENSITIES=[2,3,4,5,6,8,10]`, `REPS=200`, `MASTER_SEED`,
   `TARGET_SCORE=1.0` (never early-stop; run full budget), `MAX_ATTEMPTS=40`. Pipeline per
   `(density, rep)`: `SeedSequence([MASTER_SEED, d_idx, rep]).spawn(2)` → `rng_graph`,
   `rng_algo`; build Binomial feasible graph with `rng_graph` (identical across all
   algorithms); apply `thin` per sender (validate indices) → intention graph; scatter-add
   receiver degrees; `select` per sender with ≥1 kept neighbor (validate index) → mark granted
   receiver; fraction = `#granted / N`. Aggregate: `score = mean fraction over all
   reps×densities`; print one JSON line `{"score", "stage", "mean_fraction",
   "ci95_halfwidth", "per_density": {d: mean}}`. Keep `NotApplicableError`/`JUDGE_MODE`
   scaffolding (inert; we have a real scalar). Wrap solution import + calls in try/except →
   `stage="error"` on exception. Imports `thin, select` directly and runs **in-process**
   (per-sender callbacks can't be subprocess-per-call); step.py's 300s subprocess timeout
   still provides isolation.

3. **`step.py`** (light edit) — only the human-readable display lines that currently surface
   `merit_factor`; change to surface `mean_fraction` / `ci95_halfwidth`. The JSON protocol,
   state file, by-approach, elites, and commit logic are problem-agnostic and stay as-is.

4. **`prompts/strategies.txt`** (rewrite, 4 branch biases): (1) **selection tuning** — DB(α),
   α≤0, sweep exponent / greedy, per the density mix; (2) **thinning** — `max(k)` and
   `Bern(q)`, find the best cap (2CGS family); (3) **joint/robust** — thinning×selection
   combined, beat 2CGS's ~0.73 robustly across the sweep; (4) **novel local rules** —
   creative *leak-free* decision functions (degree-threshold grants, degree-adaptive thinning,
   randomized-greedy tie handling, two-stage local heuristics).

5. **`CLAUDE.md`** — replace the `## Problem` section (it explicitly invites editing) with the
   matching statement, the fixed parameters, baselines (DB(0)≈0.63 / 2CGS≈0.73), the locality
   contract, and a one-line pointer to the commented seeds in `solution.py`. Leave the rest
   (Loop, Mode, Diversity rules) unchanged.

6. **`README.md` + `log/` templates** (`README.md`, `frontier.md`, `digest.md`,
   `next-direction.md`) — swap LABS/merit-factor wording for matching/mean-fraction so the
   tracking scaffolding reads correctly. Cosmetic; no logic.

## Progress tracking (already provided by the framework — verify, don't rebuild)

`step.py` writes per-branch logs, `by-approach/*.md`, `state-*.json`, copies branch bests to
`elites/`, and commits on improvement; `status.sh`/`digest.sh` summarize. These work unchanged
once `evaluate.py` emits the standard JSON. New-best `score` is now directly the mean matching
fraction (no `/10` rescale), so logs read in natural units.

## Verification

1. `python3 evaluate.py` on the **DB(0)** baseline → JSON with `mean_fraction ≈ 0.63`,
   `stage="full"`, finishes in well under the 300s step timeout.
2. Swap the EVOLVE-BLOCK to the **2CGS** seed (`K=2`, greedy) → `mean_fraction ≈ 0.73`,
   confirming the sampler reproduces the reference ordering DB(0) < 2CGS.
3. **Determinism / CRN:** run `evaluate.py` twice on the same `solution.py` → identical
   `score` (fixed master seed).
4. **No-leakage guard:** temporarily make `select` return an out-of-range index → evaluator
   reports `stage="invalid"`, `score=0` (fails closed).
5. End-to-end harness: `BRANCH_ID=solo SHANNON_LOG_DIR=./log python3 step.py "baseline DB(0)"
   --approach db-uniform` → prints status JSON with `attempt`, `score`, `new_best`, and writes
   the branch log + `state-solo.json`.
