# shannon-evolve

A minimal, agentic template for evolutionary algorithm discovery with Claude
at the center. Inspired by AlphaEvolve (Novikov et al., 2025) but stripped to
what the current generation of agents actually needs.

## Philosophy

The four-component AlphaEvolve scaffolding (program database, prompt sampler,
LLM ensemble, evaluator pool) was a workaround for limitations that no longer
fully apply. shannon-evolve keeps the conceptual decomposition but collapses
each component onto the simplest substrate that still works:

| AlphaEvolve component | shannon-evolve substrate                       |
|-----------------------|------------------------------------------------|
| Program database      | `log/by-approach/*.md` + `log/elites/*.py` + git history |
| Prompt sampler        | Claude's own context (the agent reads the log) |
| LLM ensemble          | N parallel `claude` sessions in git worktrees  |
| Evaluator pool        | `evaluate.py` (cascade if expensive)           |
| Bookkeeping           | `step.py` — append log, manage elites, commit  |

`step.py` is the one place the protocol is mechanical. Everything else
is the model reading CLAUDE.md.

## Placeholder problem

The shipped `solution.py` targets the **low-autocorrelation binary
sequence** (LABS) problem at `N = 60`: find `b ∈ {-1, +1}^60` maximizing
the merit factor `F(b) = N² / (2 Σ c_k(b)²)`. This is a genuine open
combinatorial-search problem in signal design — random sequences score
about 0.1, structured constructions (Legendre/Jacobi) reach about 0.6,
and the best known via search is ~0.85. There is no closed form for the
optimum, so the four branches actually have something to do.

Replace `solution.py` and the "Problem" section of `CLAUDE.md` for your
own problem.

## Quick start

```bash
git clone <this-repo> my-problem
cd my-problem

# Customize for your problem:
#   - solution.py             : the artifact being evolved
#   - evaluate.py             : scalar scorer (+ cascade if expensive)
#   - prompts/strategies.txt  : 4 lines, one algorithmic bias per branch
#   - CLAUDE.md               : edit the "Problem" section

./run.sh                 # spawns 4 parallel branches as git worktrees
./status.sh              # live snapshot of best / attempts per branch
```

In another terminal, run the digest periodically:

```bash
./digest.sh              # one cycle
# or via cron / launchd / `at`; while-sleep loops are fragile.
```

Stop a run any time by touching `STOP` at the repo root.

## What you customize per problem

1. **`solution.py`** — the artifact being evolved. Mutable region between
   `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END` markers.
2. **`evaluate.py`** — the scalar scorer. Constants at the top (`N`,
   `TARGET_SCORE`, `MAX_ATTEMPTS`, scaling) are marked `TUNE_ME`. Add
   a `quick`/`medium`/`full` cascade if your evaluator is expensive.
3. **`prompts/strategies.txt`** — four lines, one algorithmic bias per
   branch. The single most important file for diversity.
4. **`CLAUDE.md`** — typically only the "Problem" section needs editing.

## Solo mode

For small problems you don't need the parallel rig. Skip `run.sh` and just:

```bash
claude "Follow CLAUDE.md."
```

in the repo root. With `BRANCH_ID` unset, the agent treats itself as
the only worker: `step.py` writes to `./log/branch-solo.md`, and the
diversity / elites machinery is dormant.

## Non-code artifacts

The default assumes Python with a scalar evaluator. To evolve a LaTeX
manuscript, a multi-file codebase, a design document, or a mathematical
construction instead, see `docs/non-code-artifacts.md`.

## LLM-as-judge fallback

When a scalar evaluator isn't natural — proof clarity, manuscript tightness,
design quality — set `JUDGE_MODE=true` and `evaluate.py` will call
`claude -p` with `prompts/judge.md` as the rubric. See that file for guidance
on writing rubrics that don't degrade into "yes, this is great".

## Layout

```
shannon-evolve/
├── README.md                      # this file
├── CLAUDE.md                      # the spec each branch reads
├── solution.py                    # artifact being evolved (LABS placeholder)
├── evaluate.py                    # scalar scorer
├── step.py                        # bookkeeping helper the agent calls per iteration
├── run.sh                         # spawns N parallel worktrees
├── digest.sh                      # cross-pollination step
├── status.sh                      # live inspection
├── .gitignore
├── docs/
│   └── non-code-artifacts.md
├── prompts/
│   ├── strategies.txt             # 4 lines, one bias per branch
│   └── judge.md                   # LLM-as-judge rubric
└── log/
    ├── README.md
    ├── branch-{1..4}.md           # appended by step.py
    ├── by-approach/               # MAP-Elites in markdown
    ├── elites/                    # current-best solution.py per branch
    ├── state-*.json               # per-branch best / attempt counter
    ├── frontier.md                # curated by digest
    ├── digest.md                  # rolling human-readable summary
    └── next-direction.md          # written by digest, read by branches
```
