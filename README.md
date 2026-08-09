# Escapement-Continuum

**A research line exploring whether adaptive, uncertainty-aware execution
can outperform fixed routing for AI-assisted delivery.**

`0.1.0-alpha` · research → experimental → validated · **nothing here is
validated yet**

---

## Status, stated plainly

This repository has **not** demonstrated its thesis. It has one
experiment, on a fixture, which has been independently scored twice and
**failed both times**.

```text
Experiment 001   FAIL (9/15)   second independent scoring
                 fixes applied for all six failing criteria
                 NOT yet re-scored -- a third review is required
                 before any claim of passing
```

The machinery is real and tested (125 tests). What is missing is
evidence that the machinery helps. Those are different things, and this
README will not blur them.

**This is not a successor to [Escapement v1](https://github.com/SiddheshKGupta/Escapement).**
v1 is the stable line, is not deprecated, and is not waiting to be
replaced. Nothing here is a reason to delay adopting or continuing to
use it. Within Continuum's own capability model, v1 is catalogued as a
`HARNESS` capability — prior art to measure against, not a legacy to
migrate away from.

---

## What "Continuum" means

**The continuum is the retained strategy space, not the belief scale.**

That distinction matters enough to state on the first screen. Beliefs
here are deliberately *discrete* — five ordered labels, no floats —
because a point probability cannot distinguish uncertainty from
ignorance. `P = 0.5` asserts "equally likely", which is a strong claim,
not an absence of information.

What is continuous is optionality: multiple strategies are held
simultaneously and commitment is delayed until further information stops
being worth its cost.

The line was previously called *Quantum Escapement*. It was renamed
because the metaphor caused engineering errors, not merely marketing
confusion — classical probabilities cannot interfere, so "interference"
invited amplitude arithmetic that would have produced negative
probabilities. See `QUANTUM_ESCAPEMENT_FORMAL_FOUNDATIONS_v1.0.md` §10.

---

## The idea

```text
INTENT
  -> observed state + belief state
  -> strategy ensemble            several routes held at once
  -> is uncertainty worth reducing?
       yes -> information action -> evidence -> update beliefs
       no  -> commitment required? -> policy gate -> action
  -> evidence -> new state -> repeat
```

The loop owns the reasoning. **Models are capabilities inside it, not the
brain.** Nothing in `run_episode()` asks a model when to stop gathering
information or when to commit — the loop decides, and behaves identically
with a human, a tool, or a harness supplying evidence.

Underneath, the honest formal frame is a POMDP whose action set is
heterogeneous capabilities. Solving POMDPs optimally is intractable,
which is *why* the estimates here are coarse — not a shortcut to be
replaced later.

---

## Try it

```bash
python experiments/_001/run.py          # writes experiments/_001/events.jsonl
python -m unittest discover -s tests    # 125 tests
```

No network, no model provider, no MCP, no API key. Standard library
only. Experiment 001 is deterministic by contract — two runs produce
byte-identical traces.

The decision journal:

```bash
python -m escapement.journal --path journal/decisions.jsonl list
python -m escapement.journal --path journal/decisions.jsonl report
```

---

## Layout

```text
escapement/
  intent/ state/ capabilities/ policy/ strategy/ evidence/   six primitives
  information/       information actions, EVI, MVT stopping rule
  belief/            five ordered labels; no floats
  jtms/              justification-based truth maintenance
  observation/       append-only event trace, replay
  commitment/        (reserved; Commitment currently lives in strategy/)
  loop.py            the canonical execution loop

experiments/_001/    Useful Uncertainty
journal/             decision journal + calibration
```

---

## How this is reviewed

Every mechanism must survive an experiment that could falsify it, and
**nothing self-authored is accepted on its author's word.**

That rule was earned. Across this project, independent review has three
times found real defects in work that passed its own author's tests —
including a case where the committed strategy was invariant to what the
evidence said, and a claim in a docstring that was simply false. Each
scoring cycle produced findings the author had missed.

The acceptance criteria are written **before** implementation and cannot
be retrofitted. They include anti-gaming clauses: an assertion that
cannot fail does not count, an empty collection is not evidence, and a
correct outcome with an undemonstrated path is a failure, not a pass.

- `QUANTUM_EXPERIMENT_001_REVIEW_CONTRACT_v1.0.md` — binding criteria
- `QUANTUM_ESCAPEMENT_FORMAL_FOUNDATIONS_v1.0.md` — which formalism
  solves which problem, and what was deliberately *not* borrowed
- `EXPERIMENT_002_PREREGISTRATION_v1.0.md` — including what counts as a
  null result, committed before any data exists
- [`ROADMAP.md`](ROADMAP.md) — sequencing, and why self-hosting is scoped
  to a decision journal rather than literal self-execution

---

## What this does not claim

- That it beats Escapement v1. No comparison has been run.
- That adaptive strategy selection works. Experiment 002 tests that, and
  has not been run.
- That Experiment 001 passes. It does not, yet.
- That any of it is production-ready. It is `0.1.0-alpha` research.
- Any connection to quantum computing. The implementation is entirely
  classical.

---

## Licence

See [LICENSE](LICENSE) if present; otherwise all rights reserved pending
a licence decision.
