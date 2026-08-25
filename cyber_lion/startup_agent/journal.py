"""Append-only JSONL journal for startup evolution state.

This is a local persistence primitive for reproducible development and replay. It stores
explicit state snapshots and deltas; it does not infer missing history. Persistent writes
are mediated by the R9D-2 local persistence boundary.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .local_persistence import LocalPersistenceBoundary, LocalPersistenceGate
from .models import EvolutionState, VentureVector


class EvolutionJournal:
    def __init__(self, path: str | Path, *, persistence: LocalPersistenceBoundary | None = None) -> None:
        self.path = Path(path)
        self._persistence = persistence or LocalPersistenceBoundary()

    @staticmethod
    def encode_record(state: EvolutionState) -> bytes:
        state.validate()
        record = {
            "startup_id": state.startup_id,
            "cycle": state.cycle,
            "stage": state.stage,
            "vector": state.vector.to_dict(),
            "previous_vector": state.previous_vector.to_dict() if state.previous_vector else None,
            "delta": state.delta(),
            "active_hypothesis_id": state.active_hypothesis_id,
            "evidence_ids": list(state.evidence_ids),
            "unknowns": list(state.unknowns),
            "blockers": list(state.blockers),
            "created_at": state.created_at.isoformat(),
        }
        return (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    def append(self, state: EvolutionState, *, gate: LocalPersistenceGate) -> None:
        payload = self.encode_record(state)
        self._persistence.append(target=self.path, payload=payload, purpose="startup-evolution-journal-append", gate=gate)

    def read_records(self) -> List[dict]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid journal JSON at line {line_no}") from exc
        return records

    def replay(self) -> List[EvolutionState]:
        states: List[EvolutionState] = []
        expected_cycle = 0
        startup_id = None
        previous = None
        for record in self.read_records():
            if record.get("cycle") != expected_cycle:
                raise ValueError(f"non-contiguous cycle: expected {expected_cycle}, got {record.get('cycle')}")
            if startup_id is None:
                startup_id = record.get("startup_id")
            elif record.get("startup_id") != startup_id:
                raise ValueError("journal mixes multiple startup_id values")
            vector = VentureVector(**record["vector"]).validate()
            previous_vector = VentureVector(**record["previous_vector"]).validate() if record.get("previous_vector") else None
            if previous is not None and previous_vector != previous.vector:
                raise ValueError("journal previous_vector does not match prior cycle")
            state = EvolutionState(
                startup_id=record["startup_id"],
                cycle=record["cycle"],
                stage=record["stage"],
                vector=vector,
                previous_vector=previous_vector,
                active_hypothesis_id=record.get("active_hypothesis_id"),
                evidence_ids=list(record.get("evidence_ids", [])),
                unknowns=list(record.get("unknowns", [])),
                blockers=list(record.get("blockers", [])),
                created_at=datetime.fromisoformat(record["created_at"]),
            ).validate()
            states.append(state)
            previous = state
            expected_cycle += 1
        return states

    def latest(self) -> EvolutionState | None:
        states = self.replay()
        return states[-1] if states else None
