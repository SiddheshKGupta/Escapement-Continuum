"""Append-only decision journal store.

One JSON object per line, same shape as the event trace, for the same
reason: a mutable store would let a prediction be quietly rewritten
after its outcome was known, which would destroy the only property that
makes this evidence rather than a diary.

Resolution is handled by appending a new revision of the entry rather
than editing in place. The full history stays on disk; `load()` returns
the latest revision of each id. That way "what did we predict at the
time" remains answerable even after resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

from escapement.journal.models import DecisionEntry, Resolution

DEFAULT_PATH = Path("journal/decisions.jsonl")


class Journal:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path

    # -- writing ------------------------------------------------------

    def append(self, entry: DecisionEntry) -> DecisionEntry:
        existing = self.load()
        if entry.id in existing:
            raise ValueError(
                f"entry {entry.id} already exists; use resolve() to record an "
                "outcome, rather than appending a second entry under the same id"
            )
        self._write(entry)
        return entry

    def resolve(self, entry_id: str, resolution: Resolution, note: str) -> DecisionEntry:
        entries = self.load()
        if entry_id not in entries:
            raise KeyError(f"no journal entry {entry_id!r}")
        resolved = entries[entry_id].resolve(resolution, note)
        self._write(resolved)
        return resolved

    def _write(self, entry: DecisionEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")

    # -- reading ------------------------------------------------------

    def load(self) -> dict[str, DecisionEntry]:
        """Latest revision of each entry, keyed by id."""
        if not self.path.exists():
            return {}
        entries: dict[str, DecisionEntry] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = DecisionEntry.from_dict(json.loads(line))
            entries[entry.id] = entry
        return entries

    def history(self, entry_id: str) -> list[DecisionEntry]:
        """Every recorded revision of one entry, oldest first.

        This is what makes after-the-fact rewriting visible rather than
        merely forbidden.
        """
        if not self.path.exists():
            return []
        return [
            entry
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for entry in [DecisionEntry.from_dict(json.loads(line))]
            if entry.id == entry_id
        ]

    def unresolved(self) -> list[DecisionEntry]:
        return sorted(
            (e for e in self.load().values() if e.prediction.resolution is Resolution.UNRESOLVED),
            key=lambda e: e.id,
        )
