"""Calibration reporting over the decision journal.

Foundations section 8 names Brier score and log score as the strictly
proper scoring rules, and they are the right instruments eventually.
They are **not implemented here**, and the reason matters.

A proper scoring rule needs a probability. Our confidences are ordered
labels, deliberately, because foundations section 4 argues point
probabilities cannot distinguish uncertainty from ignorance. Computing a
Brier score would require inventing a label-to-probability mapping --
deciding that LIKELY "means" 0.75 -- on no evidence whatsoever. The
system would then be optimising against a number nobody measured, which
is the exact False precision failure the ordinal representation exists
to prevent.

What is measurable without inventing anything is a **reliability
table**: for each confidence label, how often did predictions at that
label actually hold? That is an observed frequency, not an asserted one.
If ESTABLISHED predictions hold 60% of the time, that is overconfidence,
and it is visible without any float ever being assigned to a belief.

The raw label and outcome are stored, so Brier can be computed later if
and when a calibrated mapping is ever justified by data. Deferred, not
discarded -- the same discipline foundations section 12 applies to
Shapley, d-separation and SPRT thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

from escapement.belief.labels import BeliefLabel
from escapement.journal.models import DecisionEntry, Resolution


@dataclass(frozen=True)
class LabelReliability:
    label: BeliefLabel
    made: int
    held: int

    @property
    def hit_rate(self) -> float | None:
        """Observed frequency. None when nothing has resolved yet.

        A float here is a *measurement*, not a belief -- it is counted,
        not asserted, which is why it does not violate the no-floats rule
        that governs BeliefLabel.
        """
        return None if self.made == 0 else self.held / self.made


@dataclass(frozen=True)
class CalibrationReport:
    rows: tuple[LabelReliability, ...]
    scoreable: int
    unresolved: int
    excluded_retrospective: int

    @property
    def has_signal(self) -> bool:
        """Whether there is enough data to say anything at all.

        Ten resolved predictions is not a calibration curve. It is the
        threshold below which reading the numbers is self-deception, so
        the report says so rather than printing percentages that invite
        over-reading.
        """
        return self.scoreable >= 10


def report(
    entries: list[DecisionEntry], *, include_retrospective: bool = False
) -> CalibrationReport:
    """Reliability by confidence label.

    Retrospective entries are excluded by default. Their predictions were
    written by someone who already knew how things were going, so
    counting them would flatter the hit rate for free -- the journal's
    value depends entirely on predictions preceding their outcomes.
    """
    excluded = sum(1 for e in entries if e.retrospective)
    considered = [e for e in entries if include_retrospective or not e.retrospective]

    counts: dict[BeliefLabel, list[int]] = {label: [0, 0] for label in BeliefLabel}
    unresolved = 0
    for entry in considered:
        prediction = entry.prediction
        if not prediction.is_scoreable:
            if prediction.resolution is Resolution.UNRESOLVED:
                unresolved += 1
            continue
        counts[prediction.confidence][0] += 1
        if prediction.resolution is Resolution.HELD:
            counts[prediction.confidence][1] += 1

    rows = tuple(
        LabelReliability(label=label, made=made, held=held)
        for label, (made, held) in sorted(counts.items(), key=lambda kv: int(kv[0]))
        if made > 0
    )
    return CalibrationReport(
        rows=rows,
        scoreable=sum(row.made for row in rows),
        unresolved=unresolved,
        excluded_retrospective=excluded if not include_retrospective else 0,
    )


def render(report: CalibrationReport) -> str:
    lines = ["Decision journal calibration", ""]
    if not report.rows:
        lines.append("No resolved predictions yet.")
    else:
        lines.append(f"{'confidence':<14}{'made':>6}{'held':>6}{'rate':>8}")
        for row in report.rows:
            rate = "--" if row.hit_rate is None else f"{row.hit_rate:.0%}"
            lines.append(f"{row.label.name:<14}{row.made:>6}{row.held:>6}{rate:>8}")

    lines += [
        "",
        f"scoreable:              {report.scoreable}",
        f"unresolved:             {report.unresolved}",
        f"excluded retrospective: {report.excluded_retrospective}",
    ]
    if not report.has_signal:
        lines += [
            "",
            "NOT ENOUGH DATA. Fewer than 10 resolved predictions is not a",
            "calibration curve; reading these rates as a trend would be",
            "self-deception. Keep recording.",
        ]
    return "\n".join(lines) + "\n"
