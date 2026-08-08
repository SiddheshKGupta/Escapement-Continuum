"""EVIDENCE primitive.

Frozen baseline section 5.6. POMDP correspondence: an observation.

Evidence is the only thing permitted to create an Observation, which is
how the baseline's `Observed != Believed` invariant is enforced
structurally rather than by convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    """A recorded result of an information action or execution.

    `source` and `produced_by` together are the provenance the baseline's
    "Memory contamination" risk mitigation requires: it must always be
    answerable *where did this come from* without consulting a transcript.
    """

    id: str
    #: What was learned, in a form the belief engine can act on.
    claim: str
    #: The capability id that produced it (see CAPABILITY).
    source: str
    #: The information action or execution that ran, if any.
    produced_by: str | None = None
    #: Whether this evidence is strong enough to move a belief more than
    #: one step. Foundations section 4.
    decisive: bool = False
    payload: dict = field(default_factory=dict)
