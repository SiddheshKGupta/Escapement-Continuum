# R0 Pressure Test — before any implementation

Written against repository HEAD `977c45a`. The task was to try to kill R0
before building it. I was unable to justify it, and the reasoning follows.

---

## A. MECHANISM DECOMPOSITION

"Retained-alternative recovery" decomposes into six mechanisms. Each is
assessed against the repository and against a strong fixed-router
control.

| # | Mechanism | Implemented at HEAD? | Necessary for the recovery advantage? | Can a strong control have it? | Continuum distinct? |
|---|---|---|---|---|---|
| M1 | Retain alternatives after commitment | **Yes, but write-only.** `Commitment.retained_alternatives` is read by nothing except serialization and `replay.py` | Yes | **Trivially** — persist a list | **No** |
| M2 | Retain evidence and rationale per alternative | **Partial.** `eliminated_because` is a free-text string; there is no per-alternative evidence linkage | Yes | Yes — persist records | **No** |
| M3 | Dependency relations between evidence, assumptions, alternatives | **Present but inert.** `jtms/core.py` has `justify(in_list, out_list)`; deleting all JTMS calls leaves the trace byte-identical | Yes | Yes — persist a DAG | **No** |
| M4 | Automatic invalidation after contradictory evidence | **Capable but unused.** JTMS `retract()` propagates IN/OUT to fixpoint; never called by the loop | Yes | Yes — walk the DAG at re-entry | **No** (timing only, see C) |
| M5 | Selective recomputation of stale parts | **Not implemented.** `grep` for `resume\|recompute\|revalidate\|invalidate` in `escapement/` returns nothing | Yes | Yes — recompute only marked-stale nodes | **No** |
| M6 | Resume from prior alternative state rather than rerun routing | **Not implemented.** No resume path exists | **This is the claim itself** | Yes — reconstruct from the same persisted record | **See C** |

**The structural observation.** M1–M5 are all *data* mechanisms. Data can
be persisted, and anything persisted can be reloaded. None of them can
distinguish two architectures that are both allowed to persist.

Only M6 concerns *process*: maintain-incrementally versus
reconstruct-on-demand. Every candidate distinction therefore collapses
into M6, and M6 is the generic incremental-computation question, not a
Continuum-specific one.

**Answering the instruction not to protect the treatment definition:**
0 of 6 mechanisms give Continuum a capability a strong control cannot
have.

---

## B. STRONGEST CONTROL

Recognisably an Escapement-style fixed router. Permitted to persist
everything the treatment holds.

```text
CONTROL: v1-style router + structured decision record + re-entry

Persisted after every decision:
  decision graph
    nodes:  evidence | assumption | alternative | commitment
    edges:  supports | depends-on | contradicts
    per alternative:  status, supporting evidence ids,
                      assumptions relied on, prior evaluation,
                      rejection rationale
  ordered evidence log
  the committed choice and its justification path

On contradictory evidence (re-entry):
  1. load the decision graph
  2. mark the contradicted node invalid
  3. propagate invalidity along depends-on edges  -> stale set
  4. recompute evaluations for stale alternatives only
  5. re-rank; commit
```

**This control is not hypothetical — Continuum already contains it.**
`escapement/observation/events.py` writes a complete, ordered,
append-only decision record, and `escapement/observation/replay.py`
already reconstructs belief state from it. A control that replays the
trace, invalidates along a dependency graph and recomputes the stale
subset is roughly fifty lines on top of code that exists today.

The uncomfortable implication: the artifact we built to make Continuum
*auditable* is also a complete specification of its strongest
competitor.

**What does the treatment retain that this control lacks?**

Nothing in kind. The candidates and why each fails:

- *In-memory objects vs deserialized objects* — caching.
- *No reconstruction step* — deserialization cost, which is machine
  speed, and the primary metric explicitly excludes machine speed.
- *Path-dependent intermediate state* — the event trace is ordered and
  complete, so any path-dependent state is derivable from it.
- *Knowing why an alternative was rejected* — persisted as rationale.

---

## C. IRREDUCIBLE DIFFERENCE

**There is none that survives the experiment's own parity requirements.**

The argument is short and I could not break it:

1. **Information parity** (requirement §4) states the treatment must not
   receive information the control is denied. Therefore the treatment
   cannot know anything not present in the control's persisted record.
2. **Computation parity** (requirement §5) states the control may use
   the same algorithms and may cheaply index persisted state. Therefore
   the control may run the identical invalidation and recomputation
   procedure.
3. Same information, same algorithms, same inputs ⇒ **same outputs and
   the same recomputation set**.

The only surviving asymmetry is *when* the graph is materialised — held
across the episode versus rebuilt at re-entry. That is caching. Under a
work metric that counts reasoning operations rather than machine speed
(as required), caching is invisible by construction. Under a metric that
would make it visible, we would be measuring deserialization, not
recovery.

**One real difference that is out of R0's scope.** The treatment
maintains validity continuously, so it *notices* a contradiction the
moment evidence arrives; the control notices at re-entry. That is a
detection-latency difference, not a recovery-cost difference. It only
becomes material in long-running or concurrent execution, which R0 does
not model and Continuum does not implement.

**On JTMS.** The minimal operations R0 would need — register dependency,
invalidate, mark stale, selectively revalidate, restore validity — are
all expressible with a dependency DAG and explicit status propagation.
JTMS earns its way back only if a required behaviour cannot be
represented that way. The specific failure that would justify it:
**non-monotonic justification**, where an alternative is valid *because*
another is currently invalid (`out_list`), producing states with no
stable labelling that a DAG walk cannot resolve. No R0 topology
identified requires this. JTMS stays deactivated.

---

## D. R0 CONTROL SPECIFICATION

Written as instructed, frozen and implementation-independent — and the
act of writing it is the clearest demonstration of the finding, because
**every clause below applies unchanged to the treatment.** There is no
sentence I can write that constrains one arm and not the other without
deliberately crippling the control.

### D.1 Inputs (identical for both arms)

- Strategy set, opaque ids, no semantics in the engine.
- Evidence items, ordered, each with: id, subject, value, direction
  (supports/undermines), decisiveness, and the assumptions it bears on.
- Assumption set with dependency edges to strategies.
- One reversal evidence item per scenario.
- Intent with an explicit correctness criterion.
- Scoring function, stopping condition, policy — supplied by the harness,
  identical to both arms.

### D.2 Allowed state

Both arms may hold: the decision graph, per-alternative status, evidence
provenance, assumption dependencies, prior evaluations, and the
commitment record. Neither may hold anything absent from the other's
input.

### D.3 Allowed algorithms

Both arms may: index persisted state, cache, propagate invalidity along
dependency edges, and recompute selectively. **The control must not be
deliberately inefficient.** If the control could reasonably cache
something, it does.

### D.4 Correctness condition (gate, evaluated first)

An arm passes only if its post-reversal commitment equals the
scenario's declared correct strategy. **Efficiency is compared only
among arms that pass.** An arm that recovers cheaply to the wrong answer
scores no result at all.

### D.5 Primary metric (fixed before any run)

> **Number of strategy-evaluation recomputations performed between
> reversal detection and valid recommitment.**

Chosen over the alternatives because it is the unit of *reasoning* work
the mechanism claims to save; it is computable identically for both arms
by instrumenting one function; it is deterministic; it is independent of
machine speed and of token accounting; and it is hard to game without
changing observable behaviour.

Rejected: evidence nodes reread and dependency nodes traversed (measure
graph-walk cost, i.e. caching); state transitions (implementation
artifact); total primitive operations (unstable across refactors).

Secondary, reported never substituted: assumptions re-evaluated,
evidence items re-read, recommitment latency in operations.

### D.6 Reversal topologies (data only, never code)

Direct · shared-support · partial · misleading (runner-up also invalid)
· irrelevant-evidence.

### D.7 Negative controls

At least one scenario each where the treatment **should not** win:
all alternatives depend on the invalidated assumption; the reversal
destroys all retained reasoning; the correct answer is a strategy not
previously generated. **If the treatment reports a large advantage on
these, the metric or the implementation is biased** and the run is void.

### D.8 Prohibited leakage

Neither engine may contain code referencing specific strategy ids, the
expected winner, the reversal location, specific evidence ids, or the
expected dependency path. A permutation test renaming all ids and
reordering all inputs must produce a semantically identical result;
alphabetical or insertion order must never affect the outcome.

### D.9 Pre-mortem protections

*Five ways a treatment win could be rigged:* a control forbidden to
persist something the treatment holds; a control forced to recompute
non-stale nodes; a metric counting deserialization; scenarios whose
reversals always favour the retained runner-up; the treatment
instrumented at a different granularity. → Protections: D.2, D.3, D.5,
D.6, and one shared instrumentation point.

*Five ways a null could be an artifact:* reversals too shallow to make
recomputation costly; too few alternatives; dependency graphs too flat;
correctness gate too lenient, so both arms "pass" trivially; the metric
too coarse to resolve a real difference. → Protections: D.6 topologies,
graph depth ≥ 3, explicit correctness declaration per scenario.

---

# VERDICT: **R0 NOT JUSTIFIED**

R0 cannot be justified as framed, and the reason is structural rather
than practical. The experiment's own two fairness requirements are
jointly fatal to it: information parity forbids the treatment from
knowing anything the control's persisted record does not contain, and
computation parity permits the control to run the same invalidation and
selective-recomputation algorithm over that record. Satisfy both and the
arms compute the same stale set and perform the same recomputations; the
only residue is whether the dependency graph was held in memory or
rebuilt from disk, which is caching, and which the required
machine-speed-independent metric is specifically designed not to see. I
could not write a single specification clause that constrains the
control without deliberately crippling it — the strongest evidence that
the distinction has collapsed. The sharper conclusion is the one
anticipated in the brief's §12: the candidate mechanism was never
StrategyEnsemble, delayed commitment or belief ranking; it is
**incremental dependency-aware recomputation**, which is a generic
and well-understood technique, is not novel to Continuum, and — decisively
— is already latent in Continuum's own event trace and replay engine,
meaning we have built the strongest competitor to our own thesis without
noticing. The correct next step is therefore not to run R0 but to state
plainly that Continuum's distinguishing claim has not survived
specification, and to treat its genuinely earned results — evidence
direction, dependency-aware invalidation of persisted decisions, the
belief/utility separation, and the conformance-and-independent-review
methodology — as improvements to Escapement v1 rather than as
justification for a separate architecture.
