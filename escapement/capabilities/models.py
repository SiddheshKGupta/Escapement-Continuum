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

    No cost or reliability fields yet. Foundations section 12 defers
    anything needing empirical magnitudes until there is data; a
    hand-typed `reliability=0.8` would be invented precision, and the
    system would then optimise against a number nobody measured.
    """

    id: str
    kind: CapabilityKind
    description: str
