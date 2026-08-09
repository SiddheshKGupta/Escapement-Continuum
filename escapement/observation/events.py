"""Append-only event trace.

Baseline section 27 places this in `observation/events.py`. The Experiment
001 contract makes it the **only** evidence surface: the verdict is
computed from this file, not from source inspection, not from a summary,
and not from the implementer's description of what happened.

Three properties follow from that, and each is enforced here rather than
left to discipline:

1. **Machine-generated, never hand-authored.** The writer owns `seq`;
   callers cannot set it. A hand-edited trace would be indistinguishable
   from a real one otherwise.

2. **`caused_by` is mandatory on decision events.** Contract section 2
   lists which. An event that changes a decision without a causal link to
   the evidence that changed it is a contract violation *even when the
   resulting decision is correct* -- the v1 precedent being eval cases
   that carried an accurate description while asserting a different field
   than the one the description named.

3. **Self-describing payloads.** Escapement-Continuum is intended to be
   an MCP server, so a host will eventually read this trace to
   reconstruct reasoning without holding our context. Meaning must not be
   encoded in field ordering or implicit context. That costs nothing now
   and is expensive to retrofit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

#: Contract section 2. Any event type outside this set is rejected --
#: a typo'd event name would otherwise silently fail every criterion
#: that looks for it, which passes as "not present" rather than "wrong".
EVENT_TYPES = frozenset({
    "EPISODE_OPENED",
    "INTENT_DECLARED",
    "OBSERVATION_CREATED",
    "BELIEF_UPDATED",
    "STRATEGY_GENERATED",
    "STRATEGY_RANKED",
    "INFORMATION_ACTION_EVALUATED",
    "INFORMATION_ACTION_SELECTED",
    "INFORMATION_ACTION_EXECUTED",
    "EVIDENCE_ADDED",
    "EXPLORATION_STOPPED",
    "STRATEGY_COMMITTED",
    "EXECUTION_COMPLETED",
    "VERIFICATION_COMPLETED",
    "EPISODE_CLOSED",
})

#: Contract section 2: these carry a decision, so they must say what
#: caused them and why.
REQUIRES_CAUSATION = frozenset({
    "BELIEF_UPDATED",
    "STRATEGY_RANKED",
    "INFORMATION_ACTION_SELECTED",
    "EXPLORATION_STOPPED",
    "STRATEGY_COMMITTED",
})


@dataclass(frozen=True)
class Event:
    seq: int
    type: str
    episode_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    caused_by: tuple[int, ...] = ()
    rationale: str = ""

    def to_json(self) -> str:
        """Serialise with sorted keys.

        Criterion 14 requires byte-identical traces across runs. Python
        dicts preserve insertion order, so two runs that build a payload
        by different code paths could serialise the same data
        differently. Sorting removes that whole class of nondeterminism
        rather than relying on every call site to be consistent.
        """
        return json.dumps(
            {
                "seq": self.seq,
                "type": self.type,
                "episode_id": self.episode_id,
                "payload": self.payload,
                "caused_by": list(self.caused_by),
                "rationale": self.rationale,
            },
            sort_keys=True,
            ensure_ascii=False,
        )


class EventTrace:
    """Append-only writer with contract enforcement at the point of write.

    Deliberately has no `update`, `delete` or `rewrite`. An append-only
    log is what makes replay (criterion 15) meaningful; a mutable one
    would let a later correction erase the reasoning that led to it.
    """

    def __init__(self, episode_id: str, path: Path | None = None) -> None:
        self.episode_id = episode_id
        self.path = path
        self._events: list[Event] = []
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    def emit(
        self,
        type: str,
        *,
        payload: dict[str, Any] | None = None,
        caused_by: tuple[int, ...] | list[int] = (),
        rationale: str = "",
    ) -> Event:
        if type not in EVENT_TYPES:
            raise ValueError(
                f"unknown event type {type!r}; add it to EVENT_TYPES and to "
                "the contract's section 2 list, or fix the typo -- an "
                "unrecognised type would silently satisfy nothing"
            )

        causes = tuple(caused_by)
        if type in REQUIRES_CAUSATION:
            if not causes:
                raise ValueError(
                    f"{type} is a decision event and must cite the events "
                    "that caused it (contract section 2)"
                )
            if not rationale:
                raise ValueError(
                    f"{type} is a decision event and must carry a rationale "
                    "(criterion 12)"
                )

        known = {event.seq for event in self._events}
        unknown = [c for c in causes if c not in known]
        if unknown:
            raise ValueError(
                f"{type} cites unknown causes {unknown}; a causal link must "
                "point at an event that already happened"
            )

        event = Event(
            seq=len(self._events) + 1,
            type=type,
            episode_id=self.episode_id,
            payload=payload or {},
            caused_by=causes,
            rationale=rationale,
        )
        self._events.append(event)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(event.to_json() + "\n")
        return event

    # -- inspection ---------------------------------------------------

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def of_type(self, type: str) -> list[Event]:
        return [event for event in self._events if event.type == type]

    def first(self, type: str) -> Event | None:
        return next((event for event in self._events if event.type == type), None)

    def render(self) -> str:
        return "".join(event.to_json() + "\n" for event in self._events)

    def connected_from(self, root_seq: int) -> set[int]:
        """Sequence numbers reachable from `root_seq` by causal links.

        Criterion 13 requires the graph to be fully connected from
        INTENT_DECLARED to STRATEGY_COMMITTED with no orphan decision
        events. Walking forward from the root is how that is checked.
        """
        reachable = {root_seq}
        changed = True
        while changed:
            changed = False
            for event in self._events:
                if event.seq in reachable:
                    continue
                if any(cause in reachable for cause in event.caused_by):
                    reachable.add(event.seq)
                    changed = True
        return reachable


def load(path: Path) -> list[Event]:
    """Read a trace back for replay (criterion 15)."""
    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        events.append(
            Event(
                seq=raw["seq"],
                type=raw["type"],
                episode_id=raw["episode_id"],
                payload=raw["payload"],
                caused_by=tuple(raw["caused_by"]),
                rationale=raw["rationale"],
            )
        )
    return events
