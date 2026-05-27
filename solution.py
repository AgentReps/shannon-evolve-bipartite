"""Placeholder solution: low-autocorrelation binary sequences (LABS).

The goal is to construct a sequence b ∈ {-1, +1}^N that maximizes the
merit factor

        F(b) = N^2 / (2 * sum_{k=1}^{N-1} c_k(b)^2)

where c_k(b) = sum_{i=0}^{N-1-k} b_i * b_{i+k} is the aperiodic
autocorrelation at lag k. Higher F is better.

Reference points (rough, for N around 60):
  - random ±1 sequences: F ≈ 1
  - Legendre/Jacobi-style constructions: F up to ~6
  - best known via search (Mertens, Borwein–Choi–Jedwab, ...): F ≈ 8–9

There is no closed form for the optimum; the problem is the canonical
"hard combinatorial search" benchmark in signal design.

Replace this file for your own problem. The required structure is:

- A `solve(...)` entry point (signature may change per problem).
- A mutable region marked by `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`.
- Everything outside the EVOLVE-BLOCK is scaffolding that branches must not
  modify.
"""
import random

# Fixed problem size. Branches should not change this.
N = 60


def solve() -> list[int]:
    """Return a sequence of length N with entries in {-1, +1}."""
    # EVOLVE-BLOCK-START
    # Baseline: a single random ±1 sequence. Replace with a better method.
    random.seed(0)
    return [random.choice([-1, 1]) for _ in range(N)]
    # EVOLVE-BLOCK-END


if __name__ == "__main__":
    seq = solve()
    # Local sanity print; evaluate.py is authoritative.
    n = len(seq)
    total = 0
    for k in range(1, n):
        c = sum(seq[i] * seq[i + k] for i in range(n - k))
        total += c * c
    mf = n * n / (2 * total) if total > 0 else float("inf")
    print(f"N={n} merit_factor={mf:.4f}")
