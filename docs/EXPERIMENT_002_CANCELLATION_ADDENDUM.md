# Experiment 002 — Cancellation Addendum

```text
STATUS   CANCELLED BEFORE EXECUTION
REASON   the motivating architectural distinction did not survive
         adversarial specification
DATE     Phase I closure
RUNS     zero
```

`EXPERIMENT_002_PREREGISTRATION_v1.0.md` is preserved **byte-untouched**.
Nothing in it has been edited, softened or retro-fitted. This addendum
is a separate document precisely so the preregistration remains readable
as it was written, before the result was known.

---

## What was cancelled

A 180-execution comparison (30 tasks × k=3 × 2 arms) of fixed routing
against adaptive strategy selection, with a preregistered null
definition (<10 percentage points on functional success), a 2× cost
ceiling, and a frozen task set.

## Why

Not because the result was disliked. **The experiment was never run.**

During specification of a cheaper precursor (R0, a deterministic
reversal test), the treatment/control distinction was found to collapse
under the experiment's own fairness requirements:

```text
information parity   the treatment may not know anything absent from
                     the control's persisted record

computation parity   the control may run the same invalidation and
                     selective-recomputation algorithm over that record

therefore            same information + same algorithms
                     -> same stale set, same recomputations
```

The residue was whether the dependency graph was held in memory or
rebuilt from disk — caching, which the required machine-speed-independent
metric is designed not to see.

It proved impossible to write a single specification clause constraining
the control without deliberately crippling it. See
`R0_PRESSURE_TEST.md`.

## The reduction, in full

Each strengthening of the null removed another candidate distinction:

```text
delayed commitment              -> a strong router can gather before routing
strategy ensemble               -> a strong router can persist alternatives
retained-alternative recovery   -> a strong router can persist rationale + evidence
dependency-aware recovery       -> a strong router can persist a dependency graph
selective revalidation          -> a strong router can run the same algorithm
remaining difference            -> incremental maintenance vs reconstruction
                                -> a generic incremental-computation trade-off
```

Experiment 002 bundled at least four of these into a single comparison.
Neither outcome would have been interpretable: a positive result could
not have been attributed to any mechanism, and a null could not have
distinguished "adaptive execution does not help" from "the tasks
contained no reversal, so the only differentiating mechanism was never
exercised."

## A defect found in the successor, worth recording

R0's own primary metric — recomputations between reversal detection and
valid recommitment — measured **only the recovery window** and therefore
systematically favoured the treatment:

```text
incremental    20 + 20 + 10  -> reports 10   (total 50)
reconstruct     0 +  0 + 35  -> reports 35   (total 35)
```

The treatment "wins" 3.5× while costing 43% more overall. This bias was
written into the same document as the section on preventing rigged
results, and was caught in external review. It is recorded because the
pattern — an instrument carrying the bias it was built to detect — has
now occurred twice in this project.

## Why this is a good methodological outcome, stated carefully

180 expensive runs were not performed, disliked, and then rationalised
away. The experiment was found **before execution** to be incapable of
discriminating the architectures.

That claim should not be inflated. Nothing was empirically falsified. A
specification exercise established that there was no treatment left to
test — which is cheaper than an experiment and answers a narrower
question.

## What would have to be true to revive it

Experiment 002 becomes meaningful only if Phase II admits a mechanism
under the admission rule in `CONTINUUM_OPEN_PROBLEMS.md`. At that point
it would need re-preregistration from scratch: a single manipulated
mechanism, a control that is v1 plus the smallest reasonable
enhancement, a primary metric accounting for **total** rather than
post-reversal cost, and power derived from an observed pilot variance
rather than the invented `n=30`, `k=3`, `2×` figures.

This document does not amend the preregistration. It records that it
will not be executed as written.
