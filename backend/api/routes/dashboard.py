from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter
from api.state import state
from api.routes.exceptions import build_exception_items

router = APIRouter()


@router.get("/dashboard")
def get_dashboard():
    total = len(state.m6_final)
    statuses = Counter(d.get("status", "UNKNOWN") for d in state.m6_final.values())
    eval_headline = state.eval_results["full_controller"]["headline"]
    review_count = statuses.get("AMBIGUOUS", 0) + statuses.get("UNRESOLVED", 0)
    exception_items = build_exception_items()

    timestamps = [e.get("timestamp") for events in state.audit_by_payment.values() for e in events if e.get("timestamp")]
    generated_at = max(timestamps) if timestamps else datetime.now(timezone.utc).isoformat()
    run_id = f"DEV-M6-{generated_at[:10]}"

    status_breakdown = [
        {"status": status, "count": statuses.get(status, 0)}
        for status in ("MATCH", "PARTIAL_MATCH", "REFUND", "CONFLICT", "MISSING", "DUPLICATE", "AMBIGUOUS", "UNRESOLVED")
        if statuses.get(status, 0)
    ]

    return {
        "run_id": run_id,
        "dataset": "DEV",
        "generated_at": generated_at,
        "metrics": {
            "transactions_processed": total,
            "reconciled": eval_headline["overall_correct"],
            "safe_automation_rate": state.eval_results["full_controller"]["safe_automation_rate"]["rate"] * 100,
            "financial_false_positives": eval_headline["false_positives"]["count"],
        },
        "pipeline": [
            {"stage": "sources", "label": "Payments", "count": len(state.payments)},
            {"stage": "sources", "label": "Settlements", "count": len(state.settlements)},
            {"stage": "sources", "label": "Orders", "count": len(state.orders)},
            {"stage": "normalization", "label": "Normalization", "count": None, "detail": "References resolved across sources"},
            {"stage": "deterministic", "label": "Deterministic Resolution", "count": total - statuses.get("AMBIGUOUS", 0) - statuses.get("UNRESOLVED", 0), "detail": "M1 identity + M2/M4 rules"},
            {"stage": "ai", "label": "AI Review", "count": statuses.get("AMBIGUOUS", 0), "detail": "residual ambiguous cases only"},
            {"stage": "policy", "label": "Policy Controlled", "count": None, "detail": "M6 global safety invariants"},
            {"stage": "final", "label": "Final Decision", "count": total, "detail": f"{review_count} sent to review"},
        ],
        "status_breakdown": status_breakdown,
        "recent_exceptions": exception_items[:5],
    }
