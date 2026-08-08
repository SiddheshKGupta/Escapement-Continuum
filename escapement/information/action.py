"""Information actions.

Baseline section 27 places these in `information/`. Ownership of the
*concept* sits with CAPABILITY -- baseline section 5.3 already defines a
capability as anything invocable "to obtain information" -- which is why
an action must name the capability that performs it and cannot exist
without one.

This module exists because an independent review found a gap that blocks
Experiment 001 criterion 3. That criterion requires at least three
`INFORMATION_ACTION_EVALUATED` events "each with its own EVI figure", and
baseline section 12 computes EVI by subtracting information acquisition
cost. Cost is a property of the capability performing the action. The
baseline lists action names and capability kinds but never binds them, so
without this module three distinct EVI figures could only come from three
hardcoded numbers -- which mutation M2 is designed to catch and clause A7
rules out as proving nothing.

**Naming.** Baseline section 12 lists nine action *kinds*, one of which is
`INSPECT_REPOSITORY`. The contract's criterion 4 requires the selected
action to be `INSPECT_DEPENDENCY_MAP`. These are not in conflict once the
levels are separated: the baseline enumerates kinds, Experiment 001 needs
a concrete instance of one. `INSPECT_DEPENDENCY_MAP` is an
`InformationAction` whose `kind` is `INSPECT_REPOSITORY`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from escapement.strategy.models import Reversibility


class ActionKind(Enum):
    """The nine kinds frozen in baseline section 12."""

    ASK_USER = "ask_user"
    SEARCH_AUTHORITATIVE_SOURCE = "search_authoritative_source"
    SEARCH_STATE_FABRIC = "search_state_fabric"
    INSPECT_REPOSITORY = "inspect_repository"
    RUN_EXPERIMENT = "run_experiment"
    PROBE_CAPABILITY = "probe_capability"
    DELEGATE_INVESTIGATION = "delegate_investigation"
    EXECUTE_REVERSIBLE_TEST = "execute_reversible_test"
    STOP_EXPLORING = "stop_exploring"


@dataclass(frozen=True)
class InformationAction:
    """A concrete, invocable act that yields evidence.

    `cost` is a coarse ordinal, not a currency or a duration. Foundations
    section 12 defers anything needing empirical magnitudes until data
    exists; a hand-typed `cost=0.37` would be invented precision that the
    system would then optimise against. Small integers are honest about
    being a ranking rather than a measurement.

    Reversibility lives on the action, not on the capability, because the
    same capability is reversible for one act and not another -- a shell
    is reversible when listing files and irreversible when deleting them.
    The review argued for capability ownership on the grounds that a
    strategy could otherwise disagree with the capability it calls; that
    concern is real and is resolved by `Strategy.reversibility` being
    defined as the least-reversible action the strategy will take, rather
    than an independently-assigned value.
    """

    id: str
    kind: ActionKind
    capability_id: str
    description: str
    cost: int = 1
    reversibility: Reversibility = Reversibility.HIGH

    def __post_init__(self) -> None:
        if self.cost < 0:
            raise ValueError(f"action {self.id} has negative cost {self.cost}")
        if not self.capability_id:
            raise ValueError(
                f"action {self.id} names no capability; an information "
                "action that nothing performs has no cost and therefore no "
                "computable EVI (criterion 3)"
            )
