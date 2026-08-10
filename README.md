# Escapement-Continuum

Research programme investigating whether AI execution problems exist that a strong, simple harness cannot already solve.

```text
Status         FROZEN
Phase I        concluded -- negative result
Architecture   frozen, not validated
Distinguishing claim   none established
```

## Result

Phase I explored one candidate architecture. Its central claims did not survive adversarial specification. **That negative result is this repository's main output.**

Three candidate distinctions were removed, each by strengthening the baseline they were compared against:

```text
delayed commitment              a strong router can gather before routing
strategy ensemble               a strong router can persist alternatives
retained-alternative recovery   a strong router can persist rationale
dependency-aware recovery       a strong router can persist a dep graph
selective revalidation          a strong router can run the same algorithm
remaining difference            incremental maintenance vs reconstruction
                                -- a generic incremental-computation tradeoff
```

Nothing was empirically falsified. Once the strongest fair comparator was specified there was no treatment left to test. The planned 180-run Experiment 002 was **cancelled before execution**, not run and rationalised away.

## This is not v2

[Escapement v1](https://github.com/SiddheshKGupta/Escapement) is the stable line — not deprecated, not superseded. Nothing here is a reason to defer adopting it. [Escapement Core](https://github.com/SiddheshKGupta/Escapement-Core) is the current engineering line and inherits Continuum's lessons, not its code.

```text
v1         proves the harness
Core       industrialises the trust boundary
Continuum  researches what Core still cannot solve
```

Continuum reopens only when Core meets a concrete problem that deterministic mechanisms handle badly.

## C001 conformance suite

What was called "Experiment 001" is a deterministic conformance test, not scientific evidence — a fixture whose inputs, thresholds and expected output were all authored by the implementer cannot produce information about the world.

**C001 currently FAILS criteria 8 and 10** on anti-gaming grounds. The FAIL history is preserved deliberately and is not sanitised.

Three independent scorings found defects the author's own tests and checker missed:

```text
review 1   the committed strategy was invariant to what the evidence said
review 2   a regression, plus two "fixes" that were structurally inert
review 3   the author's own checker passed the defect it was built to catch
```

```bash
python conformance/c001/run.py        # writes conformance/c001/events.jsonl
python -m scoring.independent_checks  # independently written checker
python -m unittest discover -s tests  # 125 tests
```

No network, no model provider, no MCP, no API key. Standard library only.

## Layout

```text
escapement/        reference implementation (frozen, not validated)
conformance/c001/  deterministic conformance suite
scoring/           independently written contract checker
journal/           decision journal, 12 entries
tests/             125 tests
docs/              Phase I record
```

## Documents

| Document | Contents |
|---|---|
| [Open problems](docs/CONTINUUM_OPEN_PROBLEMS.md) | Phase II agenda and its governing rules |
| [R0 pressure test](docs/R0_PRESSURE_TEST.md) | how the last candidate distinction collapsed |
| [002 cancellation](docs/EXPERIMENT_002_CANCELLATION_ADDENDUM.md) | why 002 was cancelled before execution |
| [002 preregistration](docs/EXPERIMENT_002_PREREGISTRATION_v1.0.md) | preserved byte-untouched |
| [001 review contract](docs/QUANTUM_EXPERIMENT_001_REVIEW_CONTRACT_v1.0.md) | binding criteria |
| [Formal foundations](docs/QUANTUM_ESCAPEMENT_FORMAL_FOUNDATIONS_v1.0.md) | formalisms borrowed and refused |

## What this does not claim

- That it beats v1. No comparison has been run.
- That delayed commitment, strategy ensembles or retained alternatives confer any advantage. Each was examined; none survived.
- That C001 passes. It does not.
- That it is production-ready. It is a frozen research artifact.
- Any connection to quantum computing. Entirely classical. Renamed from *Quantum Escapement* because the metaphor caused engineering errors, not only marketing confusion.

## Rules that carry forward

1. No mechanism ships without an experiment that could falsify it.
2. Independent scoring for anything self-authored. Four consecutive independent reviews found real defects in work its author had assessed as correct.
3. Compare against v1 **plus the smallest reasonable enhancement**, never frozen historical v1.
4. Complexity is not evidence of distinction. The simpler architecture wins ties.
