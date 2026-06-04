# About

**Distributed bipartite matching.** `N = 144` senders and `N` receivers form a
bipartite *feasible* graph: each sender is willing to match with some subset of
receivers. In a single round we want to match as many sender–receiver pairs as
possible — a matching uses each sender and each receiver at most once.

**The catch: locality.** No node sees the whole graph. The matching is built in
four synchronous message-passing stages:

```
NOTIFY  sender → receivers : "I'm willing to match"  (send to a THINNED subset)
REQ     receiver → senders : ACK, piggybacking the receiver's degree
GRANT   sender → ONE receiver : pick one neighbor via the SELECTION rule
ACCEPT  receiver → ONE sender : if it got ≥1 grant, accept one
```

So a sender knows only its own neighbors and their degrees; a receiver knows
only the grants it received. The matching size equals the number of receivers
that got at least one grant.

**Objective.** Maximize the **mean matching fraction** (matched pairs / N),
averaged by Monte Carlo over a fixed robustness sweep of Binomial D-out graphs
at mean degrees `d ∈ {2,3,4,5,6,8,10}`. Score lies in `[0,1]`; higher is better.

**What we tune.** Two purely-local decision rules:

- **`thin(degree, rng)`** — NOTIFY thinning. Subsample which neighbors to notify.
- **`select(neighbor_degrees, rng)`** — GRANT selection. Pick which neighbor to
  grant to, given its neighbors' intention-graph degrees.

**Reference points.** Uniform DB(0) ≈ **0.63**; greedy DB(−∞) wins when sparse
but collapses when dense; **2CGS** (cap at 2 neighbors + greedy) ≈ **0.73**,
robust and tuning-free — the bar to beat.

This is the problem from `description/` (paper: *Degree-Biased Matching for
Datacenter Transport*), distilled so it can be iterated on directly via
`solution.py` and `step.py` in this root folder.
