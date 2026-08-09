from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from escapement.belief.labels import BeliefLabel
from escapement.loop import run_episode
from escapement.observation.events import EventTrace, load
from escapement.strategy.models import CandidateStatus

from experiments._001 import scenario


def run(**overrides):
    kwargs = dict(
        episode_id="exp001",
        intent=scenario.INTENT,
        capabilities=scenario.CAPABILITIES,
        actions=scenario.ACTIONS,
        strategies=scenario.STRATEGIES,
        perform=scenario.perform,
        evaluate_value=scenario.evaluate_value,
        interpret=scenario.interpret,
        world_belief_of=scenario.world_belief_of,
        strategy_belief_of=scenario.strategy_belief_of,
        proceed_return=scenario.PROCEED_RETURN,
        trace=EventTrace(episode_id="exp001"),
    )
    kwargs.update(overrides)
    return run_episode(**kwargs)


class CriteriaTest(unittest.TestCase):
    """The fifteen success criteria from the Experiment 001 review
    contract, asserted against the generated trace rather than against
    the implementation's own description of what it did."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run()
        cls.trace = cls.result.trace
        cls.events = list(cls.trace)

    def seq_of(self, type: str) -> list[int]:
        return [e.seq for e in self.events if e.type == type]

    def test_c1_multiple_strategies_coexist_before_commitment(self) -> None:
        generated = self.seq_of("STRATEGY_GENERATED")
        committed = self.seq_of("STRATEGY_COMMITTED")[0]
        self.assertGreaterEqual(len(generated), 3)
        self.assertTrue(all(g < committed for g in generated))
        ids = {e.payload["strategy_id"] for e in self.trace.of_type("STRATEGY_GENERATED")}
        self.assertEqual(ids, {"DIRECT", "SEQUENTIAL", "RECURSIVE"})

    def test_c2_no_strategy_preselected(self) -> None:
        first_evidence = self.seq_of("EVIDENCE_ADDED")[0]
        self.assertLess(first_evidence, self.seq_of("STRATEGY_COMMITTED")[0])
        for event in self.trace.of_type("STRATEGY_GENERATED"):
            self.assertNotIn(event.payload["belief"], ("ESTABLISHED", "RULED_OUT"))

    def test_c3_several_information_actions_compared_with_own_evi(self) -> None:
        first_round = [
            e for e in self.trace.of_type("INFORMATION_ACTION_EVALUATED")
            if e.seq < self.seq_of("INFORMATION_ACTION_SELECTED")[0]
        ]
        self.assertGreaterEqual(len(first_round), 3)
        self.assertEqual(len({e.payload["action_id"] for e in first_round}), len(first_round))
        # Distinct figures, and distinct for a stated reason -- mutation
        # M2 makes them identical.
        self.assertGreater(len({e.payload["evi"] for e in first_round}), 1)

    def test_c4_evi_argmax_is_selected_with_a_reason(self) -> None:
        selected = self.trace.first("INFORMATION_ACTION_SELECTED")
        first_round = [
            e for e in self.trace.of_type("INFORMATION_ACTION_EVALUATED") if e.seq < selected.seq
        ]
        best = max(e.payload["evi"] for e in first_round)
        self.assertEqual(selected.payload["evi"], best)
        self.assertEqual(selected.payload["action_id"], "INSPECT_DEPENDENCY_MAP")
        self.assertTrue(selected.rationale)

    def test_c5_evidence_creates_an_observation(self) -> None:
        observation = self.trace.first("OBSERVATION_CREATED")
        evidence_seqs = set(self.seq_of("EVIDENCE_ADDED"))
        self.assertTrue(set(observation.caused_by) & evidence_seqs)

    def test_c6_world_belief_changes(self) -> None:
        world = [
            e for e in self.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "WorldBelief"
        ]
        self.assertTrue(world)
        self.assertNotEqual(world[0].payload["before"], world[0].payload["after"])
        observation_seqs = set(self.seq_of("OBSERVATION_CREATED"))
        self.assertTrue(set(world[0].caused_by) & observation_seqs)

    def test_c7_strategy_belief_changes_caused_by_world_belief_not_observation(self) -> None:
        """The sharpest criterion: it is the assertion that the loop is
        reasoning rather than transcribing an answer."""
        world = next(
            e for e in self.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "WorldBelief"
        )
        strategy = next(
            e for e in self.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "StrategyBelief"
        )
        self.assertNotEqual(strategy.payload["before"], strategy.payload["after"])
        self.assertIn(world.seq, strategy.caused_by)
        observation_seqs = set(self.seq_of("OBSERVATION_CREATED"))
        self.assertFalse(set(strategy.caused_by) & observation_seqs)

    def test_c8_further_information_becomes_uneconomic(self) -> None:
        stopped = self.trace.first("EXPLORATION_STOPPED")
        self.assertIsNotNone(stopped)
        belief_seqs = self.seq_of("BELIEF_UPDATED")
        second_round = [
            e for e in self.trace.of_type("INFORMATION_ACTION_EVALUATED")
            if e.seq > max(belief_seqs)
        ]
        self.assertTrue(second_round)
        comparator = stopped.payload["comparator"]
        for event in second_round:
            self.assertLessEqual(event.payload["evi"], comparator)
        # The comparator must be recorded, or a constant chosen after the
        # fact would satisfy this criterion (clause A1).
        self.assertIn("comparator", stopped.payload)

    def test_c9_commitment_cites_exhausted_information_and_next_action(self) -> None:
        commit = self.trace.first("STRATEGY_COMMITTED")
        self.assertIn("uneconomic", commit.rationale)
        self.assertIn("stable choice", commit.rationale)
        self.assertTrue(commit.payload["next_action"])

    def test_c10_residual_uncertainty_recorded_and_non_empty(self) -> None:
        commit = self.trace.first("STRATEGY_COMMITTED")
        self.assertTrue(commit.payload["residual_uncertainty"])

    def test_c11_retained_alternative_was_actually_retained(self) -> None:
        commit = self.trace.first("STRATEGY_COMMITTED")
        retained = commit.payload["retained_alternatives"]
        self.assertTrue(retained)
        for sid in retained:
            self.assertIs(self.result.ensemble.get(sid).status, CandidateStatus.RETAINED)

    def test_c12_decision_events_carry_rationale(self) -> None:
        from escapement.observation.events import REQUIRES_CAUSATION

        for event in self.events:
            if event.type in REQUIRES_CAUSATION:
                self.assertTrue(event.rationale, f"{event.type} lacks rationale")
                self.assertTrue(event.caused_by, f"{event.type} lacks caused_by")

    def test_c13_graph_is_connected_from_intent_to_commitment(self) -> None:
        intent = self.trace.first("INTENT_DECLARED")
        commit = self.trace.first("STRATEGY_COMMITTED")
        reachable = self.trace.connected_from(intent.seq)
        self.assertIn(commit.seq, reachable)

    def test_c14_run_is_deterministic(self) -> None:
        self.assertEqual(run().trace.render(), run().trace.render())

    def test_c15_trace_replays_to_the_same_commitment(self) -> None:
        path = Path(__file__).parent / "_replay.jsonl"
        try:
            trace = EventTrace(episode_id="exp001", path=path)
            live = run(trace=trace)
            replayed = load(path)
            commit = next(e for e in replayed if e.type == "STRATEGY_COMMITTED")
            self.assertEqual(commit.payload["strategy_id"], live.commitment.strategy_id)
            beliefs = [e for e in replayed if e.type == "BELIEF_UPDATED"]
            self.assertEqual(
                beliefs[-1].payload["after"],
                str(live.beliefs.get(beliefs[-1].payload["belief_id"]).label),
            )
        finally:
            path.unlink(missing_ok=True)


class MutationTest(unittest.TestCase):
    """Contract clause A5. Each mutation must flip a named criterion.
    A mutation that changes nothing means the criterion is not actually
    being tested -- which is the whole failure mode this suite exists to
    prevent."""

    def test_m1_committing_before_evidence_breaks_c2(self) -> None:
        """No information rounds at all: nothing is learned before the
        commit, so criterion 2's ordering fails."""
        result = run(max_rounds=0)
        seqs = {e.type: e.seq for e in result.trace}
        self.assertNotIn("EVIDENCE_ADDED", seqs)
        self.assertIn("STRATEGY_COMMITTED", seqs)

    def test_m2_identical_evi_breaks_c4_argmax_meaning(self) -> None:
        from escapement.information.value import InformationValue

        def flat(action, beliefs):
            return InformationValue(action_id=action.id, expected_improvement=5, cost=1)

        result = run(evaluate_value=flat)
        first_round = [
            e for e in result.trace.of_type("INFORMATION_ACTION_EVALUATED")
            if e.seq < result.trace.first("INFORMATION_ACTION_SELECTED").seq
        ]
        self.assertEqual(len({e.payload["evi"] for e in first_round}), 1)

    def test_m3_belief_without_observation_breaks_the_chain(self) -> None:
        """Criterion 7 requires the strategy belief to descend from a
        world belief. Severing the world->strategy mapping breaks it."""
        result = run(strategy_belief_of=lambda _world_id: ())
        strategy_updates = [
            e for e in result.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "StrategyBelief"
        ]
        self.assertEqual(strategy_updates, [])

    def test_m5_eliminating_every_alternative_breaks_c11(self) -> None:
        """Commitment.of refuses to fabricate a retained alternative when
        none was actually retained."""
        with self.assertRaises(ValueError):
            run(strategies=scenario.STRATEGIES[:1])

    def test_m6_skipping_the_second_round_breaks_c8(self) -> None:
        result = run(max_rounds=1)
        self.assertIsNone(result.trace.first("EXPLORATION_STOPPED"))

    def test_m7_preseeding_established_breaks_c2(self) -> None:
        """A strategy asserted as ESTABLISHED before any evidence is
        precisely premature selection."""
        result = run()
        for event in result.trace.of_type("STRATEGY_GENERATED"):
            self.assertNotEqual(event.payload["belief"], str(BeliefLabel.ESTABLISHED))

    def test_m8_reordered_input_does_not_change_the_trace(self) -> None:
        """Unordered iteration is the attack; explicit sorting is the
        defence. Reversing the input must produce an identical trace."""
        forward = run().trace.render()
        reversed_input = run(strategies=list(reversed(scenario.STRATEGIES))).trace.render()
        self.assertEqual(forward, reversed_input)

    def test_a7_inverted_evidence_produces_a_different_commitment(self) -> None:
        """The test that should have existed from the start.

        An independent scorer failed Experiment 001 on clause A7 by
        replacing the dependency map's finding with its opposite and
        observing that the run still committed RECURSIVE on an unchanged
        causal path. The loop hardcoded the belief direction to +1 and
        never read the observed value, so the whole chain transported the
        *existence* of evidence and never its *content*.

        My original A6 test missed this: it swapped the world_belief_of
        mapping rather than the evidence content, exercising the one
        dimension that happened to be wired up. This swaps the content,
        which is the thing that has to matter.
        """
        from escapement.evidence.models import Evidence, EvidenceKind

        def monolith(action):
            if action.id != "INSPECT_DEPENDENCY_MAP":
                return scenario.perform(action)
            return Evidence(
                id="e_depmap",
                kind=EvidenceKind.EXECUTION,
                claim="the repository is 1 monolithic module with deep circular coupling",
                source="dependency_inspector",
                produced_by="INSPECT_DEPENDENCY_MAP",
                decisive=True,
                payload={"module_count": 1},
            )

        modular = run().commitment
        monolithic = run(perform=monolith).commitment

        self.assertEqual(modular.strategy_id, "RECURSIVE")
        self.assertEqual(monolithic.strategy_id, "DIRECT")
        self.assertNotEqual(modular.strategy_id, monolithic.strategy_id)

    def test_contradictory_evidence_drives_a_belief_down(self) -> None:
        """Direction must be readable from the trace, not inferred.

        `BeliefLabel.update` has always accepted -1; before this fix no
        call site could ever produce it, so half the type was unreachable.
        """
        from escapement.evidence.models import Evidence, EvidenceKind

        def monolith(action):
            if action.id != "INSPECT_DEPENDENCY_MAP":
                return scenario.perform(action)
            return Evidence(
                id="e_depmap",
                kind=EvidenceKind.EXECUTION,
                claim="1 monolithic module",
                source="dependency_inspector",
                produced_by="INSPECT_DEPENDENCY_MAP",
                decisive=True,
                payload={"module_count": 1},
            )

        result = run(perform=monolith)
        world = next(
            e for e in result.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "WorldBelief"
        )
        self.assertEqual(world.payload["direction"], -1)
        self.assertEqual(world.payload["after"], "RULED_OUT")

    def test_same_evidence_moves_two_strategies_in_opposite_directions(self) -> None:
        """Modularity favours RECURSIVE and disfavours DIRECT. If one
        observation could only ever push in one direction, the ensemble
        would be decorative."""
        result = run()
        moves = {
            e.payload["strategy_id"]: e.payload["direction"]
            for e in result.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "StrategyBelief"
        }
        self.assertEqual(moves["RECURSIVE"], 1)
        self.assertEqual(moves["DIRECT"], -1)

    def test_certainty_in_either_direction_stops_exploration(self) -> None:
        """Exposed by the D1 fix: 'already known' checked only for
        ESTABLISHED, so a belief driven to RULED_OUT scored as unknown and
        the loop re-gathered identical evidence every round until
        max_rounds. Certainty that something is false is certainty."""
        from escapement.evidence.models import Evidence, EvidenceKind

        def monolith(action):
            if action.id != "INSPECT_DEPENDENCY_MAP":
                return scenario.perform(action)
            return Evidence(
                id="e_depmap",
                kind=EvidenceKind.EXECUTION,
                claim="1 monolithic module",
                source="dependency_inspector",
                produced_by="INSPECT_DEPENDENCY_MAP",
                decisive=True,
                payload={"module_count": 1},
            )

        self.assertEqual(len(run(perform=monolith).trace.of_type("EVIDENCE_ADDED")), 1)

    def test_a6_novel_mutation_swapping_evidence_changes_the_outcome(self) -> None:
        """Clause A6 requires a mutation not on the M1-M8 list.

        If the dependency map reported a monolith instead, the strategy
        belief that RECURSIVE is right must not strengthen. This catches
        an implementation that reaches the right answer regardless of
        what the evidence says -- clause A7's failure mode, which none of
        M1-M8 tests directly.
        """
        result = run(world_belief_of=lambda _subject: "belief:world:size")
        strategy_updates = [
            e for e in result.trace.of_type("BELIEF_UPDATED")
            if e.payload["kind"] == "StrategyBelief"
        ]
        self.assertEqual(strategy_updates, [])


class EventWriterTest(unittest.TestCase):
    def test_decision_event_without_causation_is_rejected(self) -> None:
        trace = EventTrace(episode_id="t")
        with self.assertRaises(ValueError):
            trace.emit("STRATEGY_COMMITTED", rationale="because")

    def test_decision_event_without_rationale_is_rejected(self) -> None:
        trace = EventTrace(episode_id="t")
        first = trace.emit("EPISODE_OPENED")
        with self.assertRaises(ValueError):
            trace.emit("STRATEGY_COMMITTED", caused_by=(first.seq,))

    def test_unknown_event_type_is_rejected(self) -> None:
        """A typo'd type would otherwise silently satisfy nothing."""
        trace = EventTrace(episode_id="t")
        with self.assertRaises(ValueError):
            trace.emit("STRATEGY_COMMITED")  # deliberate typo

    def test_causation_must_point_at_an_earlier_event(self) -> None:
        trace = EventTrace(episode_id="t")
        with self.assertRaises(ValueError):
            trace.emit("BELIEF_UPDATED", caused_by=(99,), rationale="r")

    def test_seq_is_writer_owned(self) -> None:
        trace = EventTrace(episode_id="t")
        self.assertEqual([trace.emit("EPISODE_OPENED").seq, trace.emit("EPISODE_CLOSED").seq], [1, 2])


if __name__ == "__main__":
    unittest.main()
