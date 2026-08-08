"""CAPABILITY primitive.

Frozen baseline section 5.3. POMDP correspondence: the action set.

The Capability Fabric abstraction is what makes the identity claim real:
a model is not the agent, it is one kind of capability among tools,
humans and harnesses. Escapement v1 itself appears here as a capability
(kind HARNESS), which is the concrete form of "v1 is evidence, not
baggage".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # typing only, so the dependency stays one-way
    from escapement.information.action import InformationAction


class CapabilityKind(Enum):
    """Subset of frozen baseline section 5.3 that Experiment 001 uses.

    The baseline lists sixteen kinds. Instantiating all of them now would
    be the "Overdesign" risk; the enum grows when an experiment needs a
    kind, not before.
    """

    MODEL = "model"
    AGENT = "agent"
    HUMAN = "human"
    TOOL = "tool"
    HARNESS = "harness"
    RETRIEVER = "retriever"


@dataclass(frozen=True)
class Capability:
    """Something that can act or inform.

    No reliability or latency fields yet. Foundations section 12 defers
    anything needing empirical magnitudes until there is data; a
    hand-typed `reliability=0.8` would be invented precision, and the
    system would then optimise against a number nobody measured.

    `provides` is the exception, and it is not a magnitude. It is the
    binding an independent review found missing: baseline section 12
    lists information actions, section 5.3 lists capability kinds, and
    nothing connects them. Criterion 3 needs three distinct EVI figures,
    EVI subtracts acquisition cost, and cost comes from whatever performs
    the action -- so without this declaration the figures could only be
    hardcoded.
    """

    id: str
    kind: CapabilityKind
    description: str
    #: Ids of the information actions this capability can perform.
    provides: tuple[str, ...] = ()

    def can_perform(self, action_id: str) -> bool:
        return action_id in self.provides


def validate_bindings(
    capabilities: dict[str, Capability], actions: dict[str, "InformationAction"]
) -> list[str]:
    """Check every action names a capability that claims to provide it.

    Returns a list of problems, empty when consistent. The binding is
    declared on both sides on purpose -- an action names its performer,
    and a capability lists what it performs -- because a one-sided
    declaration can drift silently. Checking that they agree turns a
    latent inconsistency into a startup failure.
    """
    problems: list[str] = []
    for action in actions.values():
        capability = capabilities.get(action.capability_id)
        if capability is None:
            problems.append(
                f"action {action.id} names unknown capability {action.capability_id!r}"
            )
        elif not capability.can_perform(action.id):
            problems.append(
                f"action {action.id} names capability {capability.id!r}, "
                f"which does not list it in `provides`"
            )
    return problems
