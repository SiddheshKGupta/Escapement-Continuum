"""Ordered interval belief labels.

Foundations v1.0 section 4: point probabilities cannot express ignorance.
`P = 0.5` asserts "equally likely", which is a strong claim, and is not the
same as having no information -- but a single float cannot tell those
apart. That indistinguishability is exactly how the baseline's named
"False precision" risk enters a system.

At v0.1 we therefore use ordered labels rather than floats. This is coarse
on purpose. Floats are permitted later only if calibration data justifies
them, which is the baseline's own rule (section 23: calibration only from
data).
"""

from __future__ import annotations

from enum import IntEnum


class BeliefLabel(IntEnum):
    """Ordered, coarse belief strength.

    IntEnum so that comparison and one-step movement are well defined
    without inviting arithmetic that implies precision we do not have.
    Deliberately no `probability` property -- adding one would reintroduce
    the false precision this representation exists to prevent.
    """

    RULED_OUT = 0
    UNLIKELY = 1
    PLAUSIBLE = 2
    LIKELY = 3
    ESTABLISHED = 4

    def __str__(self) -> str:
        return self.name


#: The label an unexamined proposition holds. Distinct from UNLIKELY:
#: this is ignorance, not a leaning.
UNKNOWN = BeliefLabel.PLAUSIBLE


class Decisiveness(IntEnum):
    """How far one piece of evidence is permitted to move a belief.

    Foundations section 4: evidence moves a belief at most one step per
    observation *unless the evidence is decisive*. Without this cap a
    single confident-sounding observation can drive a belief from
    RULED_OUT to ESTABLISHED, which is precisely the overconfidence the
    interval representation exists to prevent.
    """

    ORDINARY = 1
    DECISIVE = 4


def update(
    current: BeliefLabel,
    direction: int,
    decisiveness: Decisiveness = Decisiveness.ORDINARY,
) -> BeliefLabel:
    """Move a belief by evidence, clamped to the label range.

    `direction` is +1 (evidence supports) or -1 (evidence undermines).
    Movement is capped by `decisiveness` and clamped at the endpoints, so
    repeated ordinary evidence approaches but cannot overshoot
    ESTABLISHED/RULED_OUT.
    """
    if direction not in (-1, 1):
        raise ValueError(f"direction must be +1 or -1, got {direction!r}")

    step = int(decisiveness) * direction
    moved = int(current) + step
    clamped = max(int(BeliefLabel.RULED_OUT), min(int(BeliefLabel.ESTABLISHED), moved))
    return BeliefLabel(clamped)


def contracted(before: BeliefLabel, after: BeliefLabel) -> bool:
    """Whether an update represents movement away from ignorance.

    Experiment 001 criterion 6 requires world beliefs to *change* in an
    observable way. With labels, "learning" means moving away from the
    UNKNOWN midpoint toward a commitment in either direction.
    """
    return abs(int(after) - int(UNKNOWN)) > abs(int(before) - int(UNKNOWN))
