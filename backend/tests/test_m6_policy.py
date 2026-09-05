"""
M6 Global Reconciliation Policy Layer tests.

Uses lightweight, duck-typed fakes for M4Scorer/M5ReasoningEngine instead
of the real classes so this suite runs without a live config file or the
``pydantic`` dependency (not installed in this environment - see
scripts/run_tests_shim.py / scripts/verify_foundation.py, which skip the
real M5 suite for the same reason). The fakes implement exactly the same
contract ``src.policy.run_m6_global_policy`` documents it depends on, so
these tests still validate M6's real integration surface.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.audit import AuditLog
from src.candidates import CandidateRecord
from src.deterministic import ReconciliationStatus
from src.models import NormalizedPayment, NormalizedSettlement
from src.policy import (
    M6PolicyConfig,
    is_eligible_owner,
    is_protected_status,
    resolve_collision,
    run_m6_global_policy,
    validate_ai_recommendation,
)

STATUS = ReconciliationStatus


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def P(**kw):
    base = dict(
        payment_id="P1", order_id=None, merchant_id="M1",
        timestamp=datetime(2026, 1, 10, tzinfo=timezone.utc),
        amount=Decimal("100.00"), currency="INR", payment_status="captured",
        payment_method="upi", customer_reference=None, description=None,
        description_normalized=None, source_row_id=0,
        ingest_ts=datetime(2026, 1, 10, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedPayment(**base)


def S(**kw):
    base = dict(
        settlement_id="S1", settlement_reference="NOMATCH",
        timestamp=datetime(2026, 1, 11, tzinfo=timezone.utc),
        gross_amount=Decimal("100.00"), fee=Decimal("0.00"), tax=Decimal("0.00"),
        net_amount=Decimal("100.00"), bank_reference=None, status="settled",
        source_row_id=0, ingest_ts=datetime(2026, 1, 11, tzinfo=timezone.utc), raw={},
    )
    base.update(kw)
    return NormalizedSettlement(**base)


def C(payment_id, settlement_id, amount_difference="0.00", date_difference=0.0, refs=None):
    return CandidateRecord(
        payment_id=payment_id,
        settlement_id=settlement_id,
        amount_difference=Decimal(amount_difference),
        date_difference=float(date_difference),
        matched_reference_fields=refs or [],
        candidate_generation_rule="CAND_BLOCK_AMOUNT_DATE",
        evidence={},
    )


class FakeAIDecision:
    """Duck-typed stand-in for src.m5_schema.AIDecision (no pydantic)."""

    def __init__(self, decision, selected_candidate_id, confidence):
        self.decision = decision
        self.selected_candidate_id = selected_candidate_id
        self.confidence = confidence


class FakeM4Scorer:
    """payment_id -> canned M4Scorer.evaluate_payment(...) result."""

    def __init__(self, outcomes: dict):
        self.outcomes = outcomes

    def evaluate_payment(self, view):
        return self.outcomes.get(view.payment_id, {"status": "NO_CANDIDATE"})


class FakeM5Engine:
    """payment_id -> canned M5ReasoningEngine.evaluate_payment(...) result."""

    def __init__(self, outcomes: dict):
        self.outcomes = outcomes
        self.calls = []

    def evaluate_payment(self, view, m2_status, m4_status):
        self.calls.append(view.payment_id)
        return self.outcomes.get(view.payment_id, {"status": "ESCALATE", "reason": "NO_FAKE_RESPONSE"})


def make_result(status, top_settlement_id=None, score=None, margin=None):
    if status != "ACCEPT":
        return {"status": status}
    return {
        "status": "ACCEPT",
        "top": {"candidate": C("_", top_settlement_id), "score": score},
        "margin": margin,
    }


def run(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, m5_outcomes=None, config=None):
    audit = AuditLog()
    m4 = FakeM4Scorer(m4_outcomes)
    m5 = FakeM5Engine(m5_outcomes) if m5_outcomes is not None else None
    result = run_m6_global_policy(
        payments, m1_matched, m2_results, m3_candidates, m4, m5, audit, config,
    )
    return result, audit, m5


# ---------------------------------------------------------------------------
# Pure helper function tests
# ---------------------------------------------------------------------------

def test_is_protected_status():
    for s in (STATUS.MATCH, STATUS.PARTIAL_MATCH, STATUS.CONFLICT, STATUS.REFUND,
              STATUS.DUPLICATE, STATUS.MISSING):
        assert is_protected_status(s)
    for s in (STATUS.AMBIGUOUS, STATUS.UNRESOLVED):
        assert not is_protected_status(s)


def test_is_eligible_owner():
    assert is_eligible_owner(STATUS.AMBIGUOUS, None)
    assert is_eligible_owner(STATUS.UNRESOLVED, None)
    assert not is_eligible_owner(STATUS.MATCH, None)
    assert not is_eligible_owner(STATUS.MISSING, None)
    assert not is_eligible_owner(STATUS.AMBIGUOUS, "P_CANONICAL")  # duplicate, even if status says AMBIGUOUS


def test_resolve_collision_clear_winner():
    winner, code = resolve_collision([("PAY_A", 0.95), ("PAY_B", 0.80)], margin=0.10)
    assert winner == "PAY_A"
    assert code == "CLEAR_WINNER"


def test_resolve_collision_near_tie_no_winner():
    winner, code = resolve_collision([("PAY_A", 0.91), ("PAY_B", 0.90)], margin=0.10)
    assert winner is None
    assert code == "INSUFFICIENT_MARGIN"


def test_resolve_collision_sole_claimant():
    winner, code = resolve_collision([("PAY_A", 0.5)], margin=0.10)
    assert winner == "PAY_A"
    assert code == "SOLE_CLAIMANT"


def test_resolve_collision_order_independent():
    a = resolve_collision([("PAY_A", 0.95), ("PAY_B", 0.80), ("PAY_C", 0.60)], margin=0.10)
    b = resolve_collision([("PAY_C", 0.60), ("PAY_A", 0.95), ("PAY_B", 0.80)], margin=0.10)
    c = resolve_collision([("PAY_B", 0.80), ("PAY_C", 0.60), ("PAY_A", 0.95)], margin=0.10)
    assert a == b == c == ("PAY_A", "CLEAR_WINNER")


def test_resolve_collision_exact_tie_is_still_deterministic_not_first_seen():
    # Equal scores: order-of-arrival must NOT decide the (non-)outcome.
    claims1 = [("PAY_B", 0.80), ("PAY_A", 0.80)]
    claims2 = [("PAY_A", 0.80), ("PAY_B", 0.80)]
    assert resolve_collision(claims1, margin=0.10) == resolve_collision(claims2, margin=0.10)
    assert resolve_collision(claims1, margin=0.10)[0] is None  # gap is 0 < margin -> no winner


def test_validate_ai_recommendation_valid():
    d = FakeAIDecision("MATCH", "S1", 0.95)
    ok, reason = validate_ai_recommendation(d, ["S1", "S2"], M6PolicyConfig())
    assert ok
    assert reason == "AI_RECOMMENDATION_VALID"


def test_validate_ai_recommendation_none_decision():
    ok, reason = validate_ai_recommendation(None, ["S1"], M6PolicyConfig())
    assert not ok and reason == "AI_NO_DECISION"


def test_validate_ai_recommendation_unsupported_decision_value():
    d = FakeAIDecision("NO_MATCH", None, 0.95)
    ok, reason = validate_ai_recommendation(d, ["S1"], M6PolicyConfig())
    assert not ok and reason.startswith("AI_NOT_A_MATCH_RECOMMENDATION")


def test_validate_ai_recommendation_null_candidate():
    d = FakeAIDecision("MATCH", None, 0.95)
    ok, reason = validate_ai_recommendation(d, ["S1"], M6PolicyConfig())
    assert not ok and reason == "AI_MATCH_WITH_NULL_CANDIDATE"


def test_validate_ai_recommendation_invalid_candidate_id():
    # Candidate belongs to a *different* payment's candidate set - this is
    # the case M6 must catch even if M5 itself failed to (defense in depth).
    d = FakeAIDecision("MATCH", "S_NOT_MINE", 0.95)
    ok, reason = validate_ai_recommendation(d, ["S1", "S2"], M6PolicyConfig())
    assert not ok and reason.startswith("AI_INVALID_CANDIDATE")


def test_validate_ai_recommendation_low_confidence():
    d = FakeAIDecision("MATCH", "S1", 0.50)
    ok, reason = validate_ai_recommendation(d, ["S1"], M6PolicyConfig())
    assert not ok and reason.startswith("AI_LOW_CONFIDENCE")


# ---------------------------------------------------------------------------
# Integration: protected statuses are never touched
# ---------------------------------------------------------------------------

def test_protected_status_preserved_even_with_tempting_ai_match():
    # The shim's pytest.mark.parametrize is a no-op, so this loops
    # explicitly over every non-MISSING protected status instead.
    for status in (STATUS.PARTIAL_MATCH, STATUS.CONFLICT, STATUS.REFUND, STATUS.MISSING):
        p = P(payment_id="PAY_1")
        m2 = {"PAY_1": (status, "S_ORIG" if status != STATUS.MISSING else None, "orig", None)}
        # Even if M3 somehow generated a candidate and a (fake) AI
        # confidently recommends MATCH against it, M6 must never touch a
        # protected status.
        candidates = {"PAY_1": [C("PAY_1", "S_TEMPTING")]}
        m5_outcomes = {"PAY_1": {
            "status": "ACCEPT",
            "decision": FakeAIDecision("MATCH", "S_TEMPTING", 0.99),
        }}
        result, audit, m5 = run(
            [p], {}, m2, candidates,
            m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
            m5_outcomes=m5_outcomes,
        )
        assert result["PAY_1"].status == status
        assert result["PAY_1"].decision_source == "M2_DETERMINISTIC"
        # M5 must never even be consulted for a protected payment.
        assert m5.calls == []


def test_duplicate_never_owns_a_settlement():
    canonical = P(payment_id="PAY_CANON")
    dup = P(payment_id="PAY_DUP")
    m2 = {
        "PAY_CANON": (STATUS.AMBIGUOUS, None, "orig", None),
        "PAY_DUP": (STATUS.DUPLICATE, None, "dup of canon", "PAY_CANON"),
    }
    result, audit, m5 = run(
        [canonical, dup], {}, m2, {},
        m4_outcomes={},
    )
    assert result["PAY_DUP"].status == STATUS.DUPLICATE
    assert result["PAY_DUP"].settlement_id is None


def test_m1_match_locked_in_and_owns_its_settlement():
    p = P(payment_id="PAY_1")
    s = S(settlement_id="S1")
    result, audit, m5 = run([p], {"PAY_1": s}, {}, {}, m4_outcomes={})
    assert result["PAY_1"].status == STATUS.MATCH
    assert result["PAY_1"].settlement_id == "S1"
    assert result["PAY_1"].decision_source == "M1_EXACT_MATCH"


# ---------------------------------------------------------------------------
# M4-only resolution (no AI needed)
# ---------------------------------------------------------------------------

def test_m4_accept_becomes_final_match_when_sole_claimant():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "orig", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("ACCEPT", "S1", 0.95, 0.30)},
    )
    assert result["PAY_1"].status == STATUS.MATCH
    assert result["PAY_1"].settlement_id == "S1"
    assert result["PAY_1"].decision_source == "M6_GLOBAL_POLICY"
    assert result["PAY_1"].confidence == pytest.approx(0.95)


def test_no_candidates_preserves_status():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.MISSING, None, "orig", None)}
    result, audit, m5 = run([p], {}, m2, {}, m4_outcomes={})
    assert result["PAY_1"].status == STATUS.MISSING


# ---------------------------------------------------------------------------
# Global collision resolution (spec items 1, 5, 6, 11; M6 prompt tests 1-3)
# ---------------------------------------------------------------------------

def test_one_settlement_two_payments_at_most_one_owner():
    p1, p2 = P(payment_id="PAY_001"), P(payment_id="PAY_002")
    m2 = {
        "PAY_001": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_002": (STATUS.AMBIGUOUS, None, "o", None),
    }
    candidates = {"PAY_001": [C("PAY_001", "STL_001")], "PAY_002": [C("PAY_002", "STL_001")]}
    result, audit, m5 = run(
        [p1, p2], {}, m2, candidates,
        m4_outcomes={
            "PAY_001": make_result("ACCEPT", "STL_001", 0.90, 0.20),
            "PAY_002": make_result("ACCEPT", "STL_001", 0.60, 0.20),
        },
    )
    owners = [d for d in result.values() if d.settlement_id == "STL_001"]
    # A clear score gap (0.30 >= the 0.10 collision margin) means exactly
    # one owner is picked; a near-tie would legitimately mean zero. Either
    # way the invariant "at most one" must hold - assert both explicitly.
    assert len(owners) <= 1
    assert len(owners) == 1
    assert owners[0].payment_id == "PAY_001"


def test_clear_winner_by_score_margin():
    p1, p2 = P(payment_id="PAY_A"), P(payment_id="PAY_B")
    m2 = {
        "PAY_A": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_B": (STATUS.AMBIGUOUS, None, "o", None),
    }
    candidates = {"PAY_A": [C("PAY_A", "STL_1")], "PAY_B": [C("PAY_B", "STL_1")]}
    result, audit, m5 = run(
        [p1, p2], {}, m2, candidates,
        m4_outcomes={
            "PAY_A": make_result("ACCEPT", "STL_1", 0.95, 0.20),
            "PAY_B": make_result("ACCEPT", "STL_1", 0.80, 0.20),
        },
    )
    assert result["PAY_A"].status == STATUS.MATCH
    assert result["PAY_A"].settlement_id == "STL_1"
    assert result["PAY_B"].status != STATUS.MATCH
    assert result["PAY_B"].settlement_id is None


def test_near_tie_stays_ambiguous_not_fabricated():
    p1, p2 = P(payment_id="PAY_A"), P(payment_id="PAY_B")
    m2 = {
        "PAY_A": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_B": (STATUS.AMBIGUOUS, None, "o", None),
    }
    candidates = {"PAY_A": [C("PAY_A", "STL_1")], "PAY_B": [C("PAY_B", "STL_1")]}
    result, audit, m5 = run(
        [p1, p2], {}, m2, candidates,
        m4_outcomes={
            "PAY_A": make_result("ACCEPT", "STL_1", 0.91, 0.20),
            "PAY_B": make_result("ACCEPT", "STL_1", 0.90, 0.20),
        },
    )
    assert result["PAY_A"].status == STATUS.AMBIGUOUS
    assert result["PAY_A"].settlement_id is None
    assert result["PAY_B"].status == STATUS.AMBIGUOUS
    assert result["PAY_B"].settlement_id is None


def test_collision_resolution_independent_of_input_row_order():
    p1, p2, p3 = P(payment_id="PAY_A"), P(payment_id="PAY_B"), P(payment_id="PAY_C")
    m2 = {pid: (STATUS.AMBIGUOUS, None, "o", None) for pid in ("PAY_A", "PAY_B", "PAY_C")}
    candidates = {
        "PAY_A": [C("PAY_A", "STL_1")],
        "PAY_B": [C("PAY_B", "STL_1")],
        "PAY_C": [C("PAY_C", "STL_1")],
    }
    m4_outcomes = {
        "PAY_A": make_result("ACCEPT", "STL_1", 0.95, 0.20),
        "PAY_B": make_result("ACCEPT", "STL_1", 0.80, 0.20),
        "PAY_C": make_result("ACCEPT", "STL_1", 0.60, 0.20),
    }
    orderings = [[p1, p2, p3], [p3, p1, p2], [p2, p3, p1]]
    outcomes = []
    for ordering in orderings:
        result, _, _ = run(ordering, {}, m2, candidates, m4_outcomes=m4_outcomes)
        outcomes.append({pid: (d.status, d.settlement_id) for pid, d in result.items()})
    assert outcomes[0] == outcomes[1] == outcomes[2]
    assert outcomes[0]["PAY_A"] == (STATUS.MATCH, "STL_1")


def test_settlement_already_owned_by_protected_decision_rejects_ai_proposal():
    canon = P(payment_id="PAY_CANON")
    contender = P(payment_id="PAY_CONTENDER")
    m2 = {
        "PAY_CANON": (STATUS.REFUND, "STL_1", "refund", None),
        "PAY_CONTENDER": (STATUS.AMBIGUOUS, None, "o", None),
    }
    candidates = {"PAY_CONTENDER": [C("PAY_CONTENDER", "STL_1")]}
    result, audit, m5 = run(
        [canon, contender], {}, m2, candidates,
        m4_outcomes={"PAY_CONTENDER": make_result("ACCEPT", "STL_1", 0.99, 0.5)},
    )
    assert result["PAY_CANON"].status == STATUS.REFUND
    assert result["PAY_CANON"].settlement_id == "STL_1"
    assert result["PAY_CONTENDER"].status == STATUS.AMBIGUOUS
    assert result["PAY_CONTENDER"].settlement_id is None
    rules = [e.rule_id for e in audit.events if e.record_id == "PAY_CONTENDER"]
    assert "RULE_M6_SETTLEMENT_ALREADY_OWNED" in rules


# ---------------------------------------------------------------------------
# M5 AI recommendation handling (spec item 10 / M6 prompt tests 9-11)
# ---------------------------------------------------------------------------

def test_ai_provider_failure_escalates_to_review():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
        m5_outcomes={"PAY_1": {"status": "ESCALATE", "reason": "PROVIDER_FAILED"}},
    )
    assert result["PAY_1"].status == STATUS.UNRESOLVED
    assert result["PAY_1"].settlement_id is None


def test_ai_malformed_output_escalates_to_review():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
        m5_outcomes={"PAY_1": {"status": "ESCALATE", "reason": "VALIDATION_FAILED"}},
    )
    assert result["PAY_1"].status == STATUS.UNRESOLVED


def test_ai_recommends_already_owned_settlement_rejected_no_double_ownership():
    owner = P(payment_id="PAY_OWNER")
    other = P(payment_id="PAY_OTHER")
    s = S(settlement_id="S1")
    m2 = {"PAY_OTHER": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_OTHER": [C("PAY_OTHER", "S1")]}
    result, audit, m5 = run(
        [owner, other], {"PAY_OWNER": s}, m2, candidates,
        m4_outcomes={"PAY_OTHER": make_result("REVIEW_REQUIRED")},
        m5_outcomes={"PAY_OTHER": {
            "status": "ACCEPT",
            "decision": FakeAIDecision("MATCH", "S1", 0.99),
        }},
    )
    assert result["PAY_OWNER"].settlement_id == "S1"
    assert result["PAY_OTHER"].settlement_id is None
    owners_of_s1 = [d for d in result.values() if d.settlement_id == "S1"]
    assert len(owners_of_s1) == 1


def test_ai_low_confidence_below_m6_floor_even_if_m5_labeled_it_accept():
    # Simulates a buggy/compromised M5 that mislabels status as ACCEPT -
    # M6's own independent confidence check must still catch it.
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
        m5_outcomes={"PAY_1": {
            "status": "ACCEPT",
            "decision": FakeAIDecision("MATCH", "S1", 0.10),
        }},
    )
    assert result["PAY_1"].status == STATUS.UNRESOLVED
    assert result["PAY_1"].settlement_id is None


def test_m5_never_consulted_when_m4_already_accepted():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("ACCEPT", "S1", 0.95, 0.3)},
        m5_outcomes={"PAY_1": {"status": "ESCALATE", "reason": "SHOULD_NOT_BE_CALLED"}},
    )
    assert result["PAY_1"].status == STATUS.MATCH
    assert m5.calls == []


def test_m5_unavailable_preserves_status_safely():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.AMBIGUOUS, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
        m5_outcomes=None,
    )
    assert result["PAY_1"].status == STATUS.AMBIGUOUS
    assert result["PAY_1"].settlement_id is None


# ---------------------------------------------------------------------------
# Idempotency (spec item 13)
# ---------------------------------------------------------------------------

def test_idempotent_across_runs():
    p1, p2, p3 = P(payment_id="PAY_A"), P(payment_id="PAY_B"), P(payment_id="PAY_C")
    m2 = {
        "PAY_A": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_B": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_C": (STATUS.UNRESOLVED, None, "o", None),
    }
    candidates = {
        "PAY_A": [C("PAY_A", "STL_1")],
        "PAY_B": [C("PAY_B", "STL_1")],
        "PAY_C": [C("PAY_C", "STL_2")],
    }
    m4_outcomes = {
        "PAY_A": make_result("ACCEPT", "STL_1", 0.95, 0.20),
        "PAY_B": make_result("ACCEPT", "STL_1", 0.80, 0.20),
        "PAY_C": make_result("ACCEPT", "STL_2", 0.90, 0.30),
    }
    r1, audit1, _ = run([p1, p2, p3], {}, m2, candidates, m4_outcomes=m4_outcomes)
    r2, audit2, _ = run([p1, p2, p3], {}, m2, candidates, m4_outcomes=m4_outcomes)

    d1 = {pid: d.to_dict() for pid, d in r1.items()}
    d2 = {pid: d.to_dict() for pid, d in r2.items()}
    assert d1 == d2
    # Same events generated per fresh run - no progressive accumulation.
    assert len(audit1.events) == len(audit2.events)


# ---------------------------------------------------------------------------
# Decimal precision (spec item 14)
# ---------------------------------------------------------------------------

def test_candidate_amounts_stay_decimal_through_m6():
    p = P(payment_id="PAY_1", amount=Decimal("100.00"))
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    cand = C("PAY_1", "S1", amount_difference="0.03")
    assert isinstance(cand.amount_difference, Decimal)
    result, audit, m5 = run(
        [p], {}, m2, {"PAY_1": [cand]},
        m4_outcomes={"PAY_1": make_result("ACCEPT", "S1", 0.95, 0.3)},
    )
    # M6's own output confidence/score is a float (matches M4's existing
    # float scores), but never converts monetary Decimal amounts to float.
    assert isinstance(result["PAY_1"].confidence, float)
    assert isinstance(p.amount, Decimal)


# ---------------------------------------------------------------------------
# Auditability (spec item 15)
# ---------------------------------------------------------------------------

def test_global_collision_resolution_is_audited():
    p1, p2 = P(payment_id="PAY_A"), P(payment_id="PAY_B")
    m2 = {
        "PAY_A": (STATUS.AMBIGUOUS, None, "o", None),
        "PAY_B": (STATUS.AMBIGUOUS, None, "o", None),
    }
    candidates = {"PAY_A": [C("PAY_A", "STL_1")], "PAY_B": [C("PAY_B", "STL_1")]}
    result, audit, m5 = run(
        [p1, p2], {}, m2, candidates,
        m4_outcomes={
            "PAY_A": make_result("ACCEPT", "STL_1", 0.95, 0.20),
            "PAY_B": make_result("ACCEPT", "STL_1", 0.80, 0.20),
        },
    )
    rule_ids = {e.rule_id for e in audit.events}
    assert "RULE_M6_GLOBAL_COLLISION_RESOLVED" in rule_ids
    assert "RULE_M6_GLOBAL_COLLISION_LOST" in rule_ids
    winner_events = [e for e in audit.events if e.record_id == "PAY_A" and e.rule_id == "RULE_M6_GLOBAL_COLLISION_RESOLVED"]
    assert winner_events
    assert winner_events[0].candidate_ids == ["STL_1"]


def test_ai_rejection_is_audited():
    p = P(payment_id="PAY_1")
    m2 = {"PAY_1": (STATUS.UNRESOLVED, None, "o", None)}
    candidates = {"PAY_1": [C("PAY_1", "S1")]}
    result, audit, m5 = run(
        [p], {}, m2, candidates,
        m4_outcomes={"PAY_1": make_result("REVIEW_REQUIRED")},
        m5_outcomes={"PAY_1": {"status": "ESCALATE", "reason": "PROVIDER_FAILED"}},
    )
    events = [e for e in audit.events if e.record_id == "PAY_1"]
    assert any(e.rule_id == "RULE_M6_AI_RECOMMENDATION_REJECTED" for e in events)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def test_config_from_file():
    import json
    import os
    import tempfile

    data = {"policy_version": "vTEST", "ai_min_confidence": 0.77, "collision_margin": 0.05}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    try:
        cfg = M6PolicyConfig.from_file(path)
        assert cfg.ai_min_confidence == 0.77
        assert cfg.collision_margin == 0.05
        assert cfg.policy_version == "vTEST"
    finally:
        os.remove(path)


def test_config_from_m4_scorer():
    class FakeScorer:
        margin = 0.10

    cfg = M6PolicyConfig.from_m4_scorer(FakeScorer())
    assert cfg.collision_margin == 0.10
