"""Run Experiment 001 and write the event trace."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from escapement.loop import run_episode
from escapement.observation.events import EventTrace

from conformance.c001 import scenario


def main(out: Path | None = None) -> int:
    path = out or Path(__file__).parent / "events.jsonl"
    trace = EventTrace(episode_id="exp001", path=path)
    result = run_episode(
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
        trace=trace,
    )
    print(f"committed: {result.commitment.strategy_id}")
    print(f"retained:  {list(result.commitment.retained_alternatives)}")
    print(f"events:    {len(trace)} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
