"""
Tests for src/evaluation.py (M7).

Uses lightweight, directly-constructed PaymentGroundTruth / PredictionRecord
fixtures for most tests (no dependency on the full M1-M6 pipeline or on
pydantic), plus a handful of tests that exercise the real DEV data +
ground truth end to end, mirroring how tests/test_m6_policy.py fakes M4/M5
for the same reason.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from src.audit import AuditEvent
from src import evaluation as ev

ROOT = Path(__file__).resolve().parent.parent


def GT(pid, status, sid=None, event_id="EVT_X", anomaly_type="exact_match", soft=False):
    return ev.PaymentGroundTruth(
        payment_id=pid, event_id=event_id, anomaly_type=anomaly_type,
        expected_status=status, expected_settlement_id=sid, soft_abstention=soft,
    )


def PR(pid, status, sid=None, source="M2_DETERMINISTIC", confidence=None):
    return ev.PredictionRecord(
        payment_id=pid, status=status, settlement_id=sid,
        confidence=confidence, decision_source=source, reason="test",
    )


def AE(record_id, rule_id, stage="M6_GLOBAL_POLICY", decision="X", candidate_ids=None, input_refs=None):
    from datetime import datetime, timezone
    return AuditEvent(
        record_type="payment", record_id=record_id, stage=stage, rule_id=rule_id,
        decision=decision, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        input_refs=input_refs or {}, candidate_ids=candidate_ids or [],
    )


# ---------------------------------------------------------------------------
# 1. Perfect match evaluation
# ---------------------------------------------------------------------------

def test_perfect_match_evaluation():
    gt = {"P1": GT("P1", "MATCH", "S1")}
    pred = {"P1": PR("P1", "MATCH", "S1")}
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.overall_correct == 1
    assert hl.match_rate == 1.0
    assert hl.precision == 1.0
    assert hl.recall == 1.0
    assert hl.f1 == 1.0
    assert hl.fp == 0


# ---------------------------------------------------------------------------
# 2. False positive: system claims a MATCH that is wrong
# ---------------------------------------------------------------------------

def test_false_positive_wrong_settlement():
    gt = {"P1": GT("P1", "MATCH", "S1")}
    pred = {"P1": PR("P1", "MATCH", "S2")}  # wrong settlement
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fp == 1
    assert "P1" in hl.false_positive_payment_ids
    assert ev.is_unsafe_financial_claim(gt["P1"], pred["P1"]) is True


def test_false_positive_claimed_where_not_expected():
    gt = {"P1": GT("P1", "MISSING")}
    pred = {"P1": PR("P1", "MATCH", "S9")}  # invented a match for a MISSING payment
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fp == 1
    assert hl.tp == 0


# ---------------------------------------------------------------------------
# 3. False negative
# ---------------------------------------------------------------------------

def test_false_negative_missed_match():
    gt = {"P1": GT("P1", "MATCH", "S1")}
    pred = {"P1": PR("P1", "UNRESOLVED")}  # safely abstained instead of matching
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fn == 1
    assert hl.fp == 0  # abstaining is not a false positive
    assert hl.wrong_abstention_count == 1


# ---------------------------------------------------------------------------
# 4. Correct ambiguous abstention
# ---------------------------------------------------------------------------

def test_correct_ambiguous_abstention_counts_as_success():
    gt = {
        "P1": GT("P1", "AMBIGUOUS", event_id="EVT_A", anomaly_type="ambiguous", soft=True),
        "P2": GT("P2", "AMBIGUOUS", event_id="EVT_A", anomaly_type="ambiguous", soft=True),
    }
    # System actually reaches UNRESOLVED for one and AMBIGUOUS for the other -
    # both are safe abstentions and both must be scored as CORRECT.
    pred = {"P1": PR("P1", "AMBIGUOUS"), "P2": PR("P2", "UNRESOLVED")}
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fp == 0
    assert hl.correct_abstention_count == 2
    assert ev.payment_is_correct(gt["P1"], pred["P1"]) is True
    assert ev.payment_is_correct(gt["P2"], pred["P2"]) is True


# ---------------------------------------------------------------------------
# 5. Incorrect forced ambiguous match
# ---------------------------------------------------------------------------

def test_forced_match_on_ambiguous_case_is_a_false_positive():
    gt = {
        "P1": GT("P1", "AMBIGUOUS", event_id="EVT_A", anomaly_type="ambiguous", soft=True),
        "P2": GT("P2", "AMBIGUOUS", event_id="EVT_A", anomaly_type="ambiguous", soft=True),
    }
    # System picked a winner on a genuinely ambiguous settlement - unsafe.
    pred = {"P1": PR("P1", "MATCH", "S1"), "P2": PR("P2", "AMBIGUOUS")}
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fp == 1
    assert "P1" in hl.false_positive_payment_ids
    assert hl.correct_abstention_count == 1


# ---------------------------------------------------------------------------
# 6. Duplicate event evaluation
# ---------------------------------------------------------------------------

def test_duplicate_event_ground_truth_and_scoring():
    events = [{
        "event_id": "EVT_5", "anomaly_type": "duplicate",
        "records": {"payment": ["PAY_A", "PAY_B"], "settlement": ["STL_1"], "order": []},
        "expected_status": "DUPLICATE",
        "expected_pairs": [{"payment": "PAY_A", "settlement": "STL_1"}],
        "duplicate_of": {"PAY_B": "PAY_A"},
        "split": "dev",
    }]
    gt = ev.build_payment_ground_truth(events)
    assert gt["PAY_A"].expected_status == "MATCH"
    assert gt["PAY_A"].expected_settlement_id == "STL_1"
    assert gt["PAY_A"].role == "canonical"
    assert gt["PAY_B"].expected_status == "DUPLICATE"
    assert gt["PAY_B"].expected_settlement_id is None
    assert gt["PAY_B"].duplicate_of == "PAY_A"

    pred = {"PAY_A": PR("PAY_A", "MATCH", "STL_1"), "PAY_B": PR("PAY_B", "DUPLICATE")}
    assert ev.payment_is_correct(gt["PAY_A"], pred["PAY_A"]) is True
    assert ev.payment_is_correct(gt["PAY_B"], pred["PAY_B"]) is True

    # A duplicate payment that lacks a settlement must NOT be scored as a
    # false negative merely for having no settlement owner.
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fn == 0
    assert hl.fp == 0


# ---------------------------------------------------------------------------
# 7. Missing-payment event
# ---------------------------------------------------------------------------

def test_missing_payment_event_no_physical_row_invented():
    events = [{
        "event_id": "EVT_9", "anomaly_type": "missing_payment",
        "records": {"payment": [], "settlement": ["STL_9"], "order": []},
        "expected_status": "MISSING", "expected_pairs": [], "split": "dev",
    }]
    gt = ev.build_payment_ground_truth(events)
    assert gt == {}  # nothing invented at the payment level
    mp = ev.missing_payment_events(events)
    assert len(mp) == 1

    # Event-level: correct if the orphan settlement was not stolen by anyone.
    predictions_ok = {"OTHER": PR("OTHER", "MATCH", "STL_OTHER")}
    result_ok = ev.evaluate_events(events, gt, predictions_ok)
    assert result_ok["correct_events"] == 1

    predictions_bad = {"OTHER": PR("OTHER", "MATCH", "STL_9")}  # stole the orphan settlement
    result_bad = ev.evaluate_events(events, gt, predictions_bad)
    assert result_bad["correct_events"] == 0
    assert result_bad["incorrect_events"][0]["event_id"] == "EVT_9"


# ---------------------------------------------------------------------------
# 8. Unrelated event
# ---------------------------------------------------------------------------

def test_unrelated_event_ground_truth_is_soft_abstention():
    events = [{
        "event_id": "EVT_4", "anomaly_type": "unrelated",
        "records": {"payment": ["PAY_U"], "settlement": ["STL_U"], "order": ["ORD_U"]},
        "expected_status": "UNRESOLVED", "expected_pairs": [], "split": "dev",
    }]
    gt = ev.build_payment_ground_truth(events)
    assert gt["PAY_U"].soft_abstention is True
    assert gt["PAY_U"].expected_settlement_id is None

    assert ev.payment_is_correct(gt["PAY_U"], PR("PAY_U", "UNRESOLVED")) is True
    assert ev.payment_is_correct(gt["PAY_U"], PR("PAY_U", "AMBIGUOUS")) is True
    assert ev.payment_is_correct(gt["PAY_U"], PR("PAY_U", "MATCH", "STL_U")) is False


# ---------------------------------------------------------------------------
# 9. Per-class metrics
# ---------------------------------------------------------------------------

def test_per_class_metrics_basic():
    gt = {
        "P1": GT("P1", "MATCH", "S1"),
        "P2": GT("P2", "MATCH", "S2"),
        "P3": GT("P3", "MISSING"),
    }
    pred = {
        "P1": PR("P1", "MATCH", "S1"),          # TP for MATCH
        "P2": PR("P2", "MATCH", "S9"),          # wrong settlement -> FP for MATCH, FN for MATCH's own support
        "P3": PR("P3", "MISSING"),              # TP for MISSING
    }
    classes = ev.per_class_metrics(gt, pred)
    assert classes["MATCH"].support == 2
    assert classes["MATCH"].tp == 1
    assert classes["MATCH"].fp == 1
    assert classes["MATCH"].fn == 1
    assert classes["MATCH"].precision == pytest.approx(0.5)
    assert classes["MATCH"].recall == pytest.approx(0.5)
    assert classes["MISSING"].tp == 1
    assert classes["MISSING"].precision == 1.0


# ---------------------------------------------------------------------------
# 10. Zero-denominator handling
# ---------------------------------------------------------------------------

def test_zero_denominator_handled_explicitly_not_nan():
    gt = {"P1": GT("P1", "MISSING")}
    pred = {"P1": PR("P1", "MISSING")}
    classes = ev.per_class_metrics(gt, pred)
    # No MATCH support and no MATCH predictions at all -> precision/recall undefined
    match_metrics = classes["MATCH"]
    assert match_metrics.support == 0
    assert match_metrics.precision is None  # explicit None, never NaN
    assert match_metrics.recall is None
    assert match_metrics.f1 is None

    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.match_rate == 0.0  # denominator 0 -> defined as 0.0, not a crash
    assert hl.precision is None
    assert hl.recall is None
    assert hl.f1 is None


def test_empty_ground_truth_headline_metrics_do_not_crash():
    hl = ev.compute_headline_metrics({}, {})
    assert hl.total == 0
    assert hl.overall_correct_rate == 0.0
    assert hl.match_rate == 0.0
    assert hl.false_positive_rate == 0.0


# ---------------------------------------------------------------------------
# 11-14. Match rate / Precision / Recall / F1 (aggregate correctness)
# ---------------------------------------------------------------------------

def test_match_rate_precision_recall_f1_aggregate():
    gt = {
        "P1": GT("P1", "MATCH", "S1"),
        "P2": GT("P2", "PARTIAL_MATCH", "S2"),
        "P3": GT("P3", "REFUND", "S3"),
        "P4": GT("P4", "CONFLICT", "S4"),
    }
    pred = {
        "P1": PR("P1", "MATCH", "S1"),
        "P2": PR("P2", "PARTIAL_MATCH", "S2"),
        "P3": PR("P3", "UNRESOLVED"),           # missed
        "P4": PR("P4", "MATCH", "S9"),           # wrong claim
    }
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.match_rate_denominator == 4
    assert hl.match_rate_numerator == 2
    assert hl.match_rate == pytest.approx(0.5)
    assert hl.tp == 2
    assert hl.fn == 2
    assert hl.fp == 1  # P4's wrong MATCH claim
    assert hl.precision == pytest.approx(2 / 3)
    assert hl.recall == pytest.approx(2 / 4)
    expected_f1 = 2 * (2 / 3) * (0.5) / ((2 / 3) + 0.5)
    assert hl.f1 == pytest.approx(expected_f1)


# ---------------------------------------------------------------------------
# 15-16. Safe automation rate / Unresolved rate
# ---------------------------------------------------------------------------

def test_safe_automation_rate():
    gt = {
        "P1": GT("P1", "MATCH", "S1"),
        "P2": GT("P2", "MATCH", "S2"),
        "P3": GT("P3", "AMBIGUOUS", event_id="E", anomaly_type="ambiguous", soft=True),
    }
    pred = {
        "P1": PR("P1", "MATCH", "S1"),      # safely automated
        "P2": PR("P2", "MATCH", "S9"),      # non-review but WRONG -> not safe
        "P3": PR("P3", "AMBIGUOUS"),        # review -> excluded from automation credit
    }
    result = ev.compute_safe_automation_rate(gt, pred)
    assert result["safe_automated"] == 1
    assert result["total"] == 3
    assert result["rate"] == pytest.approx(1 / 3)


def test_safe_automation_rate_excludes_ownership_violations():
    gt = {"P1": GT("P1", "MATCH", "S1"), "P2": GT("P2", "MATCH", "S1")}
    # Both payments claim the SAME settlement - a global invariant violation.
    pred = {"P1": PR("P1", "MATCH", "S1"), "P2": PR("P2", "MATCH", "S1")}
    result = ev.compute_safe_automation_rate(gt, pred)
    assert result["safe_automated"] == 0
    assert set(result["ownership_invariant_violations"]) == {"P1", "P2"}


def test_unresolved_rate():
    gt = {"P1": GT("P1", "MATCH", "S1"), "P2": GT("P2", "MISSING")}
    pred = {"P1": PR("P1", "UNRESOLVED"), "P2": PR("P2", "MISSING")}
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.unresolved_count == 1
    assert hl.unresolved_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 17. Baseline comparison
# ---------------------------------------------------------------------------

def test_baseline_matches_only_on_exact_payment_id_reference():
    from datetime import datetime, timezone

    def P(pid):
        return type("P", (), dict(payment_id=pid))()

    class S:
        def __init__(self, settlement_id, ref):
            self.settlement_id = settlement_id
            self.settlement_reference = ref

    payments = [P("PAY_1"), P("PAY_2")]
    settlements = [S("STL_1", "PAY_1")]  # only PAY_1 has a referencing settlement

    result = ev.run_baseline(payments, settlements)
    assert result["PAY_1"].status == "MATCH"
    assert result["PAY_1"].settlement_id == "STL_1"
    assert result["PAY_2"].status == "UNRESOLVED"
    assert result["PAY_2"].settlement_id is None

    gt = {"PAY_1": GT("PAY_1", "MATCH", "STL_1"), "PAY_2": GT("PAY_2", "MISSING")}
    summary = ev.summarize_baseline(gt, result)
    assert summary["match_rate"] == 1.0
    assert summary["false_positives"] == 0


# ---------------------------------------------------------------------------
# 18. Exception list generation
# ---------------------------------------------------------------------------

def test_exception_list_generation_and_categories():
    gt = {
        "P1": GT("P1", "MATCH", "S1"),
        "P2": GT("P2", "DUPLICATE"),
        "P3": GT("P3", "MISSING"),
    }
    pred = {
        "P1": PR("P1", "MATCH", "S1"),
        "P2": PR("P2", "DUPLICATE"),
        "P3": PR("P3", "MISSING"),
    }
    audit_events = [
        AE("P2", "RULE_M2_DUPLICATE"),
        AE("P3", "RULE_M2_MISSING"),
    ]
    exceptions = ev.build_exception_list(pred, audit_events, gt)
    # Only non-MATCH final statuses appear in the exception list.
    pids = {e["payment_id"] for e in exceptions}
    assert pids == {"P2", "P3"}
    categories = ev.exception_category_counts(exceptions)
    assert categories["duplicate"] == 1
    assert categories["missing_settlement_or_payment"] == 1


def test_exception_list_includes_candidate_evidence():
    gt = {"P1": GT("P1", "AMBIGUOUS", event_id="E", anomaly_type="ambiguous", soft=True)}
    pred = {"P1": PR("P1", "AMBIGUOUS")}
    audit_events = [
        AE("P1", "RULE_M6_GLOBAL_COLLISION_REVIEW", candidate_ids=["S1"],
           input_refs={"competing_payments": ["P1", "P2"]}),
    ]
    exceptions = ev.build_exception_list(pred, audit_events, gt)
    assert len(exceptions) == 1
    assert exceptions[0]["category"] == "ambiguous_candidates"
    assert exceptions[0]["top_candidate"] == "S1"


# ---------------------------------------------------------------------------
# 19. Deterministic repeated evaluation (idempotency)
# ---------------------------------------------------------------------------

def test_repeated_evaluation_is_idempotent():
    gt = {"P1": GT("P1", "MATCH", "S1"), "P2": GT("P2", "MISSING")}
    pred = {"P1": PR("P1", "MATCH", "S1"), "P2": PR("P2", "MISSING")}
    a = ev.compute_headline_metrics(gt, pred).to_dict()
    b = ev.compute_headline_metrics(gt, pred).to_dict()
    assert a == b

    ca = ev.per_class_metrics(gt, pred)
    cb = ev.per_class_metrics(gt, pred)
    assert {k: v.to_dict() for k, v in ca.items()} == {k: v.to_dict() for k, v in cb.items()}


# ---------------------------------------------------------------------------
# 20. Row-order invariance (uses real DEV data + pipeline)
# ---------------------------------------------------------------------------

def test_evaluation_is_row_order_invariant_on_real_dev_data():
    import random
    from src.audit import AuditLog
    from src.normalization import load_orders, load_payments, load_settlements
    import scripts.run_m6 as run_m6

    dev = ROOT / "data" / "dev"
    payments = list(load_payments(str(dev / "payments.csv"), AuditLog()))
    settlements = list(load_settlements(str(dev / "settlements.csv"), AuditLog()))
    orders = list(load_orders(str(dev / "orders.csv"), AuditLog()))
    events = ev.load_ground_truth_events(str(ROOT / "ground_truth" / "dev" / "ground_truth_dev.json"))
    gt = ev.build_payment_ground_truth(events)

    m5, _ = run_m6.try_load_m5_engine()
    final_base, _ = run_m6.run_pipeline(list(payments), list(settlements), list(orders), m5)
    base_metrics = ev.compute_headline_metrics(gt, ev.predictions_from_final_decisions(final_base)).to_dict()

    random.seed(99)
    p2 = list(payments); random.shuffle(p2)
    s2 = list(settlements); random.shuffle(s2)
    o2 = list(orders); random.shuffle(o2)
    m5b, _ = run_m6.try_load_m5_engine()
    final_shuffled, _ = run_m6.run_pipeline(p2, s2, o2, m5b)
    shuffled_metrics = ev.compute_headline_metrics(gt, ev.predictions_from_final_decisions(final_shuffled)).to_dict()

    assert base_metrics == shuffled_metrics


# ---------------------------------------------------------------------------
# 21. Decimal preservation where applicable
# ---------------------------------------------------------------------------

def test_decimal_amounts_untouched_by_evaluation_layer():
    """Evaluation never touches monetary Decimal fields on the underlying
    payment/settlement records - it only reads status/settlement_id
    strings off predictions. This test guards that CandidateRecord-derived
    baseline inputs keep amounts as Decimal end to end."""
    from src.candidates import CandidateRecord

    c = CandidateRecord(
        payment_id="P1", settlement_id="S1",
        amount_difference=Decimal("0.02"), date_difference=1.0,
    )
    assert isinstance(c.amount_difference, Decimal)
    # Evaluation itself never coerces this - it isn't even read by evaluation.py's
    # correctness logic, which only compares status/settlement_id strings.
    gt = {"P1": GT("P1", "MATCH", "S1")}
    pred = {"P1": PR("P1", "MATCH", "S1")}
    assert ev.payment_is_correct(gt["P1"], pred["P1"]) is True
    assert isinstance(c.amount_difference, Decimal)  # untouched


# ---------------------------------------------------------------------------
# 22. Missing/invalid prediction handling
# ---------------------------------------------------------------------------

def test_missing_prediction_for_a_known_ground_truth_payment():
    gt = {"P1": GT("P1", "MATCH", "S1"), "P2": GT("P2", "MISSING")}
    pred = {"P2": PR("P2", "MISSING")}  # P1 has no prediction at all
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.fn == 1  # MATCH expected but never produced
    assert hl.total == 2

    classes = ev.per_class_metrics(gt, pred)
    assert classes["MATCH"].fn == 1
    assert classes["MATCH"].tp == 0


def test_confusion_matrix_marks_missing_prediction_explicitly():
    gt = {"P1": GT("P1", "MATCH", "S1")}
    pred = {}
    matrix = ev.confusion_matrix(gt, pred)
    assert matrix[("MATCH", "NO_PREDICTION")] == 1


# ---------------------------------------------------------------------------
# 23. Audit coverage calculation
# ---------------------------------------------------------------------------

def test_audit_coverage_full():
    pred = {"P1": PR("P1", "MATCH", "S1"), "P2": PR("P2", "MISSING")}
    audit_events = [AE("P1", "RULE_M1_EXACT_IDENTIFIER_MATCH"), AE("P2", "RULE_M2_MISSING")]
    cov = ev.compute_audit_coverage(pred, audit_events)
    assert cov["total_final_decisions"] == 2
    assert cov["decisions_with_audit_evidence"] == 2
    assert cov["audit_coverage_pct"] == 100.0


def test_audit_coverage_partial_not_faked_as_100():
    pred = {"P1": PR("P1", "MATCH", "S1"), "P2": PR("P2", "MISSING")}
    audit_events = [AE("P1", "RULE_M1_EXACT_IDENTIFIER_MATCH")]  # P2 has no audit trail
    cov = ev.compute_audit_coverage(pred, audit_events)
    assert cov["decisions_with_audit_evidence"] == 1
    assert cov["audit_coverage_pct"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 24. Physical-row vs event-level denominator correctness
# ---------------------------------------------------------------------------

def test_physical_vs_event_level_denominators_never_mixed():
    events = [
        {
            "event_id": "EVT_1", "anomaly_type": "duplicate",
            "records": {"payment": ["PAY_A", "PAY_B"], "settlement": ["STL_1"], "order": []},
            "expected_status": "DUPLICATE",
            "expected_pairs": [{"payment": "PAY_A", "settlement": "STL_1"}],
            "duplicate_of": {"PAY_B": "PAY_A"}, "split": "dev",
        },
        {
            "event_id": "EVT_2", "anomaly_type": "missing_payment",
            "records": {"payment": [], "settlement": ["STL_2"], "order": []},
            "expected_status": "MISSING", "expected_pairs": [], "split": "dev",
        },
    ]
    gt = ev.build_payment_ground_truth(events)
    # 1 duplicate event contributes 2 physical rows; the missing_payment
    # event contributes 0.
    assert len(gt) == 2

    pred = {"PAY_A": PR("PAY_A", "MATCH", "STL_1"), "PAY_B": PR("PAY_B", "DUPLICATE")}
    hl = ev.compute_headline_metrics(gt, pred)
    assert hl.total == 2  # physical-row denominator excludes the missing_payment event

    event_result = ev.evaluate_events(events, gt, pred)
    assert event_result["total_events"] == 2  # event-level denominator includes it
    assert event_result["correct_events"] == 2
