from fastapi import APIRouter, HTTPException
from api.state import state, EXCEPTION_STATUSES, _case_id, _exception_type, _priority, _recommended_action, _money

router = APIRouter()


def build_exception_items():
    by_payment = {x["payment_id"]: x for x in state.exceptions_dev}
    items = []
    for pid, final in state.m6_final.items():
        status = final.get("status")
        if status not in EXCEPTION_STATUSES:
            continue
        payment = state.payments_by_id.get(pid)
        if payment is None:
            continue
        src = by_payment.get(pid, {})
        candidates = state.candidates_for(pid)
        top = candidates[0].settlement_id if candidates else src.get("top_candidate")
        items.append({
            "case_id": _case_id(pid),
            "payment_id": pid,
            "type": _exception_type(status),
            "amount": _money(payment.amount),
            "currency": payment.currency,
            "reason": final.get("reason", src.get("reason", "")),
            "status": status,
            "priority": _priority(status),
            "candidate_count": len(candidates) if candidates else int(src.get("candidate_count", 0)),
            "top_candidate_id": top,
            "ai_invoked": False,
            "recommended_action": _recommended_action(status),
        })
    return items


@router.get("/exceptions")
def list_exceptions():
    items = build_exception_items()
    statuses = [i["status"] for i in items]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "high_priority": sum(i["priority"] == "HIGH" for i in items),
            "review_required": sum(s in {"AMBIGUOUS", "UNRESOLVED"} for s in statuses),
            "unresolved": statuses.count("UNRESOLVED"),
            "duplicates": statuses.count("DUPLICATE"),
        },
    }


@router.get("/exceptions/{case_id}")
def get_exception_detail(case_id: str):
    item = next((x for x in build_exception_items() if x["case_id"] == case_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Exception case not found")
    from api.routes.reconciliation import build_detail
    detail = build_detail(item["payment_id"])
    detail.update({
        "case_id": case_id,
        "investigation_prompts": [
            "What direct references (order ID, settlement reference) exist between these records?",
            "Do the amounts differ by a fee, tax, or currency-rounding delta that would explain a mismatch?",
            "Is another payment contesting the same settlement candidate?",
            "Is there a plausible settlement in a wider date window that the deterministic rules excluded?",
        ],
    })
    return detail
