"""Scalar evaluator for the LABS placeholder.

Prints a single JSON line to stdout. Reads `solution.py` from the cwd.

Usage:
    python3 evaluate.py                   # scalar mode (default)
    JUDGE_MODE=true python3 evaluate.py   # LLM-as-judge fallback

Design notes:
- For *cheap* evaluators (like this one — computing a merit factor is
  O(N^2) at N=60), a single stage is fine. When you adopt the template
  for an expensive evaluator, add a quick/medium/full cascade: have
  `evaluate()` short-circuit on a cheap proxy and only run the full
  scorer when the proxy clears a threshold.
- `_run_solve` invokes solve() in a fresh subprocess so the agent can't
  accidentally leak state across attempts (caches, RNG, module globals).
- Shape verification rejects malformed returns *before* scoring. This is
  the template's anti-gaming hook: extend it per problem with sanity
  checks the evaluator can run cheaply (canary inputs, invariants, etc.).
"""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

# ----------------------------------------------------------------------------
# Constants the agent reads. TUNE_ME per problem.
# ----------------------------------------------------------------------------
N = 60                  # sequence length; must match solution.py
TARGET_SCORE = 1.0      # MF >= 10 caps the score; effectively never stop early
MAX_ATTEMPTS = 30       # per-branch attempt budget
MF_SCALE = 10.0         # score = min(merit_factor / MF_SCALE, 1.0)


class NotApplicableError(Exception):
    """Raised when a scalar score isn't natural; triggers JUDGE_MODE fallback."""


# ----------------------------------------------------------------------------
# Run solve() in a subprocess and return whatever it returned.
# ----------------------------------------------------------------------------
def _run_solve(timeout: float = 60.0) -> tuple[list[int], float]:
    """Run solve() in a fresh subprocess. Return (sequence, wall_seconds)."""
    code = (
        "import sys, json, time\n"
        "sys.path.insert(0, '.')\n"
        "from solution import solve\n"
        "t = time.perf_counter(); v = solve(); dt = time.perf_counter() - t\n"
        "print(json.dumps({'value': list(v), 'time': dt}))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(f"solve failed: {out.stderr[:500]}")
    # Take the last JSON-looking line so prints inside solve() don't break us.
    for line in reversed(out.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            return data["value"], data["time"]
    raise RuntimeError("solve produced no JSON line")


def _verify_shape(seq) -> str | None:
    """Return None if seq is a valid ±1 sequence of length N, else an error string."""
    if not isinstance(seq, list):
        return f"expected list, got {type(seq).__name__}"
    if len(seq) != N:
        return f"expected length {N}, got {len(seq)}"
    bad = [x for x in seq if x not in (-1, 1)]
    if bad:
        return f"non-±1 values present (first offender: {bad[0]!r})"
    return None


def _merit_factor(seq: list[int]) -> float:
    n = len(seq)
    total = 0
    for k in range(1, n):
        c = 0
        for i in range(n - k):
            c += seq[i] * seq[i + k]
        total += c * c
    if total == 0:
        return float("inf")
    return n * n / (2.0 * total)


def _score(mf: float) -> float:
    if not math.isfinite(mf):
        return 1.0
    return max(0.0, min(1.0, mf / MF_SCALE))


def evaluate() -> dict:
    """Single-stage evaluation. Returns a dict suitable for JSON dump."""
    t0 = time.perf_counter()
    try:
        seq, solve_time = _run_solve(timeout=60.0)
    except Exception as e:  # noqa: BLE001
        return {"score": 0.0, "stage": "error", "error": str(e)[:300],
                "time": time.perf_counter() - t0}

    shape_err = _verify_shape(seq)
    if shape_err is not None:
        return {"score": 0.0, "stage": "invalid", "error": shape_err,
                "time": time.perf_counter() - t0}

    mf = _merit_factor(seq)
    return {
        "score": _score(mf),
        "stage": "full",
        "merit_factor": mf,
        "time": time.perf_counter() - t0,
        "solve_time": solve_time,
    }


# ----------------------------------------------------------------------------
# LLM-as-judge fallback. Use when no natural scalar exists. Calls `claude -p`
# with the rubric in prompts/judge.md.
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
