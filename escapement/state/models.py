"""STATE primitive: ObservedState and BeliefState.

Frozen baseline section 5.2. POMDP correspondence: observation history
and belief state b(s).

The baseline states two invariants as fundamental:

    Observed != Believed
    Believed != Proven

These are enforced by type, not by discipline. `ObservedState` holds only
`Observation`s, and an `Observation` cannot be constructed without an
`Evidence` id. `BeliefState` holds only `Belief`s, which carry a
`BeliefLabel` and can never be read as a fact. There is deliberately no
method anywhere that promotes a Belief into an Observation -- Experiment
001 contract precondition P5 forbids exactly that path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from escapement.belief.labels import UNKNOWN, BeliefLabel

if TYPE_CHECKING:  # import only for typing, to keep the dependency one-way
    from escapement.evidence.models import Evidence


@dataclass(frozen=True)
class Observation:
    """A fact supported by evidence.

    `evidence_id` is mandatory and has no default. An observation that
    cannot name its evidence cannot be constructed, which is the
    structural form of the Observed != Believed invariant.
    """

    id: str
    subject: str
    value: object
    evidence_id: str

    @classmethod
    def derive(cls, evidence: "Evidence", *, id: str, subject: str, value: object) -> "Observation":
        """Admit a fact from an evidence record.

        The only intended construction path. Taking the whole Evidence
        object rather than a bare id makes the derivation direction
        (evidence -> observation) explicit in the call site, so mutation
        M3 -- writing an observation without intervening evidence -- has
        to be a visible edit rather than an omission that looks like
        ordinary code.
        """
        return cls(id=id, subject=subject, value=value, evidence_id=evidence.id)


@dataclass(frozen=True)
class Belief:
    """An uncertain interpretation.

    `kind` distinguishes the two belief families the baseline separates in
    section 11: WorldBelief (about the world) and StrategyBelief (about
    which strategy will work). Experiment 001 criterion 7 requires a
    strategy belief to change *because* a world belief changed, so the two
    must be distinguishable at the type level.
    """

    id: str
    kind: str  # "WorldBelief" | "StrategyBelief"
    proposition: str
    label: BeliefLabel = UNKNOWN

    def with_label(self, label: BeliefLabel) -> "Belief":
        return Belief(id=self.id, kind=self.kind, proposition=self.proposition, label=label)


@dataclass
class ObservedState:
    """Facts. Never interpretations."""

    observations: dict[str, Observation] = field(default_factory=dict)

    def record(self, observation: Observation) -> None:
        self.observations[observation.id] = observation

    def get(self, observation_id: str) -> Observation | None:
        return self.observations.get(observation_id)


@dataclass
class BeliefState:
    """Interpretations. Never facts."""

    beliefs: dict[str, Belief] = field(default_factory=dict)

    def hold(self, belief: Belief) -> None:
        self.beliefs[belief.id] = belief

    def get(self, belief_id: str) -> Belief | None:
        return self.beliefs.get(belief_id)

    def of_kind(self, kind: str) -> list[Belief]:
        return [b for b in self.beliefs.values() if b.kind == kind]
