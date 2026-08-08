from __future__ import annotations

import unittest

from escapement.belief.labels import UNKNOWN, BeliefLabel, Decisiveness, contracted, update
from escapement.capabilities.models import Capability, CapabilityKind
from escapement.evidence.models import Evidence, EvidenceKind
from escapement.intent.models import Intent
from escapement.policy.models import Invariant, Policy, Zone
from escapement.state.models import Belief, BeliefState, Observation, ObservedState
from escapement.strategy.models import CandidateStatus, Commitment, Reversibility, Strategy, StrategyEnsemble


class BeliefLabelTest(unittest.TestCase):
    def test_ordinary_evidence_moves_one_step(self) -> None:
        self.assertIs(update(BeliefLabel.PLAUSIBLE, +1), BeliefLabel.LIKELY)
        self.assertIs(update(BeliefLabel.PLAUSIBLE, -1), BeliefLabel.UNLIKELY)

    def test_decisive_evidence_may_move_further(self) -> None:
        self.assertIs(
            update(BeliefLabel.PLAUSIBLE, +1, Decisiveness.DECISIVE),
            BeliefLabel.ESTABLISHED,
        )

    def test_movement_is_clamped_at_the_endpoints(self) -> None:
        self.assertIs(update(BeliefLabel.ESTABLISHED, +1), BeliefLabel.ESTABLISHED)
        self.assertIs(update(BeliefLabel.RULED_OUT, -1), BeliefLabel.RULED_OUT)

    def test_a_single_ordinary_observation_cannot_cross_the_whole_range(self) -> None:
        """Foundations section 4: the one-step cap exists so a single
        confident-sounding observation cannot drive RULED_OUT to
        ESTABLISHED. That is the overconfidence the representation exists
        to prevent."""
        self.assertIs(update(BeliefLabel.RULED_OUT, +1), BeliefLabel.UNLIKELY)

    def test_unknown_is_the_midpoint_not_a_leaning(self) -> None:
        self.assertIs(UNKNOWN, BeliefLabel.PLAUSIBLE)

    def test_contraction_detects_movement_away_from_ignorance(self) -> None:
        self.assertTrue(contracted(BeliefLabel.PLAUSIBLE, BeliefLabel.LIKELY))
        self.assertTrue(contracted(BeliefLabel.PLAUSIBLE, BeliefLabel.UNLIKELY))
        self.assertFalse(contracted(BeliefLabel.LIKELY, BeliefLabel.PLAUSIBLE))

    def test_direction_must_be_explicit(self) -> None:
        with self.assertRaises(ValueError):
            update(BeliefLabel.PLAUSIBLE, 0)

    def test_no_probability_accessor_exists(self) -> None:
        """Adding one would reintroduce the false precision this
        representation exists to prevent, so its absence is asserted."""
        self.assertFalse(hasattr(BeliefLabel.PLAUSIBLE, "probability"))


class ObservedNotBelievedTest(unittest.TestCase):
    """Contract precondition P5: ObservedState and BeliefState are
    separate types and nothing promotes a belief into an observation."""

    def test_observation_cannot_be_built_without_evidence(self) -> None:
        with self.assertRaises(TypeError):
            Observation(id="o1", subject="modular", value=True)  # type: ignore[call-arg]

    def test_the_two_stores_do_not_accept_each_others_types(self) -> None:
        observed = ObservedState()
        beliefs = BeliefState()

        observation = Observation(id="o1", subject="module_count", value=14, evidence_id="e1")
        belief = Belief(id="b1", kind="WorldBelief", proposition="repo is modular")

        observed.record(observation)
        beliefs.hold(belief)

        self.assertIsNone(observed.get("b1"))
        self.assertIsNone(beliefs.get("o1"))

    def test_no_promotion_path_exists_on_either_store(self) -> None:
        for forbidden in ("promote", "to_observation", "as_fact", "believe_as_observed"):
            self.assertFalse(hasattr(BeliefState(), forbidden))
            self.assertFalse(hasattr(Belief(id="b", kind="WorldBelief", proposition="p"), forbidden))

    def test_belief_kinds_are_distinguishable(self) -> None:
        """Criterion 7 requires a StrategyBelief change caused by a
        WorldBelief change, so the two must be separable."""
        beliefs = BeliefState()
        beliefs.hold(Belief(id="b1", kind="WorldBelief", proposition="repo is modular"))
        beliefs.hold(Belief(id="b2", kind="StrategyBelief", proposition="recursive will work"))

        self.assertEqual([b.id for b in beliefs.of_kind("WorldBelief")], ["b1"])
        self.assertEqual([b.id for b in beliefs.of_kind("StrategyBelief")], ["b2"])

    def test_relabelling_produces_a_new_belief_rather_than_mutating(self) -> None:
        original = Belief(id="b1", kind="WorldBelief", proposition="repo is modular")
        updated = original.with_label(BeliefLabel.LIKELY)
        self.assertIs(original.label, UNKNOWN)
        self.assertIs(updated.label, BeliefLabel.LIKELY)


class CommitmentTest(unittest.TestCase):
    """Contract clause A2: an empty collection is a no-op assertion and
    must FAIL rather than pass. Enforced at construction so a
    contract-violating commitment cannot be recorded at all."""

    def test_valid_commitment_is_accepted(self) -> None:
        commitment = Commitment(
            strategy_id="RECURSIVE",
            rationale="further information is uneconomic and the next action needs a stable choice",
            residual_uncertainty=("module coupling is only partly known",),
            retained_alternatives=("SEQUENTIAL",),
        )
        self.assertEqual(commitment.strategy_id, "RECURSIVE")

    def test_empty_residual_uncertainty_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Commitment(
                strategy_id="RECURSIVE",
                rationale="because",
                residual_uncertainty=(),
                retained_alternatives=("SEQUENTIAL",),
            )

    def test_empty_retained_alternatives_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Commitment(
                strategy_id="RECURSIVE",
                rationale="because",
                residual_uncertainty=("something",),
                retained_alternatives=(),
            )

    def test_missing_rationale_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Commitment(
                strategy_id="RECURSIVE",
                rationale="",
                residual_uncertainty=("something",),
                retained_alternatives=("SEQUENTIAL",),
            )


class PolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.direct = Strategy(id="DIRECT", description="single pass", reversibility=Reversibility.HIGH)
        self.destructive = Strategy(
            id="DESTRUCTIVE", description="rewrite history", reversibility=Reversibility.LOW
        )
        self.policy = Policy(
            invariants=[Invariant(id="i1", description="no history rewriting", forbids=("DESTRUCTIVE",))]
        )

    def test_forbidden_strategy_is_rejected_with_its_reason(self) -> None:
        permitted, rejected = self.policy.filter([self.direct, self.destructive])
        self.assertEqual([s.id for s in permitted], ["DIRECT"])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0][1].id, "i1")

    def test_rejections_are_returned_not_silently_dropped(self) -> None:
        """Criterion 13 requires every transition to be explainable; a
        candidate vanishing without a recorded reason breaks the chain."""
        _, rejected = self.policy.filter([self.destructive])
        self.assertTrue(rejected[0][1].description)

    def test_zones_follow_invariants_then_reversibility(self) -> None:
        self.assertIs(self.policy.zone_for(self.destructive), Zone.BLACK)
        self.assertIs(self.policy.zone_for(self.direct), Zone.WHITE)

        risky_but_allowed = Strategy(
            id="MIGRATE", description="schema migration", reversibility=Reversibility.LOW
        )
        self.assertIs(self.policy.zone_for(risky_but_allowed), Zone.GREY)


class IntentTest(unittest.TestCase):
    def test_all_criteria_required_for_satisfaction(self) -> None:
        intent = Intent(
            id="i1",
            outcome="choose an execution strategy",
            success_criteria=("strategy chosen", "rationale recorded"),
        )
        self.assertFalse(intent.satisfied_by({"strategy chosen"}))
        self.assertTrue(intent.satisfied_by({"strategy chosen", "rationale recorded"}))

    def test_intent_without_criteria_is_never_satisfied(self) -> None:
        """An intent with nothing to measure cannot be declared met."""
        self.assertFalse(Intent(id="i1", outcome="do something good").satisfied_by(set()))


class EnsembleAndCapabilityTest(unittest.TestCase):
    def test_ensemble_holds_candidates_simultaneously(self) -> None:
        ensemble = StrategyEnsemble()
        for sid in ("DIRECT", "SEQUENTIAL", "RECURSIVE"):
            ensemble.add(Strategy(id=sid, description=sid.lower()))
        self.assertEqual(ensemble.ids(), ["DIRECT", "RECURSIVE", "SEQUENTIAL"])

    def test_ensemble_has_no_amplitude_or_phase(self) -> None:
        """Foundations section 10.3: this is a mixture, not a
        superposition. It must never acquire quantum-style attributes."""
        strategy = Strategy(id="DIRECT", description="single pass")
        for forbidden in ("amplitude", "phase", "wavefunction"):
            self.assertFalse(hasattr(strategy, forbidden))

    def test_escapement_v1_is_representable_as_a_capability(self) -> None:
        """The identity claim made concrete: v1 is one capability among
        many, not the agent."""
        v1 = Capability(
            id="escapement_v1", kind=CapabilityKind.HARNESS, description="governed repository delivery"
        )
        self.assertIs(v1.kind, CapabilityKind.HARNESS)

    def test_capability_carries_no_invented_reliability(self) -> None:
        capability = Capability(id="claude", kind=CapabilityKind.MODEL, description="reasoning")
        for forbidden in ("reliability", "cost", "latency"):
            self.assertFalse(hasattr(capability, forbidden))


class EvidenceTest(unittest.TestCase):
    def test_evidence_records_its_provenance(self) -> None:
        evidence = Evidence(
            id="e1",
            kind=EvidenceKind.EXECUTION,
            claim="repository contains 14 separable modules",
            source="dependency_inspector",
            produced_by="INSPECT_DEPENDENCY_MAP",
        )
        self.assertEqual(evidence.source, "dependency_inspector")
        self.assertEqual(evidence.produced_by, "INSPECT_DEPENDENCY_MAP")

    def test_evidence_defaults_to_non_decisive(self) -> None:
        """Decisiveness must be claimed deliberately, since it unlocks
        multi-step belief movement."""
        evidence = Evidence(
            id="e1", kind=EvidenceKind.BEHAVIOURAL, claim="looks modular", source="glance"
        )
        self.assertFalse(evidence.decisive)


if __name__ == "__main__":
    unittest.main()


class CandidateLifecycleTest(unittest.TestCase):
    """Added after an independent review found criterion 11 was not
    representable: the model could not distinguish a retained alternative
    from an eliminated one."""

    def setUp(self) -> None:
        self.ensemble = StrategyEnsemble()
        for sid in ("DIRECT", "SEQUENTIAL", "RECURSIVE"):
            self.ensemble.add(Strategy(id=sid, description=sid.lower()))

    def test_eliminated_strategy_must_say_why(self) -> None:
        with self.assertRaises(ValueError):
            Strategy(id="DIRECT", description="d", status=CandidateStatus.ELIMINATED)

    def test_eliminated_strategy_is_marked_not_deleted(self) -> None:
        """Baseline section 17 says remove; we mark instead, because
        removal destroys the distinction criterion 11 tests."""
        direct = self.ensemble.get("DIRECT").eliminate("context budget exceeded")
        self.ensemble.add(direct)
        self.assertIn("DIRECT", self.ensemble.ids())
        self.assertIs(self.ensemble.get("DIRECT").status, CandidateStatus.ELIMINATED)
        self.assertTrue(self.ensemble.get("DIRECT").eliminated_because)

    def test_commitment_derives_retained_from_actual_status(self) -> None:
        self.ensemble.add(self.ensemble.get("DIRECT").eliminate("context budget exceeded"))
        self.ensemble.add(self.ensemble.get("SEQUENTIAL").retain())
        chosen = self.ensemble.get("RECURSIVE").commit()
        self.ensemble.add(chosen)

        commitment = Commitment.of(
            chosen=chosen,
            ensemble=self.ensemble,
            rationale="information exhausted; next action needs a stable choice",
            residual_uncertainty=("coupling only partly known",),
        )
        self.assertEqual(commitment.retained_alternatives, ("SEQUENTIAL",))

    def test_eliminated_strategy_cannot_pose_as_retained(self) -> None:
        """The vacuous pass contract clause A1 forbids: satisfying
        criterion 11 with an already-eliminated candidate."""
        self.ensemble.add(self.ensemble.get("DIRECT").eliminate("too coarse"))
        self.ensemble.add(self.ensemble.get("SEQUENTIAL").eliminate("too slow"))
        chosen = self.ensemble.get("RECURSIVE").commit()
        self.ensemble.add(chosen)

        with self.assertRaises(ValueError):
            Commitment.of(
                chosen=chosen,
                ensemble=self.ensemble,
                rationale="everything else eliminated",
                residual_uncertainty=("something",),
            )

    def test_next_action_is_available_for_criterion_9(self) -> None:
        strategy = Strategy(
            id="RECURSIVE",
            description="decompose by module",
            next_action="spawn analysis of the billing module",
        )
        self.assertTrue(strategy.next_action)
