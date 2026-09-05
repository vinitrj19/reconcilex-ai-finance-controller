"""
Unit tests for M2 Deterministic Reconciliation Module (canonical API).
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from src.models import NormalizedPayment, NormalizedSettlement, NormalizedOrder
from src.audit import AuditLog
from src.config import ReconciliationConfig
from src.deterministic import DeterministicReconciliationEngine, ReconciliationStatus


def P(**kw):
    base = dict(
        payment_id="P101", order_id="ORD101", merchant_id="M1",
        timestamp=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        amount=Decimal("100.00"), currency="INR", payment_status="captured",
        payment_method="upi", customer_reference="C1", description=None,
        description_normalized=None, source_row_id=0,
        ingest_ts=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedPayment(**base)


def S(**kw):
    base = dict(
        settlement_id="S101", settlement_reference="P101",
        timestamp=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        gross_amount=Decimal("100.00"), fee=Decimal("0.00"), tax=Decimal("0.00"),
        net_amount=Decimal("100.00"), bank_reference=None, status="settled",
        source_row_id=0, ingest_ts=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedSettlement(**base)


def O(**kw):
    base = dict(
        order_id="ORD101", order_timestamp=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        customer_id="C1", expected_amount=Decimal("100.00"), order_status="completed",
        payment_reference="P101", invoice_reference=None, source_row_id=0,
        ingest_ts=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedOrder(**base)


@pytest.fixture
def config():
    return ReconciliationConfig()


@pytest.fixture
def audit():
    return AuditLog()


@pytest.fixture
def engine(config, audit):
    return DeterministicReconciliationEngine(config, audit)


def test_exact_amount_valid_date_match(engine):
    p = P()
    s = S()
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P101"][0] == ReconciliationStatus.MATCH


def test_explainable_fee_and_gst_partial_match(engine):
    p = P(payment_id="P102")
    s = S(settlement_id="S102", settlement_reference="P102", net_amount=Decimal("97.64"))
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P102"][0] == ReconciliationStatus.PARTIAL_MATCH


def test_materially_unexplained_shortfall_conflict(engine):
    p = P(payment_id="P103")
    s = S(settlement_id="S103", settlement_reference="P103", net_amount=Decimal("80.00"))
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P103"][0] == ReconciliationStatus.CONFLICT


def test_duplicate_payment_detected_before_missing(engine, audit):
    p1 = P(payment_id="P104_1", order_id="ORD104", amount=Decimal("50.00"),
           timestamp=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc))
    p2 = P(payment_id="P104_2", order_id="ORD104", amount=Decimal("50.00"),
           timestamp=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc))
    results = engine.reconcile_unmatched([p1, p2], [p2], [], set(), [])
    assert results["P104_2"][0] == ReconciliationStatus.DUPLICATE
    assert results["P104_2"][3] == "P104_1"
    assert audit.audit_facts["N_DUPLICATES_DETECTED"] == 1


def test_valid_corroborated_refund(engine, audit):
    p = P(payment_id="P105", amount=Decimal("-50.00"), payment_status="refunded")
    s = S(settlement_id="S105", settlement_reference="P105", gross_amount=Decimal("-50.00"),
          net_amount=Decimal("-50.00"), status="refunded")
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P105"][0] == ReconciliationStatus.REFUND
    assert audit.audit_facts["N_REFUNDS_CORROBORATED"] == 1


def test_uncorroborated_refund_signal_not_falsely_classified(engine, audit):
    p = P(payment_id="P106", amount=Decimal("50.00"), payment_status="refunded")
    s = S(settlement_id="S106", settlement_reference="P106", net_amount=Decimal("50.00"), status="settled")
    o = O(order_id="ORD101", order_status="completed")
    results = engine.reconcile_unmatched([p], [p], [s], set(), [o])
    assert results["P106"][0] != ReconciliationStatus.REFUND
    assert audit.audit_facts["N_REFUNDS_UNCORROBORATED"] == 1


def test_late_settlement_does_not_automatically_become_conflict(engine):
    p = P(payment_id="P107", amount=Decimal("150.00"),
          timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc))
    s = S(settlement_id="S107", settlement_reference="P107", net_amount=Decimal("150.00"),
          timestamp=datetime(2026, 1, 21, 10, 0, tzinfo=timezone.utc))
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P107"][0] == ReconciliationStatus.MATCH


def test_dangling_order_reference_is_unresolved(engine):
    p = P(payment_id="P108", order_id="ORD_NOPE")
    results = engine.reconcile_unmatched([p], [p], [], set(), [])
    assert results["P108"][0] == ReconciliationStatus.UNRESOLVED


def test_decimal_monetary_precision(engine):
    p = P(payment_id="P109", amount=Decimal("100.05"))
    s = S(settlement_id="S109", settlement_reference="P109", net_amount=Decimal("100.05"))
    results = engine.reconcile_unmatched([p], [p], [s], set(), [])
    assert results["P109"][0] == ReconciliationStatus.MATCH


def test_cross_payment_ambiguous_collision(engine, audit):
    # Two payments, no direct reference, both plausibly claim ONE orphan
    # settlement. Neither should win arbitrarily.
    p1 = P(payment_id="P110", order_id=None, amount=Decimal("300.00"),
           timestamp=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc))
    p2 = P(payment_id="P111", order_id=None, amount=Decimal("300.00"),
           timestamp=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc))
    s = S(settlement_id="S999", settlement_reference="UNRELATED_REF", net_amount=Decimal("300.00"),
          timestamp=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc))
    results = engine.reconcile_unmatched([p1, p2], [p1, p2], [s], set(), [])
    assert results["P110"][0] == ReconciliationStatus.AMBIGUOUS
    assert results["P111"][0] == ReconciliationStatus.AMBIGUOUS
    assert audit.audit_facts["N_AMBIGUOUS_CASES"] == 2


def test_cross_payment_ambiguity_independent_of_order(engine):
    # Same scenario, payments supplied in reversed order - result must
    # not depend on iteration/CSV order.
    p1 = P(payment_id="P110", order_id=None, amount=Decimal("300.00"),
           timestamp=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc))
    p2 = P(payment_id="P111", order_id=None, amount=Decimal("300.00"),
           timestamp=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc))
    s = S(settlement_id="S999", settlement_reference="UNRELATED_REF", net_amount=Decimal("300.00"),
          timestamp=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc))
    results = engine.reconcile_unmatched([p2, p1], [p2, p1], [s], set(), [])
    assert results["P110"][0] == ReconciliationStatus.AMBIGUOUS
    assert results["P111"][0] == ReconciliationStatus.AMBIGUOUS


def test_missing_when_no_candidate_at_all(engine):
    p = P(payment_id="P112", order_id=None, amount=Decimal("999.00"))
    results = engine.reconcile_unmatched([p], [p], [], set(), [])
    assert results["P112"][0] == ReconciliationStatus.MISSING
