"""STRATEGY primitive.

Frozen baseline sections 5.5, 14, 15. POMDP correspondence: a policy.

Reversibility lives here rather than on CAPABILITY because it is a
property of *what a strategy does*, not of the tool it does it with: the
same shell capability is reversible when listing files and irreversible
when deleting them. Foundations section 3.2 makes reversibility the input
that governs commitment timing, so it must be readable from the object
being committed to.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class Reversibility(Enum):
    """Frozen baseline section 9.

    Governs how long optionality stays open. Foundations section 3.2 is
    explicit that irreversibility makes *waiting more valuable* and raises
    the evidence bar -- it is the policy gate that moves earlier, not the
    action. Encoded as an ordered pair of values rather than a float
    because we have no data to justify finer gradations.
    """

    HIGH = "high"
    LOW = "low"


class CandidateStatus(Enum):
    """Lifecycle of a strategy within the ensemble.

    Added after an independent review found Experiment 001 criterion 11
    was not representable without it. Criterion 11 requires the commitment
    to retain "a strategy that was still plausible at commit time -- not a
    strategy already eliminated", and that distinction needs three states,
    not two.

    Baseline section 17 says to *remove* dominated strategies. Removal
    destroys exactly the distinction criterion 11 tests, so we mark
    instead. This matches the baseline's own instinct elsewhere -- section
    21.5 marks invalidated state STALE rather than deleting it -- and
    foundations section 5, where keeping invalidated nodes recoverable is
    named as the property worth copying from a JTMS.
    """

    CANDIDATE = "candidate"
    ELIMINATED = "eliminated"
    RETAINED = "retained"
    COMMITTED = "committed"


@dataclass(frozen=True)
class Strategy:
    """A candidate execution route.

    Only fields Experiment 001 needs. Notably absent: cost and latency
    estimates. Foundations section 12 defers anything requiring empirical
    magnitudes, and inventing them here would be the "False precision"
    risk the baseline names.
    """

    id: str
    description: str
    reversibility: Reversibility = Reversibility.HIGH
    #: Free-text reason this route is a candidate at all.
    rationale: str = ""
    status: CandidateStatus = CandidateStatus.CANDIDATE
    #: Why this candidate was eliminated, when it was. Required whenever
    #: status is ELIMINATED so a discarded route can still be explained --
    #: criterion 13 requires every transition to be explainable, and a
    #: candidate disappearing without a reason breaks that chain.
    eliminated_because: str | None = None
    #: The concrete next action that would follow if this strategy is
    #: chosen. Criterion 9 requires the commitment rationale to cite an
    #: action requiring a stable choice; without this field that citation
    #: is unverifiable prose.
    next_action: str | None = None

    def __post_init__(self) -> None:
        if self.status is CandidateStatus.ELIMINATED and not self.eliminated_because:
            raise ValueError(
                f"strategy {self.id} is ELIMINATED without a reason; "
                "criterion 13 requires every transition to be explainable"
            )

    def eliminate(self, because: str) -> "Strategy":
        return replace(self, status=CandidateStatus.ELIMINATED, eliminated_because=because)

    def retain(self) -> "Strategy":
        return replace(self, status=CandidateStatus.RETAINED)

    def commit(self) -> "Strategy":
        return replace(self, status=CandidateStatus.COMMITTED)


@dataclass
class StrategyEnsemble:
    """The set of candidates held simultaneously.

    Foundations section 10.3: this is a *mixture* of candidate policies,
    not a superposition. It cannot interfere with itself and must never
    acquire phase or amplitude.
    """

    strategies: dict[str, Strategy] = field(default_factory=dict)

    def add(self, strategy: Strategy) -> None:
        self.strategies[strategy.id] = strategy

    def get(self, strategy_id: str) -> Strategy | None:
        return self.strategies.get(strategy_id)

    def ids(self) -> list[str]:
        return sorted(self.strategies)


@dataclass(frozen=True)
class Commitment:
    """The record of choosing one strategy.

    Every field here exists to satisfy a specific Experiment 001
    criterion, and none is decorative:

      criterion  9  -> `rationale` must cite both exhausted information
                       value and the concrete next action requiring a
                       stable choice
      criterion 10  -> `residual_uncertainty` non-empty
      criterion 11  -> `retained_alternatives` holds strategies still
                       plausible at commit time, not ones already
                       eliminated

    Contract clause A2 makes an empty `retained_alternatives` or
    `residual_uncertainty` a FAIL rather than a pass, so both are
    validated on construction instead of being silently acceptable.
    """

    strategy_id: str
    rationale: str
    residual_uncertainty: tuple[str, ...]
    retained_alternatives: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.rationale:
            raise ValueError("commitment requires a rationale (criterion 9)")
        if not self.residual_uncertainty:
            raise ValueError(
                "commitment must record residual uncertainty (criterion 10); "
                "an empty record is a no-op assertion under contract A2"
            )
        if not self.retained_alternatives:
            raise ValueError(
                "commitment must retain a material alternative (criterion 11); "
                "an empty record is a no-op assertion under contract A2"
            )

    @classmethod
    def of(
        cls,
        *,
        chosen: Strategy,
        ensemble: "StrategyEnsemble",
        rationale: str,
        residual_uncertainty: tuple[str, ...],
    ) -> "Commitment":
        """Build a commitment, deriving retained alternatives from status.

        Constructing a Commitment directly lets a caller pass any list of
        ids as `retained_alternatives`, including ids of strategies that
        were already eliminated -- which would satisfy criterion 11's
        letter while proving nothing, exactly the vacuous pass contract
        clause A1 forbids. This path derives the list from actual
        candidate status, so it cannot be faked without also lying in the
        ensemble, where the trace would show it.
        """
        retained = tuple(
            sorted(
                s.id
                for s in ensemble.strategies.values()
                if s.status is CandidateStatus.RETAINED and s.id != chosen.id
            )
        )
        if not retained:
            raise ValueError(
                "no strategy is marked RETAINED, so criterion 11 cannot be "
                "satisfied honestly; eliminating every alternative before "
                "commit means optionality was not actually preserved"
            )
        return cls(
            strategy_id=chosen.id,
            rationale=rationale,
            residual_uncertainty=residual_uncertainty,
            retained_alternatives=retained,
        )
