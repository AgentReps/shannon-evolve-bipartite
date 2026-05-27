# log/ — shannon-evolve evolutionary record

This directory is the "program database" in AlphaEvolve terms. It's
markdown and JSON rather than SQLite because the agent reads markdown
natively and git already gives us versioning, diff, and audit.

## Files

- **`branch-{1..4}.md`** (or `branch-solo.md`) — per-branch chronological
  log. Appended by `step.py`, one entry per iteration.

- **`by-approach/<approach>.md`** — MAP-Elites in markdown. One short
  line per attempt, grouped by algorithmic family. Branches consult these
  before proposing, to avoid duplicating each other's work. The set of
  approach files is discovered by the agents, not predefined.

- **`elites/branch-N.py`** — the current best `solution.py` for each
  branch. Written by `step.py` on a new branch best. The *only*
  sanctioned channel for cross-branch code sharing; sibling worktrees
  are off-limits.

- **`state-N.json`** — per-branch best score and attempt counter.
  Maintained by `step.py`; read by `status.sh` and (transitively) by
  the branch itself for stop decisions.

- **`frontier.md`** — curated by `digest.sh`. The current best-per-niche.
  Overwritten each digest cycle.

- **`next-direction.md`** — written by `digest.sh`. Short hints addressed
  to each branch. Overwritten each digest cycle. Branches treat these as
  suggestions, not commands.

- **`digest.md`** — rolling human-readable summary. Appended each digest
  cycle so you can skim it Monday morning without reading 500 attempts.

## Diversity invariant

The MAP-Elites bins are `by-approach/*.md`. As long as every branch
files each attempt under one approach key, and the digest step
rebalances based on coverage, the population stays diverse. If two
branches start filing under the same approach key, the digest should
redirect one of them in `next-direction.md`.

## Cross-pollination

`elites/branch-N.py` lets a stuck branch seed from a sibling without
violating the worktree-isolation rule. CLAUDE.md instructs branches
to *adapt* — not copy — elites into their own strategy bias.
