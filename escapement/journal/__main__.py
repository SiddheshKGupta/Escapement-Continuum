"""Decision journal CLI.

    python -m escapement.journal record ...
    python -m escapement.journal resolve <id> held|broke|voided --note "..."
    python -m escapement.journal list [--all]
    python -m escapement.journal report [--include-retrospective]
    python -m escapement.journal show <id>
"""

from __future__ import annotations

import argparse
from pathlib import Path

from escapement.belief.labels import BeliefLabel
from escapement.journal.calibration import render, report
from escapement.journal.models import DecisionEntry, Prediction, Resolution
from escapement.journal.store import DEFAULT_PATH, Journal


def _journal(args: argparse.Namespace) -> Journal:
    return Journal(Path(args.path))


def cmd_record(args: argparse.Namespace) -> int:
    entry = DecisionEntry(
        id=args.id,
        question=args.question,
        chosen=args.chosen,
        alternatives=tuple(args.alternative),
        rationale=args.rationale,
        evidence=tuple(args.evidence),
        retrospective=args.retrospective,
        tags=tuple(args.tag),
        prediction=Prediction(
            claim=args.predict,
            confidence=BeliefLabel[args.confidence],
            resolution_criteria=args.criteria,
        ),
    )
    _journal(args).append(entry)
    print(f"recorded {entry.id}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    entry = _journal(args).resolve(args.id, Resolution(args.resolution), args.note)
    print(f"{entry.id}: {entry.prediction.resolution.value}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    journal = _journal(args)
    entries = journal.load().values() if args.all else journal.unresolved()
    for entry in sorted(entries, key=lambda e: e.id):
        marker = "R" if entry.retrospective else " "
        state = entry.prediction.resolution.value
        print(f"{marker} {entry.id:<44} {entry.prediction.confidence.name:<12} {state}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    entries = _journal(args).load()
    entry = entries.get(args.id)
    if entry is None:
        print(f"no entry {args.id!r}")
        return 1
    print(f"{entry.id}\n")
    print(f"  question:     {entry.question}")
    print(f"  chosen:       {entry.chosen}")
    print(f"  alternatives: {', '.join(entry.alternatives)}")
    print(f"  rationale:    {entry.rationale}")
    if entry.evidence:
        print(f"  evidence:     {', '.join(entry.evidence)}")
    print(f"  retrospective: {entry.retrospective}")
    print(f"\n  prediction:   {entry.prediction.claim}")
    print(f"  confidence:   {entry.prediction.confidence.name}")
    print(f"  falsified if: {entry.prediction.resolution_criteria}")
    print(f"  resolution:   {entry.prediction.resolution.value}")
    if entry.prediction.resolution_note:
        print(f"  note:         {entry.prediction.resolution_note}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    entries = list(_journal(args).load().values())
    print(render(report(entries, include_retrospective=args.include_retrospective)), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="escapement.journal")
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--id", required=True)
    record.add_argument("--question", required=True)
    record.add_argument("--chosen", required=True)
    record.add_argument("--alternative", action="append", required=True)
    record.add_argument("--rationale", required=True)
    record.add_argument("--predict", required=True, help="a falsifiable claim")
    record.add_argument("--confidence", required=True, choices=[b.name for b in BeliefLabel])
    record.add_argument("--criteria", required=True, help="how this would be judged wrong")
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--tag", action="append", default=[])
    record.add_argument("--retrospective", action="store_true")
    record.set_defaults(func=cmd_record)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("id")
    resolve.add_argument("resolution", choices=["held", "broke", "voided"])
    resolve.add_argument("--note", required=True)
    resolve.set_defaults(func=cmd_resolve)

    listing = sub.add_parser("list")
    listing.add_argument("--all", action="store_true")
    listing.set_defaults(func=cmd_list)

    show = sub.add_parser("show")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)

    rep = sub.add_parser("report")
    rep.add_argument("--include-retrospective", action="store_true")
    rep.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
