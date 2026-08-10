# Continuum — Open Problems

```text
CONTINUUM

Research status        OPEN  (Phase II)
Architecture status    FROZEN / NOT VALIDATED
Distinguishing claim   NONE ESTABLISHED
v2 status              NOT CLAIMED — must be re-earned

Research objective
  Discover whether an execution problem exists for which a mechanism
  materially stronger than Escapement v1 + the smallest reasonable
  enhancement is required.

Engineering rule
  No production architecture until such a mechanism survives a
  strong-null specification.
```

---

## Why Phase II exists

**Not** because effort has been invested. That is sunk cost and is
explicitly rejected as a reason.

Because the investigation has repeatedly produced findings nobody set
out to find:

```text
validate delayed commitment      -> a strong router reproduces it
test evidence sensitivity        -> hardcoded interpretation defect
test the stopping rule           -> belief/utility category error
challenge ordinal beliefs        -> the 71% saturation reading was wrong
test retained-alternative recovery -> collapses to persistence + reconstruction
specify R0                       -> the metric itself favoured the treatment
strengthen the baseline          -> architectural novelty kept disappearing
```

A weak research programme keeps confirming its original story. This one
keeps changing it, and the most valuable findings arrived while trying
to *kill* an idea rather than defend it.

**Phase II continues the investigation, not the architecture.**

### What Phase I established

Three candidate answers to "what is Continuum" were removed:

```text
delayed commitment              ✕  reproducible by a strong router
strategy ensemble               ✕  no distinct capability
retained-alternative recovery   ✕  reduces to persistence + reconstruction
```

The distinguishing architectural claim **did not survive adversarial
specification**. Nothing was empirically falsified; once the strongest
fair comparator was specified there was no treatment left to test.

---

## Governing rules

### The admission rule

A mechanism enters Continuum only when **all five** hold:

1. An observed or precisely defined problem exists.
2. v1 + the smallest reasonable enhancement has been considered.
3. That simpler solution has a **specific** insufficiency.
4. The mechanism produces an **observable distinction**, not merely a
   new representation.
5. The distinction survives adversarial specification **before**
   implementation.

Fail any one → research note, or v1 improvement. Not architecture.

### The comparator rule

Always compare against **v1 + smallest reasonable enhancement**, never
frozen historical v1. Comparing against a system deliberately denied an
obvious improvement lets any mechanism manufacture its own necessity.
This is the rule that ended Phase I.

### The simplicity rule

**Continuum may not use complexity as evidence of distinction.**

```text
v1 + a 50-line enhancement
    beats
a Continuum subsystem
```

unless the subsystem demonstrates a materially different capability or
result. **The simpler architecture wins ties.**

Phase I repeatedly gave first-class names to concepts a strong baseline
reproduced with small enhancements. The burden is now asymmetric by
design.

### The process

```text
problem
  -> strongest simple solution
  -> try to kill the need for architecture
  -> surviving gap
  -> mechanism
  -> experiment
```

Not `idea -> architecture -> experiment`.

### Phase II stopping condition

Phase II **closes** if no open problem reaches `WORTH_EXPERIMENT`
within six problem-cycles.

A **cycle** is one research problem taken through:

```text
precise problem statement
    -> observed / defined failure
    -> strongest null
    -> v1 + smallest enhancement
    -> attempted reduction
    -> cheapest falsification
    -> independent challenge
    -> STATUS
```

A cycle ends only when exactly one status is assigned:

```text
REDUCED_TO_V1   THEORY_ONLY   CLOSED   WORTH_EXPERIMENT
```

**Rewording the same underlying problem does not reset the count.**
Splitting P1 into P1a/P1b/P1c consumes one cycle, not three.

**Early-stop rule.** If two consecutive cycles yield `REDUCED_TO_V1`,
`THEORY_ONLY` or `CLOSED`, and no new non-reducible problem emerged from
either, Phase II undergoes immediate closure review rather than
automatically consuming the remaining budget.

Six is a **maximum research budget, not a target**.

Closing is a legitimate outcome. "A separate adaptive execution
architecture was not necessary" answers an important question and
materially strengthens v1. Without this bound, `OPEN` becomes permanent
by default and the repository's existence generates its own gravity.

### Applying the rule to problems, not only mechanisms

The admission rule applies to what enters this document too, or it
becomes a wish list. Problems below are triaged, not listed equally.

---

## P1 — What can a harness guarantee when interpretation is delegated?

*(merges the earlier "who owns semantic state transitions")*

**Status: OPEN — strongest current candidate**

### Problem

With deterministic fixtures, `interpret()` is hand-written and the loop
owns the epistemic reasoning. With a real model the pipeline becomes
`evidence -> model says what it means -> loop records it`, and the loop
may own almost none of the reasoning it claims to govern.

> **When semantic interpretation is delegated to a fallible model, what
> properties of the resulting decision process can a harness
> independently guarantee without itself becoming another semantic
> reasoner?**

### Why the earlier framing was wrong

An earlier version asked what the harness could verify "without redoing
the semantic reasoning", and proposed testing it against a
self-consistent-but-false interpretation.

That test was **unfair by construction**. Consider:

```text
model says   "this evidence implies X"
reality      X is false
state        perfectly self-consistent
```

No structural check can discover the falsehood here. If it could, it
would already possess the semantic knowledge required to tell true X
from false X — and would therefore be the second semantic reasoner the
question excludes. The test could only ever return "harness fails",
which makes it uninformative.

**Semantic truth is not independently guaranteeable.** Conceding that
sharpens the question rather than weakening it.

### The candidate boundary

```text
SEMANTIC TRUTH      probably NOT independently guaranteeable

PROVENANCE          yes     was the evidence actually observed?
AUTHORITY           yes     was the source permitted to establish this?
INFERENCE STATUS    yes     recorded as observation or as interpretation?
CONSISTENCY         partly  does it contradict another explicit state object?
INDEPENDENCE        yes     was verification performed by the same reasoning path?
EVIDENCE COVERAGE   yes     what evidence supports this claim?
EFFECT GOVERNANCE   yes     what may happen if this interpretation is wrong?
REVERSIBILITY       yes     how costly is an incorrect commitment?
RECURRENCE          yes     has this assumption failed before?
AUDITABILITY        yes     can we reconstruct why the action occurred?
```

Which suggests the real claim:

> **The harness may not own truth. It may own the conditions under which
> a fallible semantic judgement is allowed to become durable state or
> consequential action.**

That is a governance boundary, not an epistemic one — and it connects
directly to what v1 already does.

### What v1 currently does

Enforces phase gates, authority, evidence records, effect gates and
closure semantics. It does not carry typed epistemic state and does not
distinguish observation from interpretation as a first-class property.

### Smallest v1 enhancement

v1 + typed epistemic state (observation vs interpretation, with
provenance) + independent-verification and effect gates keyed to
reversibility.

### Strongest null — deliberately brutal

> **v1 + typed epistemic state + independent-verification/effect gates
> provides every guarantee in the table above.**

Most of that list is already v1 territory. Authority, effect governance,
reversibility gating and auditability are things v1 does today. If
adding two typed fields and one gate closes the remainder, P1 reduces.

### What would justify a separate mechanism

A guarantee in the table that **cannot** be expressed as a gate over v1's
existing decision record — most plausibly `INDEPENDENCE` (was this
verified by a reasoning path other than the one that produced it?) or
`RECURRENCE` across runs, since both require state v1 does not currently
keep.

### Cheapest falsification attempt

Take the ten candidate guarantees. For each, write the v1 enhancement
that would provide it, and estimate its size. If every one is a field
plus a gate, P1 is `REDUCED_TO_V1` and Phase II is close to concluding.
This costs one sitting and needs no code.

---

## P2 — Machine-operable decision state

**Status: LIKELY REDUCES TO V1 — verify, then close**

### Problem

v1 persists decisions as prose. Is there a qualitative difference
between "memory of prior work" and an executable representation of
decision, support, assumptions, validity, authority, evidence and
supersession?

### Smallest v1 enhancement

Give v1 a structured decision record with those fields.

### Why that is probably sufficient

Nothing prevents v1 from holding structured records. Phase I established
that persistence-shaped mechanisms do not survive the comparator rule —
this is the same shape.

### Cheapest falsification

Name one runtime behaviour that a structured record enables and prose
plus an index cannot. If none can be named in one sitting, mark
`REDUCED TO V1` and move the structured record to the v1 candidate list.

---

## P3 — Information acquisition under real uncertainty

**Status: OPEN — bar is now much higher**

### Problem

Agents must choose among asking the user, inspecting code, searching
docs, running a test, calling another model, prototyping, or acting now.
The EVI implementation was conceptually broken (belief ordinal compared
against utility), but the underlying decision problem did not disappear.

### Smallest v1 enhancement

A heuristic rule table: if precondition X is unresolved and cheap check
Y exists, run Y.

### Why that might be insufficient

Rules must be authored per situation and do not generalise. A derived
criterion would. **But** Phase I showed that "derived rather than
authored" is an engineering-effort argument, not a capability argument —
so this must clear a higher bar than it did before.

### What would justify a mechanism

A decision class where the rule table is not merely tedious but
*cannot* be written correctly in advance, and a derived criterion
measurably outperforms a strong heuristic router.

### Note

Blocked on P4: a correct information-value calculation requires the
belief/outcome/utility separation first.

---

## P4 — Belief → outcome → utility

**Status: THEORY NOTE — not an architecture question**

Design work, not an experiment. It will not by itself justify a
mechanism, and should not be presented as if it might.

The separation, frozen conceptually and **not implemented**:

```text
WorldBelief(proposition)
    epistemic claim about the environment
    may remain ordinal / coarse

OutcomeEstimate(strategy | beliefs, intent)
    expected consequences of taking a strategy under current beliefs

ActNowValue(strategy)
    decision utility derived from outcome estimates and intent/policy

InformationValue(action)
    expected improvement in achievable ActNowValue, minus acquisition cost
```

The stop/observe decision compares `InformationValue` against
`ActNowValue` — **same decision-value space**, which removes the
category error at its source. No numeric scales. No probabilities. No
implementation.

Consequence already accepted: **`StrategyBelief` should not exist.**
"RECURSIVE is the right route = LIKELY" is not an epistemic proposition;
it is the output of a decision calculation wearing belief clothing.
Ordinal representation stays where it belongs — on world beliefs.

---

## Ordinal beliefs — status correction

The earlier "71% saturation, abandon ordinal belief" conclusion is
**withdrawn**. It measured how often a ±1 update changes the ranking,
and counted appropriate stability as saturation. Corrected enumeration
over the 125-state space:

```text
leader/runner-up gap <= 1     66%   representation is sensitive at the boundary
leader unchangeable            10%   both at ceiling
top rank tied                  28%   resolved alphabetically  <- real defect
>=1 strategy at a bound        78%   pile-up                  <- real defect
```

Two specific defects, not an indictment. Fixes, in order:

1. Remove alphabetical tie-breaking — a strategy's **name** must never
   decide a commitment.
2. Define tie handling explicitly: preserve, gather discriminating
   evidence, defer to decision utility, or escalate.
3. Study reachable belief trajectories before changing representation.
4. Remove `StrategyBelief` from the decision-value role (P4).

Representation change is **not** currently justified.

---

## Problem template

```text
Problem
Why it matters
What v1 currently does
Smallest v1 enhancement that might solve it
Why that enhancement might be insufficient
Strongest null
What observation would justify a separate mechanism
Cheapest falsification attempt
Status:  OPEN | REDUCED TO V1 | WORTH EXPERIMENT | CLOSED
```

---

## On the name

"Continuum" no longer needs to mean a continuous belief system. It can
name the continuum between evidence, uncertainty, decision and
execution.

But the science does not bend around the name. If Phase II concludes
that no separate architecture is warranted, Continuum remains the name
of the research programme that established it.
