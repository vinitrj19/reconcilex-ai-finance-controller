from fastapi import APIRouter, HTTPException
from api.state import state

router = APIRouter()

STATUSES = ["MATCH", "PARTIAL_MATCH", "DUPLICATE", "MISSING", "REFUND", "CONFLICT", "AMBIGUOUS", "UNRESOLVED"]


@router.get("/evaluation")
def get_evaluation(dataset: str = "dev"):
    if dataset.lower() != "dev":
        raise HTTPException(status_code=403, detail="Only the DEV evaluation is exposed. Holdout is protected.")
    full = state.eval_results["full_controller"]
    headline = full["headline"]
    baseline = state.eval_results["baseline"]
    per_class = []
    for anomaly, values in full["event_level"]["by_anomaly_type"].items():
        per_class.append({"anomaly_type": anomaly, "support": values["total"], "correct": values["correct"], "rate": values["rate"]})

    return {
        "dataset": "DEV",
        "evaluation_type": "DEV",
        "run_id": "DEV-EVALUATION-RESULTS",
        "metrics": {
            "match_rate": headline["match_rate"]["rate"],
            "precision": headline["precision"],
            "recall": headline["recall"],
            "f1": headline["f1"],
            "financial_false_positives": headline["false_positives"]["count"],
            "safe_automation_rate": full["safe_automation_rate"]["rate"],
            "unresolved_rate": headline["unresolved_rate"]["rate"],
            "review_rate": headline["review_rate"]["rate"],
        },
        "baseline": [
            {"metric": "Precision", "baseline": baseline["precision"], "controller": headline["precision"], "unit": "percent"},
            {"metric": "Recall", "baseline": baseline["recall"], "controller": headline["recall"], "unit": "percent"},
            {"metric": "F1", "baseline": baseline["precision"], "controller": headline["f1"], "unit": "percent"},
            {"metric": "Match rate", "baseline": baseline["match_rate"], "controller": headline["match_rate"]["rate"], "unit": "percent"},
            {"metric": "False positives", "baseline": baseline["false_positives"], "controller": headline["false_positives"]["count"], "unit": "count"},
        ],
        "per_class": per_class,
        "confusion_matrix": [
            {"expected": r["expected_status"], "predicted": r["predicted_status"], "count": r["count"]}
            for r in state.confusion
        ],
        "statuses": STATUSES,
        "methodology": [
            "Matching thresholds and scoring weights were tuned only on the DEV split.",
            "Configuration is frozen before evaluation.",
            "HOLDOUT data is kept completely untouched outside this DEV evaluation adapter.",
            "Predictions are frozen before evaluation metrics are reported.",
            "Row-order shuffling and repeat runs were verified as deterministic and idempotent in the DEV evaluation artifact.",
        ],
    }
