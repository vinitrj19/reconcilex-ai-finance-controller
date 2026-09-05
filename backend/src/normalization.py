"""
Normalization layer (M1).

Converts the three raw CSV sources into typed canonical records
(NormalizedPayment / NormalizedSettlement / NormalizedOrder).

Two categories of "wrong data" are handled completely differently, on
purpose:

  1. Genuinely malformed input (missing payment_id, unparseable amount,
     unparseable timestamp) -> raises NormalizationError. This is a defect
     in the input and the system should fail loudly, not guess.

  2. An unresolved soft foreign key (payment.order_id pointing to an order
     that doesn't exist, order.payment_reference pointing to a payment that
     doesn't exist) -> NOT an error. It's expected data - the `unrelated`
     anomaly category in this dataset is built entirely out of dangling
     references in both directions. resolve_references() logs a structured
     audit fact for each one and never raises.
"""

import csv
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .audit import AuditEvent, AuditLog
from .models import NormalizedOrder, NormalizedPayment, NormalizedSettlement

# Dataset timestamps are naive (no offset). Per architecture review, they are
# treated as IST at the source and normalized to UTC for all internal
# comparison/storage. The original raw string is preserved in `.raw` for
# display, so nothing about this conversion is one-way or lossy.
_IST = ZoneInfo("Asia/Kolkata")

_VALID_CURRENCY = "INR"


class NormalizationError(ValueError):
    """Raised only for genuinely malformed input. Never raised for an
    unresolved foreign key - see module docstring."""


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------

def _norm_str(raw: Optional[str], allow_none: bool = True) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    if s == "":
        return None if allow_none else ""
    return s


def _parse_decimal(raw: Optional[str], field_name: str, record_id: str) -> Decimal:
    if raw is None or raw.strip() == "":
        raise NormalizationError(f"{field_name} missing for record {record_id!r}")
    try:
        return Decimal(raw.strip()).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise NormalizationError(
            f"{field_name} unparseable for record {record_id!r}: {raw!r}"
        ) from exc


def _parse_timestamp(raw: Optional[str], field_name: str, record_id: str) -> datetime:
    if not raw or not raw.strip():
        raise NormalizationError(f"{field_name} missing for record {record_id!r}")
    try:
        dt = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise NormalizationError(
            f"{field_name} unparseable for record {record_id!r}: {raw!r}"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_IST)
    return dt.astimezone(timezone.utc)


def _normalize_description(desc: Optional[str]) -> Optional[str]:
    """Uppercase, strip non-alphanumeric characters, collapse whitespace.
    Used for future fuzzy matching (M3+) - NOT used for anything in M1."""
    if desc is None:
        return None
    s = desc.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_payments(csv_path: str, audit: AuditLog) -> List[NormalizedPayment]:
    records: List[NormalizedPayment] = []
    ingest_ts = datetime.now(timezone.utc)

    with open(csv_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            pid = _norm_str(row.get("payment_id"), allow_none=False)
            if not pid:
                raise NormalizationError(f"payment row {i} missing payment_id")

            amount = _parse_decimal(row.get("amount"), "amount", pid)
            timestamp = _parse_timestamp(row.get("timestamp"), "timestamp", pid)

            currency_raw = _norm_str(row.get("currency"), allow_none=False) or ""
            currency = currency_raw.upper()
            if currency != _VALID_CURRENCY:
                audit.record(AuditEvent(
                    record_type="payment", record_id=pid, stage="normalization",
                    rule_id="N_CURRENCY_UNEXPECTED", decision="FLAGGED",
                    timestamp=ingest_ts, input_refs={"currency": currency_raw},
                    notes=f"expected {_VALID_CURRENCY}",
                ))

            description = _norm_str(row.get("description"))

            records.append(NormalizedPayment(
                payment_id=pid,
                order_id=_norm_str(row.get("order_id")),
                merchant_id=_norm_str(row.get("merchant_id"), allow_none=False) or "",
                timestamp=timestamp,
                amount=amount,
                currency=currency,
                payment_status=(_norm_str(row.get("payment_status")) or "").lower(),
                payment_method=(_norm_str(row.get("payment_method")) or None),
                customer_reference=_norm_str(row.get("customer_reference")),
                description=description,
                description_normalized=_normalize_description(description),
                source_row_id=i,
                ingest_ts=ingest_ts,
                raw=dict(row),
            ))

    return records


def load_settlements(csv_path: str, audit: AuditLog) -> List[NormalizedSettlement]:
    records: List[NormalizedSettlement] = []
    ingest_ts = datetime.now(timezone.utc)

    with open(csv_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            sid = _norm_str(row.get("settlement_id"), allow_none=False)
            if not sid:
                raise NormalizationError(f"settlement row {i} missing settlement_id")

            # sign is preserved deliberately - refunds are negative and must
            # stay negative all the way through the pipeline.
            gross = _parse_decimal(row.get("gross_amount"), "gross_amount", sid)
            fee = _parse_decimal(row.get("fee"), "fee", sid)
            tax = _parse_decimal(row.get("tax"), "tax", sid)
            net = _parse_decimal(row.get("net_amount"), "net_amount", sid)
            timestamp = _parse_timestamp(row.get("timestamp"), "timestamp", sid)

            reference = _norm_str(row.get("settlement_reference"), allow_none=False) or ""

            records.append(NormalizedSettlement(
                settlement_id=sid,
                settlement_reference=reference,
                timestamp=timestamp,
                gross_amount=gross,
                fee=fee,
                tax=tax,
                net_amount=net,
                bank_reference=_norm_str(row.get("bank_reference")),
                status=(_norm_str(row.get("status")) or "").lower(),
                source_row_id=i,
                ingest_ts=ingest_ts,
                raw=dict(row),
            ))

    return records


def load_orders(csv_path: str, audit: AuditLog) -> List[NormalizedOrder]:
    records: List[NormalizedOrder] = []
    ingest_ts = datetime.now(timezone.utc)

    with open(csv_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            oid = _norm_str(row.get("order_id"), allow_none=False)
            if not oid:
                raise NormalizationError(f"order row {i} missing order_id")

            expected_amount = _parse_decimal(row.get("expected_amount"), "expected_amount", oid)
            order_ts = _parse_timestamp(row.get("order_timestamp"), "order_timestamp", oid)

            records.append(NormalizedOrder(
                order_id=oid,
                order_timestamp=order_ts,
                customer_id=_norm_str(row.get("customer_id"), allow_none=False) or "",
                expected_amount=expected_amount,
                order_status=(_norm_str(row.get("order_status")) or "").lower(),
                payment_reference=_norm_str(row.get("payment_reference")),
                invoice_reference=_norm_str(row.get("invoice_reference")),
                source_row_id=i,
                ingest_ts=ingest_ts,
                raw=dict(row),
            ))

    return records


# ---------------------------------------------------------------------------
# Soft-FK resolution
# ---------------------------------------------------------------------------

def resolve_references(
    payments: List[NormalizedPayment],
    orders: List[NormalizedOrder],
    audit: AuditLog,
) -> None:
    """Checks payment.order_id and order.payment_reference against each
    other's ID sets. Never raises. Every unresolved reference becomes a
    structured audit fact (rule_id=N_FK_UNRESOLVED), not a silent gap and
    not a crash. This is what makes the `unrelated` anomaly category safe
    to run: its payment.order_id and order.payment_reference are dangling
    by construction, in both directions."""

    order_ids = {o.order_id for o in orders}
    payment_ids = {p.payment_id for p in payments}
    now = datetime.now(timezone.utc)

    for p in payments:
        if p.order_id is not None and p.order_id not in order_ids:
            audit.record(AuditEvent(
                record_type="payment", record_id=p.payment_id, stage="normalization",
                rule_id="N_FK_UNRESOLVED", decision="REFERENCE_UNRESOLVED",
                timestamp=now,
                input_refs={"reference_type": "payment.order_id", "reference_value": p.order_id},
                notes="order_id does not resolve to any known order",
            ))

    for o in orders:
        if o.payment_reference is not None and o.payment_reference not in payment_ids:
            audit.record(AuditEvent(
                record_type="order", record_id=o.order_id, stage="normalization",
                rule_id="N_FK_UNRESOLVED", decision="REFERENCE_UNRESOLVED",
                timestamp=now,
                input_refs={
                    "reference_type": "order.payment_reference",
                    "reference_value": o.payment_reference,
                },
                notes="payment_reference does not resolve to any known payment",
            ))
