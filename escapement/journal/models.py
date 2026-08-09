"""Decision journal entries.

Roadmap step 1. This is the honest form of self-hosting: Continuum does
not write Continuum, it records the decisions *about* Continuum as
structured entries carrying a prediction made before the outcome is
known.

Why this shape rather than routing decisions through `run_episode()`:
in a journal entry a human or an agent decides. The loop does not.
Forcing the decision through the autonomous loop would mean recording
that Continuum chose something it did not choose, which is precisely the
unverifiable claim this whole approach exists to avoid. Entries reuse
the primitives (BeliefLabel, Strategy ids, Evidence ids) so the data is
homogeneous with real episodes later, but they claim no autonomy.

The prediction is the load-bearing part. A decision record without a
falsifiable prediction is a diary; with one it is data. "It built
itself" cannot be audited. "Here are N predictions made before their
outcomes were known, and here is the hit rate per confidence level" can.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from escapement.belief.labels import BeliefLabel


class Resolution(Enum):
    """What actually happened to a prediction."""

    UNRESOLVED = "unresolved"
    HELD = "held"          # the prediction was correct
    BROKE = "broke"        # the prediction was wrong
    VOIDED = "voided"      # circumstances changed; not scoreable either way


@dataclass(frozen=True)
class Prediction:
    """A falsifiable claim about the future of a decision.

    `confidence` is an ordered label, not a probability -- foundations
    section 4. Calibration is measured as an observed hit rate per label
    (a reliability table), which needs no invented float on the belief
    side.

    `resolution_criteria` is mandatory. A prediction that does not say
    how it would be judged wrong is not a prediction, and would quietly
    become unfalsifiable the moment it was inconvenient.
    """

    claim: str
    confidence: BeliefLabel
    resolution_criteria: str
    resolution: Resolution = Resolution.UNRESOLVED
    resolution_note: str = ""

    def __post_init__(self) -> None:
        if not self.claim:
            raise ValueError("a prediction must state a claim")
        if not self.resolution_criteria:
            raise ValueError(
                "a prediction must state how it would be judged wrong; "
                "without that it is not falsifiable"
            )

    @property
    def is_scoreable(self) -> bool:
        return self.resolution in (Resolution.HELD, Resolution.BROKE)


@dataclass(frozen=True)
class DecisionEntry:
    """One material decision about Continuum.

    `alternatives` and `evidence` are not decoration -- they are what
    distinguishes a recorded decision from a recorded outcome. A journal
    that stores only what was chosen cannot later answer whether the
    reasoning was sound or merely lucky.
    """

    id: str
    #: What was being decided.
    question: str
    #: What was chosen.
    chosen: str
    #: What else was genuinely on the table. Not a list of strawmen --
    #: an alternative recorded here should have been defensible.
    alternatives: tuple[str, ...]
    #: Why. Free text, but it should cite something.
    rationale: str
    prediction: Prediction
    #: Evidence ids or short descriptions of what informed the choice.
    evidence: tuple[str, ...] = ()
    #: Set when the entry records a decision already made before the
    #: journal existed. Retrospective entries are excluded from
    #: calibration by default: the author already knew how things were
    #: going when they wrote the prediction, so counting them would
    #: flatter the hit rate for free.
    retrospective: bool = False
    #: Optional path to an event trace, when a real episode produced this.
    trace_path: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.alternatives:
            raise ValueError(
                f"entry {self.id} records no alternatives; a decision with "
                "no alternative was not a decision, and recording it as one "
                "inflates the journal without adding evidence"
            )
        if self.chosen in self.alternatives:
            raise ValueError(
                f"entry {self.id} lists the chosen option {self.chosen!r} "
                "among the alternatives; alternatives are what was *not* chosen"
            )

    def resolve(self, resolution: Resolution, note: str) -> "DecisionEntry":
        if self.prediction.resolution is not Resolution.UNRESOLVED:
            raise ValueError(
                f"entry {self.id} is already resolved as "
                f"{self.prediction.resolution.value}; re-resolving would let "
                "a prediction be quietly rewritten after the fact"
            )
        if not note:
            raise ValueError("resolving a prediction requires a note saying what happened")
        return replace(
            self,
            prediction=replace(self.prediction, resolution=resolution, resolution_note=note),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "chosen": self.chosen,
            "alternatives": list(self.alternatives),
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "retrospective": self.retrospective,
            "trace_path": self.trace_path,
            "tags": list(self.tags),
            "prediction": {
                "claim": self.prediction.claim,
                "confidence": self.prediction.confidence.name,
                "resolution_criteria": self.prediction.resolution_criteria,
                "resolution": self.prediction.resolution.value,
                "resolution_note": self.prediction.resolution_note,
            },
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "DecisionEntry":
        p = raw["prediction"]
        return cls(
            id=raw["id"],
            question=raw["question"],
            chosen=raw["chosen"],
            alternatives=tuple(raw["alternatives"]),
            rationale=raw["rationale"],
            evidence=tuple(raw.get("evidence", ())),
            retrospective=raw.get("retrospective", False),
            trace_path=raw.get("trace_path"),
            tags=tuple(raw.get("tags", ())),
            prediction=Prediction(
                claim=p["claim"],
                confidence=BeliefLabel[p["confidence"]],
                resolution_criteria=p["resolution_criteria"],
                resolution=Resolution(p["resolution"]),
                resolution_note=p.get("resolution_note", ""),
            ),
        )
