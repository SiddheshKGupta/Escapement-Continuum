from __future__ import annotations

import unittest

from escapement.capabilities.models import Capability, CapabilityKind, validate_bindings
from escapement.evidence.models import Evidence, EvidenceKind
from escapement.information.action import ActionKind, InformationAction
from escapement.information.value import (
    InformationValue,
    best_action,
    proceed_return,
    stop_exploring,
)
from escapement.state.models import Observation
from escapement.strategy.models import Reversibility


class DerivationDirectionTest(unittest.TestCase):
    """Baseline 5.6 says only "Evidence updates STATE". Contract P5,
    criterion 5 and mutation M3 all presume a pipeline it never draws:
    evidence -> observation -> belief."""

    def setUp(self) -> None:
        self.evidence = Evidence(
            id="e1",
            kind=EvidenceKind.EXECUTION,
            claim="repository contains 14 separable modules",
            source="dependency_inspector",
            produced_by="INSPECT_DEPENDENCY_MAP",
        )

    def test_observation_derives_from_an_evidence_object(self) -> None:
        observation = Observation.derive(
            self.evidence, id="o1", subject="module_count", value=14
        )
        self.assertEqual(observation.evidence_id, "e1")

    def test_evidence_must_state_a_claim(self) -> None:
        with self.assertRaises(ValueError):
            Evidence(id="e2", kind=EvidenceKind.EXECUTION, claim="", source="inspector")

    def test_evidence_must_name_its_source(self) -> None:
        """Origin provenance is what makes evidence auditable; without it
        the memory-contamination mitigation has nothing to check."""
        with self.assertRaises(ValueError):
            Evidence(id="e2", kind=EvidenceKind.EXECUTION, claim="something", source="")

    def test_all_nine_frozen_kinds_are_present(self) -> None:
        self.assertEqual(len(EvidenceKind), 9)


class CapabilityBindingTest(unittest.TestCase):
    """The gap that blocks criterion 3: nothing bound an information
    action to the capability whose cost the EVI subtracts."""

    def setUp(self) -> None:
        self.inspector = Capability(
            id="dependency_inspector",
            kind=CapabilityKind.TOOL,
            description="reads the dependency map",
            provides=("INSPECT_DEPENDENCY_MAP",),
        )
        self.action = InformationAction(
            id="INSPECT_DEPENDENCY_MAP",
            kind=ActionKind.INSPECT_REPOSITORY,
            capability_id="dependency_inspector",
            description="read the module dependency map",
            cost=1,
        )

    def test_consistent_binding_has_no_problems(self) -> None:
        problems = validate_bindings(
            {self.inspector.id: self.inspector}, {self.action.id: self.action}
        )
        self.assertEqual(problems, [])

    def test_unknown_capability_is_reported(self) -> None:
        orphan = InformationAction(
            id="ASK_ARCHITECT",
            kind=ActionKind.ASK_USER,
            capability_id="nobody",
            description="ask",
        )
        problems = validate_bindings({self.inspector.id: self.inspector}, {orphan.id: orphan})
        self.assertEqual(len(problems), 1)
        self.assertIn("unknown capability", problems[0])

    def test_one_sided_declaration_is_reported(self) -> None:
        """The binding is declared on both sides precisely so drift
        between them becomes a startup failure rather than a silent
        inconsistency."""
        undeclared = InformationAction(
            id="INSPECT_TESTS",
            kind=ActionKind.INSPECT_REPOSITORY,
            capability_id="dependency_inspector",
            description="read the test layout",
        )
        problems = validate_bindings(
            {self.inspector.id: self.inspector}, {undeclared.id: undeclared}
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("does not list it", problems[0])

    def test_action_must_name_a_capability(self) -> None:
        with self.assertRaises(ValueError):
            InformationAction(
                id="X", kind=ActionKind.ASK_USER, capability_id="", description="d"
            )

    def test_kind_and_instance_are_separate_levels(self) -> None:
        """Resolves the naming collision: the baseline enumerates action
        kinds (INSPECT_REPOSITORY); criterion 4 requires a concrete
        instance (INSPECT_DEPENDENCY_MAP)."""
        self.assertEqual(self.action.id, "INSPECT_DEPENDENCY_MAP")
        self.assertIs(self.action.kind, ActionKind.INSPECT_REPOSITORY)

    def test_reversibility_lives_on_the_action(self) -> None:
        self.assertIs(self.action.reversibility, Reversibility.HIGH)


class InformationValueTest(unittest.TestCase):
    def test_score_is_improvement_less_cost(self) -> None:
        self.assertEqual(
            InformationValue(action_id="a", expected_improvement=5, cost=2).score, 3
        )

    def test_distinct_figures_come_from_distinct_costs(self) -> None:
        """Criterion 3 wants three EVI figures that differ for a reason,
        not three literals. Mutation M2 makes them identical."""
        values = [
            InformationValue(action_id="INSPECT_DEPENDENCY_MAP", expected_improvement=5, cost=1),
            InformationValue(action_id="ASK_USER", expected_improvement=5, cost=4),
            InformationValue(action_id="INSPECT_SIZE", expected_improvement=2, cost=1),
        ]
        self.assertEqual([v.score for v in values], [4, 1, 1])

    def test_best_action_picks_the_argmax(self) -> None:
        values = [
            InformationValue(action_id="ASK_USER", expected_improvement=5, cost=4),
            InformationValue(action_id="INSPECT_DEPENDENCY_MAP", expected_improvement=5, cost=1),
        ]
        self.assertEqual(best_action(values).action_id, "INSPECT_DEPENDENCY_MAP")

    def test_ties_break_deterministically_on_id(self) -> None:
        """Coarse integer scores make ties common, and criterion 14
        requires byte-identical traces. M8 attacks exactly this."""
        forward = [
            InformationValue(action_id="B_ACTION", expected_improvement=3, cost=1),
            InformationValue(action_id="A_ACTION", expected_improvement=3, cost=1),
        ]
        self.assertEqual(best_action(forward).action_id, "A_ACTION")
        self.assertEqual(best_action(list(reversed(forward))).action_id, "A_ACTION")


class StoppingRuleTest(unittest.TestCase):
    """Marginal Value Theorem: stop when the best remaining information
    action yields less than simply proceeding -- not when a configured
    constant is crossed."""

    def test_keeps_exploring_while_information_beats_proceeding(self) -> None:
        values = [InformationValue(action_id="a", expected_improvement=5, cost=1)]
        should_stop, comparator = stop_exploring(values, comparator=2)
        self.assertFalse(should_stop)
        self.assertEqual(comparator, 2)

    def test_stops_once_information_is_worth_less_than_proceeding(self) -> None:
        values = [InformationValue(action_id="a", expected_improvement=2, cost=1)]
        should_stop, comparator = stop_exploring(values, comparator=3)
        self.assertTrue(should_stop)
        self.assertEqual(comparator, 3)

    def test_comparator_is_returned_for_the_trace(self) -> None:
        """Criterion 8 requires EXPLORATION_STOPPED to carry the value
        actually used; otherwise a constant picked after the fact would
        satisfy the criterion, which is clause A1."""
        _, comparator = stop_exploring([], comparator=7)
        self.assertEqual(comparator, 7)

    def test_exhausted_action_set_stops(self) -> None:
        should_stop, _ = stop_exploring([], comparator=0)
        self.assertTrue(should_stop)


if __name__ == "__main__":
    unittest.main()


class ComputedComparatorTest(unittest.TestCase):
    """Criterion 8 failed two independent reviews because the comparator
    was a module constant echoed straight back: setting it to -3, 0, 3 or
    99 changed the recorded value verbatim, so any stopping behaviour
    could be produced after the fact. It must be derived from state."""

    def test_comparator_rises_with_the_best_strategy_belief(self) -> None:
        """Acting on an ESTABLISHED belief is worth more than acting on a
        PLAUSIBLE one, so the bar for further inspection rises with
        confidence and exploration stops sooner."""
        self.assertEqual(proceed_return([2, 2, 2]), 2)
        self.assertEqual(proceed_return([4, 2, 0]), 4)

    def test_comparator_is_not_merely_the_floor(self) -> None:
        """If it echoed its input the way the old constant did, this
        would return the floor rather than the belief-derived value."""
        self.assertEqual(proceed_return([3], floor=0), 3)

    def test_floor_applies_only_when_it_dominates(self) -> None:
        self.assertEqual(proceed_return([1], floor=2), 2)
        self.assertEqual(proceed_return([], floor=2), 2)

    def test_stronger_beliefs_stop_exploration_sooner(self) -> None:
        values = [InformationValue(action_id="a", expected_improvement=4, cost=1)]
        weak, _ = stop_exploring(values, comparator=proceed_return([2]))
        strong, _ = stop_exploring(values, comparator=proceed_return([4]))
        self.assertFalse(weak)   # EVI 3 > 2, keep looking
        self.assertTrue(strong)  # EVI 3 <= 4, act on what we know
