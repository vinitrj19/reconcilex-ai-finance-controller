"""
End-to-end M5 <-> M6 integration tests (M9).

Unlike tests/test_m6_policy.py (which uses a duck-typed FakeM5Engine so M6
can be tested without pydantic), these tests wire the REAL
``src.m5_reasoning.M5ReasoningEngine`` with a REAL ``src.m5_provider``
provider into the REAL ``src.policy.run_m6_global_policy``. This is the
"M5 genuinely executes and M6 remains final authority" proof the M9 brief
asks for (section 9 cases 1-7, section 11 items J/K/L/M/N/O/P, section 12
leakage audit) - none of src/policy.py, src/scoring.py, src/candidates.py,
src/deterministic.py, src/matching.py is modified by this fix; this file
only exercises them.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.audit import AuditLog
from src.candidates import CandidateRecord
from src.deterministic import ReconciliationStatus
from src.m5_provider import MockProvider, FailingProvider
from src.m5_reasoning import M5ReasoningEngine
from src.models import NormalizedPayment, NormalizedSettlement
from src.policy import M6PolicyConfig, run_m6_global_policy

STATUS = ReconciliationStatus


# ---------------------------------------------------------------------------
# Factories (mirrors tests/test_m6_policy.py's shape exactly)
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
        evidence={"amount_difference": amount_difference},
    )


class FakeM4Scorer:
    """payment_id -> canned M4Scorer.evaluate_payment(...) result. M4 is
    frozen for M9 (see M9_CHANGELOG.md) - faked here only so these tests
    can drive M5/M6 without depending on config/m4_thresholds.json's
    exact locked numbers."""

    def __init__(self, outcomes: dict):
        self.outcomes = outcomes

    def evaluate_payment(self, view):
        return self.outcomes.get(view.payment_id, {"status": "REVIEW_REQUIRED", "top": None, "margin": None})


def run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider, config=None):
    audit = AuditLog()
    m4 = FakeM4Scorer(m4_outcomes)
    m5 = M5ReasoningEngine(provider=provider, audit_log=[]) if provider is not None else None
    result = run_m6_global_policy(payments, m1_matched, m2_results, m3_candidates, m4, m5, audit, config)
    return result, audit, m5


def _residual_setup(m4_status="REVIEW_REQUIRED"):
    """One AMBIGUOUS payment with two candidates - the standard case for
    exercising M5 -> M6."""
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    payments = [p1]
    m1_matched = {}
    m2_results = {"P1": (STATUS.AMBIGUOUS, None, "genuinely ambiguous", None)}
    m3_candidates = {"P1": [C("P1", "S1"), C("P1", "S2")]}
    m4_outcomes = {"P1": {"status": m4_status, "top": {"candidate": C("P1", "S1"), "score": 0.6}, "margin": 0.02}}
    return payments, m1_matched, m2_results, m3_candidates, m4_outcomes


# ---------------------------------------------------------------------------
# Section 9 / safety cases - AI proposes, M6 disposes
# ---------------------------------------------------------------------------

def test_case1_ai_match_rejected_when_settlement_already_owned():
    """AI says MATCH on S1, but S1 is already owned by a protected M2
    decision for a different payment -> M6 must reject the AI proposal."""
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    p2 = P(payment_id="P2", amount=Decimal("100.00"))
    payments = [p1, p2]
    m1_matched = {}
    m2_results = {
        "P1": (STATUS.MISSING, "S1", "protected owner", None),  # P1 owns S1, protected
        "P2": (STATUS.AMBIGUOUS, None, "residual", None),
    }
    m3_candidates = {"P2": [C("P2", "S1")]}
    m4_outcomes = {"P2": {"status": "REVIEW_REQUIRED", "top": {"candidate": C("P2", "S1"), "score": 0.6}, "margin": 0.02}}
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S1", "confidence": 0.95,
        "reasoning": "looks right", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)

    assert final["P1"].settlement_id == "S1"          # protected owner unchanged
    assert final["P2"].status != STATUS.MATCH          # AI's proposal was NOT granted
    assert final["P2"].settlement_id is None
    rule_ids = {e.rule_id for e in audit.all()}
    assert "RULE_M6_SETTLEMENT_ALREADY_OWNED" in rule_ids


def test_case2_ai_match_below_confidence_floor_safe_fails():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S1", "confidence": 0.79,  # below 0.80 floor
        "reasoning": "fairly sure", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)

    assert final["P1"].status != STATUS.MATCH
    assert final["P1"].settlement_id is None
    # M5's OWN internal floor (0.80) rejects this before M6 even sees a
    # decision object - confirms the confidence floor is enforced, not
    # merely documented.
    assert any(e.rule_id == "RULE_M6_AI_RECOMMENDATION_REJECTED" for e in audit.all())


def test_case3_ai_match_insufficient_margin_routes_to_review():
    """Two payments both get a validated AI MATCH proposal on the SAME
    settlement with too small a score gap -> M6 must not pick a winner."""
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    p2 = P(payment_id="P2", amount=Decimal("100.00"))
    payments = [p1, p2]
    m1_matched = {}
    m2_results = {
        "P1": (STATUS.AMBIGUOUS, None, "residual", None),
        "P2": (STATUS.AMBIGUOUS, None, "residual", None),
    }
    m3_candidates = {"P1": [C("P1", "S1")], "P2": [C("P2", "S1")]}
    m4_outcomes = {
        "P1": {"status": "REVIEW_REQUIRED", "top": {"candidate": C("P1", "S1"), "score": 0.6}, "margin": 0.02},
        "P2": {"status": "REVIEW_REQUIRED", "top": {"candidate": C("P2", "S1"), "score": 0.6}, "margin": 0.02},
    }

    class TwoResponseProvider:
        def __init__(self):
            self.calls = 0

        def reason(self, evidence):
            self.calls += 1
            confidence = 0.90 if evidence["payment_id"] == "P1" else 0.88  # gap < collision_margin
            from src.m5_schema import AIDecision
            return AIDecision(
                decision="MATCH", selected_candidate_id="S1", confidence=confidence,
                reasoning="plausible", missing_evidence=[], recommended_action="ACCEPT",
            )

    final, audit, _ = run_real_pipeline(
        payments, m1_matched, m2_results, m3_candidates, m4_outcomes,
        provider=TwoResponseProvider(), config=M6PolicyConfig(ai_min_confidence=0.80, collision_margin=0.10),
    )
    assert final["P1"].status != STATUS.MATCH
    assert final["P2"].status != STATUS.MATCH
    assert any(e.rule_id == "RULE_M6_GLOBAL_COLLISION_REVIEW" for e in audit.all())


def test_case4_malformed_ai_json_safe_fails():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()

    class MalformedProvider:
        def reason(self, evidence):
            raise ValueError("could not parse model output as JSON")

    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, MalformedProvider())
    assert final["P1"].status != STATUS.MATCH
    assert any(e.rule_id == "RULE_M6_AI_RECOMMENDATION_REJECTED" for e in audit.all())


def test_case5_nonexistent_candidate_safe_fails():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S_DOES_NOT_EXIST", "confidence": 0.95,
        "reasoning": "hallucinated", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    assert final["P1"].status != STATUS.MATCH
    assert final["P1"].settlement_id is None


def test_case6_ai_no_match_never_claims_ownership():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "NO_MATCH", "selected_candidate_id": None, "confidence": 0.9,
        "reasoning": "neither candidate fits", "missing_evidence": [], "recommended_action": "ESCALATE",
    })
    final, _, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    assert final["P1"].settlement_id is None
    assert final["P1"].status != STATUS.MATCH


def test_case7_ai_ambiguous_never_claims_ownership():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "AMBIGUOUS", "selected_candidate_id": None, "confidence": 0.5,
        "reasoning": "both equally plausible", "missing_evidence": ["no reference id"], "recommended_action": "ESCALATE",
    })
    final, _, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    assert final["P1"].settlement_id is None
    assert final["P1"].status != STATUS.MATCH


# ---------------------------------------------------------------------------
# Successful path - AI proposal genuinely accepted end-to-end
# ---------------------------------------------------------------------------

def test_successful_ai_match_is_accepted_when_safe():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S1", "confidence": 0.95,
        "reasoning": "clear reference match", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    assert final["P1"].status == STATUS.MATCH
    assert final["P1"].settlement_id == "S1"
    assert final["P1"].decision_source == "M6_GLOBAL_POLICY"
    assert any(e.rule_id == "RULE_M6_AI_PROPOSAL_ACCEPTED" for e in audit.all())
    assert any(e.rule_id == "RULE_M6_SETTLEMENT_ASSIGNED" for e in audit.all())


# ---------------------------------------------------------------------------
# Provider failure / timeout
# ---------------------------------------------------------------------------

def test_provider_exception_safe_fails():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    final, audit, _ = run_real_pipeline(
        payments, m1_matched, m2_results, m3_candidates, m4_outcomes, FailingProvider(),
    )
    assert final["P1"].status != STATUS.MATCH
    assert any(e.rule_id == "RULE_M6_AI_RECOMMENDATION_REJECTED" for e in audit.all())


def test_provider_timeout_safe_fails():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    final, audit, _ = run_real_pipeline(
        payments, m1_matched, m2_results, m3_candidates, m4_outcomes,
        FailingProvider(exception=TimeoutError("provider timed out")),
    )
    assert final["P1"].status != STATUS.MATCH


# ---------------------------------------------------------------------------
# AI cannot create duplicate settlement ownership across two payments
# ---------------------------------------------------------------------------

def test_ai_cannot_create_duplicate_settlement_ownership():
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    p2 = P(payment_id="P2", amount=Decimal("100.00"))
    payments = [p1, p2]
    m1_matched = {}
    m2_results = {
        "P1": (STATUS.AMBIGUOUS, None, "residual", None),
        "P2": (STATUS.AMBIGUOUS, None, "residual", None),
    }
    m3_candidates = {"P1": [C("P1", "S1")], "P2": [C("P2", "S1")]}
    m4_outcomes = {
        "P1": {"status": "REVIEW_REQUIRED", "top": {"candidate": C("P1", "S1"), "score": 0.6}, "margin": 0.02},
        "P2": {"status": "REVIEW_REQUIRED", "top": {"candidate": C("P2", "S1"), "score": 0.6}, "margin": 0.02},
    }

    class SameCandidateDistinctConfidenceProvider:
        """Clear score gap (>= collision_margin) so M6 CAN pick a winner -
        the interesting assertion is that it never picks BOTH."""
        def reason(self, evidence):
            from src.m5_schema import AIDecision
            confidence = 0.95 if evidence["payment_id"] == "P1" else 0.80
            return AIDecision(
                decision="MATCH", selected_candidate_id="S1", confidence=confidence,
                reasoning="looks right", missing_evidence=[], recommended_action="ACCEPT",
            )

    final, audit, _ = run_real_pipeline(
        payments, m1_matched, m2_results, m3_candidates, m4_outcomes, SameCandidateDistinctConfidenceProvider(),
    )
    winners = [pid for pid, d in final.items() if d.status == STATUS.MATCH and d.settlement_id == "S1"]
    assert len(winners) <= 1, "S1 must never be finally owned by more than one payment"
    assert winners == ["P1"], "clear score gap should let M6 pick the higher-confidence claim"
    assert final["P2"].status != STATUS.MATCH


# ---------------------------------------------------------------------------
# AI invocation boundary - never called for protected/accepted/empty cases
# ---------------------------------------------------------------------------

def test_no_ai_invocation_for_deterministic_match():
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    payments = [p1]
    m1_matched = {"P1": S(settlement_id="S1")}
    m2_results = {}
    m3_candidates = {}
    m4_outcomes = {}

    class SpyProvider:
        def __init__(self):
            self.calls = 0

        def reason(self, evidence):
            self.calls += 1
            raise AssertionError("must not be called for a deterministic M1 match")

    spy = SpyProvider()
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, spy)
    assert final["P1"].status == STATUS.MATCH
    assert spy.calls == 0


def test_no_ai_invocation_when_m4_already_accepted():
    payments, m1_matched, m2_results, m3_candidates, _ = _residual_setup()
    m4_outcomes = {"P1": {"status": "ACCEPT", "top": {"candidate": C("P1", "S1"), "score": 0.9}, "margin": 0.3}}

    class SpyProvider:
        def __init__(self):
            self.calls = 0

        def reason(self, evidence):
            self.calls += 1
            raise AssertionError("must not be called once M4 already accepted a candidate")

    spy = SpyProvider()
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, spy)
    assert final["P1"].status == STATUS.MATCH
    assert spy.calls == 0


def test_no_ai_invocation_with_no_candidates():
    p1 = P(payment_id="P1", amount=Decimal("100.00"))
    payments = [p1]
    m1_matched = {}
    m2_results = {"P1": (STATUS.UNRESOLVED, None, "no candidates", None)}
    m3_candidates = {}
    m4_outcomes = {}

    class SpyProvider:
        def __init__(self):
            self.calls = 0

        def reason(self, evidence):
            self.calls += 1
            raise AssertionError("must not be called with zero candidates")

    spy = SpyProvider()
    final, audit, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, spy)
    assert spy.calls == 0
    assert final["P1"].status == STATUS.UNRESOLVED


# ---------------------------------------------------------------------------
# Audit record created for every AI invocation
# ---------------------------------------------------------------------------

def test_audit_record_created_for_every_ai_invocation():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S1", "confidence": 0.95,
        "reasoning": "x", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    m5_audit_log = []
    engine = M5ReasoningEngine(provider=provider, audit_log=m5_audit_log)
    audit = AuditLog()
    m4 = FakeM4Scorer(m4_outcomes)
    run_m6_global_policy(payments, m1_matched, m2_results, m3_candidates, m4, engine, audit)
    assert len(m5_audit_log) == 1
    assert m5_audit_log[0]["status"] == "SUCCESS"
    assert m5_audit_log[0]["payment_id"] == "P1"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_m5_idempotent_same_input_same_output():
    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    provider = MockProvider({
        "decision": "MATCH", "selected_candidate_id": "S1", "confidence": 0.95,
        "reasoning": "x", "missing_evidence": [], "recommended_action": "ACCEPT",
    })
    final_a, _, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    final_b, _, _ = run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, provider)
    assert {k: v.to_dict() for k, v in final_a.items()} == {k: v.to_dict() for k, v in final_b.items()}


# ---------------------------------------------------------------------------
# Section 12 - data-leakage audit
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYS = {"expected_status", "expected_pairs", "anomaly_type", "ground_truth", "holdout_label", "split"}


def test_ai_context_contains_no_ground_truth():
    """Serializes the exact evidence dict M5 sends to the provider and
    asserts none of the forbidden ground-truth fields are present, at any
    nesting level."""
    captured = {}

    class CapturingProvider:
        def reason(self, evidence):
            captured.update(evidence)
            from src.m5_schema import AIDecision
            return AIDecision(
                decision="AMBIGUOUS", selected_candidate_id=None, confidence=0.5,
                reasoning="x", missing_evidence=[], recommended_action="ESCALATE",
            )

    payments, m1_matched, m2_results, m3_candidates, m4_outcomes = _residual_setup()
    run_real_pipeline(payments, m1_matched, m2_results, m3_candidates, m4_outcomes, CapturingProvider())

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in _FORBIDDEN_KEYS, f"forbidden key '{k}' reached the AI provider"
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)

    assert captured, "provider was never invoked - test setup problem"
    walk(captured)


def test_ai_context_source_code_has_no_ground_truth_import():
    """Static check: src/m5_reasoning.py and src/m5_provider.py must not
    reference any ground-truth field/file name. M5 has no legitimate
    reason to ever open a ground-truth file or read a labeled field.
    (Deliberately NOT checking for the word "holdout" - both files
    legitimately discuss, in comments, which dataset split a *caller*
    scores against; that is architecture documentation, not a leaked
    label. The runtime check above - test_ai_context_contains_no_ground_
    truth - is the primary safeguard for actual data flow.)"""
    import pathlib
    for fname in ("m5_reasoning.py", "m5_provider.py"):
        text = (pathlib.Path(__file__).resolve().parent.parent / "src" / fname).read_text()
        lowered = text.lower()
        for bad_token in ("ground_truth", "ground-truth file", "expected_status", "expected_pairs", "anomaly_type"):
            assert bad_token not in lowered, f"{fname} references '{bad_token}'"
