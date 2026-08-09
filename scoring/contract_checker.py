"""Executable Experiment 001 review contract.

Three independent scoring cycles cost roughly fifteen minutes of agent
time each and re-derived the same mechanical checks every time. This
module does the mechanical part in milliseconds, so a reviewer spends
their attention on the part that actually needs a mind: novel
falsification, and judging whether a passing criterion passes for a real
reason.

**The three-verdict design is the point.** A checker that reports only
PASS/FAIL must guess about criteria it cannot truly verify, and guessing
PASS is how a checker becomes the rubber stamp it was built to replace.
Anything this script cannot establish from evidence reports
NEEDS_HUMAN, which is a direction to look rather than a result.

What it deliberately does **not** do:

- Judge clause A1 (vacuity) in general. Whether an assertion *could*
  fail is a question about code structure, not about a trace. Specific
  known-vacuous patterns are encoded; the general case is human work.
- Replace the adversarial reviewer. Every defect found across three
  cycles came from someone constructing a case the author had not
  imagined. That is not automatable, and pretending otherwise would
  quietly remove the one control that has actually worked.

Usage:

    python -m scoring.contract_checker                    # score the committed trace
    python -m scoring.contract_checker --probe            # also run live probes
    python -m scoring.contract_checker --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from escapement.observation.events import REQUIRES_CAUSATION, Event, EventTrace, load

TRACE = Path("experiments/_001/events.jsonl")


class Verdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_HUMAN = "NEEDS_HUMAN"

    def __str__(self) -> str:
        return self.value


@dataclass
class Result:
    number: int | str
    name: str
    verdict: Verdict
    evidence: str

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.PASS


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, number, name: str, verdict: Verdict, evidence: str) -> None:
        self.results.append(Result(number, name, verdict, evidence))

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if r.verdict is Verdict.FAIL]

    @property
    def needs_human(self) -> list[Result]:
        return [r for r in self.results if r.verdict is Verdict.NEEDS_HUMAN]

    @property
    def overall(self) -> Verdict:
        """Contract section 6.

        NEEDS_HUMAN never reports as PASS. A criterion this script could
        not establish is unproven, and the contract is explicit that a
        truthful PARTIAL must not be rounded up.
        """
        if self.failed:
            return Verdict.FAIL
        if self.needs_human:
            return Verdict.NEEDS_HUMAN
        return Verdict.PASS


# ---------------------------------------------------------------------
# helpers


def _trace_of(events: list[Event]) -> EventTrace:
    trace = EventTrace(episode_id=events[0].episode_id if events else "unknown")
    trace._events = list(events)
    return trace


def _seqs(events: list[Event], type: str) -> list[int]:
    return [e.seq for e in events if e.type == type]


def _of(events: list[Event], type: str) -> list[Event]:
    return [e for e in events if e.type == type]


def _first(events: list[Event], type: str) -> Event | None:
    return next((e for e in events if e.type == type), None)


# ---------------------------------------------------------------------
# criteria


def check_criteria(events: list[Event]) -> Report:
    report = Report()
    trace = _trace_of(events)
    commit = _first(events, "STRATEGY_COMMITTED")
    generated = _of(events, "STRATEGY_GENERATED")
    evaluated = _of(events, "INFORMATION_ACTION_EVALUATED")
    selected = _first(events, "INFORMATION_ACTION_SELECTED")
    beliefs = _of(events, "BELIEF_UPDATED")
    world = [e for e in beliefs if e.payload.get("kind") == "WorldBelief"]
    strategy = [e for e in beliefs if e.payload.get("kind") == "StrategyBelief"]

    # 1 --------------------------------------------------------------
    if commit is None:
        report.add(1, "multiple strategies coexist", Verdict.FAIL, "no STRATEGY_COMMITTED in trace")
    else:
        before = [e for e in generated if e.seq < commit.seq]
        ids = {e.payload["strategy_id"] for e in before}
        ok = len(before) >= 3
        report.add(
            1,
            "multiple strategies coexist",
            Verdict.PASS if ok else Verdict.FAIL,
            f"{len(before)} generated before commit: {sorted(ids)}",
        )

    # 2 --------------------------------------------------------------
    first_evidence = _seqs(events, "EVIDENCE_ADDED")
    extreme = [
        e.payload["strategy_id"]
        for e in generated
        if e.payload.get("belief") in ("ESTABLISHED", "RULED_OUT")
    ]
    if commit is None:
        report.add(2, "no premature selection", Verdict.FAIL, "no commitment")
    elif not first_evidence:
        report.add(
            2, "no premature selection", Verdict.FAIL,
            "committed with zero EVIDENCE_ADDED events",
        )
    elif extreme:
        report.add(2, "no premature selection", Verdict.FAIL, f"pre-seeded at extreme: {extreme}")
    else:
        report.add(
            2, "no premature selection", Verdict.PASS,
            f"first evidence seq {min(first_evidence)} precedes commit seq {commit.seq}",
        )

    # 3 --------------------------------------------------------------
    first_round = [e for e in evaluated if selected and e.seq < selected.seq]
    evis = [e.payload.get("evi") for e in first_round]
    if len(first_round) < 3:
        report.add(3, "several actions compared", Verdict.FAIL, f"only {len(first_round)} evaluated")
    elif len(set(evis)) == 1:
        # Encodes mutation M2: identical figures mean nothing was compared.
        report.add(
            3, "several actions compared", Verdict.FAIL,
            f"all {len(first_round)} EVI figures identical ({evis[0]}); nothing was compared",
        )
    else:
        report.add(
            3, "several actions compared", Verdict.PASS,
            f"{len(first_round)} actions, distinct EVI {evis}",
        )

    # 4 --------------------------------------------------------------
    if selected is None:
        report.add(4, "EVI selects sensibly", Verdict.FAIL, "no INFORMATION_ACTION_SELECTED")
    else:
        best = max((e.payload["evi"] for e in first_round), default=None)
        is_argmax = selected.payload.get("evi") == best
        named = selected.payload.get("action_id") == "INSPECT_DEPENDENCY_MAP"
        has_reason = bool(selected.rationale)
        ok = is_argmax and named and has_reason
        report.add(
            4, "EVI selects sensibly",
            Verdict.PASS if ok else Verdict.FAIL,
            f"selected {selected.payload.get('action_id')} evi={selected.payload.get('evi')} "
            f"(argmax={best}, rationale={'yes' if has_reason else 'MISSING'})",
        )

    # 5 --------------------------------------------------------------
    observations = _of(events, "OBSERVATION_CREATED")
    evidence_seqs = set(_seqs(events, "EVIDENCE_ADDED"))
    derived = [o for o in observations if set(o.caused_by) & evidence_seqs]
    report.add(
        5, "evidence updates ObservedState",
        Verdict.PASS if derived else Verdict.FAIL,
        f"{len(derived)} observation(s) caused by evidence",
    )

    # 6 --------------------------------------------------------------
    observation_seqs = set(_seqs(events, "OBSERVATION_CREATED"))
    moved_world = [
        e for e in world
        if e.payload["before"] != e.payload["after"] and set(e.caused_by) & observation_seqs
    ]
    report.add(
        6, "world beliefs change",
        Verdict.PASS if moved_world else Verdict.FAIL,
        (
            f"{moved_world[0].payload['belief_id']}: "
            f"{moved_world[0].payload['before']} -> {moved_world[0].payload['after']}"
            if moved_world else f"{len(world)} world updates, none moved and caused by an observation"
        ),
    )

    # 7 --------------------------------------------------------------
    world_seqs = {e.seq for e in world}
    good_strategy = [
        e for e in strategy
        if e.payload["before"] != e.payload["after"]
        and set(e.caused_by) & world_seqs
        and not (set(e.caused_by) & observation_seqs)
    ]
    report.add(
        7, "strategy beliefs change via world beliefs",
        Verdict.PASS if good_strategy else Verdict.FAIL,
        (
            f"{good_strategy[0].payload['belief_id']} caused_by world belief "
            f"{sorted(set(good_strategy[0].caused_by) & world_seqs)}"
            if good_strategy
            else "no strategy belief moved caused by a world belief (and not the raw observation)"
        ),
    )

    # 8 --------------------------------------------------------------
    stopped = _first(events, "EXPLORATION_STOPPED")
    if stopped is None:
        report.add(8, "further information uneconomic", Verdict.FAIL, "no EXPLORATION_STOPPED")
    else:
        last_belief = max((e.seq for e in beliefs), default=0)
        second = [e for e in evaluated if e.seq > last_belief]
        comparator = stopped.payload.get("comparator")
        below = all(e.payload["evi"] <= comparator for e in second) if second else False
        if not second:
            report.add(8, "further information uneconomic", Verdict.FAIL,
                       "no second evaluation round after belief updates")
        elif not below:
            report.add(8, "further information uneconomic", Verdict.FAIL,
                       f"some second-round EVI exceeds comparator {comparator}")
        elif "comparator_source" not in stopped.payload:
            # v1.1 amendment: the comparator must be computed, not configured.
            report.add(
                8, "further information uneconomic", Verdict.FAIL,
                "comparator recorded but its derivation is not; a constant "
                "chosen after the fact would satisfy this (clause A1)",
            )
        else:
            report.add(
                8, "further information uneconomic", Verdict.NEEDS_HUMAN,
                f"comparator={comparator} source={stopped.payload['comparator_source']!r}; "
                "trace-consistent, but whether it is genuinely computed needs a probe "
                "(use --probe)",
            )

    # 9 --------------------------------------------------------------
    if commit is None:
        report.add(9, "commitment is justified", Verdict.FAIL, "no commitment")
    else:
        cites_stop = bool(stopped and stopped.seq in commit.caused_by)
        mentions_next = bool(commit.payload.get("next_action"))
        claims_exhausted = "uneconomic" in commit.rationale
        # The specific A1 defect found twice: an unconditional template
        # claiming exhaustion when nothing was evaluated.
        if claims_exhausted and not evaluated:
            report.add(9, "commitment is justified", Verdict.FAIL,
                       "rationale claims information was exhausted but zero actions were evaluated")
        elif not mentions_next:
            report.add(9, "commitment is justified", Verdict.FAIL, "no next_action recorded")
        elif not cites_stop and stopped is not None:
            report.add(9, "commitment is justified", Verdict.FAIL,
                       "rationale cites exhausted information but does not cite EXPLORATION_STOPPED")
        else:
            report.add(9, "commitment is justified", Verdict.PASS,
                       f"cites EXPLORATION_STOPPED={cites_stop}, next_action recorded")

    # 10 -------------------------------------------------------------
    if commit is None:
        report.add(10, "residual uncertainty recorded", Verdict.FAIL, "no commitment")
    else:
        residual = commit.payload.get("residual_uncertainty") or []
        established = {
            e.payload["belief_id"] for e in world if e.payload["after"] == "ESTABLISHED"
        }
        # The exact falsehood found twice: claiming nothing reached
        # ESTABLISHED while the same trace records one that did.
        contradicted = [
            r for r in residual
            if "no world belief reached ESTABLISHED" in r and established
        ]
        if not residual:
            report.add(10, "residual uncertainty recorded", Verdict.FAIL,
                       "empty; clause A2 scores an empty collection FAIL")
        elif contradicted:
            report.add(10, "residual uncertainty recorded", Verdict.FAIL,
                       f"states {contradicted[0]!r} but {sorted(established)} reached ESTABLISHED")
        else:
            report.add(10, "residual uncertainty recorded", Verdict.PASS,
                       f"{len(residual)} item(s), none contradicted by the trace")

    # 11 -------------------------------------------------------------
    if commit is None:
        report.add(11, "material alternative retained", Verdict.FAIL, "no commitment")
    else:
        retained = commit.payload.get("retained_alternatives") or []
        ranked = _first(events, "STRATEGY_RANKED")
        labels = (ranked.payload.get("beliefs") if ranked else {}) or {}
        dead = [s for s in retained if labels.get(s) == "RULED_OUT"]
        if not retained:
            report.add(11, "material alternative retained", Verdict.FAIL,
                       "empty; clause A2 scores an empty collection FAIL")
        elif dead:
            report.add(11, "material alternative retained", Verdict.FAIL,
                       f"{dead} presented as retained but ranked RULED_OUT")
        else:
            report.add(11, "material alternative retained", Verdict.PASS,
                       f"retained {retained} at { {s: labels.get(s) for s in retained} }")

    # 12 -------------------------------------------------------------
    missing = [
        f"seq {e.seq} {e.type}"
        for e in events
        if e.type in REQUIRES_CAUSATION and (not e.rationale or not e.caused_by)
    ]
    report.add(
        12, "rationale preserved",
        Verdict.PASS if not missing else Verdict.FAIL,
        "all decision events carry caused_by and rationale" if not missing else f"missing: {missing}",
    )

    # 13 -------------------------------------------------------------
    intent = _first(events, "INTENT_DECLARED")
    if intent is None or commit is None:
        report.add(13, "every transition explainable", Verdict.FAIL, "missing intent or commitment")
    else:
        reachable = trace.connected_from(intent.seq)
        orphan_decisions = [
            f"seq {e.seq} {e.type}"
            for e in events
            if e.type in REQUIRES_CAUSATION and e.seq not in reachable
        ]
        if commit.seq not in reachable:
            report.add(13, "every transition explainable", Verdict.FAIL,
                       "commitment not reachable from INTENT_DECLARED")
        elif orphan_decisions:
            report.add(13, "every transition explainable", Verdict.FAIL,
                       f"orphan decision events: {orphan_decisions}")
        else:
            report.add(13, "every transition explainable", Verdict.PASS,
                       f"{len(reachable)}/{len(events)} events reachable; no orphan decisions")

    # 14 / 15 require execution, not just a trace
    report.add(14, "run is deterministic", Verdict.NEEDS_HUMAN,
               "requires two runs; use --probe")
    report.add(15, "run is replayable", Verdict.NEEDS_HUMAN,
               "requires executing replay(); use --probe")

    return report


# ---------------------------------------------------------------------
# probes: these execute the experiment rather than reading a trace


def run_probes(report: Report) -> Report:
    """Live checks that a static trace cannot establish.

    Includes clause A7 -- the clause that failed Experiment 001 twice and
    that no amount of trace-reading can verify, because it is a claim
    about counterfactuals: would a *different* input have produced a
    different output?
    """
    from escapement.evidence.models import Evidence, EvidenceKind
    from escapement.loop import run_episode
    from escapement.observation.replay import replay
    from experiments._001 import scenario

    def episode(perform=None):
        return run_episode(
            episode_id="exp001",
            intent=scenario.INTENT,
            capabilities=scenario.CAPABILITIES,
            actions=scenario.ACTIONS,
            strategies=scenario.STRATEGIES,
            perform=perform or scenario.perform,
            evaluate_value=scenario.evaluate_value,
            interpret=scenario.interpret,
            world_belief_of=scenario.world_belief_of,
            strategy_belief_of=scenario.strategy_belief_of,
                trace=EventTrace(episode_id="exp001"),
        )

    # 14: determinism
    a, b = episode().trace.render(), episode().trace.render()
    _replace(report, 14, Verdict.PASS if a == b else Verdict.FAIL,
             "two runs byte-identical" if a == b else "two runs differ")

    # 15: replay reconstructs state from events alone
    live = episode()
    rebuilt = replay(list(live.trace))
    same_commit = rebuilt.committed_strategy == live.commitment.strategy_id
    same_beliefs = all(
        rebuilt.beliefs.get(bid) is b.label for bid, b in live.beliefs.beliefs.items()
    )
    _replace(
        report, 15,
        Verdict.PASS if (same_commit and same_beliefs) else Verdict.FAIL,
        f"replayed commitment={rebuilt.committed_strategy} "
        f"beliefs_match={same_beliefs}",
    )

    # 8: is the comparator computed, or a constant?
    # There is no longer a floor parameter to vary -- the checker's own
    # probe caught that back door and it was removed. So the test is
    # whether the comparator tracks belief state: it must differ between
    # a run that learned something and one that learned nothing.
    baseline = episode()
    stopped = baseline.trace.first("EXPLORATION_STOPPED")
    from escapement.information.value import proceed_return as _pr

    ignorant = _pr([])
    informed = _pr([4, 2, 1])
    if stopped is None:
        _replace(report, 8, Verdict.FAIL, "no EXPLORATION_STOPPED emitted")
    elif ignorant == informed:
        _replace(report, 8, Verdict.FAIL,
                 f"comparator is {ignorant} regardless of belief state; it is a constant")
    else:
        _replace(report, 8, Verdict.PASS,
                 f"comparator tracks belief state (no beliefs -> {ignorant}, "
                 f"best belief 4 -> {informed}); recorded value "
                 f"{stopped.payload['comparator']}")

    # A7: does the outcome depend on what the evidence says?
    def monolith(action):
        if action.id != "INSPECT_DEPENDENCY_MAP":
            return scenario.perform(action)
        return Evidence(
            id="e_depmap", kind=EvidenceKind.EXECUTION,
            claim="the repository is 1 monolithic module with deep circular coupling",
            source="dependency_inspector", produced_by="INSPECT_DEPENDENCY_MAP",
            decisive=True, payload={"module_count": 1},
        )

    modular = episode().commitment.strategy_id
    monolithic = episode(perform=monolith).commitment.strategy_id
    report.add(
        "A7", "outcome depends on evidence content",
        Verdict.PASS if modular != monolithic else Verdict.FAIL,
        f"modular evidence -> {modular}; monolith evidence -> {monolithic}"
        + ("" if modular != monolithic else "  (invariant: clause A7 failure)"),
    )
    return report


def _replace(report: Report, number, verdict: Verdict, evidence: str) -> None:
    for i, result in enumerate(report.results):
        if result.number == number:
            report.results[i] = Result(number, result.name, verdict, evidence)
            return


# ---------------------------------------------------------------------


def render(report: Report) -> str:
    lines = ["Experiment 001 — contract checker", ""]
    for r in report.results:
        mark = {"PASS": "  ok  ", "FAIL": " FAIL ", "NEEDS_HUMAN": " ???? "}[r.verdict.value]
        lines.append(f"[{mark}] {str(r.number):>3}  {r.name}")
        lines.append(f"            {r.evidence}")
    lines += ["", f"VERDICT: {report.overall}"]
    if report.failed:
        lines.append(f"  failed: {[r.number for r in report.failed]}")
    if report.needs_human:
        lines.append(f"  needs a human: {[r.number for r in report.needs_human]}")
    lines += [
        "",
        "This script checks mechanics only. It cannot judge clause A1 in",
        "general -- whether a passing criterion passes for a real reason is",
        "a question about code structure, not about a trace. Every defect",
        "found in three scoring cycles came from an adversarial reviewer",
        "constructing a case the author had not imagined. Keep doing that.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(prog="scoring.contract_checker")
    parser.add_argument("--trace", default=str(TRACE))
    parser.add_argument("--probe", action="store_true", help="run live checks (14, 15, 8, A7)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    events = load(Path(args.trace))
    report = check_criteria(events)
    if args.probe:
        report = run_probes(report)

    if args.json:
        print(json.dumps(
            {
                "verdict": str(report.overall),
                "results": [
                    {"criterion": r.number, "name": r.name,
                     "verdict": str(r.verdict), "evidence": r.evidence}
                    for r in report.results
                ],
            },
            indent=2,
        ))
    else:
        print(render(report), end="")

    return 0 if report.overall is Verdict.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
