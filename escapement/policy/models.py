"""POLICY primitive.

Frozen baseline sections 5.4, 19, 8 (grey-space governance).

Policy answers "what is permitted", which is a different question from
"what is best" (STRATEGY) and "what is worth knowing" (information
strategy). Keeping them separate matters because a hard invariant must be
able to veto a strategy that scores well -- baseline section 9: "Hard
invariants always override adaptive scores."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from escapement.strategy.models import Reversibility, Strategy


class Zone(Enum):
    """Frozen baseline section 8."""

    BLACK = "black"  # forbidden
    WHITE = "white"  # permitted without gate
    GREY = "grey"  # permitted with an explicit gate


@dataclass(frozen=True)
class Invariant:
    """A hard rule. Not scored, not traded off, not overridable."""

    id: str
    description: str
    #: Strategy ids this invariant forbids outright.
    forbids: tuple[str, ...] = ()


@dataclass
class Policy:
    """Filters the strategy ensemble before scoring.

    Ordering is deliberate and load-bearing: `filter` runs *before* any
    expected-free-energy comparison. A strategy removed here is never
    scored, so no accumulation of pragmatic or epistemic value can
    resurrect it.
    """

    invariants: list[Invariant] = field(default_factory=list)
    #: Reversibility at or below which a commitment needs an explicit gate.
    gate_below: Reversibility = Reversibility.LOW

    def forbidden(self, strategy: Strategy) -> Invariant | None:
        for invariant in self.invariants:
            if strategy.id in invariant.forbids:
                return invariant
        return None

    def filter(self, strategies: list[Strategy]) -> tuple[list[Strategy], list[tuple[Strategy, Invariant]]]:
        """Return (permitted, rejected-with-reason).

        Rejections are returned rather than dropped so the event trace can
        record *why* a candidate disappeared. Experiment 001 criterion 13
        requires every transition to be explainable, and a strategy
        vanishing without a recorded reason breaks that chain.
        """
        permitted: list[Strategy] = []
        rejected: list[tuple[Strategy, Invariant]] = []
        for strategy in strategies:
            invariant = self.forbidden(strategy)
            if invariant is None:
                permitted.append(strategy)
            else:
                rejected.append((strategy, invariant))
        return permitted, rejected

    def zone_for(self, strategy: Strategy) -> Zone:
        if self.forbidden(strategy) is not None:
            return Zone.BLACK
        if strategy.reversibility is Reversibility.LOW:
            return Zone.GREY
        return Zone.WHITE
