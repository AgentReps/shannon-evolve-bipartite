#!/usr/bin/env bash
# shannon-evolve: spawn N parallel branches as git worktrees.
# Each branch reads its strategy bias from prompts/strategies.txt
# and runs an unattended claude session that follows CLAUDE.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNS_DIR="${SHANNON_RUNS_DIR:-${REPO_ROOT}/../shannon-evolve-runs}"
N_BRANCHES="${SHANNON_N_BRANCHES:-4}"

# Read strategies (one per line, blank lines and # comments allowed).
mapfile -t STRATEGIES < <(grep -vE '^\s*(#|$)' "${REPO_ROOT}/prompts/strategies.txt")

if [[ "${#STRATEGIES[@]}" -lt "$N_BRANCHES" ]]; then
    echo "prompts/strategies.txt has ${#STRATEGIES[@]} non-empty lines, need $N_BRANCHES" >&2
    exit 1
fi

mkdir -p "$RUNS_DIR"
cd "$REPO_ROOT"

# Ensure we're in a git repo (worktrees require it).
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "shannon-evolve must be a git repository. Run: git init && git add -A && git commit -m init" >&2
    exit 1
fi

# Shared log directory lives outside any worktree so all branches can read
# and append to it without git-branch isolation getting in the way.
SHARED_LOG="$RUNS_DIR/shared-log"
if [[ ! -d "$SHARED_LOG" ]]; then
    mkdir -p "$SHARED_LOG/by-approach"
    # Seed with the repo's initial log templates (README, empty frontier, etc.)
    cp -R "$REPO_ROOT/log/." "$SHARED_LOG/"
fi
export SHANNON_LOG_DIR="$SHARED_LOG"

# Clean up any stale STOP file from a previous run.
rm -f "${REPO_ROOT}/STOP"

PIDS=()
for i in $(seq 1 "$N_BRANCHES"); do
    branch_name="branch-$i"
    worktree="$RUNS_DIR/$branch_name"
    strategy="${STRATEGIES[$((i-1))]}"

    if [[ ! -d "$worktree" ]]; then
        # Create the branch and worktree. If the branch already exists from a
        # previous run, attach to it instead of failing.
        if git show-ref --quiet --verify "refs/heads/$branch_name"; then
            git worktree add "$worktree" "$branch_name"
        else
            git worktree add -b "$branch_name" "$worktree"
        fi
    fi

    (
        cd "$worktree"
        export BRANCH_ID="$i"
        export SHANNON_LOG_DIR  # inherited from parent
        echo "[branch $i] worktree=$worktree strategy='$strategy' log=$SHANNON_LOG_DIR"
        claude --dangerously-skip-permissions \
            "Follow CLAUDE.md. Your BRANCH_ID is $i. Your strategy bias is: $strategy" \
            > "branch-$i.out" 2>&1
        echo "[branch $i] finished"
    ) &
    PIDS+=("$!")
done

# If the user hits Ctrl-C, kill all branches.
trap 'echo "stopping branches..."; touch "${REPO_ROOT}/STOP"; kill "${PIDS[@]}" 2>/dev/null || true' INT TERM

wait
echo "all branches finished."
