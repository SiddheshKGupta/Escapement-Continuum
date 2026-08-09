"""The canonical execution loop.

Frozen baseline section 6. This is the piece that makes the identity
claim real: **the loop owns the reasoning, and models are capabilities
inside it.** A model does not decide when to stop gathering information
or when to commit -- this function does, and it would run identically
with a human, a tool, or a harness supplying the evidence.

    INTENT
      -> observed + belief state
      -> strategy ensemble
      -> is uncertainty worth reducing?
           yes -> information action -> evidence -> update beliefs
           no  -> commitment required? -> policy gate -> action
      -> evidence -> new state -> repeat

Deliberately synchronous and deliberately free of I/O. Every capability
is injected. Contract precondition P7 forbids any network, provider or
MCP call during an Experiment 001 run, and the cheapest way to guarantee
that is a loop that has no way to make one.

Determinism (criterion 14) is a property of this module, not an accident:
every ordering decision is explicit, every collection is sorted before
iteration, and nothing consults wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from escapement.belief.labels import BeliefLabel, Decisiveness, update
from escapement.capabilities.models import Capability, validate_bindings
from escapement.evidence.models import Evidence, Interpretation
from escapement.information.action import InformationAction
from escapement.information.value import InformationValue, best_action, stop_exploring
from escapement.jtms.core import JTMS
from escapement.observation.events import EventTrace
from escapement.state.models import Belief, BeliefState, Observation, ObservedState
from escapement.strategy.models import (
    CandidateStatus,
    Commitment,
    Strategy,
    StrategyEnsemble,
)
from escapement.intent.models import Intent


class Performs(Protocol):
    """Executes an information action and returns evidence.

    The seam where a real capability -- a model, a tool, a human -- would
    attach. Experiment 001 supplies a deterministic fixture, which is why
    the run needs no provider.
    """

    def __call__(self, action: InformationAction) -> Evidence: ...


@dataclass
class LoopResult:
    commitment: Commitment
    trace: EventTrace
    observed: ObservedState
    beliefs: BeliefState
    ensemble: StrategyEnsemble
    jtms: JTMS


def run_episode(
    *,
    episode_id: str,
    intent: Intent,
    capabilities: dict[str, Capability],
    actions: dict[str, InformationAction],
    strategies: list[Strategy],
    perform: Performs,
    evaluate_value: Callable[[InformationAction, BeliefState], InformationValue],
    interpret: Callable[[Evidence], Interpretation],
    world_belief_of: Callable[[str], str],
    #: Maps a world-belief id to the strategies it bears on, each with a
    #: correlation of +1 (this proposition favours the strategy) or -1
    #: (it disfavours it). Returning correlations rather than a single
    #: strategy name is what lets one observation strengthen one route
    #: while weakening another.
    strategy_belief_of: Callable[[str], tuple[tuple[str, int], ...]],
    proceed_return: int,
    trace: EventTrace,
    max_rounds: int = 5,
) -> LoopResult:
    """Run one episode to commitment.

    The injected callables are the deliberate seams. `perform` executes,
    `evaluate_value` scores, `interpret` turns evidence into a fact, and
    the two `*_belief_of` functions map subjects to belief ids. Injecting
    them keeps the loop's own logic -- the ordering, the stopping rule,
    the commitment condition -- free of anything experiment-specific, so
    Experiment 002 can reuse it unchanged.
    """
    problems = validate_bindings(capabilities, actions)
    if problems:
        raise ValueError(f"capability/action bindings inconsistent: {problems}")

    observed = ObservedState()
    beliefs = BeliefState()
    ensemble = StrategyEnsemble()
    jtms = JTMS()

    opened = trace.emit("EPISODE_OPENED", payload={"episode_id": episode_id})
    declared = trace.emit(
        "INTENT_DECLARED",
        payload={
            "outcome": intent.outcome,
            "success_criteria": list(intent.success_criteria),
            "non_goals": list(intent.non_goals),
        },
    )

    # -- strategy ensemble ------------------------------------------------
    # Criterion 1: several strategies coexist before any commitment.
    # Criterion 2: none starts at ESTABLISHED, so none is pre-selected.
    for strategy in sorted(strategies, key=lambda s: s.id):
        ensemble.add(strategy)
        belief_id = f"belief:strategy:{strategy.id}"
        beliefs.hold(
            Belief(
                id=belief_id,
                kind="StrategyBelief",
                proposition=f"{strategy.id} is the right execution route",
            )
        )
        trace.emit(
            "STRATEGY_GENERATED",
            payload={
                "strategy_id": strategy.id,
                "reversibility": strategy.reversibility.value,
                "belief": str(beliefs.get(belief_id).label),
            },
        )

    # -- information rounds -----------------------------------------------
    last_evidence_seq: int | None = None
    last_belief_seq: int | None = None
    comparator_used = proceed_return

    for _round in range(max_rounds):
        # Criterion 3: several information actions compared, each scored.
        values: list[InformationValue] = []
        evaluated_seqs: list[int] = []
        for action_id in sorted(actions):
            action = actions[action_id]
            value = evaluate_value(action, beliefs)
            values.append(value)
            event = trace.emit(
                "INFORMATION_ACTION_EVALUATED",
                payload={
                    "action_id": action.id,
                    "kind": action.kind.value,
                    "capability_id": action.capability_id,
                    "expected_improvement": value.expected_improvement,
                    "cost": value.cost,
                    "evi": value.score,
                },
            )
            evaluated_seqs.append(event.seq)

        # Criterion 8: stop when the best action is worth less than
        # proceeding. Marginal Value Theorem, so the comparator is
        # computed rather than configured -- and recorded, or a constant
        # chosen after the fact would satisfy the criterion (clause A1).
        should_stop, comparator_used = stop_exploring(values, proceed_return=proceed_return)
        if should_stop:
            trace.emit(
                "EXPLORATION_STOPPED",
                payload={
                    "comparator": comparator_used,
                    "best_evi": max((v.score for v in values), default=None),
                    "rule": "marginal-value-theorem",
                },
                caused_by=tuple(evaluated_seqs),
                rationale=(
                    "no remaining information action yields more than the "
                    f"expected return of proceeding ({comparator_used})"
                ),
            )
            break

        # Criterion 4: the argmax is selected, with a stated reason.
        chosen_value = best_action(values)
        chosen_action = actions[chosen_value.action_id]
        selected = trace.emit(
            "INFORMATION_ACTION_SELECTED",
            payload={"action_id": chosen_action.id, "evi": chosen_value.score},
            caused_by=tuple(evaluated_seqs),
            rationale=(
                f"{chosen_action.id} has the highest expected value of "
                f"information ({chosen_value.score}) and exceeds the "
                f"return of proceeding ({comparator_used})"
            ),
        )

        executed = trace.emit(
            "INFORMATION_ACTION_EXECUTED",
            payload={"action_id": chosen_action.id},
            caused_by=(selected.seq,),
        )

        evidence = perform(chosen_action)
        evidence_event = trace.emit(
            "EVIDENCE_ADDED",
            payload={
                "evidence_id": evidence.id,
                "kind": evidence.kind.value,
                "claim": evidence.claim,
                "source": evidence.source,
                "decisive": evidence.decisive,
            },
            caused_by=(executed.seq,),
        )
        last_evidence_seq = evidence_event.seq

        # Criterion 5: evidence creates an observation, never a belief.
        interpretation = interpret(evidence)
        subject, value = interpretation.subject, interpretation.value
        observation = Observation.derive(
            evidence, id=f"obs:{evidence.id}", subject=subject, value=value
        )
        observed.record(observation)
        observation_event = trace.emit(
            "OBSERVATION_CREATED",
            payload={"observation_id": observation.id, "subject": subject, "value": value},
            caused_by=(evidence_event.seq,),
        )
        jtms.premise(
            f"observed:{observation.id}",
            rationale=f"{subject} = {value} (evidence {evidence.id})",
        )

        # Criterion 6: a world belief moves, caused by the observation,
        # *in the direction the evidence actually points*. The direction
        # comes from interpretation.supports, not from a constant -- see
        # Interpretation's docstring for the defect this replaced.
        world_id = world_belief_of(subject)
        before = beliefs.get(world_id) or Belief(
            id=world_id, kind="WorldBelief", proposition=world_id
        )
        after = before.with_label(
            update(
                before.label,
                interpretation.supports,
                Decisiveness.DECISIVE if evidence.decisive else Decisiveness.ORDINARY,
            )
        )
        beliefs.hold(after)
        direction_word = "supports" if interpretation.supports > 0 else "undermines"
        jtms.justify(
            f"belief:{world_id}",
            in_list=[f"observed:{observation.id}"],
            rationale=f"{subject}={value!r} {direction_word} {after.proposition}",
        )
        world_event = trace.emit(
            "BELIEF_UPDATED",
            payload={
                "belief_id": world_id,
                "kind": "WorldBelief",
                "before": str(before.label),
                "after": str(after.label),
                "direction": interpretation.supports,
            },
            caused_by=(observation_event.seq,),
            rationale=(
                f"observation {observation.id} ({subject}={value!r}) "
                f"{direction_word} this proposition"
            ),
        )
        last_belief_seq = world_event.seq

        # Criterion 7: strategy beliefs move, caused by the *world
        # belief*, not by the raw observation. Each affected strategy
        # declares how it correlates with the proposition, so the same
        # evidence can strengthen one route and weaken another -- which
        # is what makes the commitment depend on what was learned rather
        # than merely that something was learned.
        for target_strategy, correlation in strategy_belief_of(world_id):
            sb_id = f"belief:strategy:{target_strategy}"
            # A world belief can name a strategy absent from this
            # episode's ensemble -- found by mutation M5. Not an error:
            # you cannot update a belief about a route you are not
            # considering. Skip rather than crash.
            sb_before = beliefs.get(sb_id)
            if sb_before is None:
                continue
            step = interpretation.supports * correlation
            sb_after = sb_before.with_label(update(sb_before.label, step))
            beliefs.hold(sb_after)
            effect = "raises" if step > 0 else "lowers"
            jtms.justify(
                sb_id,
                in_list=[f"belief:{world_id}"],
                rationale=f"{world_id} {effect} confidence in {target_strategy}",
            )
            last_belief_seq = trace.emit(
                "BELIEF_UPDATED",
                payload={
                    "belief_id": sb_id,
                    "kind": "StrategyBelief",
                    "strategy_id": target_strategy,
                    "before": str(sb_before.label),
                    "after": str(sb_after.label),
                    "direction": step,
                },
                caused_by=(world_event.seq,),
                rationale=(
                    f"the world belief {world_id} moved "
                    f"{'up' if interpretation.supports > 0 else 'down'}, which "
                    f"{effect} how promising {target_strategy} is"
                ),
            ).seq

    # -- ranking ----------------------------------------------------------
    # Sorted by belief then id: coarse labels make ties common, and
    # criterion 14 wants byte-identical traces (mutation M8 attacks this).
    ranked = sorted(
        ensemble.strategies.values(),
        key=lambda s: (-int(beliefs.get(f"belief:strategy:{s.id}").label), s.id),
    )
    rank_causes = tuple(c for c in (last_belief_seq, declared.seq) if c is not None)
    ranked_event = trace.emit(
        "STRATEGY_RANKED",
        payload={
            "order": [s.id for s in ranked],
            "beliefs": {
                s.id: str(beliefs.get(f"belief:strategy:{s.id}").label) for s in ranked
            },
        },
        caused_by=rank_causes,
        rationale="ranked by strategy belief, ties broken on id for determinism",
    )

    # -- commitment -------------------------------------------------------
    # Criterion 11: the runner-up is RETAINED, not eliminated. Anything
    # ranked below it that is strictly weaker is eliminated *with a
    # reason*, because criterion 13 needs every transition explainable.
    winner, *rest = ranked
    ensemble.add(winner.commit())
    if rest:
        ensemble.add(rest[0].retain())
    for loser in rest[1:]:
        ensemble.add(
            loser.eliminate(
                f"belief {beliefs.get(f'belief:strategy:{loser.id}').label} is below "
                f"the retained alternative {rest[0].id}"
            )
        )

    residual = tuple(
        f"{b.proposition} is only {b.label}"
        for b in sorted(beliefs.of_kind("WorldBelief"), key=lambda b: b.id)
        if b.label is not BeliefLabel.ESTABLISHED
    ) or ("no world belief reached ESTABLISHED",)

    commitment = Commitment.of(
        chosen=ensemble.get(winner.id),
        ensemble=ensemble,
        rationale=(
            f"further information is uneconomic (best EVI below the "
            f"comparator {comparator_used}), and the next action "
            f"({winner.next_action or 'execution'}) requires a stable choice"
        ),
        residual_uncertainty=residual,
    )
    commit_causes = tuple(
        c for c in (ranked_event.seq, last_evidence_seq) if c is not None
    )
    trace.emit(
        "STRATEGY_COMMITTED",
        payload={
            "strategy_id": commitment.strategy_id,
            "residual_uncertainty": list(commitment.residual_uncertainty),
            "retained_alternatives": list(commitment.retained_alternatives),
            "next_action": winner.next_action,
        },
        caused_by=commit_causes,
        rationale=commitment.rationale,
    )
    trace.emit("EPISODE_CLOSED", payload={"episode_id": episode_id})

    return LoopResult(
        commitment=commitment,
        trace=trace,
        observed=observed,
        beliefs=beliefs,
        ensemble=ensemble,
        jtms=jtms,
    )
