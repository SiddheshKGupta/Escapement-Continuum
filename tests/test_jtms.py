from __future__ import annotations

import unittest

from escapement.jtms.core import JTMS, JTMSError, Label


class PremiseAndDerivationTest(unittest.TestCase):
    def test_premise_is_believed_unconditionally(self) -> None:
        jtms = JTMS()
        jtms.premise("repo_inspected", rationale="the inspection ran")
        self.assertIs(jtms.label("repo_inspected"), Label.IN)

    def test_unjustified_node_is_out_not_missing(self) -> None:
        """OUT is a belief state, not an absence.

        The distinction matters: an unsupported node must remain
        addressable so a later justification can bring it IN.
        """
        jtms = JTMS()
        jtms.node("modular")
        self.assertIs(jtms.label("modular"), Label.OUT)
        self.assertIn("modular", jtms.nodes())

    def test_derived_node_follows_its_antecedent(self) -> None:
        jtms = JTMS()
        jtms.premise("high_module_count", rationale="dependency map shows 14 modules")
        jtms.justify(
            "modular",
            in_list=["high_module_count"],
            rationale="many separable modules implies modularity",
        )
        self.assertIs(jtms.label("modular"), Label.IN)

    def test_chain_propagates_transitively(self) -> None:
        jtms = JTMS()
        jtms.premise("high_module_count", rationale="observed")
        jtms.justify("modular", in_list=["high_module_count"], rationale="implies modularity")
        jtms.justify("recursive_viable", in_list=["modular"], rationale="modularity suits recursion")
        self.assertIs(jtms.label("recursive_viable"), Label.IN)


class RetractionTest(unittest.TestCase):
    """The property that makes a TMS worth having over hand-rolled
    invalidation: retracting support marks dependents OUT without
    destroying them, so support can be restored."""

    def setUp(self) -> None:
        self.jtms = JTMS()
        self.premise = self.jtms.premise("high_module_count", rationale="observed")
        self.jtms.justify("modular", in_list=["high_module_count"], rationale="implies modularity")
        self.jtms.justify("recursive_viable", in_list=["modular"], rationale="suits recursion")

    def test_retraction_propagates_to_dependents(self) -> None:
        self.jtms.retract(self.premise.id)
        self.assertIs(self.jtms.label("modular"), Label.OUT)
        self.assertIs(self.jtms.label("recursive_viable"), Label.OUT)

    def test_retracted_nodes_are_stale_not_deleted(self) -> None:
        self.jtms.retract(self.premise.id)
        self.assertIn("modular", self.jtms.nodes())
        self.assertIn("recursive_viable", self.jtms.nodes())

    def test_restoring_support_revives_the_chain(self) -> None:
        self.jtms.retract(self.premise.id)
        self.jtms.premise("high_module_count", rationale="re-inspected, confirmed")
        self.assertIs(self.jtms.label("modular"), Label.IN)
        self.assertIs(self.jtms.label("recursive_viable"), Label.IN)

    def test_alternative_support_keeps_a_node_in(self) -> None:
        """A node with two independent reasons survives losing one."""
        self.jtms.premise("user_confirmed_modular", rationale="the user said so")
        self.jtms.justify(
            "modular", in_list=["user_confirmed_modular"], rationale="user confirmation"
        )
        self.jtms.retract(self.premise.id)
        self.assertIs(self.jtms.label("modular"), Label.IN)


class NonMonotonicTest(unittest.TestCase):
    def test_out_list_justification_fires_only_while_antecedent_is_out(self) -> None:
        jtms = JTMS()
        jtms.justify(
            "assume_monolith",
            out_list=["modular"],
            rationale="default assumption absent evidence of modularity",
        )
        self.assertIs(jtms.label("assume_monolith"), Label.IN)

        jtms.premise("high_module_count", rationale="observed")
        jtms.justify("modular", in_list=["high_module_count"], rationale="implies modularity")

        self.assertIs(jtms.label("modular"), Label.IN)
        self.assertIs(jtms.label("assume_monolith"), Label.OUT)

    def test_odd_cycle_raises_rather_than_returning_an_arbitrary_state(self) -> None:
        """A network with no stable labelling must fail loudly.

        Returning whichever state the fixpoint loop happened to stop on
        would be a silently wrong answer, which is worse than an error.
        """
        jtms = JTMS()
        with self.assertRaises(JTMSError):
            jtms.justify("p", out_list=["p"], rationale="self-defeating")


class ExplanationTest(unittest.TestCase):
    """`explain()` is the source of `caused_by` in the Experiment 001
    event trace. Because it is derived from the live network it cannot
    drift from the reasoning that actually produced the belief."""

    def test_explanation_orders_antecedents_before_consequents(self) -> None:
        jtms = JTMS()
        jtms.premise("high_module_count", rationale="dependency map shows 14 modules")
        jtms.justify("modular", in_list=["high_module_count"], rationale="implies modularity")
        jtms.justify("recursive_viable", in_list=["modular"], rationale="suits recursion")

        chain = jtms.explain("recursive_viable")
        rationales = [j.rationale for j in chain]
        self.assertEqual(
            rationales,
            [
                "dependency map shows 14 modules",
                "implies modularity",
                "suits recursion",
            ],
        )

    def test_out_node_has_no_explanation(self) -> None:
        jtms = JTMS()
        jtms.node("modular")
        self.assertEqual(jtms.explain("modular"), [])

    def test_explanation_reflects_the_actual_support_not_the_first_added(self) -> None:
        """If the original support is retracted, the explanation must
        follow the surviving justification -- otherwise `caused_by` would
        cite a reason that is no longer operative."""
        jtms = JTMS()
        first = jtms.premise("map_inspection", rationale="dependency map inspected")
        jtms.justify("modular", in_list=["map_inspection"], rationale="from the map")
        jtms.premise("user_statement", rationale="user described the architecture")
        jtms.justify("modular", in_list=["user_statement"], rationale="from the user")

        jtms.retract(first.id)

        chain = jtms.explain("modular")
        self.assertEqual([j.rationale for j in chain], ["user described the architecture", "from the user"])


class ContractTest(unittest.TestCase):
    def test_justification_without_rationale_is_rejected(self) -> None:
        """Contract criterion 12 requires rationale on every decision
        event. Enforcing it at construction means a trace cannot be
        emitted without one."""
        jtms = JTMS()
        with self.assertRaises(ValueError):
            jtms.justify("modular", in_list=[], rationale="")


if __name__ == "__main__":
    unittest.main()
