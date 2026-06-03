"""Monte-Carlo evaluator for distributed bipartite matching.

Prints a single JSON line to stdout. Imports `thin` and `select` from
`solution.py` in the cwd and runs the one-round protocol on many random
feasible graphs, scoring by the **mean matching fraction**.

Usage:
    python3 evaluate.py                   # scalar mode (default)
    JUDGE_MODE=true python3 evaluate.py   # LLM-as-judge fallback (inert here)

Design notes:
- The score is averaged over a FIXED robustness sweep of mean degrees on the
  Binomial D-out model at N=144 (see constants below). All randomness is derived
  from a fixed MASTER_SEED via SeedSequence, and the feasible graph for each
  (density, rep) is generated from its own dedicated stream BEFORE any call into
  the solution. So every attempt is scored on byte-identical feasible graphs —
  *common random numbers* — making comparisons paired and the search monotone.
- No information can leak: the solution's `thin`/`select` are handed only a single
  sender's own out-degree (NOTIFY) and its own neighbors' degrees (GRANT). The
  evaluator validates the returned indices and scores any violation as `invalid`.
- The matching size is the number of receivers that receive >=1 grant (the ACCEPT
  stage does not change the count), so we tally right after GRANT.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# Constants the agent reads. These define the problem — do not tune to inflate
# the score. They are FIXED for the network and the feasible-graph model.
# ----------------------------------------------------------------------------
N = 144                                  # senders = receivers
DIST = "binomial"                        # D_u ~ Bin(N, d/N), then D_u distinct receivers
DENSITIES = (2, 3, 4, 5, 6, 8, 10)       # mean-degree sweep the score averages over
REPS = 200                               # Monte-Carlo reps per density (common random numbers)
MASTER_SEED = 20240601                   # fixes the sampled graphs across all attempts
TARGET_SCORE = 1.0                       # unreachable cap; run the full attempt budget
MAX_ATTEMPTS = 40                        # per-branch attempt budget


class NotApplicableError(Exception):
    """Raised when a scalar score isn't natural; triggers JUDGE_MODE fallback."""


class InvalidSolution(Exception):
    """The solution returned an index that violates the locality / shape contract."""


# ----------------------------------------------------------------------------
# One matching round (NOTIFY + GRANT), parameterized by the solution's rules.
# ----------------------------------------------------------------------------
def _feasible_graph(rng: np.random.Generator, d: float) -> list[np.ndarray]:
    """Binomial D-out feasible graph: each sender draws D_u ~ Bin(N, d/N) and
    picks D_u distinct receivers uniformly. Returns adjacency per sender."""
    degs = np.minimum(rng.binomial(N, d / N, size=N), N)
    return [rng.choice(N, size=int(k), replace=False) for k in degs]


def _check_thin(idx, degree: int) -> np.ndarray:
    idx = np.asarray(idx)
    if idx.ndim != 1 or idx.dtype.kind not in "iu":
        raise InvalidSolution(f"thin must return a 1-D int array, got {idx!r}")
    if idx.size > degree:
        raise InvalidSolution(f"thin returned {idx.size} indices for degree {degree}")
    if idx.size and (idx.min() < 0 or idx.max() >= degree):
        raise InvalidSolution(f"thin index out of range [0,{degree})")
    if np.unique(idx).size != idx.size:
        raise InvalidSolution("thin returned duplicate indices")
    return idx


def _round_fraction(thin, select, adj: list[np.ndarray], rng: np.random.Generator) -> float:
    # Stage 0 NOTIFY: each sender thins its own feasible neighbors.
    kept = [a[_check_thin(thin(a.size, rng), a.size)] for a in adj]

    # Stage 1 REQ: receivers report their intention-graph degree.
    nonempty = [k for k in kept if k.size]
    if not nonempty:
        return 0.0
    deg_receiver = np.bincount(np.concatenate(nonempty), minlength=N)

    # Stage 2 GRANT: each sender with >=1 neighbor grants to one of them.
    granted = np.zeros(N, dtype=bool)
    for k in kept:
        if k.size:
            j = select(deg_receiver[k], rng)
            if not (isinstance(j, (int, np.integer)) and 0 <= int(j) < k.size):
                raise InvalidSolution(f"select returned index {j!r} for {k.size} neighbors")
            granted[k[int(j)]] = True

    # Matching size = number of receivers that got >=1 grant.
    return int(granted.sum()) / N


def evaluate() -> dict:
    t0 = time.perf_counter()
    try:
        sys.path.insert(0, ".")
        # Force a fresh import so repeated runs in one process pick up edits.
        for m in ("solution",):
            sys.modules.pop(m, None)
        from solution import select, thin
    except Exception as e:  # noqa: BLE001
        return {"score": 0.0, "stage": "error", "error": f"import: {str(e)[:280]}",
                "time": time.perf_counter() - t0}

    per_density: dict[str, float] = {}
    all_fractions: list[float] = []
    try:
        for di, d in enumerate(DENSITIES):
            fr = np.empty(REPS, dtype=np.float64)
            for rep in range(REPS):
                child = np.random.SeedSequence([MASTER_SEED, di, rep])
                g_seed, a_seed = child.spawn(2)
                adj = _feasible_graph(np.random.default_rng(g_seed), d)
                fr[rep] = _round_fraction(thin, select, adj, np.random.default_rng(a_seed))
            per_density[str(d)] = float(fr.mean())
            all_fractions.extend(fr.tolist())
    except InvalidSolution as e:
        return {"score": 0.0, "stage": "invalid", "error": str(e)[:280],
                "time": time.perf_counter() - t0}
    except Exception as e:  # noqa: BLE001
        return {"score": 0.0, "stage": "error", "error": str(e)[:280],
                "time": time.perf_counter() - t0}

    arr = np.asarray(all_fractions)
    mean = float(arr.mean())
    sem = float(arr.std(ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else 0.0
    return {
        "score": mean,
        "stage": "full",
        "mean_fraction": mean,
        "ci95_halfwidth": 1.96 * sem,
        "per_density": per_density,
        "time": time.perf_counter() - t0,
    }


# ----------------------------------------------------------------------------
# LLM-as-judge fallback. Inert for this problem (we have a real scalar), kept for
# template compatibility. Calls `claude -p` with the rubric in prompts/judge.md.
# ----------------------------------------------------------------------------
def judge_mode() -> dict:
    rubric = Path("prompts/judge.md").read_text()
    solution = Path("solution.py").read_text()
    prompt = (
        f"{rubric}\n\n---\n\nSolution to evaluate:\n\n"
        f"```python\n{solution}\n```\n\n"
        "Return exactly one JSON line: "
        '{"score": float in [0, 1], "reason": short string}'
    )
    out = subprocess.run(
        ["claude", "-p", "--model", "haiku"],
        input=prompt, capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"judge failed: {out.stderr[:500]}")
    for line in reversed(out.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError("judge returned no JSON line")


def main():
    if os.environ.get("JUDGE_MODE", "").lower() in ("true", "1", "yes"):
        print(json.dumps({**judge_mode(), "stage": "judge"}))
        return
    print(json.dumps(evaluate()))


if __name__ == "__main__":
    main()
