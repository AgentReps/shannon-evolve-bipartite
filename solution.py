"""Distributed bipartite matching — a one-round, local-information algorithm.

The problem (see CLAUDE.md and description/MODEL.md): N senders and N receivers
form a bipartite "feasible" graph. In a single round of four synchronous stages
(NOTIFY -> REQ -> GRANT -> ACCEPT) we want to match as many sender-receiver pairs
as possible. The catch is the *information constraint*: no node sees the global
graph. Each node acts only on its own neighborhood plus what a couple of message
round-trips reveal. The matching size equals the number of receivers that get at
least one grant.

An algorithm is fully specified by two pluggable, *purely local* decision rules,
which are the only things you evolve here:

  thin(degree, rng)             -- NOTIFY-stage thinning
  select(neighbor_degrees, rng) -- GRANT-stage selection

NO INFORMATION LEAKAGE — enforced by these signatures. Neither function is ever
handed the global graph, the other senders' choices, or any node's data but the
caller's own. It physically cannot leak:

  * `thin` sees ONLY this sender's own feasible out-degree (an int). At NOTIFY no
    receiver degrees are known yet, and a sender's neighbors are exchangeable
    (uniform-random receivers), so the out-degree is the only locality-respecting
    information. Return the indices (into range(degree)) of the neighbors to keep.

  * `select` sees ONLY the intention-graph degrees of THIS sender's own (post-thin)
    neighbors — exactly the degrees that arrive piggybacked on the REQ replies.
    Return the index (0..len-1) of the one neighbor to grant to.

`evaluate.py` validates the returned indices (in range, no duplicates); anything
out of bounds is scored as `invalid` (score 0). Constants chosen and *fixed for
the network* (N=144, Binomial degrees, mean degree d in {2,3,4,5,6,8,10}) live
inside the EVOLVE-BLOCK as well.

Reference points (mean matching fraction, averaged over the density sweep):
  - DB(0)  uniform, no thinning  : ~0.63   (this baseline)
  - DB(-inf) greedy, no thinning : best when sparse, degrades when dense
  - 2CGS = max(2) + greedy       : ~0.73   (robust, tuning-free — the bar to beat)

Everything outside the EVOLVE-BLOCK is scaffolding; do not modify it.
"""
import numpy as np

# EVOLVE-BLOCK-START
# Tunable constants, fixed for the network. ALPHA is the DB(alpha) exponent
# (<= 0; 0 = uniform, -inf = greedy). K caps the notified out-degree
# (a large value = no thinning; K=2 gives the 2CGS "max(2)" rule).
ALPHA = 0.0
K = 10**9


def thin(degree, rng):
    """NOTIFY stage. `degree`: this sender's feasible out-degree (int >= 0).
    Return a 1-D int array of indices in [0, degree) — the neighbors to notify.
    Baseline (no thinning): keep them all."""
    if degree <= K:
        return np.arange(degree)
    return rng.choice(degree, size=K, replace=False)


def select(neighbor_degrees, rng):
    """GRANT stage. `neighbor_degrees`: 1-D int array, the intention-graph degree
    of each notified neighbor (REQ piggyback). Return the index (0..len-1) of the
    one neighbor to grant to. Baseline DB(0): pick one uniformly at random."""
    return int(rng.integers(len(neighbor_degrees)))
# EVOLVE-BLOCK-END


# ---------------------------------------------------------------------------
# Seed solutions (the known solution paths). Copy a body into the EVOLVE-BLOCK
# above and adapt it — all of these respect the locality contract.
#
# DB(-inf) greedy selection — grant to a least-contended (min-degree) neighbor:
#     def select(neighbor_degrees, rng):
#         m = neighbor_degrees.min()
#         cand = np.nonzero(neighbor_degrees == m)[0]   # ties broken uniformly
#         return int(rng.choice(cand))
#
# DB(alpha) selection — weight ~ deg**ALPHA, in log-space (max-shifted) so it
# degrades smoothly toward greedy as ALPHA -> -inf (notified receivers always
# have degree >= 1, so the log is safe):
#     def select(neighbor_degrees, rng):
#         log_w = ALPHA * np.log(neighbor_degrees.astype(np.float64))
#         log_w -= log_w.max()
#         w = np.exp(log_w)
#         return int(rng.choice(len(neighbor_degrees), p=w / w.sum()))
#     # reference optimum grows with density: greedy when sparse,
#     # ALPHA ~ -1.3 to -1.4 around d=8.
#
# 2CGS — max(2) thinning + greedy selection (robust, no tuning): set K = 2 and
# use the DB(-inf) greedy select() above.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    # Local sanity check (evaluate.py is authoritative). Estimate the mean
    # matching fraction on a few small Binomial instances, exercising the same
    # NOTIFY/GRANT path the evaluator uses.
    N, reps = 144, 40
    fr = []
    for d in (2, 4, 8):
        rng = np.random.default_rng(d)
        tot = 0.0
        for _ in range(reps):
            adj = [rng.choice(N, size=min(int(rng.binomial(N, d / N)), N), replace=False)
                   for _ in range(N)]
            kept = [a[thin(a.size, rng)] for a in adj]
            deg = np.zeros(N, dtype=np.int64)
            for k in kept:
                np.add.at(deg, k, 1)
            granted = np.zeros(N, dtype=bool)
            for k in kept:
                if k.size:
                    granted[k[select(deg[k], rng)]] = True
            tot += granted.sum() / N
        mean = tot / reps
        fr.append(mean)
        print(f"d={d:2d}  mean_fraction={mean:.4f}")
    print(f"sweep_mean={np.mean(fr):.4f}")
