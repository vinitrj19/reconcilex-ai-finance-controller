"""
Typed canonical records produced by normalization (M1).

These are intentionally plain, frozen dataclasses - no behavior, no
validation logic here (that lives in normalization.py). Keeping them inert
means later stages (M2+) can depend on the shape without depending on how
it was built.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class NormalizedPayment:
    payment_id: str
    order_id: Optional[str]
    merchant_id: str
    timestamp: datetime  # UTC, timezone-aware
    amount: Decimal
    currency: str
    payment_status: str
    payment_method: Optional[str]
    customer_reference: Optional[str]
    description: Optional[str]
    description_normalized: Optional[str]
    source_row_id: int
    ingest_ts: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedSettlement:
    settlement_id: str
    settlement_reference: str
    timestamp: datetime  # UTC, timezone-aware
    gross_amount: Decimal  # sign preserved - negative for refunds
    fee: Decimal
    tax: Decimal
    net_amount: Decimal  # sign preserved
    bank_reference: Optional[str]
    status: str
    source_row_id: int
    ingest_ts: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedOrder:
    order_id: str
    order_timestamp: datetime  # UTC, timezone-aware
    customer_id: str
    expected_amount: Decimal
    order_status: str
    payment_reference: Optional[str]  # soft FK, may not resolve
    invoice_reference: Optional[str]  # not guaranteed unique
    source_row_id: int
    ingest_ts: datetime
    raw: Dict[str, Any] = field(default_factory=dict)
