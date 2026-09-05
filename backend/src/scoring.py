import json
from decimal import Decimal

class M4Scorer:
    def __init__(self, config_path="reconciliation_controller/config/m4_thresholds.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        self.w_amt = float(self.config["feature_weights"]["amount_weight"])
        self.w_date = float(self.config["feature_weights"]["date_weight"])
        self.w_ref = float(self.config["feature_weights"]["reference_weight"])
        self.threshold = float(self.config["acceptance_threshold"])
        self.margin = float(self.config["minimum_margin"])

    def score_candidate(self, candidate, target_amount: Decimal) -> float:
        # Amount Logic (Decimal only for financial math)
        if candidate.amount_difference == Decimal("0.00"):
            c_amt = 1.0
        else:
            variance_ratio = float(abs(candidate.amount_difference) / target_amount)
            c_amt = max(0.0, 1.0 - (variance_ratio * 10))

        # Date Logic
        c_date = max(0.0, 1.0 - (abs(candidate.date_difference) * 0.1))

        # Reference Logic
        c_ref = min(1.0, len(candidate.matched_reference_fields) * 0.5)

        return (self.w_amt * c_amt) + (self.w_date * c_date) + (self.w_ref * c_ref)

    def evaluate_payment(self, payment_record) -> dict:
        if not payment_record.candidates:
            return {"status": "NO_CANDIDATE"}
        
        scored = [{"candidate": c, "score": self.score_candidate(c, Decimal(payment_record.amount))} for c in payment_record.candidates]
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        top_score = scored[0]["score"]
        margin = (top_score - scored[1]["score"]) if len(scored) > 1 else 1.0
        
        if top_score >= self.threshold and margin >= self.margin:
            return {"status": "ACCEPT", "top": scored[0], "margin": margin}
        
        return {"status": "REVIEW_REQUIRED", "top": scored[0], "margin": margin}