# shannon-evolve

You are one branch (or in solo mode, the only worker) of an evolutionary
search over `solution.py`. This file is your only spec. Follow it
carefully and persistently.

## Problem

**Distributed bipartite matching.** `N = 144` senders and `N` receivers
form a bipartite *feasible* graph (each sender is willing to match with a
set of receivers). In a single round of four synchronous, message-passing
stages — `NOTIFY → REQ → GRANT → ACCEPT` — we want to match as many
sender–receiver pairs as possible. The catch is the **information
constraint**: no node sees the whole graph. A sender knows only its own
neighbors and, after the REQ replies, those neighbors' degrees; a receiver
knows only the grants it got. The matching size equals the number of
receivers that receive at least one grant.

**The objective** is to maximize the **expected matching fraction**
(matched pairs / N). `evaluate.py` estimates it by Monte Carlo over a
*fixed* robustness sweep — Binomial D-out graphs at mean degree
`d ∈ {2,3,4,5,6,8,10}`, ~200 reps each, with common random numbers (a
fixed seed) so every attempt is scored on identical graphs and the search
is monotone. The reported `score` is the mean matching fraction in `[0,1]`
(no rescaling). The full network/model parameters are fixed in
`evaluate.py` and must not be changed — they are the problem definition.

**What you evolve** (in `solution.py`, between the EVOLVE-BLOCK markers)
are two purely-local decision rules and their constants:

- `thin(degree, rng)` — NOTIFY-stage thinning. Sees only this sender's own
  feasible out-degree; returns the indices of neighbors to notify.
- `select(neighbor_degrees, rng)` — GRANT-stage selection. Sees only the
  intention-graph degrees of this sender's own neighbors; returns the index
  of the one to grant to.

**No information leakage** is enforced structurally: these signatures never
expose the global graph or any other node's data, and `evaluate.py`
validates the returned indices (out-of-range → `score = 0`, stage
`invalid`). Any creative rule is fair game *as long as it stays within this
local view*.

**Reference points** (mean fraction over the sweep): DB(0) uniform ≈ **0.63**
(the shipped baseline); DB(−∞) greedy is best when sparse but collapses when
dense; **2CGS** (`max(2)` thinning + greedy) ≈ **0.73**, robust and
tuning-free — the bar to beat. Known solution paths (DB(α), greedy, 2CGS)
are written out as copy-ready seeds in the comments of `solution.py`.

## Mode

- **Parallel mode** — `run.sh` launched you. `BRANCH_ID` is `1..N`.
  Your strategy bias is on that line of `prompts/strategies.txt`.
  `SHANNON_LOG_DIR` points to a directory shared across worktrees so
  you can see what your siblings have done.
- **Solo mode** — `BRANCH_ID` is unset (or `"solo"`). You're the only
  worker. There are no sibling branches, no `frontier.md`, no
  `next-direction.md`. Skim the rest of this file with that in mind:
  the "diversity rules" and `elites/` cross-pollination sections do
  not apply. Just propose, run `step.py`, and iterate.

## Loop

On each iteration, do exactly the following:

1. **Identify yourself.** In parallel mode, read `BRANCH_ID` from the
   environment and your strategy bias from line `BRANCH_ID` of
   `prompts/strategies.txt`. In solo mode this step is a no-op.

2. **Read state.**
   - If `${SHANNON_LOG_DIR}/state-${BRANCH_ID}.json` exists, read it.
     It has `{"best": <score>, "attempts": <int>}`. If
     `attempts >= MAX_ATTEMPTS`, stop now — this is a resumed run that
     has already exhausted its budget.
   - Read the tail of your own log at
     `${SHANNON_LOG_DIR}/branch-${BRANCH_ID}.md` (or
     `./log/branch-solo.md` in solo mode).
   - In parallel mode: skim `${SHANNON_LOG_DIR}/by-approach/*.md` to
     see what every branch has already tried, and check
     `${SHANNON_LOG_DIR}/elites/` for sibling best solutions.
   - If `${SHANNON_LOG_DIR}/next-direction.md` contains a note addressed
     to your branch, treat it as a hint, not a command.
   - Read the current `solution.py` in your worktree. Note the
     `# EVOLVE-BLOCK-START` / `# EVOLVE-BLOCK-END` markers.

3. **Propose.** Edit only the region between those markers. Keep
   `solution.py` runnable at every step.

4. **Evaluate and log.** Run:

   ```
   python3 step.py "<2-3 line rationale>" --approach <kebab-case-name>
   ```

   (Use whichever of `python` / `python3` exists on the system; the
   helper uses `sys.executable` internally so it doesn't matter which
   you invoke.)

   `step.py` runs `evaluate.py`, appends a structured entry to your
   branch log, files a one-liner under `by-approach/`, copies your
   solution into `elites/branch-${BRANCH_ID}.py` on a new branch best,
   commits on improvement, and prints a JSON status line. Read that
   status line — you'll need `attempt`, `score`, and `new_best` for
   the next iteration.

   If `evaluate.py` raises `NotApplicableError` (no natural scalar for
   the problem), re-run with `JUDGE_MODE=true python3 evaluate.py`
   before calling `step.py`.

5. **Stop** if any of:
   - `score >= TARGET_SCORE` (defined in `evaluate.py`)
   - `attempt >= MAX_ATTEMPTS` (defined in `evaluate.py`)
   - a `STOP` file exists at the repo root

   Otherwise loop back to step 2.

## Diversity rules (parallel mode only)

You are competing with three sibling branches. Convergence is the
failure mode. Before each proposal, ask yourself: *has another branch
already tried this?* Read `by-approach/*.md` to check. If yes,
deliberately pick a different point in your strategy family.

If you find yourself repeatedly proposing variants of the same idea,
run `step.py` once with the rationale `"exhausted local neighborhood"`
and then try a different sub-family within your bias.

### Seeding from sibling elites

When your local family stalls, you may read
`${SHANNON_LOG_DIR}/elites/branch-${K}.py` for any sibling `K` and
*adapt* their construction to your strategy bias. Do not blind-copy —
the point of running four branches is that they explore differently.
A useful pattern: take a sibling elite as a starting point and apply
your strategy as a mutation operator on top of it.

You may **not** read or write to other branches' worktrees directly;
the `elites/` directory in the shared log is the only sanctioned
cross-branch channel.

## Scoring fallback

`evaluate.py` raises `NotApplicableError` if the problem doesn't admit
a natural scalar (proof refinement, manuscript editing, design docs).
In that case, `JUDGE_MODE=true python3 evaluate.py` invokes the
LLM-as-judge fallback against `prompts/judge.md`.

## What not to do

- Do not edit files outside `solution.py` and the shared log directory.
  `step.py` handles all log writes — you should not be opening
  `branch-N.md` or `by-approach/*.md` for writing yourself.
- Do not modify the `EVOLVE-BLOCK` markers or the surrounding
  scaffolding in `solution.py`.
- Do not modify `N`, the evaluator, the scoring function, or
  `TARGET_SCORE` / `MAX_ATTEMPTS` to make your score look better.
  These are the problem definition.
- Do not call out to the network unless `solution.py` already does.
- Do not stop early because you "don't see an obvious improvement."
  Log a null attempt with `step.py` and try a different direction.
  The point of the budget is to outlast local plateaus.
- Do not read or write to other branches' worktrees. Read their log
  *summaries* and `elites/` only.
