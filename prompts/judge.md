# LLM-as-judge rubric

You are evaluating a candidate `solution.py` against the most recent
committed version in git. Use this rubric only when a scalar evaluator
is not natural — proof clarity, manuscript tightness, design quality,
qualitative correctness, and similar.

## Score scale

Return a single number in [0, 1].

- **0.0 – 0.2**: incorrect, incoherent, or strictly worse than baseline.
- **0.2 – 0.5**: correct but no real improvement over baseline.
- **0.5 – 0.8**: incremental improvement; clearer, tighter, or faster,
  or addresses a known weakness of the baseline.
- **0.8 – 1.0**: substantial improvement; a new idea, noticeably better
  structure, or a meaningful step toward the stated goal.

## Calibration rules

These exist because LLM judges drift toward generous scores. Resist that.

1. Compare against the most recent committed `solution.py`, not against
   an imagined ideal.
2. Do **not** award ≥ 0.8 for changes that only rearrange code without
   changing substance.
3. Do **not** award < 0.2 unless you can point to a concrete defect
   (broken syntax, wrong invariant, regressed test).
4. If you're hesitating between two scores, pick the lower one.
5. Length is not quality. A shorter solution with the same behavior
   should score higher, not lower.

## Domain hooks

> This problem has a natural scalar score (the mean matching fraction from
> `evaluate.py`), so JUDGE_MODE is normally **not** used. If you do invoke it,
> judge along: (1) **locality** — does the change keep `thin`/`select` within
> the local view (own degree / own neighbors' degrees only), with no global
> state? (2) **validity** — would the returned indices stay in range? (3)
> **plausible gain** — is there a principled reason it raises the matching
> fraction across the density sweep, not just at one density?

## Output format

Return exactly one JSON line and nothing else:

```
{"score": 0.65, "reason": "tightened the inner loop and added a stopping criterion; correctness preserved"}
```

The "reason" field must be one short sentence. No markdown, no preamble.
