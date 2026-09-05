"""Read-only API state backed by the validated DEV artifacts.

The API layer owns all serialization and presentation transforms. The M1-M6
implementation and its artifacts are never rewritten to fit the frontend.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.audit import AuditLog
from src.candidates import CandidateConfig, CandidateRecord, generate_candidates
from src.config import ReconciliationConfig
from src.normalization import load_orders, load_payments, load_settlements
from src.scoring import M4Scorer

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"
EVALUATION = ROOT / "evaluation"
M6_PATH = DEV / "m6_final.json"
AUDIT_PATH = ROOT / "audit_log_m6.jsonl"
RESULTS_PATH = EVALUATION / "results_dev.json"
CONFUSION_PATH = EVALUATION / "confusion_matrix_dev.csv"
EXCEPTIONS_PATH = EVALUATION / "exceptions_dev.json"

EXCEPTION_STATUSES = {"AMBIGUOUS", "UNRESOLVED", "DUPLICATE", "MISSING"}
RECONCILIATION_STATUSES = (
    "MATCH", "PARTIAL_MATCH", "REFUND", "CONFLICT",
    "MISSING", "DUPLICATE", "AMBIGUOUS", "UNRESOLVED",
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        # The frontend contract uses numeric amounts. Decimal is retained for
        # all internal financial calculations; conversion happens only at the
        # HTTP serialization boundary.
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _iso(dt: Any) -> str:
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _case_id(payment_id: str) -> str:
    suffix = payment_id.rsplit("_", 1)[-1]
    return f"CASE_{suffix}"


def _exception_type(status: str) -> str:
    return {
        "MISSING": "MISSING_SETTLEMENT",
        "DUPLICATE": "DUPLICATE",
        "AMBIGUOUS": "AMBIGUOUS",
        "UNRESOLVED": "UNRESOLVED",
    }[status]


def _priority(status: str) -> str:
    if status == "MISSING":
        return "HIGH"
    if status == "DUPLICATE":
        return "MEDIUM"
    return "LOW"


def _recommended_action(status: str) -> str:
    return "CONFIRM_NO_MATCHING_RECORD" if status in {"MISSING", "DUPLICATE"} else "MANUAL_REVIEW"


class DataState:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        # These are the only data files read by the API. No holdout artifact is
        # opened or inspected.
        self.m6_final: dict[str, dict[str, Any]] = _load_json(M6_PATH)
        self.eval_results: dict[str, Any] = _load_json(RESULTS_PATH)
        self.exceptions_dev: list[dict[str, Any]] = _load_json(EXCEPTIONS_PATH)
        self.confusion: list[dict[str, Any]] = []
        with CONFUSION_PATH.open("r", encoding="utf-8", newline="") as f:
            self.confusion = [dict(row) for row in csv.DictReader(f)]
            for row in self.confusion:
                row["count"] = int(row["count"])

        # Normalized DEV source records are loaded through the existing M1
        # loaders. They remain Decimal internally.
        loader_audit = AuditLog()
        self.payments = load_payments(str(DEV / "payments.csv"), loader_audit)
        self.settlements = load_settlements(str(DEV / "settlements.csv"), loader_audit)
        self.orders = load_orders(str(DEV / "orders.csv"), loader_audit)
        self.payments_by_id = {p.payment_id: p for p in self.payments}
        self.settlements_by_id = {s.settlement_id: s for s in self.settlements}
        self.orders_by_id = {o.order_id: o for o in self.orders}

        self.audit_by_payment: dict[str, list[dict[str, Any]]] = {}
        with AUDIT_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                record_id = event.get("record_id")
                if not record_id or event.get("record_type") != "payment":
                    continue
                self.audit_by_payment.setdefault(record_id, []).append(event)
        for events in self.audit_by_payment.values():
            events.sort(key=lambda e: e.get("timestamp", ""))

        # Reuse M3/M4 for evidence presentation only. This does not run M5,
        # does not change any artifact, and does not make a new reconciliation
        # decision. Candidate IDs are still constrained by the stored M6
        # settlement ownership.
        self._candidate_cfg = CandidateConfig.from_reconciliation_config(ReconciliationConfig())
        self._scorer = M4Scorer(config_path=str(ROOT / "config" / "m4_thresholds.json"))
        self._candidate_cache: dict[str, list[CandidateRecord]] = {}
        self._build_candidate_cache()

    def _build_candidate_cache(self) -> None:
        claimed = {
            d.get("settlement_id")
            for d in self.m6_final.values()
            if d.get("settlement_id")
        }
        residual_ids = {
            pid for pid, d in self.m6_final.items()
            if d.get("status") in {"MISSING", "AMBIGUOUS", "UNRESOLVED"}
        }
        if residual_ids:
            generated = generate_candidates(
                self.payments,
                self.settlements,
                self.orders,
                residual_ids,
                claimed,
                self._candidate_cfg,
                AuditLog(),
            )
            self._candidate_cache.update(generated)

    def candidates_for(self, payment_id: str) -> list[CandidateRecord]:
        final = self.m6_final[payment_id]
        status = final.get("status")
        if status in {"MISSING", "AMBIGUOUS", "UNRESOLVED"}:
            return self._candidate_cache.get(payment_id, [])

        # For a protected M1/M2 decision, expose only the settlement already
        # owned by the stored decision. This is evidence presentation, not a
        # second matching pass.
        sid = final.get("settlement_id")
        if not sid:
            return []
        payment = self.payments_by_id[payment_id]
        target = self.settlements_by_id.get(sid)
        if target is None:
            return []
        candidate = self._candidate_for_pair(payment, target)
        return [candidate] if candidate else []

    def _candidate_for_pair(self, payment: Any, settlement: Any) -> CandidateRecord | None:
        # Ask the existing M3 implementation to produce its exact candidate
        # representation, while excluding every other stored owner. This
        # keeps reference/date/amount handling in the existing backend code.
        claimed_others = {
            d.get("settlement_id")
            for d in self.m6_final.values()
            if d.get("settlement_id") and d.get("settlement_id") != settlement.settlement_id
        }
        generated = generate_candidates(
            [payment], self.settlements, self.orders, {payment.payment_id},
            claimed_others, self._candidate_cfg, AuditLog(),
        ).get(payment.payment_id, [])
        for candidate in generated:
            if candidate.settlement_id == settlement.settlement_id:
                return candidate
        return None

    def candidate_score(self, payment: Any, candidate: CandidateRecord) -> float:
        return self._scorer.score_candidate(candidate, payment.amount)


state = DataState()


def money_json(value: Any) -> Any:
    """Convert only API-bound Decimal values; internal state remains Decimal."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: money_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [money_json(v) for v in value]
    return value
