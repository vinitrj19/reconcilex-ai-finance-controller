from math import ceil
from typing import Optional

from fastapi import APIRouter, HTTPException
from api.state import state, _money, _iso

router = APIRouter()


def list_item(pid: str):
    final = state.m6_final[pid]
    p = state.payments_by_id[pid]
    sid = final.get("settlement_id")
    s = state.settlements_by_id.get(sid) if sid else None
    return {
        "payment_id": pid,
        "order_id": p.order_id,
        "settlement_id": sid,
        "payment_amount": _money(p.amount),
        "settlement_amount": _money(s.net_amount) if s else None,
        "payment_date": p.timestamp.strftime("%d %b"),
        "settlement_date": s.timestamp.strftime("%d %b") if s else None,
        "currency": p.currency,
        "source": p.payment_method or "unknown",
        "status": final.get("status"),
        "confidence": final.get("confidence"),
    }


def _deterministic(pid: str):
    final = state.m6_final[pid]
    events = state.audit_by_payment.get(pid, [])
    decision_events = [e for e in events if e.get("stage") in {"M1_EXACT_MATCH", "M2_DETERMINISTIC"}]
    event = decision_events[-1] if decision_events else None
    candidates = state.candidates_for(pid)
    payment = state.payments_by_id[pid]
    threshold = None
    score = None
    runner_up = None
    actual_margin = None
    required_margin = None
    margin_satisfied = None
    if candidates:
        scores = [state.candidate_score(payment, c) for c in candidates]
        score = scores[0]
        threshold = state._scorer.threshold
        if len(scores) > 1:
            runner_up = scores[1]
            actual_margin = scores[0] - scores[1]
            required_margin = state._scorer.margin
            margin_satisfied = actual_margin >= required_margin
    return {
        "status": final.get("status"),
        "score": score,
        "threshold": threshold,
        "runner_up_score": runner_up,
        "required_margin": required_margin,
        "actual_margin": actual_margin,
        "margin_satisfied": margin_satisfied,
        "reason": event.get("notes") if event else final.get("reason", ""),
        "rule_id": event.get("rule_id") if event else None,
    }


def _candidate_payload(pid: str):
    p = state.payments_by_id[pid]
    out = []
    candidates = state.candidates_for(pid)
    for c in candidates:
        s = state.settlements_by_id.get(c.settlement_id)
        if s is None:
            continue
        amount_similarity = max(0.0, 1.0 - float(c.amount_difference / max(abs(p.amount), 1)))
        date_proximity = max(0.0, 1.0 - abs(c.date_difference) * 0.1)
        reference_similarity = min(1.0, len(c.matched_reference_fields) * 0.5)
        out.append({
            "settlement_id": s.settlement_id,
            "settlement_reference": s.settlement_reference,
            "amount": _money(s.net_amount),
            "date": s.timestamp.date().isoformat(),
            "evidence": {
                "amount_similarity": amount_similarity,
                "date_proximity": date_proximity,
                "reference_similarity": reference_similarity,
            },
            "score": state.candidate_score(p, c),
        })
    return out


def _ai(pid: str):
    events = state.audit_by_payment.get(pid, [])
    unavailable = next((e for e in events if e.get("rule_id") == "RULE_M6_M5_UNAVAILABLE"), None)
    return {
        "invoked": False,
        "provider": None,
        "decision": None,
        "confidence": None,
        "reasoning": None,
        "missing_evidence": [],
        "recommended_action": None,
        "unavailable_reason": unavailable.get("notes") if unavailable else None,
    }


def build_detail(payment_id: str):
    if payment_id not in state.m6_final or payment_id not in state.payments_by_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    p = state.payments_by_id[payment_id]
    final = state.m6_final[payment_id]
    order = state.orders_by_id.get(p.order_id) if p.order_id else None
    settlement = state.settlements_by_id.get(final.get("settlement_id")) if final.get("settlement_id") else None

    payment = {
        "payment_id": p.payment_id,
        "order_id": p.order_id,
        "amount": _money(p.amount),
        "currency": p.currency,
        "timestamp": str(p.raw.get("timestamp") or _iso(p.timestamp)),
        "payment_method": p.payment_method or "",
        "customer_reference": p.customer_reference or "",
        "description": p.description or "",
    }
    order_payload = None
    if order:
        order_payload = {
            "order_id": order.order_id,
            "order_timestamp": str(order.raw.get("order_timestamp") or _iso(order.order_timestamp)),
            "expected_amount": _money(order.expected_amount),
            "order_status": order.order_status,
            "payment_reference": order.payment_reference,
            "invoice_reference": order.invoice_reference,
        }
    settlement_payload = None
    if settlement:
        settlement_payload = {
            "settlement_id": settlement.settlement_id,
            "settlement_reference": settlement.settlement_reference,
            "timestamp": str(settlement.raw.get("timestamp") or _iso(settlement.timestamp)),
            "gross_amount": _money(settlement.gross_amount),
            "fee": _money(settlement.fee),
            "tax": _money(settlement.tax),
            "net_amount": _money(settlement.net_amount),
            "bank_reference": settlement.bank_reference or "",
            "status": settlement.status,
        }

    status = final.get("status")
    if status in {"MATCH", "PARTIAL_MATCH", "REFUND"}:
        outcome = "MATCH_APPROVED"
    elif status in {"CONFLICT", "DUPLICATE", "MISSING"}:
        outcome = "MATCH_REJECTED"
    else:
        outcome = "REVIEW_REQUIRED"

    return {
        "payment": payment,
        "order": order_payload,
        "settlement": settlement_payload,
        "candidates": _candidate_payload(payment_id),
        "deterministic": _deterministic(payment_id),
        "ai": _ai(payment_id),
        "final_decision": {
            "status": status,
            "settlement_id": final.get("settlement_id"),
            "confidence": final.get("confidence"),
            "decision_source": final.get("decision_source"),
            "policy_outcome": outcome,
            "reason": final.get("reason", ""),
        },
    }


@router.get("/reconciliation")
def list_reconciliations(page: int = 1, page_size: int = 20, search: str = "", status: Optional[str] = None):
    page = max(page, 1)
    page_size = max(min(page_size, 1000), 1)
    pids = list(state.m6_final.keys())
    if status and status != "ALL":
        if status == "REVIEW":
            allowed = {"AMBIGUOUS", "UNRESOLVED"}
            pids = [pid for pid in pids if state.m6_final[pid].get("status") in allowed]
        else:
            pids = [pid for pid in pids if state.m6_final[pid].get("status") == status]
    q = search.strip().lower()
    if q:
        pids = [
            pid for pid in pids
            if q in pid.lower()
            or q in (state.payments_by_id[pid].order_id or "").lower()
            or q in (state.m6_final[pid].get("settlement_id") or "").lower()
        ]
    total = len(pids)
    start = (page - 1) * page_size
    items = [list_item(pid) for pid in pids[start:start + page_size]]
    return {
        "items": items,
        "pagination": {"page": page, "page_size": page_size, "total": total, "pages": max(1, ceil(total / page_size))},
    }


@router.get("/reconciliation/{payment_id}")
def get_reconciliation_detail(payment_id: str):
    return build_detail(payment_id)
