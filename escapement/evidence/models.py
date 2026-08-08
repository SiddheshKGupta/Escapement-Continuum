"""EVIDENCE primitive.

Frozen baseline section 5.6. POMDP correspondence: an observation.

The baseline defines EVIDENCE as a taxonomy of nine kinds plus the
sentence "Evidence updates STATE" -- with no fields, and no statement of
*how* it updates state. An independent review found that three things in
the Experiment 001 contract (precondition P5, criterion 5, mutation M3)
all presume a derivation pipeline the baseline never draws.

This module states it:

    EVIDENCE        the raw record, with its origin
        |
        v
    OBSERVATION     an admitted fact, carrying the evidence id that
        |           supports it            (ObservedState)
        v
    BELIEF          an interpretation over observations   (BeliefState)

Each arrow is one-way. Nothing turns a belief into an observation and
nothing turns an observation into evidence. That is the
`Observed != Believed` invariant made operational rather than asserted.

One boundary worth stating because it is genuinely ambiguous: the
baseline lists "decision evidence" as an evidence kind, while the
Experiment 001 contract makes the event trace "the only evidence
surface". Evidence objects appear *in* the trace; the trace is not itself
an Evidence object. Without that line an implementer can reasonably build
evidence records wrapping trace events, producing a self-referential
structure that cannot be replayed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EvidenceKind(Enum):
    """The nine kinds frozen in baseline section 5.6.

    Recorded in full even though Experiment 001 uses only two, because
    this is a closed taxonomy taken from the baseline rather than
    structure being invented here. Listing it costs nothing and stops a
    later contributor inventing a tenth.
    """

    EXECUTION = "execution"
    BEHAVIOURAL = "behavioural"
    PROVENANCE = "provenance"
    DECISION = "decision"
    PERFORMANCE = "performance"
    COST = "cost"
    INTERVENTION = "intervention"
    USER_FEEDBACK = "user_feedback"
    VERIFICATION = "verification"


@dataclass(frozen=True)
class Evidence:
    """A raw record of what actually happened, with its origin.

    Note the deliberate split the review identified as two different
    objects wearing one name. EVIDENCE owns **origin** provenance -- which
    capability produced this, via which action. STATE owns
    **justification** provenance -- which evidence supports this belief,
    and therefore what goes OUT if that support is retracted. An evidence
    record cannot express "this belief was justified by that other
    belief", which is exactly what criterion 7 checks, so the two cannot
    be collapsed into one field.
    """

    id: str
    kind: EvidenceKind
    #: What was learned, in a form the belief engine can act on.
    claim: str
    #: The capability id that produced it.
    source: str
    #: The information action or execution that ran, if any.
    produced_by: str | None = None
    #: Whether this is strong enough to move a belief more than one step.
    #: Foundations section 4.
    decisive: bool = False
    payload: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim:
            raise ValueError(f"evidence {self.id} must state a claim")
        if not self.source:
            raise ValueError(
                f"evidence {self.id} must name its source capability; "
                "evidence without origin provenance cannot be audited"
            )
