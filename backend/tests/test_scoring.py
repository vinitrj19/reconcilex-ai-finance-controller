import pytest
import json
from decimal import Decimal
import tempfile
import os
from src.scoring import M4Scorer

# Mock classes to simulate the expected APIs without importing external models
class MockCandidateRecord:
    def __init__(self, settlement_id, amount_diff, date_diff, matched_refs):
        self.settlement_id = settlement_id
        self.amount_difference = Decimal(str(amount_diff))
        self.date_difference = int(date_diff)
        self.matched_reference_fields = list(matched_refs)

class MockPaymentRecord:
    def __init__(self, payment_id, amount, candidates=None):
        self.payment_id = payment_id
        self.amount = Decimal(str(amount))
        self.candidates = candidates or []

@pytest.fixture
def m4_config_path():
    # Create a temporary config file to avoid file I/O dependencies
    config_data = {
        "scoring_version": "v1.0.0-M4-TEST",
        "dataset_split": "DEV",
        "acceptance_threshold": 0.75,
        "minimum_margin": 0.10,
        "feature_weights": {
            "amount_weight": 0.50,
            "date_weight": 0.15,
            "reference_weight": 0.35
        }
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump(config_data, f)
    yield path
    os.remove(path)

@pytest.fixture
def scorer(m4_config_path):
    return M4Scorer(config_path=m4_config_path)

def test_score_exact_match(scorer):
    # Exact amount, exact date, strong references
    candidate = MockCandidateRecord("set_1", "0.00", 0, ["ref1", "ref2"])
    score = scorer.score_candidate(candidate, Decimal("100.00"))
    
    # 0.50(1.0) + 0.15(1.0) + 0.35(min(1.0, 2 * 0.5)) = 0.50 + 0.15 + 0.35 = 1.0
    assert score == 1.0

def test_score_amount_degradation(scorer):
    # 5.00 diff on 100.00 target = 5% variance
    # c_amt = max(0.0, 1.0 - (0.05 * 10)) = 0.5
    candidate = MockCandidateRecord("set_1", "5.00", 0, ["ref1", "ref2"])
    score = scorer.score_candidate(candidate, Decimal("100.00"))
    
    # 0.50(0.5) + 0.15(1.0) + 0.35(1.0) = 0.25 + 0.15 + 0.35 = 0.75
    assert score == 0.75

def test_score_date_penalty(scorer):
    # Exact amount, 2 days off, no references
    candidate = MockCandidateRecord("set_1", "0.00", 2, [])
    score = scorer.score_candidate(candidate, Decimal("100.00"))
    
    # 0.50(1.0) + 0.15(1.0 - 0.2) + 0.35(0.0) = 0.50 + 0.12 + 0.0 = 0.62
    assert score == pytest.approx(0.62)

def test_evaluate_payment_accept(scorer):
    # Candidate 1: Perfect match (Score 1.0)
    # Candidate 2: Poor match (Score ~ 0.5)
    c1 = MockCandidateRecord("set_1", "0.00", 0, ["ref1", "ref2"])
    c2 = MockCandidateRecord("set_2", "10.00", 0, [])
    
    payment = MockPaymentRecord("pay_1", "100.00", [c1, c2])
    result = scorer.evaluate_payment(payment)
    
    assert result["status"] == "ACCEPT"
    assert result["top"]["candidate"].settlement_id == "set_1"
    assert result["margin"] >= 0.10

def test_evaluate_payment_review_required_margin(scorer):
    # Candidate 1 and Candidate 2 are identical/ambiguous
    c1 = MockCandidateRecord("set_1", "0.00", 0, ["ref1", "ref2"])
    c2 = MockCandidateRecord("set_2", "0.00", 0, ["ref3", "ref4"])
    
    payment = MockPaymentRecord("pay_1", "100.00", [c1, c2])
    result = scorer.evaluate_payment(payment)
    
    # Margin is 0.0, which is < 0.10
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["margin"] == 0.0

def test_evaluate_payment_no_candidate(scorer):
    payment = MockPaymentRecord("pay_1", "100.00", [])
    result = scorer.evaluate_payment(payment)
    assert result["status"] == "NO_CANDIDATE"