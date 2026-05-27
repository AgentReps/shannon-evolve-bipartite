# RATIONALE

> Why now is a reasonable time to invest in agentic evolutionary search
> for information-theoretic and algorithmic problems.

## The capability threshold has crossed in narrow regimes

For most of the past decade, *AI for science* meant supervised learning on
existing datasets. The interesting recent shift runs in the opposite
direction: using a frozen, pre-trained model as a **proposal distribution**
in a classical search loop, where a verifier — not the model — decides what
counts as progress. AlphaEvolve's improvement on Strassen's 4×5 matrix
multiplication algorithm (the first such improvement in more than half a
century), and FunSearch's new lower bound for cap-sets, are existence proofs
that this transduction can produce non-trivial novelty in narrow algorithmic
regimes. The frontier is not general mathematical discovery yet, but the
frontier is moving, and a careful reader of the early literature can see
where the next moves are likely to come from.

## The interesting machine is the verifier, not the model

A point worth being explicit about: the bottleneck in this kind of work
is almost never the LLM. It is the evaluator. A faster, cheaper, more
discriminative `evaluate.py` — one that rejects bad candidates in
milliseconds rather than minutes, or that distinguishes 99.9% of correct
solutions from 100% — is worth far more than swapping in a smarter model.
The model is a generator with priors; the verifier is the part of the
system that has opinions about ground truth.

This is fortunate, because information theory and statistical signal
processing have always lived close to good verifiers. Bit-error rate,
capacity, BP fixed points, AMP state evolution, decoding complexity, MSE
on a fixed test ensemble, mutual information estimates, dispersion-style
finite-blocklength bounds — these are honest scalars with well-understood
statistics. The same field that produced source-channel separation and
provable random-coding arguments is in an unusually strong position to
set up problems where LLM-driven search has a fair shot. Domains without
good verifiers (philosophy, parts of qualitative social science) will
struggle here for the same reason they struggle in any other branch of
computational discovery.

## Scaffolding thins as models improve, and that is the design principle

Earlier evolutionary-coding systems — FunSearch (2023), AlphaEvolve
(2025), OpenEvolve, CodeEvolve — added scaffolding to compensate for what
the LLM could not yet do on its own: maintain population diversity
(MAP-Elites), reflect on past attempts (elaborate prompt-sampler policies),
explore at different scales (Flash/Pro ensembles), and decide when to stop
(controller logic). Each of those compensations is on a trajectory toward
redundancy.

The methodological corollary, which `shannon-evolve` takes seriously, is
that **what one builds today should be designed to collapse**. Don't
re-implement AlphaEvolve's four-component architecture in Python; let the
components be markdown files, shell scripts, and one Claude session. When
the next model release makes one of those components obsolete, the right
response is deletion, not feature addition. A system whose lines-of-code
count grows monotonically as models improve is being built in the wrong
direction.

## The compute regime has democratized

The first wave of LLM-driven search papers came from labs with thousands
of GPUs. The development of the past year is that the same technique now
runs overnight on a single workstation. The orchestration cost has
collapsed to a few shell scripts and a markdown spec. A faculty member
with a curiosity, a problem with an honest verifier, and one weekend can
now run experiments that would have required a small research group two
years ago.

This matters for academic research specifically. Most labs cannot
out-compute the frontier labs, but most labs *can* out-curate them on
domain-specific problems. The researcher who knows which constructions are
interesting, which gaps in the literature are open, and which metrics are
not gameable, has the advantage. Compute is no longer the moat; taste is.

## Continuity with classical search

For someone whose research already involves Monte Carlo simulations, MCMC,
simulated annealing, genetic algorithms, or branch-and-bound, none of
this is really new. It is the same family of algorithms — propose,
evaluate, retain, repeat — with a much smarter proposal operator. The
intellectual move from a genetic algorithm with hand-coded mutation
operators to one with an LLM-driven proposal step is small in principle
and large in practice. The methodology one already trusts for setting up
search problems (define the space carefully, instrument the verifier
honestly, beware of overfitting the evaluator) transfers directly. The
new ingredient is that the proposal step now reads the problem statement.

## What this is, and what it isn't

It is: a way to convert **compute time on verifiers** into improved
algorithmic constructions, when the search space is too large for
exhaustion and too structured for random search. The right targets are
problems where candidates are easy to write down in code or formal
language, success is easy to measure, and the hypothesis space has
structure a human can recognize but not fully enumerate.

It is not: a replacement for proof, for theory, or for the part of
research that decides which questions are worth asking. The system can
search a well-defined space; it cannot tell whether the space was the
wrong one. Framing remains a human responsibility, and an automated
search can make this worse, not better, by producing a steady drizzle
of marginal improvements on a question that should have been replaced.

## Why now, concretely

Three things have lined up for the first time:

1. **Capability** — the current generation of agentic models can read a
   spec, edit a file, run a test, and reflect on the result, well enough
   that the loop closes without constant supervision.

2. **Tooling** — unattended agent execution
   (`--dangerously-skip-permissions` inside a containerized sandbox,
   Cowork for desktop tasks, MCP-based tool access) is a one-line command
   rather than a research project.

3. **Cost** — the marginal experiment is dollars-per-hour rather than
   GPU-hours-per-result. Running ten exploratory loops in a week is
   feasible for an individual researcher.

None of these will reverse. The question is whether to start now, when
the obvious low-hanging fruit is still being picked, or in two years,
when the technique is normalized and the easy problems are behind us.

## What to expect

Most experiments will find nothing new. A few will rediscover something
the literature already has, which is useful as a validation of the setup.
A small number — and this is the case worth running for — will find
something genuinely better than the best known result for a specific
narrow problem. The cost of the failed runs is small enough that the
expected value of the successful ones can dominate, provided one chooses
problems with honest verifiers and avoids re-running the same search
under different decorations.

The right disposition is patient and skeptical. Treat each apparent
discovery as a hypothesis to be verified by traditional means before
publication. Treat each failed search as data about what the search
space looks like, not as a refutation of the method. And keep the
scaffolding thin enough that it can be deleted when the next model
release makes it unnecessary.

## Closing

The interesting feature of this moment is not that machines can now do
research. They cannot, except in narrow algorithmic regimes with honest
verifiers. The interesting feature is that, for the first time, a single
researcher with a good question can run search experiments at a scale
that used to require a team — and that the same researcher's domain
expertise is exactly what determines whether the experiments produce
anything worth reading. The leverage on taste is high. The leverage on
infrastructure is low. That is an unusual configuration, and probably
a temporary one.
