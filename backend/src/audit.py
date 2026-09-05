"""
Audit stub (M1).

The audit log is append-only by design: later stages (M2+) call
AuditLog.record() to add more events for a record; nothing already written
is ever edited or removed. This is what lets "why did the system decide
this" be answered from stored data alone, for every record, from the very
first stage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AuditEvent:
    record_type: str      # "payment" | "settlement" | "order"
    record_id: str        # the record this event is about
    stage: str             # e.g. "normalization", "stage_1_exact_id"
    rule_id: str             # stable identifier so future audit UIs can look up rule docs
    decision: str              # e.g. "TENTATIVE_MATCH", "REFERENCE_UNRESOLVED"
    timestamp: datetime
    input_refs: Dict[str, Any] = field(default_factory=dict)
    candidate_ids: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "record_type": self.record_type,
            "record_id": self.record_id,
            "stage": self.stage,
            "rule_id": self.rule_id,
            "decision": self.decision,
            "timestamp": self.timestamp.isoformat(),
            "input_refs": self.input_refs,
            "candidate_ids": self.candidate_ids,
            "notes": self.notes,
        }


class AuditLog:
    """In-memory append-only audit trail. M1 keeps this simple (a list);
    M7 (per the architecture review's implementation plan) is where this
    gets persisted to JSON/SQLite. Nothing about this interface needs to
    change for that - persistence is a concern for whoever consumes
    AuditLog.all(), not for the stages that write to it.

    ``record()`` (append an AuditEvent) is the base primitive used by M1
    normalization. ``log_event()`` is a convenience wrapper over the same
    primitive for M2/M3, which log many similarly-shaped events per record
    and don't need to construct AuditEvent objects by hand. Both write into
    the same underlying list - there is exactly one audit trail, not two.

    ``increment_fact`` / ``audit_facts`` is a separate, small counter table
    for dataset-wide summary numbers (e.g. "how many duplicates did M2
    find") that are convenient to report without scanning every event."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self.audit_facts: Dict[str, int] = {}

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    def log_event(
        self,
        record_id: str,
        stage: str,
        rule_id: str,
        decision: str,
        candidate_ids: Optional[List[str]] = None,
        relevant_input_values: Optional[Dict[str, Any]] = None,
        explanation: Optional[str] = None,
        record_type: str = "payment",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Convenience wrapper around ``record()`` for M2/M3 call sites."""
        self._events.append(AuditEvent(
            record_type=record_type,
            record_id=record_id,
            stage=stage,
            rule_id=rule_id,
            decision=decision,
            timestamp=timestamp or datetime.now(timezone.utc),
            input_refs=relevant_input_values or {},
            candidate_ids=candidate_ids or [],
            notes=explanation,
        ))

    def increment_fact(self, fact_key: str, by: int = 1) -> None:
        self.audit_facts[fact_key] = self.audit_facts.get(fact_key, 0) + by

    def get_event_counts_by_rule(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._events:
            counts[e.rule_id] = counts.get(e.rule_id, 0) + 1
        return counts

    def for_record(self, record_id: str) -> List[AuditEvent]:
        return [e for e in self._events if e.record_id == record_id]

    def all(self) -> List[AuditEvent]:
        return list(self._events)

    @property
    def events(self) -> List[AuditEvent]:
        """Alias for ``all()`` - M3/verification code reads ``audit.events``."""
        return self._events

    def to_json(self) -> List[dict]:
        return [e.to_dict() for e in self._events]

    def export_jsonl(self, path: str) -> None:
        import json
        with open(path, "w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e.to_dict()) + "\n")

    def __len__(self) -> int:
        return len(self._events)
