# Experiment 002 — Pre-registration v1.0

**Fixed harness policy vs adaptive strategy ensemble.**

Written before the experiment can be run, and before Experiment 001 has
an independent verdict. That ordering is the point: everything below —
especially the definition of a null result — is committed to now, while
nobody knows how it turns out.

Authority: frozen baseline §26 (Experiment 002), §31 (hypotheses H2, H4),
§32–33 (baselines and evaluation dimensions).

---

## 0. A dependency correction

`ROADMAP.md` listed Experiment 002 as step 2 and model integration as
step 3. That ordering is wrong, and this document is where it was
caught.

Baseline §26 measures functional success, verification success, cost,
latency, tool calls and rollback rate. Every one of those is an
**execution** measure. They cannot be produced by a deterministic
fixture; they require real model calls doing real work.

Corrected ordering:

```text
pre-register 002        <- this document, now
model integration       <- roadmap step 3, must come first
run 002                 <- only then
```

Pre-registration genuinely can happen now, and should: its value depends
entirely on preceding the data.

---

## 1. The question

> Can multidimensional adaptive strategy selection outperform fixed
> harness policy on real tasks?

Two arms, one model:

```text
ARM A (control)     Escapement v1 style fixed routing policy
ARM B (treatment)   Continuum adaptive strategy ensemble with
                    delayed commitment and EVI-driven information
                    gathering
```

Testing hypotheses H2 (EVI-based information gathering) and H4 (strategy
ensembles) from baseline §31.

---

## 2. What is held identical

If any of these differs between arms, the experiment measures that
difference instead of the one we care about:

- **the model** — same provider, same model id, same temperature, same
  seed where the provider supports one;
- **the task set** — identical, in identical order;
- **tool access** — the same tools, with the same permissions;
- **budget** — the same token and wall-clock ceiling per task;
- **the grader** — one grader, blind to which arm produced the output.

The single permitted difference is the decision layer.

---

## 3. Grading must be objective

**LLM-as-judge is excluded as the primary metric.** Judges have
documented verbosity and structure biases, and Arm B's output is
systematically more structured than Arm A's — so a judge would favour
the treatment for reasons unrelated to quality, and the confound could
never be fully argued away.

Primary grading is therefore mechanical:

```text
functional success      pre-written tests pass / fail
verification success    the run's own checks pass and are executed
rollback rate           changes reverted or abandoned
```

Every task must ship with its passing criterion written **before** the
task is attempted by either arm.

---

## 4. The primary metric, declared in advance

**Primary:** functional success rate (tasks whose pre-written tests
pass).

**Secondary, reported always, never substituted for the primary:** cost
in tokens, wall-clock latency, tool calls, human interventions, question
count, outcome variance across repeats.

This is declared now because Arm B has a structural trade-off: it
deliberates, so it will almost certainly cost more tokens and more time.
If the primary metric were chosen after seeing results, one could always
find an axis on which the treatment won and report that one. Naming it
in advance removes that freedom.

**Cost ceiling.** A functional-success improvement bought at more than
**2× the control's token cost** is recorded as a *qualified* result, not
a win. Escapement's own positioning is a low-token harness; a version
that wins only by spending unboundedly is not the claim being made.

---

## 5. What counts as no difference

Committed before any data exists.

Let `n` be the number of tasks, `p_A` and `p_B` the functional success
rates.

```text
NULL RESULT        |p_B - p_A| < 10 percentage points
                   -> adaptive strategy selection did not measurably
                      outperform fixed routing on this task set

TREATMENT WINS     p_B - p_A >= 10 points AND cost_B <= 2 x cost_A

QUALIFIED WIN      p_B - p_A >= 10 points AND cost_B > 2 x cost_A

CONTROL WINS       p_A - p_B >= 10 points
```

**Minimum n = 30.** Below that the confidence interval on a proportion
is wide enough that a 10-point gap is not distinguishable from noise,
and any verdict would be storytelling. If fewer than 30 tasks can be
afforded, the honest report is *"underpowered, no verdict"* — not a
verdict with a caveat attached.

**Reliability, not just capability.** Each task is run `k = 3` times per
arm. Report both:

```text
pass@k    at least one of k runs succeeded   (capability)
pass^k    all k runs succeeded               (reliability)
```

A treatment that raises `pass@k` while lowering `pass^k` has become more
capable and less reliable. That is a real and reportable outcome, not a
win.

---

## 6. What would falsify the thesis

Stated plainly so it cannot be quietly reframed later:

1. **Null result at n ≥ 30** — adaptive selection does not beat fixed
   routing on functional success. H4 is not supported on this task set.
2. **`pass^k` falls** while `pass@k` rises — the ensemble adds variance
   rather than reliability.
3. **Information gathering does not pay** — Arm B's EVI-selected actions
   do not correlate with improved outcomes, i.e. the runs where it
   gathered more did no better. That falsifies H2 independently of H4.
4. **Cost blowup without gain** — more than 2× cost at a null functional
   result.

Any of these is publishable within the project and must be recorded in
the decision journal rather than triggering a redesign-and-retry.

**The retry rule:** the task set, the primary metric, and the thresholds
above are frozen by this document. If the experiment is re-run with a
changed task set or a changed metric, that is a **new experiment with a
new pre-registration**, reported alongside the first, not a correction of
it. Silent iteration until the result inverts is the specific failure
this section exists to prevent.

---

## 7. Task-set construction

- **Fixed before running**, listed by id in the experiment README.
- **Not selected to favour either arm.** In particular, not filtered to
  tasks where v1 is known to route poorly.
- **Spread across the workload classes** baseline §26 and Experiment 003
  name: micro-bugfix, feature, refactor, analysis. Reported per class,
  because an aggregate can hide that the treatment helps on one class
  and hurts on another — which would be a more interesting finding than
  the aggregate.
- Sourced from real repository work where possible, since fixtures are
  where the adaptive arm's advantage would be easiest to accidentally
  manufacture.

---

## 8. Confounds to control explicitly

| Confound | Control |
|---|---|
| Arm B sees tasks second and benefits from cache | Randomise arm order per task; report cache state |
| Grader knows which arm produced output | Blind the grader to arm |
| Arm B's extra tokens buy quality by volume alone | Cost ceiling (§4); report tokens per task |
| Task set implicitly chosen to suit the treatment | Fix the set in advance; publish the list |
| A single lucky seed | k = 3 repeats, report `pass^k` |
| Author scores their own system | Independent scoring, as with Experiment 001 |

---

## 9. What this experiment does not test

- Recursion (Experiment 003).
- Attribution and replay (004).
- Context projection (005).
- Whether Continuum beats *any* other harness. The control is v1
  specifically. A win here is a win over one named baseline, not a
  general claim.

---

## 10. Status

Pre-registered. **Cannot be run yet** — blocked on model integration
(roadmap step 3), which is itself blocked on Experiment 001 receiving an
independent verdict (roadmap step 0).

Recorded in the decision journal as the commitment this document
represents.
