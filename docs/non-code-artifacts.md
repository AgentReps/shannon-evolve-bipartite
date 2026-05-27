# Evolving non-code artifacts

shannon-evolve's defaults assume `solution.py` is Python and `evaluate.py`
produces a scalar. Four other patterns work with minor edits.

## Multi-file codebase

Replace `solution.py` with a `solution/` directory. Tell Claude in CLAUDE.md
which files contain `EVOLVE-BLOCK` markers (you can have many). `evaluate.py`
runs your build/test pipeline and reports a scalar — pytest exit codes,
benchmark wall-time, accuracy on a held-out set, whatever you would
measure manually.

Tip: keep the EVOLVE-BLOCK regions small. The model edits more reliably
when it can hold one block fully in mind.

## LaTeX manuscript

`solution.tex` instead of `solution.py`. EVOLVE-BLOCK markers go in
LaTeX comments:

```latex
% EVOLVE-BLOCK-START
... the proof step, paragraph, or section being refined ...
% EVOLVE-BLOCK-END
```

`evaluate.py` runs `pdflatex` (or `latexmk`), parses the log for errors,
optionally runs `chktex`, and falls back to `JUDGE_MODE=true` for
substance. Typical rubric dimensions: correctness, clarity, brevity.

## Design / specification document

`solution.md`. Same EVOLVE-BLOCK convention in HTML comments:

```html
<!-- EVOLVE-BLOCK-START -->
...
<!-- EVOLVE-BLOCK-END -->
```

Almost always `JUDGE_MODE=true` — there's rarely a natural scalar for
design quality. In the rubric, name 2–3 dimensions explicitly (e.g.,
specificity, testability, alignment with constraints) so the judge
doesn't degrade into vague approval.

## Mathematical construction

`solution.py` returns the construction; `evaluate.py` checks invariants
and reports one of:

(a) a scalar gap from optimal (e.g., kissing number lower bound);
(b) a binary feasible/infeasible flag plus a tiebreaker like construction
    size or symmetry count;
(c) a deferral to `JUDGE_MODE` for cases where verification is easy but
    ranking among feasible solutions is qualitative.

For (b), `evaluate.py` can return `0.0` for infeasible and a small
positive scalar for feasible-and-improving. Branches will quickly learn
to file infeasible attempts under a `failed-invariant` approach so they
stop trying the same dead end.

## What stays the same

In every case, five things don't change:

1. `run.sh`, `digest.sh`, and `status.sh` are artifact-agnostic.
2. `step.py` still handles bookkeeping — it appends per-branch logs,
   files by-approach summaries, copies elites, and commits on
   improvement. Adopt it as-is; it doesn't care what's in
   `solution.<ext>` as long as it lives in the cwd and `evaluate.py`
   prints a JSON line with `score`.
3. The diversity rules in CLAUDE.md still apply (one approach per
   filing, branches read each other's by-approach summaries and
   elites).
4. The cascade idea in `evaluate.py` still earns its keep — a cheap
   filter before an expensive one is the single biggest knob.
5. Git history is your audit trail. `step.py` commits on new bests;
   you can bisect or revert any time.
