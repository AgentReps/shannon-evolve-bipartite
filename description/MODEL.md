# Distributed Bipartite Matching — Model Blueprint

> **The problem in one sentence.** Two equal-sized groups of nodes — *senders* and *receivers*
> — form a bipartite graph; we want to match as many sender–receiver pairs as possible, but
> each node sees only its own neighborhood and may exchange just a few rounds of messages before
> committing.
>
> This document explains that problem, states precisely how a solution is scored, and hands off
> a candidate implementation to build from.

---

## 1. The problem

- **The graph.** A bipartite graph on $N$ senders and $N$ receivers. An **edge** from a sender
  to a receiver means *that sender is willing to be matched with that receiver* — a statement of
  intent, not yet a committed pairing. A node's **degree** is its number of edges.
- **A matching.** A set of edges that share no endpoint: every sender and every receiver is used
  at most once. In one round a sender can commit to, and a receiver can accept, at most one
  partner.
- **The goal.** Make the matching as large as possible. More matched pairs mean more senders and
  receivers successfully exchange information this round.
- **The twist — information constraints.** The matching must be built in a **distributed** way:
  no node has a global view of the graph. Each node knows only its own neighbors plus whatever
  it learns from a few rounds of message exchange (about two round-trips). This locality is what
  separates the problem from classical maximum bipartite matching, where a central planner sees
  everything.
- **The lever.** Senders break symmetry with a one-parameter **degree-biased** rule, DB($\alpha$):
  when a sender must pick which neighbor to commit to, it favors receivers by degree, with an
  exponent $\alpha$ controlling the bias. The design question is *which* $\alpha$ — and how much
  to **thin** the graph first — produces the largest matchings.

The rest of this document fixes the scoring (§2), the random graph the problem is posed over
(§3), the message protocol that enforces the information constraint (§4), the family of
algorithms (§5), and a candidate implementation (§6).

---

## 2. The performance measure

This is the single number a solution is judged by — be precise about it.

**Definition.** Run the protocol once on a graph and count the matched pairs. Divide by $N$:
that is the **matching fraction** — the fraction of senders that ended up matched. It lies
between 0 and 1, and higher is better. Because the graph is random, the score is the **matching
fraction averaged over many independently sampled graphs** (the *mean matching fraction*).

In short: *score = average fraction of senders matched, over many random instances.* A simulator
estimates it by Monte Carlo — sample a graph, run the protocol, record matched pairs / N, and
average over many repetitions.

**What good looks like (reference points).** On the standard setup ($N=144$, mean degree
around 8):

- **Uniform selection** (no bias, no thinning) matches about **0.63** of senders. This is the
  natural baseline; for any reasonable density it sits near $1-1/e \approx 0.63$.
- **2CGS** (cap each sender at 2 neighbors, then greedily prefer the least-contended receiver)
  reaches about **0.73** — and does so without tuning, across a range of densities.
- The **best degree-bias depends on density**: in sparse graphs the most aggressive bias
  (greedy) wins; as graphs get denser the optimal bias relaxes back toward uniform. So there is
  no single best $\alpha$ — it grows with mean degree.

**Secondary axis — communication cost.** Every round also has a price: the number of messages
exchanged (NOTIFY + REQ + GRANT + ACCEPT). Thinning the graph (§5.1) reduces this volume, which
is why a smaller intention graph that matches nearly as well can be the better design.

---

## 3. How problem instances are generated

The matching fraction is averaged over a random graph model, so a framework must reproduce that
model exactly.

**The D-out random bipartite graph.** Each sender independently draws an out-degree (how many
receivers it is willing to match with) from a chosen distribution, then picks that many distinct
receivers **uniformly at random**, independently of every other sender. The mean out-degree,
written $d$, is the density knob.

**Three degree distributions to support** (all with the same mean $d$, so the framework
parameterizes by mean degree):

| Distribution | Definition | Notes |
|---|---|---|
| **Deterministic** | every sender has exactly $d$ neighbors | a clean $d$-out graph |
| **Binomial** | each sender–receiver pair present with probability $d/N$ | the bipartite Erdős–Rényi graph |
| **Poisson** | out-degree is Poisson with mean $d$ | the large-$N$ limit; convenient for analysis |

A useful fact for intuition: under this model a given receiver's degree is roughly Poisson with
mean $d$ — i.e. popularity is unevenly spread, which is exactly why *which* receiver a sender
grants to matters.

**Two graphs: feasible vs. intention.** The model distinguishes:

- the **feasible graph** — *all* sender-to-receiver pairs with outstanding intent, what exists at
  the start of a round; and
- the **intention graph** — the sparser subgraph left after each sender **thins** (subsamples)
  its feasible neighbors at the NOTIFY stage, so it doesn't message everyone.

The matching is computed on the intention graph. Thinning is a first-class design knob (§5.1):
it cuts the number of messages exchanged and reshapes the degree distribution the matching sees.

---

## 4. The distributed protocol

This is where the information constraint becomes concrete. Every algorithm in the family runs a
**single round** of four synchronous stages, taking about two round-trips. Each node acts only on
local information; the message exchange is what lets senders and receivers coordinate without a
global view.

```
Stage 0  NOTIFY   sender -> receivers : "I am willing to match with you"
                  (DB algorithms send to only a THINNED subset of feasible receivers)
Stage 1  REQ      receiver -> senders  : "request" ACK
                  (DB algorithms PIGGYBACK the receiver's degree deg(v) here)
Stage 2  GRANT    sender -> ONE receiver : pick one neighbor via the SELECTION rule
Stage 3  ACCEPT   receiver -> ONE sender : if it got >=1 grant, accept one (uniform);
                  both endpoints mark themselves matched
```

**Locality — what each node knows:**

- A **sender**, after NOTIFY+REQ, knows its set of neighbors **and the degree of each neighbor**
  (degrees arrive piggybacked in the REQ replies). This is exactly the information the DB($\alpha$)
  rule needs — equivalently, the sender knows its two-hop neighborhood and nothing more.
- A **receiver** knows only the set of grants it received in Stage 2; it has no other view of the
  graph.

**Where randomness enters:** (a) thinning at NOTIFY, (b) the sender's choice at GRANT, and
(c) the receiver's uniform pick among multiple grants at ACCEPT.

**Why selection matters — the collision example.** If senders grant **uniformly at random**,
several senders can pile onto the same popular (high-degree) receiver while low-degree receivers
go unmatched — a *collision* that wastes a potential match. On a small $6\times6$ example,
uniform selection yields only 3 matches; biasing grants toward low-degree receivers, plus light
thinning, yields all 6.

**Counting the matches.** Because each sender grants once and each receiver accepts at most one
grant, the **matching size is simply the number of receivers that received at least one grant** —
the ACCEPT stage only decides *which* sender pairs with each matched receiver, not *how many*
match. A framework may therefore tally the matching right after GRANT.

---

## 5. The algorithm family (the knobs)

Every algorithm is fully specified by two pluggable choices:

```
algorithm = (thinning rule at NOTIFY)  x  (selection rule at GRANT)
```

### 5.1 Thinning (NOTIFY-stage sparsification)

Thinning subsamples each sender's feasible neighbors **before** matching, shaping the
intention-graph degrees and capping how many messages are sent.

| Thinning rule | Definition | Effect |
|---|---|---|
| **none** | keep all feasible edges | intention graph = feasible graph |
| **`max(k)`** | a sender with more than $k$ feasible edges keeps exactly $k$ of them, chosen at random; senders with $\le k$ keep all | hard cap on out-degree, giving a $k$-out graph. **`max(2)` is the recommended sweet spot** |
| **`Bern(q)`** | keep each edge independently with probability $q$ | thins the mean degree by a factor $q$; useful to dilute deterministic-degree graphs |

### 5.2 DB($\alpha$) selection (GRANT-stage rule)

When a sender grants, it picks a neighbor with **probability proportional to that receiver's
degree raised to the power $\alpha$**. The exponent $\alpha$ tunes the bias:

| $\alpha$ | Behavior | Intuition |
|---|---|---|
| $\alpha > 0$ | favors **high**-degree receivers | causes collisions, so it is poor; **excluded** from study |
| $\alpha = 0$ | **uniform** random over neighbors | the baseline |
| $\alpha < 0$ | favors **low**-degree receivers | spreads grants out, fewer collisions |
| $\alpha = -\infty$ | **greedy**: grant only to the **minimum-degree** neighbor(s), ties broken at random | maximally avoids contended receivers |

Key facts for the framework:

- Only $\alpha \le 0$ is of interest.
- The optimal $\alpha$ is **non-decreasing in mean degree**: greedy ($-\infty$) wins in
  **sparse** graphs; as graphs get **dense**, low-degree receivers become over-contended
  bottlenecks and the optimum drifts toward 0. As reference: mean degree 2 favors full greedy,
  while mean degree 8 favors a moderate bias (roughly $\alpha \approx -1.3$ to $-1.4$).

> **Implementation tip.** Treat $\alpha = -\infty$ as a special case rather than literally raising
> a degree to the $-\infty$ power: find the minimum neighbor degree and pick uniformly among the
> neighbors that achieve it.

### 5.3 Variant matrix (named algorithms)

| Name | Thinning | Selection | Notes |
|---|---|---|---|
| **DB(0)** | none | uniform | the uniform-random baseline |
| **DB($-\infty$)** | none | greedy | best in sparse graphs, degrades when dense |
| **DB($\alpha$*)** | none | tuned $\alpha$ | per-density optimum |
| **2CGS** | `max(2)` | greedy | "2-choice with greedy selection"; **recommended** — no tuning, robust across densities |

---

## 6. Candidate implementation (starting point)

A language-neutral blueprint to build from: data structures, pseudocode for each stage, and a
module sketch. This is a starting point, not a prescription.

### 6.1 Suggested data structures

```
Graph (bipartite):
  N                      : int
  adj_sender[u]          : set/list of receiver ids        # feasible or intention edges
  adj_receiver[v]        : set/list of sender ids           # reverse index
  deg_receiver[v]        : int = |adj_receiver[v]|          # cached after NOTIFY/REQ
  # Dense alt: N x N boolean/sparse adjacency matrix

NodeState (per round):
  sender[u].neighbors    : list of receiver ids (post-thinning = intention neighbors)
  sender[u].grant        : receiver id or NONE
  receiver[v].grants_in  : list of sender ids
  receiver[v].accept     : sender id or NONE
  matched_pairs          : list of (u, v)

Message types: NOTIFY(u->v), REQ(v->u, deg=deg(v)), GRANT(u->v), ACCEPT(v->u)
```

### 6.2 Pseudocode

**(a) D-out random bipartite graph generator**

```
function generate_D_out_graph(N, degree_sampler, rng):
    G = empty_bipartite(N)
    for u in 0..N-1:
        D_u = min(degree_sampler(rng), N)          # deterministic / Bin(N,d/N) / Poisson
        neighbors = rng.sample(V, k=D_u)            # uniform, without replacement
        for v in neighbors: G.add_edge(u, v)
    return G
# degree_sampler examples:
#   deterministic(d):      returns d
#   binomial(N, d/N):      returns Binomial(N, d/N) draw
#   poisson(d):            returns Poisson(d) draw
```

**(b) Thinning** *(max(k) / Bern(q))*

```
function thin_max_k(G, k, rng):           # cap each sender's out-degree at k
    for u in U:
        if deg(u) > k:
            keep = rng.sample(G.adj_sender[u], k)
            G.adj_sender[u] = keep
    rebuild_receiver_index_and_degrees(G)
    return G

function thin_bernoulli(G, q, rng):       # keep each edge w.p. q
    for (u, v) in G.edges:
        if rng.uniform() > q: G.remove_edge(u, v)
    rebuild_receiver_index_and_degrees(G)
    return G
```

**(c) One matching round — the 4 stages, parameterized by a selection strategy**

```
function matching_round(G_feasible, thinning, select, rng):
    # Stage 0 NOTIFY: apply thinning -> intention graph
    G = thinning(copy(G_feasible), rng)
    compute_receiver_degrees(G)                 # deg(v) for all v

    # Stage 1 REQ: receivers reply with their degree (modeled as: degrees now known to senders)

    # Stage 2 GRANT: each sender with >=1 neighbor picks exactly one
    for u in U where deg(u) > 0:
        v = select(u, G.adj_sender[u], deg_of=G.deg_receiver, rng=rng)
        receiver[v].grants_in.append(u)

    # Stage 3 ACCEPT: each receiver with >=1 grant accepts one uniformly
    matched = []
    for v in V where receiver[v].grants_in not empty:
        u = rng.choice(receiver[v].grants_in)
        matched.append((u, v))

    return matched                              # matching size = len(matched)
```

**(d) Selection strategies (the DB family)** — a single interface, swappable:

```
# interface: select(u, neighbors, deg_of, rng) -> chosen receiver v

function select_DB_alpha(u, neighbors, deg_of, rng, alpha):
    weights = [ deg_of[v] ** alpha for v in neighbors ]      # alpha <= 0
    return rng.choice(neighbors, p = normalize(weights))

function select_DB_uniform(u, neighbors, deg_of, rng):        # alpha = 0
    return rng.choice(neighbors)

function select_DB_greedy(u, neighbors, deg_of, rng):         # alpha = -inf
    m = min(deg_of[v] for v in neighbors)
    candidates = [v for v in neighbors if deg_of[v] == m]
    return rng.choice(candidates)                            # uniform tie-break
```

With these, the named algorithms compose directly:

```
DB0     = matching_round(G, thinning=none,            select=select_DB_uniform)
DBminf  = matching_round(G, thinning=none,            select=select_DB_greedy)
TwoCGS  = matching_round(G, thinning=thin_max_k(k=2),  select=select_DB_greedy)
```

### 6.3 Module / API sketch

```
graph_model      generate_D_out_graph(N, degree_sampler); degree samplers
thinning         none, max_k(k), bernoulli(q)                 # NOTIFY-stage rules
selection        db_alpha(alpha), db_uniform, db_greedy       # GRANT-stage strategy iface
matching_round   run the 4 stages -> matched pairs / matching size
metrics          matching_fraction; communication_cost (message count)
experiment_runner  sweep over {N, mean_degree, distribution, alpha, thinning};
                   Monte-Carlo average (e.g. 1000 reps); collect mean + quartiles
```
