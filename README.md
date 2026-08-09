# Escapement-Continuum

**A research programme investigating whether AI execution problems exist
that a strong, simple harness cannot already solve.**

```text
Research status        OPEN   (Phase II)
Architecture status    FROZEN / NOT VALIDATED
Distinguishing claim   NONE ESTABLISHED
v2 status              NOT CLAIMED — must be re-earned
```

---

## Read this first

Continuum **is not a system**. It is not v2, and it does not currently
have a distinguishing architecture. Phase I explored one and concluded
that its central claims did not survive adversarial specification.

That is a negative result, and it is the main output of this repository
so far.

**This is not a successor to [Escapement v1](https://github.com/SiddheshKGupta/Escapement).**
v1 is the stable line. It is not deprecated, not superseded, and nothing
here is a reason to defer adopting it.

---

## Phase I — concluded

Three candidate answers to "what is Continuum" were removed, each by
strengthening the baseline it was compared against:

```text
delayed commitment              ✕  a strong router reproduces it
strategy ensemble               ✕  no distinct capability
retained-alternative recovery   ✕  reduces to persistence + reconstruction
```

The reduction, in full:

```text
delayed commitment              -> a strong router can gather before routing
strategy ensemble               -> a strong router can persist alternatives
retained-alternative recovery   -> a strong router can persist rationale
dependency-aware recovery       -> a strong router can persist a dep graph
selective revalidation          -> a strong router can run the same algorithm
remaining difference            -> incremental maintenance vs reconstruction
                                -> a generic incremental-computation trade-off
```

**Nothing was empirically falsified.** Once the strongest fair
comparator was specified, there was no treatment left to test. The
planned 180-run experiment was cancelled *before execution* rather than
run, disliked and rationalised — see
`EXPERIMENT_002_CANCELLATION_ADDENDUM.md`.

## Phase II — open

> Discover whether an execution problem exists for which a mechanism
> materially stronger than **v1 + the smallest reasonable enhancement**
> is required.

Governed by three rules, all of which Phase I earned the hard way:

- **Admission rule** — a mechanism enters only if a defined problem
  exists, the simplest v1 enhancement was considered and has a *specific*
  insufficiency, the mechanism yields an observable distinction rather
  than a new representation, and that distinction survives adversarial
  specification *before* implementation.
- **Comparator rule** — always compare against v1 *plus the smallest
  reasonable enhancement*, never frozen historical v1. Comparing against
  a system denied an obvious improvement lets any mechanism manufacture
  its own necessity.
- **Simplicity rule** — complexity is not evidence of distinction. **The
  simpler architecture wins ties.**

Phase II has a **six-cycle budget** and closes if no problem reaches
`WORTH_EXPERIMENT`. Closing is a legitimate outcome.

Open problems and their triage: `CONTINUUM_OPEN_PROBLEMS.md`.

---

## C001 — conformance suite

What was called "Experiment 001" is a **deterministic conformance
test**, not scientific evidence. It was reclassified because a fixture
whose inputs, thresholds and expected output were all authored by the
implementer cannot produce information about the world — a PASS would
confirm only that we can implement our own specification.

Its diagnostic value is real and high. Three independent scorings found
defects that its author's own tests and checker missed:

```text
review 1   the committed strategy was invariant to what the evidence said
review 2   a regression, plus two "fixes" that were structurally inert
review 3   the author's own checker passed the defect it was built to catch
```

C001 currently **FAILS** criteria 8 and 10 on anti-gaming grounds. The
full FAIL history is preserved deliberately and is not sanitised.

```bash
python conformance/c001/run.py           # writes conformance/c001/events.jsonl
python -m scoring.independent_checks     # independently written checker
python -m unittest discover -s tests     # 125 tests
```

No network, no model provider, no MCP, no API key. Standard library only.

---

## Layout

```text
escapement/          reference implementation (FROZEN, not validated)
conformance/c001/    deterministic conformance suite
scoring/             independently written contract checker
journal/             decision journal
tests/               125 tests
```

## Documents

- `CONTINUUM_OPEN_PROBLEMS.md` — Phase II agenda and governing rules
- `R0_PRESSURE_TEST.md` — how the last candidate distinction collapsed
- `EXPERIMENT_002_CANCELLATION_ADDENDUM.md` — why 002 was cancelled
- `QUANTUM_EXPERIMENT_001_REVIEW_CONTRACT_v1.0.md` — binding criteria
- `QUANTUM_ESCAPEMENT_FORMAL_FOUNDATIONS_v1.0.md` — which formalisms were
  borrowed, and which were deliberately refused

---

## What this does not claim

- That it beats Escapement v1. No comparison has been run.
- That delayed commitment, strategy ensembles or retained alternatives
  confer any advantage. Each was examined and none survived.
- That C001 passes. It does not.
- That it is production-ready. It is a frozen research artifact.
- Any connection to quantum computing. Entirely classical. The line was
  renamed from *Quantum Escapement* because the metaphor caused
  engineering errors, not merely marketing confusion.

## On the name

"Continuum" no longer denotes a continuous belief system. It names the
continuum between evidence, uncertainty, decision and execution. If
Phase II concludes no separate architecture is warranted, Continuum
remains the name of the programme that established it.
