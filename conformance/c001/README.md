# Experiment 001: Useful Uncertainty

Run: `python conformance/c001/run.py`

## Determinism allow-list (criterion 14)

Criterion 14 requires two runs to produce byte-identical `events.jsonl`.
This run has **no volatile fields at all** — no wall-clock timestamps, no
random seeds, no host paths in the trace. The allow-list is therefore
empty, which is stronger than the contract requires and worth keeping
that way: a timestamp added later would need this line updated, which is
a visible edit rather than a silent weakening.

## Total order for ranking (review finding 5.5)

Coarse ordinal beliefs make ties common — three strategies over five
labels collide routinely. Ranking is therefore explicitly
`(-belief_label, strategy_id)`: strongest belief first, ties broken on
id. Mutation M8 attacks exactly this by reordering the input; the trace
must not change.

## What the fixture is

Not a real repository. A dependency map that reports 14 separable modules
with shallow coupling, a file count that reports 812, and an architect
who says "modular". The dependency map is decisive; the file count tells
you nothing about decomposability. That asymmetry is what makes the EVI
comparison mean something rather than being three arbitrary numbers.

## Expected outcome

`RECURSIVE` committed, `DIRECT` retained as a live alternative,
`SEQUENTIAL` eliminated with a recorded reason.

Note that committing RECURSIVE proves nothing on its own — contract
clause A7 is explicit that a hardcoded `return RECURSIVE` satisfies the
scenario narrative and fails the contract entirely. The verdict is about
the path: that three strategies coexisted, that the dependency map won on
expected value rather than by being listed first, that the strategy
belief moved because the *world* belief moved, and that exploration
stopped because further information stopped being worth its cost.
