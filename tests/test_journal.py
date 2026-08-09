from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from escapement.belief.labels import BeliefLabel
from escapement.journal.calibration import report
from escapement.journal.models import DecisionEntry, Prediction, Resolution
from escapement.journal.store import Journal


def entry(id: str, *, confidence=BeliefLabel.LIKELY, retrospective=False) -> DecisionEntry:
    return DecisionEntry(
        id=id,
        question="q",
        chosen="A",
        alternatives=("B", "C"),
        rationale="because",
        retrospective=retrospective,
        prediction=Prediction(
            claim="X will not need rework",
            confidence=confidence,
            resolution_criteria="BROKE if X is rewritten",
        ),
    )


class EntryIntegrityTest(unittest.TestCase):
    def test_a_decision_with_no_alternatives_is_rejected(self) -> None:
        """A decision with nothing else on the table was not a decision;
        recording it inflates the journal without adding evidence."""
        with self.assertRaises(ValueError):
            DecisionEntry(
                id="d",
                question="q",
                chosen="A",
                alternatives=(),
                rationale="r",
                prediction=Prediction(claim="c", confidence=BeliefLabel.LIKELY, resolution_criteria="x"),
            )

    def test_chosen_cannot_also_be_listed_as_an_alternative(self) -> None:
        with self.assertRaises(ValueError):
            DecisionEntry(
                id="d",
                question="q",
                chosen="A",
                alternatives=("A", "B"),
                rationale="r",
                prediction=Prediction(claim="c", confidence=BeliefLabel.LIKELY, resolution_criteria="x"),
            )

    def test_prediction_without_resolution_criteria_is_rejected(self) -> None:
        """Without criteria a prediction becomes unfalsifiable the moment
        it is inconvenient, which is the whole failure mode."""
        with self.assertRaises(ValueError):
            Prediction(claim="it will be fine", confidence=BeliefLabel.LIKELY, resolution_criteria="")

    def test_prediction_without_a_claim_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Prediction(claim="", confidence=BeliefLabel.LIKELY, resolution_criteria="x")


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.temp.name) / "decisions.jsonl")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_round_trips_through_disk(self) -> None:
        self.journal.append(entry("d001"))
        loaded = self.journal.load()["d001"]
        self.assertEqual(loaded.chosen, "A")
        self.assertEqual(loaded.prediction.confidence, BeliefLabel.LIKELY)

    def test_duplicate_id_is_rejected(self) -> None:
        self.journal.append(entry("d001"))
        with self.assertRaises(ValueError):
            self.journal.append(entry("d001"))

    def test_resolution_appends_a_revision_and_keeps_the_original(self) -> None:
        """Append-only is what stops a prediction being quietly rewritten
        once its outcome is known."""
        self.journal.append(entry("d001"))
        self.journal.resolve("d001", Resolution.HELD, "no rework needed")

        history = self.journal.history("d001")
        self.assertEqual(len(history), 2)
        self.assertIs(history[0].prediction.resolution, Resolution.UNRESOLVED)
        self.assertIs(history[1].prediction.resolution, Resolution.HELD)
        self.assertIs(self.journal.load()["d001"].prediction.resolution, Resolution.HELD)

    def test_re_resolving_is_rejected(self) -> None:
        self.journal.append(entry("d001"))
        self.journal.resolve("d001", Resolution.HELD, "held")
        with self.assertRaises(ValueError):
            self.journal.resolve("d001", Resolution.BROKE, "changed my mind")

    def test_resolution_requires_a_note(self) -> None:
        self.journal.append(entry("d001"))
        with self.assertRaises(ValueError):
            self.journal.resolve("d001", Resolution.HELD, "")

    def test_unresolved_lists_only_open_predictions(self) -> None:
        self.journal.append(entry("d001"))
        self.journal.append(entry("d002"))
        self.journal.resolve("d001", Resolution.HELD, "done")
        self.assertEqual([e.id for e in self.journal.unresolved()], ["d002"])


class CalibrationTest(unittest.TestCase):
    def test_retrospective_entries_are_excluded_by_default(self) -> None:
        """They were written by someone who already knew how things were
        going, so counting them would flatter the hit rate for free."""
        entries = [entry(f"d{i}", retrospective=True).resolve(Resolution.HELD, "n") for i in range(5)]
        result = report(entries)
        self.assertEqual(result.scoreable, 0)
        self.assertEqual(result.excluded_retrospective, 5)

    def test_retrospective_can_be_included_explicitly(self) -> None:
        entries = [entry(f"d{i}", retrospective=True).resolve(Resolution.HELD, "n") for i in range(5)]
        result = report(entries, include_retrospective=True)
        self.assertEqual(result.scoreable, 5)

    def test_hit_rate_is_measured_per_label(self) -> None:
        entries = [
            entry("d1", confidence=BeliefLabel.LIKELY).resolve(Resolution.HELD, "n"),
            entry("d2", confidence=BeliefLabel.LIKELY).resolve(Resolution.HELD, "n"),
            entry("d3", confidence=BeliefLabel.LIKELY).resolve(Resolution.BROKE, "n"),
            entry("d4", confidence=BeliefLabel.PLAUSIBLE).resolve(Resolution.BROKE, "n"),
        ]
        rows = {row.label: row for row in report(entries).rows}
        self.assertAlmostEqual(rows[BeliefLabel.LIKELY].hit_rate, 2 / 3)
        self.assertEqual(rows[BeliefLabel.PLAUSIBLE].hit_rate, 0.0)

    def test_voided_predictions_are_not_scored_either_way(self) -> None:
        entries = [entry("d1").resolve(Resolution.VOIDED, "circumstances changed")]
        self.assertEqual(report(entries).scoreable, 0)

    def test_below_ten_resolutions_reports_no_signal(self) -> None:
        """Reading a rate off nine data points is self-deception, so the
        report says so rather than printing an inviting percentage."""
        entries = [entry(f"d{i}").resolve(Resolution.HELD, "n") for i in range(9)]
        self.assertFalse(report(entries).has_signal)

    def test_ten_resolutions_reports_signal(self) -> None:
        entries = [entry(f"d{i}").resolve(Resolution.HELD, "n") for i in range(10)]
        self.assertTrue(report(entries).has_signal)

    def test_no_brier_score_is_exposed(self) -> None:
        """Deliberate: a proper scoring rule needs a probability, and
        mapping LIKELY to 0.75 would invent precision on no evidence.
        Raw labels and outcomes are stored so Brier can be computed later
        if a calibrated mapping is ever justified."""
        import escapement.journal.calibration as calibration

        self.assertFalse(hasattr(calibration, "brier_score"))


class SeededJournalTest(unittest.TestCase):
    """The real journal shipped in the repo."""

    def setUp(self) -> None:
        self.entries = Journal(
            Path(__file__).resolve().parents[1] / "journal" / "decisions.jsonl"
        ).load()

    def test_seed_entries_are_present(self) -> None:
        self.assertGreaterEqual(len(self.entries), 8)

    def test_every_seed_entry_is_marked_retrospective(self) -> None:
        """They predate the journal, so none may count toward calibration."""
        for entry_id, e in self.entries.items():
            self.assertTrue(e.retrospective, f"{entry_id} is not marked retrospective")

    def test_every_prediction_is_forward_looking_and_open(self) -> None:
        """A retrospective entry graded on hindsight would be worthless;
        these are all about rework that has not happened yet."""
        for entry_id, e in self.entries.items():
            self.assertIs(
                e.prediction.resolution,
                Resolution.UNRESOLVED,
                f"{entry_id} was seeded already resolved",
            )

    def test_the_seeded_journal_reports_no_signal(self) -> None:
        result = report(list(self.entries.values()))
        self.assertEqual(result.scoreable, 0)
        self.assertFalse(result.has_signal)


if __name__ == "__main__":
    unittest.main()
