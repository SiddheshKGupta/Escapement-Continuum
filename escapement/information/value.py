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


def stop_exploring(
    values: list[InformationValue], *, proceed_return: int
) -> tuple[bool, int]:
    """Marginal Value Theorem stopping rule.

    Returns `(should_stop, comparator_used)`.

    Charnov's theorem, from foraging ecology: leave a depleting patch when
    its marginal return rate falls to the habitat average -- not when the
    patch is empty. Transposed here, stop investigating when the best
    remaining information action yields less than simply getting on with
    the work. That is a materially different rule from "EVI below a fixed
    constant", because the bar is the opportunity cost of the alternative
    rather than an arbitrary number.

    The comparator is returned, not just consulted, because criterion 8
    requires `EXPLORATION_STOPPED` to record the value actually used.
    """
    if not values:
        return True, proceed_return
    best = max(value.score for value in values)
    return best <= proceed_return, proceed_return


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
