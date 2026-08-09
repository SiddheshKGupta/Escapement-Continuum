"""Expected value of information, and the rule for when to stop.

Baseline section 27 places this in `information/value.py`. The *decision*
it feeds belongs to strategy reasoning -- baseline section 12 is explicit
that "EVI is not a global STATE field", and section 13.1 calls choosing
among information actions an information strategy.

Two things here are deliberately coarse and one is deliberately computed.

**Coarse:** expected decision improvement and cost are small integers, not
probabilities or currency. Foundations section 12 defers anything needing
empirical magnitudes until data exists.

**Computed:** the stopping comparator. Contract criterion 8 originally
said EVI must fall "below the stated threshold", which a constant chosen
after the fact would satisfy -- clause A1. Under the Marginal Value
Theorem (foundations section 3.3) the comparator is not configured at
all: you stop when the marginal yield of further inspection drops below
the return of simply proceeding. So `stop_exploring` returns the
comparator it used, and the caller is required to record it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InformationValue:
    """The evaluation of one information action.

    Kept as a record rather than a bare number so that criterion 3's
    "each with its own EVI figure" is satisfied by structure that shows
    *why* the figures differ, rather than by three literals.
    """

    action_id: str
    #: How much this would plausibly improve the decision. Coarse ordinal.
    expected_improvement: int
    #: What it costs to acquire, from the performing capability.
    cost: int

    @property
    def score(self) -> int:
        """Net expected value of information.

        Baseline section 12's decomposition also subtracts delay, context
        burden and human burden. Those are absent here because Experiment
        001 has one execution capability, no human in the loop, and a
        fixture repository -- so all three would be constant zero, and a
        term that is always zero is not modelling anything. They are added
        when an experiment makes them vary, not before.
        """
        return self.expected_improvement - self.cost


def proceed_return(strategy_labels: list[int], *, floor: int = 0) -> int:
    """The opportunity cost of continuing to investigate.

    This is the comparator the Marginal Value Theorem actually needs, and
    it must be *computed from state*. An independent review failed
    criterion 8 twice because the previous version took a module constant
    (`PROCEED_RETURN = 1`) and echoed it straight back: setting it to -3,
    0, 3 or 99 changed the recorded comparator verbatim, so a number
    chosen after the fact could produce any stopping behaviour desired.
    That is exactly the "fixed constant" the contract's v1.1 amendment
    forbids and clause A1 calls vacuous.

    The quantity being estimated is: how much is it worth to stop
    investigating and act on what we already believe? Under MVT you leave
    a patch when its marginal yield drops to the *habitat average* -- here,
    the value of getting on with the work. That value rises as the best
    strategy becomes better supported: acting on an ESTABLISHED belief is
    worth more than acting on a PLAUSIBLE one, so the bar for further
    inspection rises with confidence and the loop stops sooner. When
    nothing is known the bar is low and exploration continues, which is
    the behaviour the rule is supposed to produce.

    Coarse by construction: the return is the top strategy's label
    ordinal. Foundations §12 defers anything needing empirical magnitudes
    until data exists, and a tuned float here would reintroduce the false
    precision the ordinal representation avoids.
    """
    if not strategy_labels:
        return floor
    return max(floor, max(strategy_labels))


def stop_exploring(
    values: list[InformationValue], *, comparator: int
) -> tuple[bool, int]:
    """Marginal Value Theorem stopping rule.

    Returns `(should_stop, comparator_used)`.

    Charnov's theorem, from foraging ecology: leave a depleting patch when
    its marginal return rate falls to the habitat average -- not when the
    patch is empty. Transposed here, stop investigating when the best
    remaining information action yields less than simply getting on with
    the work.

    The comparator is passed in rather than defaulted, and returned rather
    than merely consulted, because criterion 8 requires
    `EXPLORATION_STOPPED` to record the value actually used. Callers are
    expected to derive it from `proceed_return()` -- passing a literal is
    possible but is the defect this signature was reshaped to expose.
    """
    if not values:
        return True, comparator
    best = max(value.score for value in values)
    return best <= comparator, comparator


def best_action(values: list[InformationValue]) -> InformationValue | None:
    """Highest-scoring information action, with a deterministic tie-break.

    Ties are broken on `action_id`, not left to dict or list ordering.
    Criterion 14 requires byte-identical traces across runs and mutation
    M8 introduces unordered iteration specifically to break it; coarse
    integer scores make ties common enough that leaving the order implicit
    would be a real determinism hazard rather than a theoretical one.
    """
    if not values:
        return None
    return sorted(values, key=lambda v: (-v.score, v.action_id))[0]
