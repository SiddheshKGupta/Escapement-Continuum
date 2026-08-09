"""Experiment 001: Useful Uncertainty.

A deterministic fixture, not a real repository. The scenario from the
frozen baseline: an agent must choose how to execute work against a
codebase it does not yet understand. Three strategies are plausible.
Inspecting the dependency map has high expected value; once it shows a
highly modular repository, RECURSIVE gains weight and further inspection
stops being worth its cost.

Everything here is in-process and deterministic. Contract precondition P7
forbids network, provider and MCP calls, and section 1 says adding them
would not improve the verdict.
"""

from __future__ import annotations

from escapement.capabilities.models import Capability, CapabilityKind
from escapement.evidence.models import Evidence, EvidenceKind
from escapement.information.action import ActionKind, InformationAction
from escapement.information.value import InformationValue
from escapement.intent.models import Intent
from escapement.state.models import BeliefState
from escapement.strategy.models import Reversibility, Strategy

INTENT = Intent(
    id="exp001",
    outcome="choose an execution strategy for work against an unfamiliar repository",
    success_criteria=("a strategy is committed", "the rationale is recorded"),
    non_goals=("actually executing the work",),
)

CAPABILITIES = {
    "dependency_inspector": Capability(
        id="dependency_inspector",
        kind=CapabilityKind.TOOL,
        description="reads the module dependency map",
        provides=("INSPECT_DEPENDENCY_MAP",),
    ),
    "repo_sizer": Capability(
        id="repo_sizer",
        kind=CapabilityKind.TOOL,
        description="counts files and lines",
        provides=("INSPECT_REPO_SIZE",),
    ),
    "architect": Capability(
        id="architect",
        kind=CapabilityKind.HUMAN,
        description="a human who knows the system",
        provides=("ASK_ARCHITECT",),
    ),
}

ACTIONS = {
    # High value, low cost: this is the one the argmax should pick.
    "INSPECT_DEPENDENCY_MAP": InformationAction(
        id="INSPECT_DEPENDENCY_MAP",
        kind=ActionKind.INSPECT_REPOSITORY,
        capability_id="dependency_inspector",
        description="read the module dependency map",
        cost=1,
    ),
    # Cheap but tells us little about decomposability.
    "INSPECT_REPO_SIZE": InformationAction(
        id="INSPECT_REPO_SIZE",
        kind=ActionKind.INSPECT_REPOSITORY,
        capability_id="repo_sizer",
        description="count files and lines",
        cost=1,
    ),
    # Informative but expensive: a human's time. Distinguishes "highest
    # EVI" from "most informative", which is the point of the comparison.
    "ASK_ARCHITECT": InformationAction(
        id="ASK_ARCHITECT",
        kind=ActionKind.ASK_USER,
        capability_id="architect",
        description="ask the architect how modular the system is",
        cost=5,
    ),
}

STRATEGIES = [
    Strategy(
        id="DIRECT",
        description="one pass over the whole codebase",
        reversibility=Reversibility.HIGH,
        rationale="cheapest if the system is small and tightly coupled",
        next_action="begin editing the codebase in a single pass",
    ),
    Strategy(
        id="SEQUENTIAL",
        description="work module by module in a fixed order",
        reversibility=Reversibility.HIGH,
        rationale="safer than DIRECT when modules are separable",
        next_action="pick the first module and begin",
    ),
    Strategy(
        id="RECURSIVE",
        description="decompose by module and recurse into each",
        reversibility=Reversibility.HIGH,
        rationale="strongest when the system is highly modular",
        next_action="decompose the repository into per-module sub-tasks",
    ),
]

#: What the fixture repository is actually like. The dependency map will
#: reveal it; nothing else will.
_TRUTH_MODULE_COUNT = 14

_EVIDENCE = {
    "INSPECT_DEPENDENCY_MAP": Evidence(
        id="e_depmap",
        kind=EvidenceKind.EXECUTION,
        claim=f"the repository contains {_TRUTH_MODULE_COUNT} separable modules with shallow coupling",
        source="dependency_inspector",
        produced_by="INSPECT_DEPENDENCY_MAP",
        decisive=True,
    ),
    "INSPECT_REPO_SIZE": Evidence(
        id="e_size",
        kind=EvidenceKind.EXECUTION,
        claim="the repository contains 812 files",
        source="repo_sizer",
        produced_by="INSPECT_REPO_SIZE",
    ),
    "ASK_ARCHITECT": Evidence(
        id="e_architect",
        kind=EvidenceKind.USER_FEEDBACK,
        claim="the architect describes the system as modular",
        source="architect",
        produced_by="ASK_ARCHITECT",
        decisive=True,
    ),
}


def perform(action: InformationAction) -> Evidence:
    return _EVIDENCE[action.id]


def evaluate_value(action: InformationAction, beliefs: BeliefState) -> InformationValue:
    """Coarse EVI. Improvement falls once modularity is already known.

    The fall is what makes the second round's stop honest: it is caused
    by the belief actually changing, not by a round counter. Mutation M6
    (skip the second round) and a hardcoded threshold both fail against
    this.
    """
    modularity = beliefs.get("belief:world:modularity")
    already_known = modularity is not None and int(modularity.label) >= 4

    base = {
        "INSPECT_DEPENDENCY_MAP": 5,
        "ASK_ARCHITECT": 5,
        "INSPECT_REPO_SIZE": 2,
    }[action.id]
    improvement = 0 if already_known else base
    return InformationValue(
        action_id=action.id, expected_improvement=improvement, cost=action.cost
    )


def interpret(evidence: Evidence) -> tuple[str, object]:
    if evidence.id == "e_depmap":
        return "module_count", _TRUTH_MODULE_COUNT
    if evidence.id == "e_size":
        return "file_count", 812
    return "architect_opinion", "modular"


def world_belief_of(subject: str) -> str:
    return {
        "module_count": "belief:world:modularity",
        "architect_opinion": "belief:world:modularity",
        "file_count": "belief:world:size",
    }[subject]


def strategy_belief_of(world_belief_id: str) -> str | None:
    """Modularity is what makes recursion attractive. Size is not.

    Returning None for size matters: it proves the strategy belief moves
    because of *what was learned*, not merely because something was
    learned.
    """
    return "RECURSIVE" if world_belief_id == "belief:world:modularity" else None


#: The return of simply proceeding. Compared against EVI by the Marginal
#: Value Theorem rule; exploration continues only while some action beats
#: it.
PROCEED_RETURN = 1
