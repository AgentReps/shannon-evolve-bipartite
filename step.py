"""step.py — one iteration of the shannon-evolve loop.

The agent calls this *after* editing solution.py. It runs the evaluator,
appends a structured entry to the per-branch log, files a one-liner
under by-approach/, tracks branch-local best, copies the elite into
the shared elites/ directory on improvement, and creates a commit.

Designed so the agent's only job is to *propose* — bookkeeping is
mechanical and uniform across branches. Delete this file when the
agent can reliably do all of the above without scaffolding.

Usage:
    python step.py "<rationale>" --approach <kebab-case-name>

Reads BRANCH_ID (default "solo") and SHANNON_LOG_DIR (default "./log")
from the environment. Prints one JSON status line to stdout.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_APPROACH_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_evaluator() -> dict:
    out = subprocess.run(
        [sys.executable, "evaluate.py"],
        capture_output=True, text=True, timeout=300,
    )
    if out.returncode != 0:
        return {"score": 0.0, "stage": "error", "error": out.stderr.strip()[:300]}
    for line in reversed(out.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"score": 0.0, "stage": "error", "error": "no JSON from evaluator"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rationale", help="2-3 line rationale for this attempt")
    ap.add_argument("--approach", required=True, help="kebab-case algorithmic family")
    args = ap.parse_args()

    if not _APPROACH_RE.match(args.approach):
        print(json.dumps({
            "error": f"--approach must match [a-z0-9][a-z0-9-]{{0,63}}, got {args.approach!r}",
        }), file=sys.stderr)
        return 2

    branch = os.environ.get("BRANCH_ID", "solo")
    if not re.match(r"^[a-zA-Z0-9_-]{1,32}$", branch):
        print(json.dumps({"error": f"invalid BRANCH_ID {branch!r}"}), file=sys.stderr)
        return 2
    log_dir = Path(os.environ.get("SHANNON_LOG_DIR", "./log"))
    (log_dir / "by-approach").mkdir(parents=True, exist_ok=True)
    (log_dir / "elites").mkdir(parents=True, exist_ok=True)

    result = _run_evaluator()
    score = float(result.get("score", 0.0))
    stage = result.get("stage", "unknown")
    extra = {k: v for k, v in result.items() if k not in ("score", "stage")}
    timestamp = _utc_now_iso()

    state_path = log_dir / f"state-{branch}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"best": 0.0, "attempts": 0}
    state["attempts"] += 1
    is_new_best = score > state["best"]
    if is_new_best:
        state["best"] = score
    state_path.write_text(json.dumps(state))

    decision = "KEEP (new best)" if is_new_best else "no improvement"
    # Human-readable log shows only problem-specific scalars (mean_fraction,
    # ci95_halfwidth, error) — not timing, which clutters the line and is
    # rarely diagnostic.
    log_extras_keys = ("mean_fraction", "ci95_halfwidth", "error")
    extras_pretty = ", ".join(
        f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in extra.items()
        if k in log_extras_keys and isinstance(v, (int, float, str))
    )
    rationale_clean = args.rationale.strip()
    entry = (
        f"\n## attempt {state['attempts']} — {timestamp}\n"
        f"- score: {score:.4f} ({stage})"
        + (f" — {extras_pretty}" if extras_pretty else "")
        + "\n"
        f"- approach: {args.approach}\n"
        f"- rationale: {rationale_clean}\n"
        f"- decision: {decision}\n"
    )
    with (log_dir / f"branch-{branch}.md").open("a") as f:
        f.write(entry)

    summary = rationale_clean.splitlines()[0][:80] if rationale_clean else "(no rationale)"
    with (log_dir / "by-approach" / f"{args.approach}.md").open("a") as f:
        f.write(f"- branch {branch} attempt {state['attempts']}: score {score:.4f} — {summary}\n")

    committed = False
    if is_new_best and score > 0.0:
        shutil.copy("solution.py", log_dir / "elites" / f"branch-{branch}.py")
        # Best-effort commit. If we're not in a git repo or hooks fail, the
        # agent still gets a clean status line back.
        subprocess.run(["git", "add", "solution.py"], capture_output=True)
        commit = subprocess.run(
            ["git", "commit", "-m", f"branch {branch}: {args.approach}, score {score:.4f}"],
            capture_output=True, text=True,
        )
        committed = commit.returncode == 0

    status = {
        "branch": branch,
        "attempt": state["attempts"],
        "score": score,
        "stage": stage,
        "branch_best": state["best"],
        "new_best": is_new_best,
        "committed": committed,
        **{k: v for k, v in extra.items() if isinstance(v, (int, float, str, bool))},
    }
    print(json.dumps(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
