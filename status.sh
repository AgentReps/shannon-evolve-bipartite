#!/usr/bin/env bash
# shannon-evolve: live inspection.
#
# Prints one line per branch: best score, attempts, last update, and a
# truncated tail of the most recent log entry. Safe to run at any time;
# does not interact with the running agents.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${SHANNON_LOG_DIR:-}" ]]; then
    DEFAULT_SHARED="${REPO_ROOT}/../shannon-evolve-runs/shared-log"
    if [[ -d "$DEFAULT_SHARED" ]]; then
        SHANNON_LOG_DIR="$DEFAULT_SHARED"
    else
        SHANNON_LOG_DIR="${REPO_ROOT}/log"
    fi
fi

if [[ ! -d "$SHANNON_LOG_DIR" ]]; then
    echo "no log dir at $SHANNON_LOG_DIR" >&2
    exit 1
fi

printf "%-10s %-8s %-8s %-22s  %s\n" "branch" "best" "attempts" "last-update (UTC)" "last-rationale"
printf "%-10s %-8s %-8s %-22s  %s\n" "------" "----" "--------" "-----------------" "--------------"

shopt -s nullglob
for state in "$SHANNON_LOG_DIR"/state-*.json; do
    branch="$(basename "$state" .json | sed 's/^state-//')"
    best="$(python3 -c "import json,sys; print(f\"{json.load(open(sys.argv[1]))['best']:.4f}\")" "$state" 2>/dev/null || echo "?")"
    attempts="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['attempts'])" "$state" 2>/dev/null || echo "?")"
    log="$SHANNON_LOG_DIR/branch-$branch.md"
    if [[ -f "$log" ]]; then
        # Most recent timestamp line and rationale line.
        ts="$(grep -E '^## attempt' "$log" | tail -1 | sed -E 's/.*— //')"
        rat="$(grep -E '^- rationale:' "$log" | tail -1 | sed -E 's/^- rationale: //' | cut -c1-60)"
    else
        ts="—"
        rat="(no log)"
    fi
    printf "%-10s %-8s %-8s %-22s  %s\n" "$branch" "$best" "$attempts" "$ts" "$rat"
done

# Frontier (if digest has run).
if [[ -f "$SHANNON_LOG_DIR/frontier.md" ]]; then
    echo
    echo "--- frontier ---"
    cat "$SHANNON_LOG_DIR/frontier.md"
fi
