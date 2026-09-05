"""M3: deterministic candidate generation only.

This stage creates plausible payment -> settlement candidate pairs for
payments M2 could not safely resolve to a single status with a settlement
already attached (MISSING / AMBIGUOUS / UNRESOLVED). It never selects a
winner or assigns a reconciliation status - M4 owns scoring/acceptance,
and the global one-to-one assignment policy belongs to M6.

Candidate pool: settlements not already claimed by M1 (exact match) or by
an M2 decision that attached a specific settlement (MATCH / PARTIAL_MATCH /
CONFLICT / REFUND). This keeps M3 from ever proposing a settlement that a
prior deterministic stage has already resolved.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Set

from src.models import NormalizedPayment, NormalizedSettlement, NormalizedOrder
from src.audit import AuditLog
from src.config import ReconciliationConfig


@dataclass(frozen=True)
class CandidateConfig:
    date_window_days: int = 7
    monetary_tolerance: Decimal = Decimal("0.05")
    max_candidates_per_payment: int = 10
    # Candidate generation may admit the dataset's known fee band; M4
    # remains responsible for scoring/acceptance.
    fee_rate_max: Decimal = Decimal("0.030")
    gst_rate: Decimal = Decimal("0.18")

    @classmethod
    def from_reconciliation_config(cls, config: ReconciliationConfig, **overrides) -> "CandidateConfig":
        base = dict(
            date_window_days=config.candidate_date_window_days,
            monetary_tolerance=config.monetary_tolerance,
            fee_rate_max=config.fee_rate_max,
            gst_rate=config.gst_rate,
        )
        base.update(overrides)
        return cls(**base)


@dataclass(frozen=True)
class CandidateRecord:
    """Fields M4 (src.scoring.M4Scorer) actually consumes:
    amount_difference, date_difference, matched_reference_fields.
    ``date_difference`` is a plain number of days (float), NOT a timedelta -
    M4's scoring formula (``1.0 - abs(date_difference) * 0.1``) is defined
    over a number, and a timedelta would break that arithmetic. Everything
    else here is generation-time evidence/metadata for audit purposes.
    """
    payment_id: str
    settlement_id: str
    amount_difference: Decimal
    date_difference: float
    matched_reference_fields: List[str] = field(default_factory=list)
    candidate_generation_rule: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


def _norm(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip().upper()
    return value or None


def generate_candidates(
    payments: List[NormalizedPayment],
    settlements: List[NormalizedSettlement],
    orders: List[NormalizedOrder],
    unresolved_payment_ids: Set[str],
    claimed_settlement_ids: Set[str],
    config: CandidateConfig,
    audit: AuditLog,
) -> Dict[str, List[CandidateRecord]]:
    """``claimed_settlement_ids`` is the union of settlements already
    attached to a decision by M1 or M2 (exact matches, direct-reference
    MATCH/PARTIAL_MATCH/CONFLICT/REFUND). Those are never offered as M3
    candidates for a different payment."""
    payment_map = {p.payment_id: p for p in payments}
    order_map = {o.order_id: o for o in orders if o.order_id}
    order_by_payment_ref: Dict[str, List[NormalizedOrder]] = {}
    for o in orders:
        ref = _norm(o.payment_reference)
        if ref:
            order_by_payment_ref.setdefault(ref, []).append(o)

    pool = [s for s in settlements if s.settlement_id not in claimed_settlement_ids]

    results: Dict[str, List[CandidateRecord]] = {}

    for pid in sorted(unresolved_payment_ids):
        p = payment_map.get(pid)
        if p is None:
            continue

        related_orders: List[NormalizedOrder] = []
        if p.order_id and p.order_id in order_map:
            related_orders.append(order_map[p.order_id])
        for o in order_by_payment_ref.get(_norm(p.payment_id), []):
            if o not in related_orders:
                related_orders.append(o)

        invoice_refs = {_norm(o.invoice_reference) for o in related_orders}
        invoice_refs.discard(None)

        max_deduction = p.amount * config.fee_rate_max * (Decimal("1") + config.gst_rate)

        candidates: Dict[str, CandidateRecord] = {}
        for s in pool:
            date_diff_days = abs((s.timestamp - p.timestamp).days)
            if date_diff_days > config.date_window_days:
                continue

            s_reference = _norm(s.settlement_reference)
            s_bank_ref = _norm(s.bank_reference)

            refs: List[str] = []
            if s_reference == _norm(p.payment_id):
                refs.append("settlement_reference")
            if s_bank_ref and s_bank_ref == _norm(p.payment_id):
                refs.append("bank_reference")
            if s_reference and s_reference in invoice_refs:
                refs.append("invoice_reference")

            amount_diff = abs(p.amount - s.net_amount)
            fee_plausible = amount_diff <= (max_deduction + config.monetary_tolerance)

            # A candidate must have either a reference signal or be
            # financially plausible within the fee/tolerance band. This is
            # generation, not acceptance - M4 still has to score/rank it.
            plausible = bool(refs) or amount_diff <= config.monetary_tolerance or fee_plausible
            if not plausible:
                continue

            if "settlement_reference" in refs:
                rule = "CAND_BLOCK_REFERENCE"
            elif "bank_reference" in refs:
                rule = "CAND_BLOCK_BANK_REFERENCE"
            elif "invoice_reference" in refs:
                rule = "CAND_BLOCK_INVOICE"
            else:
                rule = "CAND_BLOCK_AMOUNT_DATE"

            evidence = {
                "amount_difference": str(amount_diff),
                "date_difference_days": date_diff_days,
                "reference_signals": list(refs),
                "fee_band_plausible": fee_plausible,
                "payment_amount": str(p.amount),
                "settlement_net_amount": str(s.net_amount),
            }
            candidates[s.settlement_id] = CandidateRecord(
                payment_id=pid,
                settlement_id=s.settlement_id,
                amount_difference=amount_diff,
                date_difference=float(date_diff_days),
                matched_reference_fields=refs,
                candidate_generation_rule=rule,
                evidence=evidence,
            )

        ordered = sorted(
            candidates.values(),
            key=lambda c: (
                0 if c.matched_reference_fields else 1,
                c.amount_difference,
                c.date_difference,
                c.settlement_id,
            ),
        )
        truncated = len(ordered) > config.max_candidates_per_payment
        if truncated:
            ordered = ordered[: config.max_candidates_per_payment]
        results[pid] = ordered

        audit.log_event(
            record_id=pid,
            stage="M3_CANDIDATE_GENERATION",
            rule_id="RULE_M3_CANDIDATE_POOL",
            decision="CANDIDATES_GENERATED",
            candidate_ids=[c.settlement_id for c in ordered],
            relevant_input_values={
                "candidate_count": len(ordered),
                "truncated": truncated,
                "max_candidates_per_payment": config.max_candidates_per_payment,
            },
            explanation="Generated plausible settlement candidates; no winner or reconciliation status assigned.",
        )

    return results
