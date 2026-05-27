#!/usr/bin/env bash
# shannon-evolve: cross-pollination step.
#
# Reads all per-branch and per-approach logs, identifies under-explored
# regions, and updates log/frontier.md and log/next-direction.md. Designed
# to be run on a cron or in a manual loop.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use the shared log directory if it exists (set up by run.sh), otherwise
# fall back to the repo-local log/ (single-branch mode).
if [[ -z "${SHANNON_LOG_DIR:-}" ]]; then
    DEFAULT_SHARED="${REPO_ROOT}/../shannon-evolve-runs/shared-log"
    if [[ -d "$DEFAULT_SHARED" ]]; then
        export SHANNON_LOG_DIR="$DEFAULT_SHARED"
    else
        export SHANNON_LOG_DIR="${REPO_ROOT}/log"
    fi
fi
cd "$SHANNON_LOG_DIR"

PROMPT=$(cat <<'EOF'
You are the digest step of an evolutionary search. You are running in the
shared log directory; all paths below are relative to your current
working directory.

Four branches are running in parallel under git worktrees. Each branch
has its own algorithmic bias and writes to its own log here. Your job is
to read those logs, summarize what the population has learned, and nudge
the branches toward unexplored ground.

Do exactly this, in order:

1. Read every file under ./by-approach/ and every ./branch-*.md.
   Skim, do not deeply parse — these can be long. Also check
   ./elites/ to see which branches currently have an elite
   solution checked in (the *contents* of the elites are not
   your concern; only that they exist).

2. Update ./frontier.md so it lists, for each approach seen so far,
   the single best attempt: (approach, best score, branch number,
   one-line description). Overwrite the file each digest.

3. Update ./next-direction.md with one short note per branch (four
   notes total, addressed by branch number). Each note should suggest
   a direction that branch has not yet tried but that complements its
   strategy bias. Where appropriate, suggest a specific sibling's
   elite the branch might consider seeding from. Keep each note
   under 50 words. Overwrite the file each digest.

4. Append a one-paragraph entry to ./digest.md timestamped with the
   current date in ISO-8601 form. Summarize what the population has
   learned this cycle, what's plateauing, and what's still missing.

Constraints:
- Do not edit any other files.
- Do not commit anything.
- If the logs are mostly empty (early in a run), say so and stop.
EOF
)

# Use a non-interactive claude session so this is safe to schedule.
claude -p --dangerously-skip-permissions "$PROMPT"
