from datetime import datetime, timezone
from decimal import Decimal

from src.audit import AuditLog
from src.config import ReconciliationConfig
from src.candidates import CandidateConfig, CandidateRecord, generate_candidates
from src.models import NormalizedPayment, NormalizedSettlement, NormalizedOrder


def P(**kw):
    base = dict(
        payment_id="P1", order_id="O1", merchant_id="M1",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        amount=Decimal("100.00"), currency="INR", payment_status="captured",
        payment_method="upi", customer_reference="C1", description=None,
        description_normalized=None, source_row_id=0,
        ingest_ts=datetime(2026, 1, 1, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedPayment(**base)


def S(**kw):
    base = dict(
        settlement_id="S1", settlement_reference="NOMATCH",
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        gross_amount=Decimal("100.00"), fee=Decimal("0.00"), tax=Decimal("0.00"),
        net_amount=Decimal("100.00"), bank_reference=None, status="settled",
        source_row_id=0, ingest_ts=datetime(2026, 1, 2, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedSettlement(**base)


def O(**kw):
    base = dict(
        order_id="O1", order_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        customer_id="C1", expected_amount=Decimal("100.00"), order_status="completed",
        payment_reference="P1", invoice_reference="INV1", source_row_id=0,
        ingest_ts=datetime(2026, 1, 1, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedOrder(**base)


def gen(p, ss, oo=None, ids=None, claimed=None, cfg=None):
    return generate_candidates(
        p, ss, oo or [], ids or {"P1"}, claimed or set(), cfg or CandidateConfig(), AuditLog()
    )


def test_amount_date_candidate():
    r = gen([P()], [S()])
    assert len(r["P1"]) == 1


def test_date_window_excluded():
    r = gen([P()], [S(timestamp=datetime(2026, 1, 20, tzinfo=timezone.utc))])
    assert r["P1"] == []


def test_date_window_boundary():
    r = gen([P()], [S(timestamp=datetime(2026, 1, 8, tzinfo=timezone.utc))])
    assert len(r["P1"]) == 1


def test_claimed_settlement_excluded():
    r = gen([P()], [S(settlement_id="S1")], claimed={"S1"})
    assert r["P1"] == []


def test_multiple_candidates_preserved():
    r = gen([P()], [S(settlement_id="S1"), S(settlement_id="S2")])
    assert len(r["P1"]) == 2


def test_amount_far_outside_fee_band_excluded():
    r = gen([P()], [S(net_amount=Decimal("50.00"))])
    assert r["P1"] == []


def test_decimal_amount_behavior():
    r = gen([P(amount=Decimal("100.00"))], [S(net_amount=Decimal("99.99"))])
    assert r["P1"][0].amount_difference == Decimal("0.01")


def test_date_difference_is_numeric_not_timedelta():
    r = gen([P()], [S()])
    c = r["P1"][0]
    assert isinstance(c.date_difference, float)


def test_max_candidate_limit():
    ss = [S(settlement_id=f"S{i}") for i in range(5)]
    r = gen([P()], ss, cfg=CandidateConfig(max_candidates_per_payment=2))
    assert len(r["P1"]) == 2


def test_schema_integrity():
    c = gen([P()], [S()])["P1"][0]
    assert isinstance(c, CandidateRecord)
    assert isinstance(c.amount_difference, Decimal)


def test_no_unresolved_ids_returns_empty():
    r = generate_candidates([P()], [S()], [], set(), set(), CandidateConfig(), AuditLog())
    assert r == {}


def test_truncation_audit():
    audit = AuditLog()
    ss = [S(settlement_id=f"S{i}") for i in range(4)]
    r = generate_candidates([P()], ss, [], {"P1"}, set(), CandidateConfig(max_candidates_per_payment=2), audit)
    assert len(r["P1"]) == 2
    assert audit.events[-1].input_refs["truncated"] is True


def test_from_reconciliation_config():
    rc = ReconciliationConfig()
    cfg = CandidateConfig.from_reconciliation_config(rc)
    assert cfg.date_window_days == rc.candidate_date_window_days
    assert cfg.monetary_tolerance == rc.monetary_tolerance
