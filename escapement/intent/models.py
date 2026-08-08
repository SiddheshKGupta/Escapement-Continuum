"""INTENT primitive.

Frozen baseline section 5.1. POMDP correspondence: the reward function.

Intent is what makes the pragmatic-value half of the expected free energy
objective computable (foundations section 2). Without an explicit success
criterion there is nothing to measure progress against, and "is this
information worth gathering?" becomes unanswerable rather than merely
hard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Intent:
    """What outcome we are trying to achieve.

    `non_goals` is not decoration. The baseline lists it as a first-class
    part of INTENT because an unstated non-goal is the most common way an
    agent produces technically-correct, unwanted work.
    """

    id: str
    outcome: str
    success_criteria: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    def satisfied_by(self, met: set[str]) -> bool:
        """Whether every declared success criterion has been met.

        Deliberately requires *all* criteria. Partial satisfaction is a
        PARTIAL outcome, which Escapement v1 treats as a truthful result
        rather than a failure, and the same semantics apply here.
        """
        return bool(self.success_criteria) and set(self.success_criteria).issubset(met)
