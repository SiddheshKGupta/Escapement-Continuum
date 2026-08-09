"""Independent executable checks for the Experiment 001 review contract.

Written without reading the author's own checker (since deleted) or
`tests/test_c001_conformance.py`, deliberately: both were authored by the
author of the implementation and both were found to contain assertions
that hold while the contract is violated. The value of this module is
that it is not anchored on those assertions.

Three design rules, each a response to how the previous attempt failed.

**1. Three verdicts.** `PASS`, `FAIL`, `UNVERIFIED`. A checker that
guesses PASS on what it cannot establish is worse than no checker, so
anything unestablished is named as such and can never roll up into an
overall PASS. Criterion 14 is the clearest case: determinism is not a
property of a single trace, and no amount of squinting at one file
establishes it.

**2. No assertion that cannot fail.** Key-presence, non-emptiness and
set-intersection checks are what defeated the previous attempt, so every
check here either recomputes a recorded value from independent trace
state, or compares two records that were emitted by different code paths,
or is demoted to UNVERIFIED. Where the contract's literal wording *is*
satisfiable vacuously, the literal check is kept and a second check is
added under the same criterion testing clause A1 (see `C8d`, `C10b`).

**3. Every check must be able to fail.** Each check below has a
constructed failing state recorded in the accompanying report. Where no
failing state could be constructed from a trace alone, the criterion is
reported UNVERIFIED rather than given a check that always passes.

Two entry points:

    check(events)   static, trace-only, no execution
    probe()         live; runs the experiment, including in subprocesses
                    under differing PYTHONHASHSEED, which is the only way
                    to observe hash-order nondeterminism

Standard library only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from escapement.belief.labels import BeliefLabel  # noqa: E402
from escapement.observation.events import (  # noqa: E402
    REQUIRES_CAUSATION,
    Event,
    EventTrace,
    load,
)

TRACE_PATH = _REPO_ROOT / "conformance" / "c001" / "events.jsonl"
README_PATH = _REPO_ROOT / "conformance" / "c001" / "README.md"

#: Criterion 1 names these three explicitly.
REQUIRED_STRATEGY_IDS = frozenset({"DIRECT", "SEQUENTIAL", "RECURSIVE"})

#: Criterion 4 names this action explicitly.
REQUIRED_SELECTED_ACTION = "INSPECT_DEPENDENCY_MAP"

#: Criterion 11's bar. "Still plausible at commit time" is read against the
#: ordinal label of the same name: PLAUSIBLE or better. UNLIKELY is below it.
PLAUSIBILITY_BAR = BeliefLabel.PLAUSIBLE

#: The comparator is documented in the trace as a max over strategy-belief
#: ordinals, so its representable range is the label range. Used by C8d to
#: ask whether *any* admissible comparator value would have changed the
#: stopping decision.
COMPARATOR_DOMAIN = tuple(int(label) for label in BeliefLabel)


class Status(Enum):
    """Three verdicts, not two."""

    PASS = "PASS"
    FAIL = "FAIL"
    #: The check could not be established from the evidence available.
    #: Never rounds up. An UNVERIFIED criterion blocks an overall PASS.
    UNVERIFIED = "UNVERIFIED"

    def __str__(self) -> str:
        return self.value


#: Worse-is-greater, for rolling several sub-checks into one criterion.
_SEVERITY = {Status.PASS: 0, Status.UNVERIFIED: 1, Status.FAIL: 2}


@dataclass(frozen=True)
class CheckResult:
    #: Stable id. Sub-checks of one criterion share its number: C8a..C8e.
    id: str
    #: Contract criterion 1-15, a precondition id like "P1", or None for an
    #: advisory finding that is not yet a criterion.
    criterion: int | str | None
    title: str
    status: Status
    detail: str
    #: Declared per clause A3 for every collection assertion.
    quantifier: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    #: Id of a check that, if it returns a definite PASS/FAIL, settles this
    #: one. Used only by the deferred UNVERIFIED markers `check()` emits for
    #: things a trace cannot establish, so that also running `probe()` does
    #: not leave the criterion permanently unverified -- while running
    #: `check()` alone still reports it honestly as unestablished.
    superseded_by: str | None = None

    def __str__(self) -> str:
        where = f"crit {self.criterion}" if self.criterion is not None else "advisory"
        return f"[{self.status}] {self.id} ({where}) {self.title}: {self.detail}"


def _ok(id, criterion, title, detail, **kw) -> CheckResult:
    return CheckResult(id, criterion, title, Status.PASS, detail, **kw)


def _bad(id, criterion, title, detail, **kw) -> CheckResult:
    return CheckResult(id, criterion, title, Status.FAIL, detail, **kw)


def _unk(id, criterion, title, detail, **kw) -> CheckResult:
    return CheckResult(id, criterion, title, Status.UNVERIFIED, detail, **kw)


# ---------------------------------------------------------------------------
# trace view
# ---------------------------------------------------------------------------


class _Trace:
    """Read-only helpers over a list of events.

    Everything a check needs is derived here from the trace alone. No
    check imports the scenario or the loop, because a checker that shares
    a source of truth with the thing it checks cannot contradict it.
    """

    def __init__(self, events: list[Event]) -> None:
        self.events = sorted(events, key=lambda e: e.seq)
        self.by_seq = {e.seq: e for e in self.events}

    def of_type(self, type: str) -> list[Event]:
        return [e for e in self.events if e.type == type]

    def first(self, type: str) -> Event | None:
        return next((e for e in self.events if e.type == type), None)

    def type_of(self, seq: int) -> str | None:
        event = self.by_seq.get(seq)
        return event.type if event else None

    def causes_of(self, event: Event) -> list[Event]:
        return [self.by_seq[c] for c in event.caused_by if c in self.by_seq]

    def eval_rounds(self) -> list[list[Event]]:
        """Contiguous runs of INFORMATION_ACTION_EVALUATED, in order.

        A "round" is a maximal block of evaluations with no other event
        between them. Criterion 8 needs to distinguish the first round
        from the second, and the trace carries no round number, so the
        block structure is the only thing available.
        """
        rounds: list[list[Event]] = []
        current: list[Event] = []
        for event in self.events:
            if event.type == "INFORMATION_ACTION_EVALUATED":
                current.append(event)
            elif current:
                rounds.append(current)
                current = []
        if current:
            rounds.append(current)
        return rounds

    def round_before(self, seq: int) -> list[Event] | None:
        """The last evaluation round entirely preceding `seq`."""
        candidates = [r for r in self.eval_rounds() if r and r[-1].seq < seq]
        return candidates[-1] if candidates else None

    def strategy_labels_at(self, seq: int) -> dict[str, BeliefLabel]:
        """Strategy-belief labels as of just before `seq`.

        Rebuilt from STRATEGY_GENERATED (initial label) and every
        StrategyBelief BELIEF_UPDATED before `seq`. This is the state the
        loop's comparator is documented to be a function of, reconstructed
        without asking the loop.
        """
        labels: dict[str, BeliefLabel] = {}
        for event in self.events:
            if event.seq >= seq:
                break
            if event.type == "STRATEGY_GENERATED":
                sid = event.payload.get("strategy_id")
                name = event.payload.get("belief")
                if sid is None or name is None:
                    continue
                labels[f"belief:strategy:{sid}"] = _label(name)
            elif (
                event.type == "BELIEF_UPDATED"
                and event.payload.get("kind") == "StrategyBelief"
            ):
                bid = event.payload.get("belief_id")
                name = event.payload.get("after")
                if bid is None or name is None:
                    continue
                labels[bid] = _label(name)
        return labels

    def descendants(self, root: int) -> set[int]:
        reachable = {root}
        changed = True
        while changed:
            changed = False
            for event in self.events:
                if event.seq in reachable:
                    continue
                if any(c in reachable for c in event.caused_by):
                    reachable.add(event.seq)
                    changed = True
        return reachable

    def ancestors(self, seq: int) -> set[int]:
        seen: set[int] = set()
        stack = [seq]
        while stack:
            current = stack.pop()
            for cause in self.by_seq.get(current, Event(0, "", "")).caused_by:
                if cause not in seen:
                    seen.add(cause)
                    stack.append(cause)
        return seen


class _Unreadable(Exception):
    """The trace does not carry what a check needs to decide."""


def _label(name: object) -> BeliefLabel:
    try:
        return BeliefLabel[str(name)]
    except KeyError as exc:  # pragma: no cover - defensive
        raise _Unreadable(f"{name!r} is not a BeliefLabel name") from exc


def _need(payload: dict, key: str, where: str) -> Any:
    if key not in payload:
        raise _Unreadable(f"{where} carries no {key!r}")
    return payload[key]


# ---------------------------------------------------------------------------
# preconditions that are checkable from the trace
# ---------------------------------------------------------------------------


def _p1_seq(t: _Trace) -> CheckResult:
    seqs = [e.seq for e in t.events]
    expected = list(range(1, len(seqs) + 1))
    if not seqs:
        return _bad("P1", "P1", "seq strictly increasing, no gaps", "trace is empty")
    if seqs != expected:
        return _bad(
            "P1",
            "P1",
            "seq strictly increasing, no gaps",
            f"seq is {seqs[:8]}... expected 1..{len(seqs)}",
            evidence={"seqs": seqs},
        )
    return _ok(
        "P1",
        "P1",
        "seq strictly increasing, no gaps",
        f"{len(seqs)} events numbered 1..{len(seqs)}",
    )


def _p6_collapse(t: _Trace) -> CheckResult:
    """P6: the word Collapse appears in no identifier.

    Only the trace's own identifiers are visible here -- event types and
    payload keys -- so this is a partial check of P6 and says so.
    """
    hits: list[str] = []
    for event in t.events:
        if "collapse" in event.type.lower():
            hits.append(f"seq {event.seq} type {event.type}")
        for key in event.payload:
            if "collapse" in str(key).lower():
                hits.append(f"seq {event.seq} payload key {key}")
    if hits:
        return _bad("P6", "P6", "no 'Collapse' identifier", "; ".join(hits[:5]))
    return _ok(
        "P6",
        "P6",
        "no 'Collapse' identifier",
        "no event type or payload key contains 'collapse' "
        "(source identifiers are outside a trace-only check)",
        quantifier="must-not-contain, over event types and payload keys",
    )


# ---------------------------------------------------------------------------
# criterion 1
# ---------------------------------------------------------------------------


def _c1(t: _Trace) -> list[CheckResult]:
    generated = t.of_type("STRATEGY_GENERATED")
    committed = t.first("STRATEGY_COMMITTED")
    ids = [e.payload.get("strategy_id") for e in generated]
    distinct = {i for i in ids if i is not None}

    results: list[CheckResult] = []

    if committed is None:
        results.append(
            _bad("C1a", 1, "3+ strategies before commit", "no STRATEGY_COMMITTED event")
        )
    else:
        before = {
            e.payload.get("strategy_id")
            for e in generated
            if e.seq < committed.seq and e.payload.get("strategy_id") is not None
        }
        if len(before) >= 3:
            results.append(
                _ok(
                    "C1a",
                    1,
                    "3+ distinct strategies before commit",
                    f"{len(before)} distinct ids generated before seq {committed.seq}: "
                    f"{sorted(before)}",
                    quantifier="count >= 3 over DISTINCT strategy_id",
                    evidence={"generated": sorted(before)},
                )
            )
        else:
            results.append(
                _bad(
                    "C1a",
                    1,
                    "3+ distinct strategies before commit",
                    f"only {len(before)} distinct id(s): {sorted(before)}",
                    quantifier="count >= 3 over DISTINCT strategy_id",
                )
            )

    missing = sorted(REQUIRED_STRATEGY_IDS - distinct)
    if missing:
        results.append(
            _bad(
                "C1b",
                1,
                "DIRECT, SEQUENTIAL, RECURSIVE all present",
                f"missing {missing}; generated {sorted(distinct)}",
                quantifier="must-contain (superset allowed)",
                evidence={"generated": sorted(distinct), "missing": missing},
            )
        )
    else:
        results.append(
            _ok(
                "C1b",
                1,
                "DIRECT, SEQUENTIAL, RECURSIVE all present",
                f"generated {sorted(distinct)}",
                quantifier="must-contain (superset allowed)",
            )
        )

    # Coexistence is not the same as having been generated: a strategy
    # dropped between generation and ranking never coexisted with the
    # others at the moment the choice was made.
    ranked = t.first("STRATEGY_RANKED")
    if ranked is None:
        results.append(
            _unk("C1c", 1, "generated strategies still coexist at ranking", "no STRATEGY_RANKED event")
        )
    else:
        order = list(ranked.payload.get("order", []))
        dropped = sorted(distinct - set(order))
        if dropped:
            results.append(
                _bad(
                    "C1c",
                    1,
                    "generated strategies still coexist at ranking",
                    f"{dropped} were generated but absent from the ranking",
                    quantifier="must-equal, generated set vs ranked set",
                )
            )
        else:
            results.append(
                _ok(
                    "C1c",
                    1,
                    "generated strategies still coexist at ranking",
                    f"all {len(distinct)} generated strategies appear in the ranking {order}",
                    quantifier="must-equal, generated set vs ranked set",
                )
            )
    return results


# ---------------------------------------------------------------------------
# criterion 2
# ---------------------------------------------------------------------------


def _c2(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    committed = t.first("STRATEGY_COMMITTED")
    first_evidence = t.first("EVIDENCE_ADDED")

    if committed is None:
        results.append(_bad("C2a", 2, "no commit before evidence", "no STRATEGY_COMMITTED event"))
    elif first_evidence is None:
        results.append(
            _bad(
                "C2a",
                2,
                "no commit before evidence",
                f"commit at seq {committed.seq} with no EVIDENCE_ADDED anywhere in the trace",
            )
        )
    elif committed.seq < first_evidence.seq:
        results.append(
            _bad(
                "C2a",
                2,
                "no commit before evidence",
                f"commit at seq {committed.seq} precedes first evidence at seq {first_evidence.seq}",
            )
        )
    else:
        results.append(
            _ok(
                "C2a",
                2,
                "no commit before evidence",
                f"first evidence seq {first_evidence.seq} < commit seq {committed.seq}",
            )
        )

    generated = t.of_type("STRATEGY_GENERATED")
    if not generated:
        results.append(_bad("C2b", 2, "no strategy at ESTABLISHED/RULED_OUT at generation", "no STRATEGY_GENERATED events"))
        return results

    unreadable = [e.seq for e in generated if "belief" not in e.payload]
    if unreadable:
        results.append(
            _unk(
                "C2b",
                2,
                "no strategy at ESTABLISHED/RULED_OUT at generation",
                f"STRATEGY_GENERATED at seq {unreadable} record no belief label, so the "
                "criterion cannot be decided from the trace",
            )
        )
        return results

    extreme = [
        (e.payload["strategy_id"], e.payload["belief"])
        for e in generated
        if _label(e.payload["belief"]) in (BeliefLabel.ESTABLISHED, BeliefLabel.RULED_OUT)
    ]
    if extreme:
        results.append(
            _bad(
                "C2b",
                2,
                "no strategy at ESTABLISHED/RULED_OUT at generation",
                f"pre-selected at generation: {extreme}",
                quantifier="universal over STRATEGY_GENERATED",
            )
        )
    else:
        results.append(
            _ok(
                "C2b",
                2,
                "no strategy at ESTABLISHED/RULED_OUT at generation",
                "all generation labels are "
                + ", ".join(sorted({e.payload["belief"] for e in generated})),
                quantifier="universal over STRATEGY_GENERATED",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 3
# ---------------------------------------------------------------------------


def _c3(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    selected = t.first("INFORMATION_ACTION_SELECTED")
    if selected is None:
        return [_bad("C3a", 3, "3+ distinct actions compared before selection", "no INFORMATION_ACTION_SELECTED event")]

    round_ = t.round_before(selected.seq)
    if not round_:
        return [
            _bad(
                "C3a",
                3,
                "3+ distinct actions compared before selection",
                f"no INFORMATION_ACTION_EVALUATED block precedes the selection at seq {selected.seq}",
            )
        ]

    action_ids = [e.payload.get("action_id") for e in round_]
    distinct = {a for a in action_ids if a is not None}
    if len(distinct) >= 3:
        results.append(
            _ok(
                "C3a",
                3,
                "3+ distinct actions compared before selection",
                f"{len(distinct)} distinct actions evaluated at seqs "
                f"{[e.seq for e in round_]}: {sorted(distinct)}",
                quantifier="count >= 3 over DISTINCT action_id in the round preceding selection",
            )
        )
    else:
        results.append(
            _bad(
                "C3a",
                3,
                "3+ distinct actions compared before selection",
                f"only {len(distinct)} distinct action(s): {sorted(distinct)}",
                quantifier="count >= 3 over DISTINCT action_id in the round preceding selection",
            )
        )

    # "each with its own EVI figure" is not satisfied by three copies of the
    # same number arriving from nowhere: the figure must be internally
    # consistent with the terms it is composed of. A fabricated evi that
    # does not equal improvement - cost is a figure with no derivation.
    inconsistent: list[str] = []
    missing: list[int] = []
    for event in round_:
        payload = event.payload
        if not {"evi", "expected_improvement", "cost"} <= set(payload):
            missing.append(event.seq)
            continue
        if payload["evi"] != payload["expected_improvement"] - payload["cost"]:
            inconsistent.append(
                f"seq {event.seq}: evi {payload['evi']} != "
                f"{payload['expected_improvement']} - {payload['cost']}"
            )
    if missing:
        results.append(
            _unk(
                "C3b",
                3,
                "each EVI figure is derived, not asserted",
                f"evaluations at seq {missing} do not record improvement/cost, so the "
                "figure cannot be recomputed",
            )
        )
    elif inconsistent:
        results.append(
            _bad("C3b", 3, "each EVI figure is derived, not asserted", "; ".join(inconsistent))
        )
    else:
        results.append(
            _ok(
                "C3b",
                3,
                "each EVI figure is derived, not asserted",
                "every recorded evi equals expected_improvement - cost",
                quantifier="universal over the round preceding selection",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 4
# ---------------------------------------------------------------------------


def _c4(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    selected = t.first("INFORMATION_ACTION_SELECTED")
    if selected is None:
        return [_bad("C4a", 4, "selection is the unique EVI argmax", "no INFORMATION_ACTION_SELECTED event")]

    round_ = t.round_before(selected.seq)
    if not round_:
        return [_bad("C4a", 4, "selection is the unique EVI argmax", "no evaluation round precedes the selection")]

    scores: dict[str, int] = {}
    for event in round_:
        try:
            scores[_need(event.payload, "action_id", f"seq {event.seq}")] = _need(
                event.payload, "evi", f"seq {event.seq}"
            )
        except _Unreadable as exc:
            return [_unk("C4a", 4, "selection is the unique EVI argmax", str(exc))]

    best = max(scores.values())
    winners = sorted(a for a, s in scores.items() if s == best)
    chosen = selected.payload.get("action_id")

    if len(winners) > 1:
        # A tie means the recorded EVI figures did not determine the
        # choice; something else did. Mutation M2 (all EVI identical) is
        # exactly this, and a "chosen in argmax" test passes straight
        # through it.
        results.append(
            _bad(
                "C4a",
                4,
                "selection is the unique EVI argmax",
                f"EVI is tied at {best} across {winners}; the selection of {chosen!r} "
                "cannot have been determined by EVI",
                quantifier="argmax must be unique",
                evidence={"scores": scores},
            )
        )
    elif chosen != winners[0]:
        results.append(
            _bad(
                "C4a",
                4,
                "selection is the unique EVI argmax",
                f"selected {chosen!r} but the argmax is {winners[0]!r} ({scores})",
                quantifier="argmax must be unique",
                evidence={"scores": scores},
            )
        )
    else:
        results.append(
            _ok(
                "C4a",
                4,
                "selection is the unique EVI argmax",
                f"{chosen!r} at EVI {best} is the strict maximum of {scores}",
                quantifier="argmax must be unique",
                evidence={"scores": scores},
            )
        )

    # The selection must cite the comparison it claims to be the result
    # of -- exactly the round's evaluations, no more and no fewer. A
    # selection citing a subset could be the argmax of a comparison that
    # never happened.
    cited = set(selected.caused_by)
    expected = {e.seq for e in round_}
    if cited != expected:
        results.append(
            _bad(
                "C4b",
                4,
                "selection cites exactly the comparison it won",
                f"caused_by {sorted(cited)} != evaluation round {sorted(expected)}",
                quantifier="must-equal",
            )
        )
    else:
        results.append(
            _ok(
                "C4b",
                4,
                "selection cites exactly the comparison it won",
                f"caused_by == the {len(expected)} evaluations of that round",
                quantifier="must-equal",
            )
        )

    if not selected.rationale.strip():
        results.append(_bad("C4c", 4, "selection rationale non-empty", "rationale is blank"))
    elif chosen and chosen not in selected.rationale:
        results.append(
            _bad(
                "C4c",
                4,
                "selection rationale non-empty and about this action",
                f"rationale does not name the selected action {chosen!r}: {selected.rationale!r}",
            )
        )
    else:
        results.append(
            _ok(
                "C4c",
                4,
                "selection rationale non-empty and about this action",
                f"rationale names {chosen!r} and its figure",
            )
        )

    if chosen != REQUIRED_SELECTED_ACTION:
        results.append(
            _bad(
                "C4d",
                4,
                f"selected action is {REQUIRED_SELECTED_ACTION}",
                f"selected {chosen!r}",
            )
        )
    else:
        results.append(
            _ok("C4d", 4, f"selected action is {REQUIRED_SELECTED_ACTION}", "as named by the criterion")
        )
    return results


# ---------------------------------------------------------------------------
# criterion 5
# ---------------------------------------------------------------------------


def _c5(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    observations = t.of_type("OBSERVATION_CREATED")
    if not observations:
        return [
            _bad(
                "C5a",
                5,
                "observation created from evidence",
                "zero OBSERVATION_CREATED events; the criterion is over an empty set "
                "and scores FAIL under clause A2, not PASS",
                quantifier="count >= 1",
            )
        ]

    grounded = [
        e
        for e in observations
        if any(t.type_of(c) == "EVIDENCE_ADDED" for c in e.caused_by)
    ]
    if not grounded:
        return [
            _bad(
                "C5a",
                5,
                "observation created from evidence",
                f"{len(observations)} observation(s), none caused by an EVIDENCE_ADDED event",
                quantifier="count >= 1",
            )
        ]

    results.append(
        _ok(
            "C5a",
            5,
            "observation created from evidence",
            f"{len(grounded)}/{len(observations)} observations cite an EVIDENCE_ADDED cause "
            f"(e.g. seq {grounded[0].seq} <- {list(grounded[0].caused_by)})",
            quantifier="count >= 1",
        )
    )

    # The interesting direction is the universal one: an observation that
    # appeared without evidence is a fabricated fact, and P5 forbids the
    # path. "At least one is grounded" cannot detect it.
    ungrounded = [e.seq for e in observations if e not in grounded]
    if ungrounded:
        results.append(
            _bad(
                "C5b",
                5,
                "every observation is grounded in evidence",
                f"observations at seq {ungrounded} cite no EVIDENCE_ADDED",
                quantifier="universal over OBSERVATION_CREATED",
            )
        )
    else:
        results.append(
            _ok(
                "C5b",
                5,
                "every observation is grounded in evidence",
                f"all {len(observations)} observations trace back to evidence",
                quantifier="universal over OBSERVATION_CREATED",
            )
        )

    contentless = [
        e.seq for e in observations if e.payload.get("subject") in (None, "") or "value" not in e.payload
    ]
    if contentless:
        results.append(
            _bad(
                "C5c",
                5,
                "observations carry subject and value",
                f"observations at seq {contentless} record no subject/value, so nothing "
                "was actually observed",
            )
        )
    else:
        results.append(
            _ok(
                "C5c",
                5,
                "observations carry subject and value",
                ", ".join(
                    f"{e.payload['subject']}={e.payload['value']!r}" for e in observations[:4]
                ),
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 6
# ---------------------------------------------------------------------------


def _world_updates_from_observation(t: _Trace) -> list[Event]:
    return [
        e
        for e in t.of_type("BELIEF_UPDATED")
        if e.payload.get("kind") == "WorldBelief"
        and any(t.type_of(c) == "OBSERVATION_CREATED" for c in e.caused_by)
    ]


def _c6(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    world = [e for e in t.of_type("BELIEF_UPDATED") if e.payload.get("kind") == "WorldBelief"]
    if not world:
        return [
            _bad(
                "C6a",
                6,
                "a world belief changed, caused by an observation",
                "zero WorldBelief BELIEF_UPDATED events",
                quantifier="count >= 1",
            )
        ]

    from_obs = _world_updates_from_observation(t)
    moved = [e for e in from_obs if e.payload.get("before") != e.payload.get("after")]
    if not moved:
        return [
            _bad(
                "C6a",
                6,
                "a world belief changed, caused by an observation",
                f"{len(world)} world-belief update(s), {len(from_obs)} caused by an "
                "observation, 0 with before != after",
                quantifier="count >= 1",
                evidence={
                    "updates": [
                        (e.seq, e.payload.get("before"), e.payload.get("after")) for e in world
                    ]
                },
            )
        ]

    example = moved[0]
    results.append(
        _ok(
            "C6a",
            6,
            "a world belief changed, caused by an observation",
            f"seq {example.seq}: {example.payload['belief_id']} "
            f"{example.payload['before']} -> {example.payload['after']}, "
            f"caused_by {list(example.caused_by)}",
            quantifier="count >= 1",
        )
    )

    # A belief that moved is not enough: it must have moved the way the
    # evidence pointed. Recording direction +1 and then falling is the
    # A7 failure -- the right destination reached by no path -- and a
    # before != after test passes through it unchanged.
    wrong: list[str] = []
    for event in moved:
        direction = event.payload.get("direction")
        if direction not in (-1, 1):
            wrong.append(f"seq {event.seq}: direction {direction!r} is neither +1 nor -1")
            continue
        delta = int(_label(event.payload["after"])) - int(_label(event.payload["before"]))
        if delta * direction <= 0:
            wrong.append(
                f"seq {event.seq}: direction {direction:+d} but label moved {delta:+d}"
            )
    if wrong:
        results.append(
            _bad(
                "C6b",
                6,
                "belief moved in the direction the evidence pointed",
                "; ".join(wrong),
                quantifier="universal over moved WorldBelief updates",
            )
        )
    else:
        results.append(
            _ok(
                "C6b",
                6,
                "belief moved in the direction the evidence pointed",
                f"all {len(moved)} moves agree in sign with their recorded direction",
                quantifier="universal over moved WorldBelief updates",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 7
# ---------------------------------------------------------------------------


def _c7(t: _Trace) -> list[CheckResult]:
    """Strategy belief moved *because a world belief moved*.

    The whole chain is required: EVIDENCE_ADDED -> OBSERVATION_CREATED ->
    WorldBelief -> StrategyBelief. Checking only "cites a WorldBelief"
    passes a trace with no observations in it at all, which is the
    B2 state and the reason criterion 7 is the one the contract calls the
    assertion that Quantum is reasoning rather than transcribing.
    """
    results: list[CheckResult] = []
    strategy = [
        e for e in t.of_type("BELIEF_UPDATED") if e.payload.get("kind") == "StrategyBelief"
    ]
    if not strategy:
        return [
            _bad(
                "C7a",
                7,
                "strategy belief changed via a world belief",
                "zero StrategyBelief BELIEF_UPDATED events",
                quantifier="count >= 1",
            )
        ]

    grounded_world = {e.seq for e in _world_updates_from_observation(t)}
    # ...and those observations must themselves be grounded in evidence.
    fully_grounded: set[int] = set()
    for seq in grounded_world:
        event = t.by_seq[seq]
        for cause in t.causes_of(event):
            if cause.type == "OBSERVATION_CREATED" and any(
                t.type_of(c) == "EVIDENCE_ADDED" for c in cause.caused_by
            ):
                fully_grounded.add(seq)

    moved = [e for e in strategy if e.payload.get("before") != e.payload.get("after")]
    qualifying = [
        e for e in moved if any(c in fully_grounded for c in e.caused_by)
    ]
    if not qualifying:
        results.append(
            _bad(
                "C7a",
                7,
                "strategy belief changed via a world belief",
                f"{len(strategy)} strategy-belief update(s), {len(moved)} that moved, "
                f"0 caused by a world belief that is itself grounded in an observation "
                f"grounded in evidence (grounded world updates: {sorted(fully_grounded)})",
                quantifier="count >= 1 over the full evidence->observation->world->strategy chain",
                evidence={
                    "strategy_updates": [
                        (e.seq, e.payload.get("belief_id"), list(e.caused_by)) for e in strategy
                    ],
                    "grounded_world_updates": sorted(fully_grounded),
                },
            )
        )
    else:
        example = qualifying[0]
        results.append(
            _ok(
                "C7a",
                7,
                "strategy belief changed via a world belief",
                f"seq {example.seq}: {example.payload['belief_id']} "
                f"{example.payload['before']} -> {example.payload['after']} "
                f"caused_by {list(example.caused_by)}, which is a world belief grounded "
                "in an observation grounded in evidence",
                quantifier="count >= 1 over the full evidence->observation->world->strategy chain",
            )
        )

    # "not caused directly by the raw observation" is the half of the
    # criterion that a count-based check silently drops.
    direct = [
        (e.seq, [t.type_of(c) for c in e.caused_by])
        for e in strategy
        if any(t.type_of(c) in ("OBSERVATION_CREATED", "EVIDENCE_ADDED") for c in e.caused_by)
    ]
    if direct:
        results.append(
            _bad(
                "C7b",
                7,
                "no strategy belief caused directly by raw observation/evidence",
                f"{direct}",
                quantifier="universal over StrategyBelief updates",
            )
        )
    else:
        results.append(
            _ok(
                "C7b",
                7,
                "no strategy belief caused directly by raw observation/evidence",
                f"all {len(strategy)} strategy-belief updates cite only "
                + str(sorted({t.type_of(c) or "?" for e in strategy for c in e.caused_by})),
                quantifier="universal over StrategyBelief updates",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 8
# ---------------------------------------------------------------------------


def _c8(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    rounds = t.eval_rounds()
    belief_updates = t.of_type("BELIEF_UPDATED")
    stopped = t.first("EXPLORATION_STOPPED")

    # 8a -- a second round, after the belief updates.
    if len(rounds) < 2:
        results.append(
            _bad(
                "C8a",
                8,
                "a second evaluation round follows the belief updates",
                f"{len(rounds)} evaluation round(s) in the trace",
                quantifier="count >= 2",
            )
        )
    elif not belief_updates:
        results.append(
            _bad(
                "C8a",
                8,
                "a second evaluation round follows the belief updates",
                "no BELIEF_UPDATED events, so no round can follow them",
            )
        )
    else:
        first_update = min(e.seq for e in belief_updates)
        second = rounds[1]
        if second[0].seq > first_update:
            results.append(
                _ok(
                    "C8a",
                    8,
                    "a second evaluation round follows the belief updates",
                    f"round 2 begins at seq {second[0].seq}, after the first belief "
                    f"update at seq {first_update}",
                    quantifier="count >= 2",
                )
            )
        else:
            results.append(
                _bad(
                    "C8a",
                    8,
                    "a second evaluation round follows the belief updates",
                    f"round 2 begins at seq {second[0].seq}, before the first belief "
                    f"update at seq {first_update}",
                )
            )

    if stopped is None:
        results.append(
            _bad(
                "C8b",
                8,
                "EXPLORATION_STOPPED records the comparator used",
                "no EXPLORATION_STOPPED event; exploration never recorded a stopping reason",
            )
        )
        return results

    payload = stopped.payload
    if "comparator" not in payload or not isinstance(payload.get("comparator"), int):
        results.append(
            _bad(
                "C8b",
                8,
                "EXPLORATION_STOPPED records the comparator used",
                f"comparator is {payload.get('comparator')!r}, not an integer",
            )
        )
        return results
    comparator = payload["comparator"]

    stop_round = t.round_before(stopped.seq)
    if not stop_round:
        results.append(
            _bad("C8b", 8, "every EVI in the stopping round is below the comparator", "no evaluation round precedes EXPLORATION_STOPPED")
        )
        return results

    evis = {e.payload.get("action_id"): e.payload.get("evi") for e in stop_round}
    above = {a: v for a, v in evis.items() if v is None or v > comparator}
    if above:
        results.append(
            _bad(
                "C8b",
                8,
                "every EVI in the stopping round is below the comparator",
                f"comparator {comparator}, but {above} did not fall below it",
                quantifier="universal over the stopping round",
            )
        )
    else:
        results.append(
            _ok(
                "C8b",
                8,
                "every EVI in the stopping round is below the comparator",
                f"comparator {comparator}, EVIs {evis}",
                quantifier="universal over the stopping round",
                evidence={"comparator": comparator, "evis": evis},
            )
        )

    # 8c -- the comparator must be what it says it is.
    #
    # This is the check the criterion's v1.1 amendment is actually asking
    # for. The event declares its own derivation in `comparator_source`;
    # that derivation is recomputable from strategy-belief state carried
    # elsewhere in the trace. A hardcoded literal survives every check
    # that only reads the number back.
    source = str(payload.get("comparator_source", ""))
    if "strategy-belief" not in source or "max" not in source.lower():
        results.append(
            _unk(
                "C8c",
                8,
                "comparator is derived from state, not chosen",
                f"comparator_source is {source!r}; without a declared derivation the "
                "recorded value cannot be recomputed, so a constant chosen after the "
                "fact is indistinguishable from a computed one",
            )
        )
    else:
        labels = t.strategy_labels_at(stopped.seq)
        if not labels:
            results.append(
                _unk(
                    "C8c",
                    8,
                    "comparator is derived from state, not chosen",
                    "no strategy-belief labels reconstructable at the stopping point",
                )
            )
        else:
            recomputed = max(int(v) for v in labels.values())
            readable = {k.rsplit(":", 1)[-1]: str(v) for k, v in sorted(labels.items())}
            if recomputed != comparator:
                results.append(
                    _bad(
                        "C8c",
                        8,
                        "comparator is derived from state, not chosen",
                        f"recorded comparator {comparator} != {recomputed}, the value its "
                        f"own declared source ({source!r}) yields from the trace's "
                        f"strategy beliefs {readable}",
                        evidence={"recorded": comparator, "recomputed": recomputed, "labels": readable},
                    )
                )
            else:
                results.append(
                    _ok(
                        "C8c",
                        8,
                        "comparator is derived from state, not chosen",
                        f"comparator {comparator} == max strategy-belief ordinal over {readable}",
                        evidence={"recorded": comparator, "recomputed": recomputed, "labels": readable},
                    )
                )

    # 8d -- clause A1. Recording a comparator and finding EVIs below it
    # proves nothing if no admissible comparator value could have produced
    # a different decision. The comparator's domain is the belief-label
    # ordinal range, because that is what its declared source is a max of.
    best = max((v for v in evis.values() if v is not None), default=None)
    if best is None:
        results.append(_unk("C8d", 8, "the comparator could have changed the decision (A1)", "no EVI figures in the stopping round"))
    else:
        flipping = [c for c in COMPARATOR_DOMAIN if best > c]
        if flipping:
            results.append(
                _ok(
                    "C8d",
                    8,
                    "the comparator could have changed the decision (A1)",
                    f"best EVI {best} exceeds comparator values {flipping} within the "
                    f"admissible range {list(COMPARATOR_DOMAIN)}, so the stop was contingent "
                    f"on the comparator actually being {comparator}",
                    evidence={"best_evi": best, "flipping_values": flipping},
                )
            )
        else:
            results.append(
                _bad(
                    "C8d",
                    8,
                    "the comparator could have changed the decision (A1)",
                    f"best EVI {best} is below every admissible comparator value "
                    f"{list(COMPARATOR_DOMAIN)}, so exploration would have stopped whatever "
                    "the comparator was. Criterion 8 is satisfied here by a condition that "
                    "cannot fail, which clause A1 says does not count and section 6 scores FAIL",
                    evidence={"best_evi": best, "admissible": list(COMPARATOR_DOMAIN)},
                )
            )
    return results


# ---------------------------------------------------------------------------
# criterion 9
# ---------------------------------------------------------------------------


def _c9(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    commit = t.first("STRATEGY_COMMITTED")
    if commit is None:
        return [_bad("C9a", 9, "commitment cites exhausted information value", "no STRATEGY_COMMITTED event")]

    stopped = t.first("EXPLORATION_STOPPED")
    if stopped is None:
        results.append(
            _bad(
                "C9a",
                9,
                "commitment cites exhausted information value",
                "no EXPLORATION_STOPPED event exists, so information value was never "
                "shown to be exhausted; any rationale claiming otherwise is prose without "
                "a record behind it",
            )
        )
    elif stopped.seq not in commit.caused_by:
        results.append(
            _bad(
                "C9a",
                9,
                "commitment cites exhausted information value",
                f"EXPLORATION_STOPPED at seq {stopped.seq} is not in the commitment's "
                f"caused_by {list(commit.caused_by)}",
                quantifier="must-contain",
            )
        )
    else:
        figures = [str(stopped.payload.get("comparator")), str(stopped.payload.get("best_evi"))]
        absent = [f for f in figures if f not in commit.rationale]
        if absent:
            results.append(
                _bad(
                    "C9a",
                    9,
                    "commitment cites exhausted information value",
                    f"rationale does not carry the recorded figure(s) {absent} from the "
                    f"EXPLORATION_STOPPED it cites: {commit.rationale!r}",
                )
            )
        else:
            results.append(
                _ok(
                    "C9a",
                    9,
                    "commitment cites exhausted information value",
                    f"caused_by includes EXPLORATION_STOPPED seq {stopped.seq}, and the "
                    f"rationale quotes its comparator {figures[0]} and best EVI {figures[1]}",
                )
            )

    next_action = commit.payload.get("next_action")
    strategy_id = commit.payload.get("strategy_id")
    if not next_action or not str(next_action).strip():
        results.append(
            _bad(
                "C9b",
                9,
                "commitment cites a concrete next action",
                f"next_action is {next_action!r}",
            )
        )
    elif str(next_action).strip() == str(strategy_id):
        results.append(
            _bad(
                "C9b",
                9,
                "commitment cites a concrete next action",
                f"next_action {next_action!r} merely restates the strategy id",
            )
        )
    elif str(next_action) not in commit.rationale:
        results.append(
            _bad(
                "C9b",
                9,
                "commitment cites a concrete next action",
                f"payload names next_action {next_action!r} but the rationale does not: "
                f"{commit.rationale!r}",
            )
        )
    else:
        results.append(
            _ok(
                "C9b",
                9,
                "commitment cites a concrete next action",
                f"rationale quotes the recorded next_action {next_action!r} verbatim",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criteria 10 and 11
# ---------------------------------------------------------------------------


def _c10(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    commit = t.first("STRATEGY_COMMITTED")
    if commit is None:
        return [_bad("C10a", 10, "residual uncertainty recorded", "no STRATEGY_COMMITTED event")]

    residual = commit.payload.get("residual_uncertainty")
    if residual is None:
        return [_bad("C10a", 10, "residual uncertainty recorded", "payload has no residual_uncertainty")]
    if not isinstance(residual, list) or not residual or not all(
        isinstance(r, str) and r.strip() for r in residual
    ):
        return [
            _bad(
                "C10a",
                10,
                "residual uncertainty recorded",
                f"residual_uncertainty is {residual!r}; an empty or blank record is a "
                "no-op assertion and scores FAIL under clause A2",
                quantifier="count >= 1, every item non-blank",
            )
        ]

    results.append(
        _ok(
            "C10a",
            10,
            "residual uncertainty recorded",
            f"{len(residual)} item(s): {residual}",
            quantifier="count >= 1, every item non-blank",
        )
    )

    # 10b -- clause A1 again, in the form this trace actually takes.
    # If every residual item is a restatement of a retained alternative,
    # then criterion 10 cannot fail unless criterion 11 also fails: it is
    # the same invariant asserted twice, and "remaining uncertainty" is
    # recording nothing that retained_alternatives did not already say.
    retained = list(commit.payload.get("retained_alternatives") or [])
    mentioned: set[str] = set()
    non_strategy: list[str] = []
    for item in residual:
        hits = [r for r in retained if r and r in item]
        if hits:
            mentioned.update(hits)
        else:
            non_strategy.append(item)
    if non_strategy:
        results.append(
            _ok(
                "C10b",
                10,
                "residual uncertainty is independent of retained alternatives (A1)",
                f"{len(non_strategy)} residual item(s) say something no retained "
                f"alternative says: {non_strategy}",
                quantifier="count >= 1 residual item not naming a retained alternative",
            )
        )
    else:
        results.append(
            _bad(
                "C10b",
                10,
                "residual uncertainty is independent of retained alternatives (A1)",
                f"every residual item restates a retained alternative "
                f"({sorted(mentioned)} == retained {sorted(retained)}); criteria 10 and 11 "
                "are the same invariant twice and criterion 10 cannot fail independently",
                quantifier="count >= 1 residual item not naming a retained alternative",
                evidence={"residual": residual, "retained": retained},
            )
        )
    return results


def _c11(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    commit = t.first("STRATEGY_COMMITTED")
    if commit is None:
        return [_bad("C11a", 11, "a material alternative is retained", "no STRATEGY_COMMITTED event")]

    retained = commit.payload.get("retained_alternatives")
    if not isinstance(retained, list) or not retained:
        return [
            _bad(
                "C11a",
                11,
                "a material alternative is retained",
                f"retained_alternatives is {retained!r}; an empty collection is a no-op "
                "assertion and scores FAIL under clause A2",
                quantifier="count >= 1",
            )
        ]

    committed_id = commit.payload.get("strategy_id")
    if committed_id in retained:
        results.append(
            _bad(
                "C11a",
                11,
                "a material alternative is retained",
                f"the committed strategy {committed_id!r} is listed as its own alternative",
            )
        )
        return results

    labels = t.strategy_labels_at(commit.seq)
    unknown = [r for r in retained if f"belief:strategy:{r}" not in labels]
    if unknown:
        results.append(
            _unk(
                "C11a",
                11,
                "a material alternative is retained",
                f"no belief label reconstructable for retained {unknown}; plausibility at "
                "commit time cannot be established from the trace",
            )
        )
        return results

    scored = {r: labels[f"belief:strategy:{r}"] for r in retained}
    plausible = {r: str(v) for r, v in scored.items() if v >= PLAUSIBILITY_BAR}
    below = {r: str(v) for r, v in scored.items() if v < PLAUSIBILITY_BAR}

    if plausible:
        results.append(
            _ok(
                "C11a",
                11,
                "a material alternative is retained",
                f"retained at or above {PLAUSIBILITY_BAR.name}: {plausible}"
                + (f"; also retained below the bar: {below}" if below else ""),
                quantifier="must-contain: >= 1 retained alternative at label >= PLAUSIBLE",
                evidence={"retained_labels": {r: str(v) for r, v in scored.items()}},
            )
        )
    else:
        results.append(
            _bad(
                "C11a",
                11,
                "a material alternative is retained",
                f"every retained alternative is below {PLAUSIBILITY_BAR.name}: {below}. "
                "The criterion asks for a strategy that was still plausible at commit "
                "time, not merely one that was not formally eliminated",
                quantifier="must-contain: >= 1 retained alternative at label >= PLAUSIBLE",
                evidence={"retained_labels": {r: str(v) for r, v in scored.items()}},
            )
        )

    # A retained alternative that was never generated is bookkeeping, not
    # optionality.
    generated = {
        e.payload.get("strategy_id") for e in t.of_type("STRATEGY_GENERATED")
    }
    phantom = [r for r in retained if r not in generated]
    if phantom:
        results.append(
            _bad(
                "C11b",
                11,
                "retained alternatives were real candidates",
                f"{phantom} appear as retained alternatives but were never generated",
                quantifier="universal over retained_alternatives",
            )
        )
    else:
        results.append(
            _ok(
                "C11b",
                11,
                "retained alternatives were real candidates",
                f"all of {retained} were generated as candidates",
                quantifier="universal over retained_alternatives",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 12
# ---------------------------------------------------------------------------


def _c12(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    missing_types = sorted(ty for ty in REQUIRES_CAUSATION if not t.of_type(ty))
    if missing_types:
        results.append(
            _bad(
                "C12a",
                12,
                "every decision-event type is present to be checked",
                f"the trace contains no {missing_types}; a universal assertion over an "
                "absent type is vacuously true and scores FAIL under clause A2",
                quantifier="count >= 1 for each type in REQUIRES_CAUSATION",
            )
        )
    else:
        results.append(
            _ok(
                "C12a",
                12,
                "every decision-event type is present to be checked",
                ", ".join(f"{ty}x{len(t.of_type(ty))}" for ty in sorted(REQUIRES_CAUSATION)),
                quantifier="count >= 1 for each type in REQUIRES_CAUSATION",
            )
        )

    offenders: list[str] = []
    checked = 0
    for event in t.events:
        if event.type not in REQUIRES_CAUSATION:
            continue
        checked += 1
        if not event.rationale.strip():
            offenders.append(f"seq {event.seq} ({event.type}): blank rationale")
        elif event.rationale.strip() == event.type:
            offenders.append(f"seq {event.seq}: rationale merely repeats the event type")
        if not event.caused_by:
            offenders.append(f"seq {event.seq} ({event.type}): empty caused_by")
    if offenders:
        results.append(
            _bad(
                "C12b",
                12,
                "decision events carry rationale and causation",
                "; ".join(offenders[:6]),
                quantifier="universal over REQUIRES_CAUSATION events",
            )
        )
    else:
        results.append(
            _ok(
                "C12b",
                12,
                "decision events carry rationale and causation",
                f"all {checked} decision events carry a non-empty rationale and caused_by",
                quantifier="universal over REQUIRES_CAUSATION events",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 13
# ---------------------------------------------------------------------------


def _c13(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []
    dangling: list[str] = []
    for event in t.events:
        for cause in event.caused_by:
            if cause not in t.by_seq:
                dangling.append(f"seq {event.seq} -> missing {cause}")
            elif cause >= event.seq:
                dangling.append(f"seq {event.seq} -> non-earlier {cause}")
    if dangling:
        results.append(
            _bad(
                "C13a",
                13,
                "causal edges are well formed",
                "; ".join(dangling[:6]),
                quantifier="universal over all caused_by edges",
            )
        )
    else:
        edges = sum(len(e.caused_by) for e in t.events)
        results.append(
            _ok(
                "C13a",
                13,
                "causal edges are well formed",
                f"all {edges} edges point at an existing, strictly earlier event",
                quantifier="universal over all caused_by edges",
            )
        )

    intent = t.first("INTENT_DECLARED")
    commit = t.first("STRATEGY_COMMITTED")
    if intent is None or commit is None:
        results.append(
            _bad(
                "C13b",
                13,
                "INTENT_DECLARED reaches STRATEGY_COMMITTED",
                f"intent={intent and intent.seq}, commit={commit and commit.seq}",
            )
        )
        return results

    reachable = t.descendants(intent.seq)
    if commit.seq not in reachable:
        results.append(
            _bad(
                "C13b",
                13,
                "INTENT_DECLARED reaches STRATEGY_COMMITTED",
                f"commit at seq {commit.seq} is not causally reachable from intent at "
                f"seq {intent.seq}",
            )
        )
    else:
        results.append(
            _ok(
                "C13b",
                13,
                "INTENT_DECLARED reaches STRATEGY_COMMITTED",
                f"commit seq {commit.seq} is reachable from intent seq {intent.seq} "
                f"({len(reachable)} of {len(t.events)} events are)",
            )
        )

    orphans = [
        f"seq {e.seq} ({e.type})"
        for e in t.events
        if e.type in REQUIRES_CAUSATION and intent.seq not in t.ancestors(e.seq)
    ]
    if orphans:
        results.append(
            _bad(
                "C13c",
                13,
                "no orphan decision events",
                f"decision events with no ancestral path back to INTENT_DECLARED: {orphans}",
                quantifier="universal over REQUIRES_CAUSATION events",
            )
        )
    else:
        results.append(
            _ok(
                "C13c",
                13,
                "no orphan decision events",
                "every decision event has an ancestral path back to INTENT_DECLARED",
                quantifier="universal over REQUIRES_CAUSATION events",
            )
        )

    unreached = [
        f"seq {e.seq} ({e.type})"
        for e in t.events
        if e.seq != intent.seq and e.seq not in reachable and e.type != "EPISODE_OPENED"
    ]
    if unreached:
        results.append(
            _unk(
                "C13d",
                13,
                "no disconnected non-decision events",
                f"not required by the criterion, but these are causally disconnected: {unreached}",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 14 (static portion only)
# ---------------------------------------------------------------------------


def _c14_static(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = [
        _unk(
            "C14a",
            14,
            "two runs produce byte-identical traces",
            "determinism is not a property of a single trace and cannot be established "
            "from one. Hash-order nondeterminism in particular only manifests across "
            "PYTHONHASHSEED values, so an in-process double-run cannot detect it either. "
            "See probe check C14c",
            superseded_by="C14c",
        )
    ]

    # A weak but genuinely falsifiable supporting signal: the loop
    # documents that every collection is sorted before iteration, and
    # unsorted iteration is visible in the trace when it happens to land
    # unsorted. Passing proves little; failing proves a lot.
    unsorted: list[str] = []
    for index, round_ in enumerate(t.eval_rounds(), start=1):
        ids = [e.payload.get("action_id") for e in round_]
        if ids != sorted(ids, key=lambda x: (x is None, x)):
            unsorted.append(f"evaluation round {index}: {ids}")
    gen = [e.payload.get("strategy_id") for e in t.of_type("STRATEGY_GENERATED")]
    if gen != sorted(gen, key=lambda x: (x is None, x)):
        unsorted.append(f"STRATEGY_GENERATED: {gen}")

    if unsorted:
        results.append(
            _bad(
                "C14b",
                14,
                "iteration order in the trace is sorted",
                "; ".join(unsorted)
                + " -- an unsorted emission order means the ordering is not the "
                "documented deterministic one",
                quantifier="universal over evaluation rounds and generation order",
            )
        )
    else:
        results.append(
            _ok(
                "C14b",
                14,
                "iteration order in the trace is sorted",
                "evaluation rounds and strategy generation are emitted in sorted id order "
                "(supporting signal only: one sorted sample does not establish determinism)",
                quantifier="universal over evaluation rounds and generation order",
            )
        )
    return results


# ---------------------------------------------------------------------------
# criterion 15 (static portion)
# ---------------------------------------------------------------------------


def _c15_static(t: _Trace) -> list[CheckResult]:
    """Replay from the trace and cross-check against independent records.

    Replaying and then comparing against the same events would be
    circular. What is not circular: STRATEGY_RANKED carries a snapshot of
    every strategy belief, emitted by a different code path from the
    BELIEF_UPDATED stream that replay consumes. If replay's reconstruction
    and that snapshot disagree, the trace is not a faithful record.
    """
    from escapement.observation.replay import ReplayError, replay

    results: list[CheckResult] = []
    try:
        episode = replay(t.events)
    except ReplayError as exc:
        return [_bad("C15a", 15, "trace replays to a consistent state", f"ReplayError: {exc}")]

    commit = t.first("STRATEGY_COMMITTED")
    ranked = t.first("STRATEGY_RANKED")
    if commit is None or ranked is None:
        return [_unk("C15a", 15, "trace replays to a consistent state", "no commitment or ranking to cross-check against")]

    problems: list[str] = []
    if episode.committed_strategy != commit.payload.get("strategy_id"):
        problems.append(
            f"replay committed {episode.committed_strategy!r}, trace says "
            f"{commit.payload.get('strategy_id')!r}"
        )

    order = list(ranked.payload.get("order", []))
    if order and episode.committed_strategy != order[0]:
        problems.append(
            f"replay committed {episode.committed_strategy!r} but the ranking's top "
            f"entry is {order[0]!r}"
        )

    snapshot = ranked.payload.get("beliefs") or {}
    for sid, label_name in sorted(snapshot.items()):
        replayed = episode.beliefs.get(f"belief:strategy:{sid}")
        if replayed is None:
            problems.append(f"replay reconstructed no belief for {sid}")
        elif replayed.name != label_name:
            problems.append(
                f"{sid}: ranking snapshot says {label_name}, replay reconstructed "
                f"{replayed.name}"
            )

    if not snapshot:
        results.append(
            _unk(
                "C15a",
                15,
                "trace replays to a consistent state",
                "STRATEGY_RANKED carries no belief snapshot, so replay's belief values "
                "have nothing independent to be checked against",
            )
        )
    elif problems:
        results.append(
            _bad("C15a", 15, "trace replays to a consistent state", "; ".join(problems))
        )
    else:
        results.append(
            _ok(
                "C15a",
                15,
                "trace replays to a consistent state",
                f"replay reproduces commitment {episode.committed_strategy!r} and all "
                f"{len(snapshot)} strategy beliefs recorded independently by STRATEGY_RANKED",
                evidence={"beliefs": {k: v.name for k, v in sorted(episode.beliefs.items())}},
            )
        )

    results.append(
        _unk(
            "C15b",
            15,
            "replay reproduces the live run without re-executing",
            "a trace cannot show what a live run produced, nor that replay avoided calling "
            "the capability. See probe check C15c",
            superseded_by="C15c",
        )
    )
    return results


# ---------------------------------------------------------------------------
# advisory checks: found, but not yet contract criteria
# ---------------------------------------------------------------------------


def _advisory(t: _Trace) -> list[CheckResult]:
    results: list[CheckResult] = []

    ids = [e.payload.get("evidence_id") for e in t.of_type("EVIDENCE_ADDED")]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        results.append(
            _bad(
                "N1",
                None,
                "no evidence admitted more than once",
                f"evidence id(s) {duplicates} appear {[ids.count(d) for d in duplicates]} "
                "times; re-admitting the same evidence moves a belief again on information "
                "it already carried",
                quantifier="universal over EVIDENCE_ADDED evidence_id",
            )
        )
    else:
        results.append(
            _ok(
                "N1",
                None,
                "no evidence admitted more than once",
                f"{len(ids)} evidence record(s), all distinct: {ids}",
                quantifier="universal over EVIDENCE_ADDED evidence_id",
            )
        )

    # One observation moves a belief at most one ordinal step, unless the
    # evidence behind it is decisive (Decisiveness.DECISIVE spans the whole
    # 0..4 range). Walk each belief update back to the evidence that
    # justified it and check the cap.
    decisive_by_seq = {
        e.seq: bool(e.payload.get("decisive")) for e in t.of_type("EVIDENCE_ADDED")
    }
    breaches: list[str] = []
    unresolved = 0
    for event in t.of_type("BELIEF_UPDATED"):
        try:
            delta = abs(
                int(_label(event.payload["after"])) - int(_label(event.payload["before"]))
            )
        except (KeyError, _Unreadable):
            unresolved += 1
            continue
        ancestors = t.ancestors(event.seq)
        decisive = any(decisive_by_seq.get(a, False) for a in ancestors)
        cap = int(BeliefLabel.ESTABLISHED) if decisive else 1
        if delta > cap:
            breaches.append(
                f"seq {event.seq} ({event.payload.get('belief_id')}): moved {delta} steps "
                f"on {'decisive' if decisive else 'ordinary'} evidence (cap {cap})"
            )
    if breaches:
        results.append(
            _bad("N2", None, "one observation moves a belief at most one step", "; ".join(breaches))
        )
    elif unresolved:
        results.append(
            _unk(
                "N2",
                None,
                "one observation moves a belief at most one step",
                f"{unresolved} belief update(s) carry unreadable before/after labels",
            )
        )
    else:
        results.append(
            _ok(
                "N2",
                None,
                "one observation moves a belief at most one step",
                "every belief update stays within its evidence's decisiveness cap",
                quantifier="universal over BELIEF_UPDATED",
            )
        )
    return results


# ---------------------------------------------------------------------------
# static entry point
# ---------------------------------------------------------------------------

_STATIC_CHECKS: tuple[Callable[[_Trace], Any], ...] = (
    _p1_seq,
    _p6_collapse,
    _c1,
    _c2,
    _c3,
    _c4,
    _c5,
    _c6,
    _c7,
    _c8,
    _c9,
    _c10,
    _c11,
    _c12,
    _c13,
    _c14_static,
    _c15_static,
    _advisory,
)


def check(events: list[Event]) -> list[CheckResult]:
    """Score a trace. Static, trace-only, executes nothing.

    A check that raises is reported UNVERIFIED rather than being allowed
    to abort the run or, worse, be counted as a pass.
    """
    t = _Trace(events)
    results: list[CheckResult] = []
    for fn in _STATIC_CHECKS:
        name = fn.__name__.lstrip("_").upper()
        try:
            out = fn(t)
        except Exception as exc:  # noqa: BLE001 - a broken check is not a pass
            results.append(
                _unk(name, None, f"{name} raised", f"{type(exc).__name__}: {exc}")
            )
            continue
        results.extend(out if isinstance(out, list) else [out])
    return results


# ---------------------------------------------------------------------------
# probe: live checks
# ---------------------------------------------------------------------------

_HASH_SEEDS = ("0", "1", "42", "31337", "987654321")


def _run_in_subprocess(out: Path, seed: str) -> tuple[int, str]:
    code = (
        "import sys; sys.path.insert(0, r'''%s''')\n"
        "from pathlib import Path\n"
        "from conformance.c001.run import main\n"
        "main(Path(r'''%s'''))\n" % (_REPO_ROOT, out)
    )
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    return proc.returncode, proc.stderr


def _probe_determinism() -> list[CheckResult]:
    """Criterion 14, done the only way that can catch hash-order drift.

    Re-running in-process reuses one interpreter and therefore one string
    hash seed, so `set()` iteration order is stable within the process and
    an in-process double-run reports determinism that is not there. These
    runs are separate interpreters with explicitly differing
    PYTHONHASHSEED values.
    """
    results: list[CheckResult] = []
    digests: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for seed in _HASH_SEEDS:
            out = Path(tmp) / f"events-{seed}.jsonl"
            rc, err = _run_in_subprocess(out, seed)
            if rc != 0:
                return [
                    _unk(
                        "C14c",
                        14,
                        "byte-identical across PYTHONHASHSEED values",
                        f"the run failed under PYTHONHASHSEED={seed} (rc {rc}): "
                        f"{err.strip().splitlines()[-1] if err.strip() else ''}",
                    )
                ]
            digests[seed] = out.read_bytes()

    distinct = {v for v in digests.values()}
    if len(distinct) != 1:
        differing = sorted(
            seed for seed in digests if digests[seed] != digests[_HASH_SEEDS[0]]
        )
        # Locate the first differing line, so the report names the defect
        # rather than just asserting one.
        base = digests[_HASH_SEEDS[0]].decode("utf-8").splitlines()
        other = digests[differing[0]].decode("utf-8").splitlines()
        where = next(
            (
                i
                for i, (a, b) in enumerate(zip(base, other), start=1)
                if a != b
            ),
            None,
        )
        results.append(
            _bad(
                "C14c",
                14,
                "byte-identical across PYTHONHASHSEED values",
                f"{len(distinct)} distinct traces across seeds {list(digests)}; "
                f"PYTHONHASHSEED={differing[0]} first differs from "
                f"PYTHONHASHSEED={_HASH_SEEDS[0]} at line {where}",
                evidence={"seeds": list(digests), "first_differing_line": where},
            )
        )
    else:
        results.append(
            _ok(
                "C14c",
                14,
                "byte-identical across PYTHONHASHSEED values",
                f"{len(_HASH_SEEDS)} separate interpreters with PYTHONHASHSEED in "
                f"{list(_HASH_SEEDS)} produced one identical trace "
                f"({len(next(iter(distinct)))} bytes)",
                quantifier="must-equal, byte-for-byte, no fields excluded",
            )
        )

    # Criterion 14 also requires the volatile-field allow-list to be
    # declared in the README rather than inferred. An allow-list naming a
    # field that does not occur in the trace would be an exclusion that
    # excludes nothing, so it is checked against the trace, not just read.
    if not README_PATH.exists():
        results.append(
            _bad("C14d", 14, "determinism allow-list declared in the README", f"{README_PATH} does not exist")
        )
    else:
        text = README_PATH.read_text(encoding="utf-8")
        if "allow-list" not in text.lower():
            results.append(
                _bad(
                    "C14d",
                    14,
                    "determinism allow-list declared in the README",
                    "the README declares no allow-list, so criterion 14's exclusions would "
                    "have to be inferred",
                )
            )
        else:
            declares_empty = "allow-list is therefore empty" in text or "no volatile fields" in text
            if declares_empty:
                results.append(
                    _ok(
                        "C14d",
                        14,
                        "determinism allow-list declared in the README",
                        "the README declares an empty allow-list, and C14c compared the "
                        "traces byte-for-byte with no fields excluded, so the declaration "
                        "is the one that was tested",
                    )
                )
            else:
                results.append(
                    _unk(
                        "C14d",
                        14,
                        "determinism allow-list declared in the README",
                        "the README mentions an allow-list but this check cannot tell which "
                        "fields it names; C14c excluded nothing, which is at least as strict",
                    )
                )
    return results


def _probe_comparator() -> list[CheckResult]:
    """Criterion 8, clause A1: does the comparator do any work?

    Recording a comparator and observing EVIs below it establishes
    nothing about whether the comparator influences anything. This runs
    the real loop twice over a synthetic scenario built so that the two
    runs differ *only* in the state the comparator is a function of, and
    so that the correct comparator sits on either side of the round-2 EVI.

        variant LOW   best strategy belief PLAUSIBLE(2), round-2 EVI 3
                      -> 3 > 2, exploration must continue
        variant HIGH  best strategy belief LIKELY(3),    round-2 EVI 3
                      -> 3 <= 3, exploration must stop

    If both variants behave the same, the comparator is inert. A
    hardcoded literal fails this, and so does any comparator that does not
    move with belief state.
    """
    from escapement.capabilities.models import Capability, CapabilityKind
    from escapement.evidence.models import Evidence, EvidenceKind, Interpretation
    from escapement.information.action import ActionKind, InformationAction
    from escapement.information.value import InformationValue
    from escapement.intent.models import Intent
    from escapement.loop import run_episode
    from escapement.state.models import BeliefState
    from escapement.strategy.models import Reversibility, Strategy

    WORLD = "belief:world:probe"

    capabilities = {
        "probe_tool": Capability(
            id="probe_tool",
            kind=CapabilityKind.TOOL,
            description="synthetic probe capability",
            provides=("PROBE_A", "PROBE_B"),
        )
    }
    actions = {
        name: InformationAction(
            id=name,
            kind=ActionKind.INSPECT_REPOSITORY,
            capability_id="probe_tool",
            description=f"synthetic {name}",
            cost=1,
        )
        for name in ("PROBE_A", "PROBE_B")
    }
    strategies = [
        Strategy(id=sid, description=sid, reversibility=Reversibility.HIGH, next_action=f"do {sid}")
        for sid in ("POS", "NEG", "STABLE_A", "STABLE_B")
    ]

    def evaluate(action: InformationAction, beliefs: BeliefState) -> InformationValue:
        # Round 1 yields EVI 5 (above the opening comparator of 2, so the
        # loop explores); every later round yields EVI 3, which is the
        # value the comparator has to straddle.
        seen = beliefs.get(WORLD) is not None
        return InformationValue(action_id=action.id, expected_improvement=4 if seen else 6, cost=1)

    def perform(action: InformationAction) -> Evidence:
        return Evidence(
            id="e_probe",
            kind=EvidenceKind.EXECUTION,
            claim="synthetic probe evidence",
            source="probe_tool",
            produced_by=action.id,
            decisive=False,
            payload={"n": 1},
        )

    def interpret(evidence: Evidence) -> Interpretation:
        return Interpretation(subject="probe_subject", value=evidence.payload["n"], supports=1)

    def world_of(subject: str) -> str:
        return WORLD

    def make_correlations(positive: bool):
        def strategy_of(world_belief_id: str) -> tuple[tuple[str, int], ...]:
            if world_belief_id != WORLD:
                return ()
            return (("POS", 1), ("NEG", -1)) if positive else (("NEG", -1),)

        return strategy_of

    def run(positive: bool) -> EventTrace:
        trace = EventTrace(episode_id="probe-comparator")
        try:
            run_episode(
                episode_id="probe-comparator",
                intent=Intent(
                    id="probe",
                    outcome="probe whether the comparator binds",
                    success_criteria=("a commitment is reached",),
                    non_goals=(),
                ),
                capabilities=capabilities,
                actions=actions,
                strategies=strategies,
                perform=perform,
                evaluate_value=evaluate,
                interpret=interpret,
                world_belief_of=world_of,
                strategy_belief_of=make_correlations(positive),
                trace=trace,
                max_rounds=3,
            )
        except Exception:  # noqa: BLE001 - the trace so far is the evidence
            pass
        return trace

    low = run(positive=False)
    high = run(positive=True)

    def stop_info(trace: EventTrace) -> tuple[bool, Any, Any]:
        stopped = trace.first("EXPLORATION_STOPPED")
        if stopped is None:
            return False, None, None
        return True, stopped.payload.get("comparator"), stopped.payload.get("best_evi")

    low_stopped, low_cmp, low_best = stop_info(low)
    high_stopped, high_cmp, high_best = stop_info(high)

    detail = (
        f"LOW variant (best strategy belief PLAUSIBLE): stopped={low_stopped} "
        f"comparator={low_cmp} best_evi={low_best}; "
        f"HIGH variant (best strategy belief LIKELY): stopped={high_stopped} "
        f"comparator={high_cmp} best_evi={high_best}"
    )
    evidence = {
        "low": {"stopped": low_stopped, "comparator": low_cmp, "best_evi": low_best},
        "high": {"stopped": high_stopped, "comparator": high_cmp, "best_evi": high_best},
    }

    if high_stopped and not low_stopped and high_cmp == 3 and low_cmp in (None, 2):
        return [
            _ok(
                "C8e",
                8,
                "the comparator changes the stopping decision (live counterfactual)",
                "the same EVI of 3 stops exploration when the comparator is 3 and does not "
                "when it is 2, so the comparator mechanism is load-bearing. " + detail,
                evidence=evidence,
            )
        ]
    if low_stopped == high_stopped:
        return [
            _bad(
                "C8e",
                8,
                "the comparator changes the stopping decision (live counterfactual)",
                "both variants behaved identically despite differing only in the belief "
                "state the comparator is defined over; the comparator did not influence "
                "the decision. " + detail,
                evidence=evidence,
            )
        ]
    return [
        _bad(
            "C8e",
            8,
            "the comparator changes the stopping decision (live counterfactual)",
            "the variants differed, but not in the direction the comparator's declared "
            "definition predicts. " + detail,
            evidence=evidence,
        )
    ]


def _probe_replay() -> list[CheckResult]:
    """Criterion 15, live: same commitment and beliefs, no re-execution.

    The no-re-execution half is made falsifiable by replacing the
    capability with one that raises. If replay reaches it, the run dies
    and the check fails; a replay that merely happens not to need it
    cannot be distinguished any other way.
    """
    from escapement.loop import run_episode
    from escapement.observation.replay import replay
    from conformance.c001 import scenario

    calls: list[str] = []

    def counting_perform(action):
        calls.append(action.id)
        return scenario.perform(action)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        trace = EventTrace(episode_id="exp001", path=path)
        live = run_episode(
            episode_id="exp001",
            intent=scenario.INTENT,
            capabilities=scenario.CAPABILITIES,
            actions=scenario.ACTIONS,
            strategies=scenario.STRATEGIES,
            perform=counting_perform,
            evaluate_value=scenario.evaluate_value,
            interpret=scenario.interpret,
            world_belief_of=scenario.world_belief_of,
            strategy_belief_of=scenario.strategy_belief_of,
            trace=trace,
        )
        during_run = len(calls)

        original = scenario.perform

        def exploding(action):  # pragma: no cover - must never be reached
            raise AssertionError(
                f"replay re-executed information action {action.id}; criterion 15 "
                "requires reconstruction from the trace alone"
            )

        scenario.perform = exploding
        try:
            episode = replay(load(path))
        finally:
            scenario.perform = original

    after_run = len(calls) - during_run
    problems: list[str] = []
    if after_run:
        problems.append(f"replay performed {after_run} information action(s)")
    if episode.committed_strategy != live.commitment.strategy_id:
        problems.append(
            f"commitment {episode.committed_strategy!r} != live {live.commitment.strategy_id!r}"
        )
    if episode.retained_alternatives != live.commitment.retained_alternatives:
        problems.append(
            f"retained {episode.retained_alternatives} != live "
            f"{live.commitment.retained_alternatives}"
        )
    if episode.residual_uncertainty != live.commitment.residual_uncertainty:
        problems.append("residual_uncertainty differs between replay and live run")

    live_labels = {b.id: b.label for b in live.beliefs.beliefs.values()}
    for bid, label in sorted(live_labels.items()):
        if episode.beliefs.get(bid) != label:
            problems.append(
                f"belief {bid}: live {label.name}, replay {episode.beliefs.get(bid)}"
            )

    if problems:
        return [
            _bad(
                "C15c",
                15,
                "replay reproduces the live run without re-executing",
                "; ".join(problems),
            )
        ]
    return [
        _ok(
            "C15c",
            15,
            "replay reproduces the live run without re-executing",
            f"replay reconstructed the same commitment ({episode.committed_strategy}), the "
            f"same retained alternatives and all {len(live_labels)} belief values, with the "
            "capability replaced by one that raises if called",
            evidence={"beliefs": {k: v.name for k, v in sorted(live_labels.items())}},
        )
    ]


def _probe_p7_no_network() -> list[CheckResult]:
    """P7, live: no socket is opened during the run.

    Installing a guard in place of `socket.socket` makes the precondition
    falsifiable instead of asserted. Anything reaching a network -- a
    provider SDK, an MCP client, a stray HTTP call -- raises.
    """
    import socket

    from escapement.loop import run_episode
    from conformance.c001 import scenario

    opened: list[str] = []
    real_socket = socket.socket
    real_create = socket.create_connection

    class _Guard(real_socket):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            opened.append("socket()")
            raise AssertionError("P7: the run opened a socket")

    def _guard_create(*a, **kw):
        opened.append("create_connection()")
        raise AssertionError("P7: the run opened a connection")

    socket.socket = _Guard  # type: ignore[assignment]
    socket.create_connection = _guard_create  # type: ignore[assignment]
    try:
        run_episode(
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
            trace=EventTrace(episode_id="exp001"),
        )
    except AssertionError as exc:
        return [_bad("P7", "P7", "no network call during the run", str(exc))]
    finally:
        socket.socket = real_socket  # type: ignore[assignment]
        socket.create_connection = real_create  # type: ignore[assignment]

    return [
        _ok(
            "P7",
            "P7",
            "no network call during the run",
            "a full episode ran with socket.socket and socket.create_connection replaced "
            "by guards that raise; neither was reached",
        )
    ]


_PROBE_CHECKS: tuple[Callable[[], list[CheckResult]], ...] = (
    _probe_p7_no_network,
    _probe_comparator,
    _probe_determinism,
    _probe_replay,
)


def probe() -> list[CheckResult]:
    """Live checks. Runs the experiment, including in subprocesses.

    Everything here answers a question a trace cannot: whether a recorded
    value is load-bearing, whether two runs agree, whether replay avoids
    the capability.
    """
    results: list[CheckResult] = []
    for fn in _PROBE_CHECKS:
        name = fn.__name__.lstrip("_").upper()
        try:
            results.extend(fn())
        except Exception as exc:  # noqa: BLE001
            results.append(
                _unk(name, None, f"{name} raised", f"{type(exc).__name__}: {exc}")
            )
    return results


# ---------------------------------------------------------------------------
# roll-up
# ---------------------------------------------------------------------------


def _effective(results: Iterable[CheckResult]) -> list[CheckResult]:
    """Drop deferred markers whose successor check actually decided."""
    results = list(results)
    settled = {r.id for r in results if r.status is not Status.UNVERIFIED}
    return [r for r in results if r.superseded_by not in settled or r.superseded_by is None]


def roll_up(results: Iterable[CheckResult]) -> dict[Any, Status]:
    """Worst status per criterion. UNVERIFIED never rounds up to PASS."""
    out: dict[Any, Status] = {}
    for result in _effective(results):
        if result.criterion is None:
            continue
        current = out.get(result.criterion)
        if current is None or _SEVERITY[result.status] > _SEVERITY[current]:
            out[result.criterion] = result.status
    return out


def verdict(results: Iterable[CheckResult]) -> Status:
    statuses = [r.status for r in _effective(results)]
    if Status.FAIL in statuses:
        return Status.FAIL
    if Status.UNVERIFIED in statuses:
        return Status.UNVERIFIED
    return Status.PASS


def _sort_key(criterion: Any) -> tuple[int, Any]:
    if isinstance(criterion, int):
        return (1, criterion)
    return (0, str(criterion))


def report(results: list[CheckResult]) -> str:
    lines = [str(r) for r in results]
    rolled = roll_up(results)
    lines.append("")
    lines.append("-- per criterion --")
    for criterion in sorted(rolled, key=_sort_key):
        label = criterion if isinstance(criterion, str) else f"criterion {criterion}"
        lines.append(f"  {rolled[criterion]:<11} {label}")
    advisory = [r for r in results if r.criterion is None]
    if advisory:
        lines.append("-- advisory (not contract criteria) --")
        for r in advisory:
            lines.append(f"  {r.status:<11} {r.id} {r.title}")
    lines.append("")
    lines.append(f"VERDICT: {verdict(results)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = TRACE_PATH
    run_probe = True
    if "--no-probe" in argv:
        argv.remove("--no-probe")
        run_probe = False
    if argv:
        path = Path(argv[0])

    results = check(load(path))
    if run_probe:
        results += probe()
    print(report(results))
    return 0 if verdict(results) is Status.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
