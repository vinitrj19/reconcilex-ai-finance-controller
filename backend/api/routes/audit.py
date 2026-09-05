from fastapi import APIRouter
from api.state import state

router = APIRouter()


@router.get("/audit/{payment_id}")
def get_audit_timeline(payment_id: str):
    events = state.audit_by_payment.get(payment_id, [])
    return {
        "payment_id": payment_id,
        "events": [
            {
                "timestamp": e.get("timestamp", ""),
                "stage": e.get("stage", ""),
                "rule_id": e.get("rule_id"),
                "decision": e.get("decision", ""),
                "notes": e.get("notes", ""),
                "candidate_ids": e.get("candidate_ids", []),
            }
            for e in events
        ],
    }
