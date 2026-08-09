"""Reconstruct episode state from an event trace.

Criterion 15 requires that replaying the recorded event stream reproduces
the same final commitment and the same belief values, *without*
re-executing the information action.

There was previously no replay engine at all. `load()` parsed JSONL into
`Event` objects and nothing consumed it; the test that claimed to prove
replay wrote a file, read it back, and compared the parsed values against
the in-memory objects of the same run. Reading a file returns what you
wrote, so it could not fail -- clause A1.

This module is the actual mechanism. It takes only events and rebuilds
state from them. It imports no scenario, calls no capability, and cannot
reach `perform()`: if the trace does not carry enough information to
reconstruct the belief state, replay fails loudly rather than quietly
recomputing.

That constraint is also why §9 of the contract matters here. Continuum is
intended to expose itself over MCP, so a host will reconstruct reasoning
from the trace without holding Continuum's context. This is that path,
and it is the reason payloads must stay self-describing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from escapement.belief.labels import BeliefLabel
from escapement.observation.events import Event


class ReplayError(RuntimeError):
    """The trace cannot be replayed."""


@dataclass
class ReplayedEpisode:
    """Episode state rebuilt from events alone."""

    episode_id: str
    beliefs: dict[str, BeliefLabel] = field(default_factory=dict)
    observations: dict[str, object] = field(default_factory=dict)
    committed_strategy: str | None = None
    residual_uncertainty: tuple[str, ...] = ()
    retained_alternatives: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.committed_strategy is not None


def replay(events: list[Event]) -> ReplayedEpisode:
    """Rebuild episode state by walking the trace in causal order.

    Deliberately strict. A `BELIEF_UPDATED` whose `before` does not match
    the state replay has already reconstructed means the trace is not a
    faithful record of the run, and that is worth failing on -- a replay
    that silently repairs inconsistencies would defeat the point of
    having one.
    """
    if not events:
        raise ReplayError("cannot replay an empty trace")

    ordered = sorted(events, key=lambda e: e.seq)
    expected_seq = [e.seq for e in ordered]
    if expected_seq != list(range(1, len(ordered) + 1)):
        raise ReplayError(f"trace has gaps or duplicates in seq: {expected_seq}")

    episode = ReplayedEpisode(episode_id=ordered[0].episode_id)
    evidence: list[str] = []

    for event in ordered:
        payload = event.payload

        if event.type == "STRATEGY_GENERATED":
            episode.beliefs[f"belief:strategy:{payload['strategy_id']}"] = BeliefLabel[
                payload["belief"]
            ]

        elif event.type == "EVIDENCE_ADDED":
            evidence.append(payload["evidence_id"])

        elif event.type == "OBSERVATION_CREATED":
            episode.observations[payload["observation_id"]] = payload["value"]

        elif event.type == "BELIEF_UPDATED":
            belief_id = payload["belief_id"]
            before = BeliefLabel[payload["before"]]
            known = episode.beliefs.get(belief_id)
            if known is not None and known is not before:
                raise ReplayError(
                    f"event {event.seq} says {belief_id} was {before.name}, but "
                    f"replay reconstructed {known.name}; the trace does not "
                    "faithfully record the run"
                )
            episode.beliefs[belief_id] = BeliefLabel[payload["after"]]

        elif event.type == "STRATEGY_COMMITTED":
            episode.committed_strategy = payload["strategy_id"]
            episode.residual_uncertainty = tuple(payload["residual_uncertainty"])
            episode.retained_alternatives = tuple(payload["retained_alternatives"])

    episode.evidence_ids = tuple(evidence)
    return episode
