import pytest
from src.m5_provider import MockProvider
from src.m5_reasoning import M5ReasoningEngine

class MockCandidateRecord:
    def __init__(self, settlement_id):
        self.settlement_id = settlement_id

class MockPaymentRecord:
    def __init__(self, payment_id, amount, candidates):
        self.payment_id = payment_id
        self.amount = amount
        self.candidates = candidates

@pytest.fixture
def empty_audit_log():
    return []

@pytest.fixture
def standard_payment():
    return MockPaymentRecord(
        payment_id="pay_123",
        amount=100.00,
        candidates=[MockCandidateRecord("set_1"), MockCandidateRecord("set_2")]
    )

def test_m5_skips_m2_deterministic(empty_audit_log, standard_payment):
    engine = M5ReasoningEngine(provider=MockProvider(), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="MATCH", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "M2_DETERMINISTIC"
    assert len(empty_audit_log) == 0

def test_m5_skips_m4_accepted(empty_audit_log, standard_payment):
    engine = M5ReasoningEngine(provider=MockProvider(), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="ACCEPT")
    
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "M4_ACCEPTED"
    assert len(empty_audit_log) == 0

def test_m5_skips_no_candidates(empty_audit_log):
    payment = MockPaymentRecord("pay_123", 100.00, [])
    engine = M5ReasoningEngine(provider=MockProvider(), audit_log=empty_audit_log)
    result = engine.evaluate_payment(payment, m2_status="UNRESOLVED", m4_status="NO_CANDIDATE")
    
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "NO_CANDIDATE"

def test_m5_valid_match(empty_audit_log, standard_payment):
    mock_response = {
        "decision": "MATCH",
        "selected_candidate_id": "set_1",
        "confidence": 0.95,
        "reasoning": "Clear linkage found.",
        "recommended_action": "ACCEPT"
    }
    engine = M5ReasoningEngine(provider=MockProvider(mock_response), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ACCEPT"
    assert result["decision"].decision == "MATCH"
    assert len(empty_audit_log) == 1
    assert empty_audit_log[0]["status"] == "SUCCESS"

def test_m5_valid_ambiguous(empty_audit_log, standard_payment):
    mock_response = {
        "decision": "AMBIGUOUS",
        "selected_candidate_id": None,
        "confidence": 0.85,
        "reasoning": "Both candidates are equally plausible.",
        "recommended_action": "ESCALATE"
    }
    engine = M5ReasoningEngine(provider=MockProvider(mock_response), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="AMBIGUOUS", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ESCALATE"
    assert result["decision"].decision == "AMBIGUOUS"
    assert len(empty_audit_log) == 1

def test_m5_hallucinated_candidate_escalates(empty_audit_log, standard_payment):
    mock_response = {
        "decision": "MATCH",
        "selected_candidate_id": "set_999", # Hallucinated ID
        "confidence": 0.90,
        "reasoning": "I made this up.",
        "recommended_action": "ACCEPT"
    }
    engine = M5ReasoningEngine(provider=MockProvider(mock_response), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ESCALATE"
    assert result["reason"] == "PROVIDER_FAILED"
    assert "Hallucinated ID" in empty_audit_log[0]["escalation_reason"]

def test_m5_low_confidence_escalates(empty_audit_log, standard_payment):
    mock_response = {
        "decision": "MATCH",
        "selected_candidate_id": "set_1",
        "confidence": 0.70, # Below 0.80 threshold
        "reasoning": "Not very sure.",
        "recommended_action": "ACCEPT"
    }
    engine = M5ReasoningEngine(provider=MockProvider(mock_response), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ESCALATE"
    assert "Confidence too low" in empty_audit_log[0]["escalation_reason"]

def test_m5_provider_network_failure(empty_audit_log, standard_payment):
    engine = M5ReasoningEngine(provider=MockProvider(should_fail=True), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ESCALATE"
    assert empty_audit_log[0]["status"] == "PROVIDER_FAILED"
    assert "Mock network failure" in empty_audit_log[0]["escalation_reason"]

def test_m5_pydantic_validation_error(empty_audit_log, standard_payment):
    # Missing selected_candidate_id while decision is MATCH violates Pydantic rules
    mock_response = {
        "decision": "MATCH",
        "selected_candidate_id": None,
        "confidence": 0.95,
        "reasoning": "Invalid format.",
        "recommended_action": "ACCEPT"
    }
    engine = M5ReasoningEngine(provider=MockProvider(mock_response), audit_log=empty_audit_log)
    result = engine.evaluate_payment(standard_payment, m2_status="UNRESOLVED", m4_status="REVIEW_REQUIRED")
    
    assert result["status"] == "ESCALATE"
    assert empty_audit_log[0]["status"] == "VALIDATION_FAILED"