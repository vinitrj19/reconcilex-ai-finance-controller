"""
M1 Stage 1 - strong exact identifier matching.

Per spec section 7, the only *strong* payment<->settlement relationship is:

    payment.payment_id == settlement.settlement_reference

Order relationships are corroborating evidence only, never proof of
settlement identity, and are therefore not consulted here.

This stage claims a payment (as MATCH) only when the referenced settlement
ALSO agrees on amount (within config.monetary_tolerance) and date (within
config.date_tolerance_days). A settlement_reference match with a differing
amount is still identity-proven, but the amount discrepancy needs the
fee/GST/refund/conflict reasoning that M2 owns (spec section 8) - so those
payments are deliberately left unmatched here and handled by M2's direct-
reference path, not duplicated in this module.

Zero LLM calls. Zero use of ground-truth/event IDs.
"""

from typing import Dict, List, Tuple

from src.models import NormalizedPayment, NormalizedSettlement
from src.audit import AuditLog
from src.config import ReconciliationConfig


def run_stage1_exact_matching(
    payments: List[NormalizedPayment],
    settlements: List[NormalizedSettlement],
    config: ReconciliationConfig,
    audit: AuditLog,
) -> Tuple[Dict[str, NormalizedSettlement], List[NormalizedPayment]]:
    """Returns (matched: payment_id -> settlement, unmatched_payments).

    ``matched`` settlements are removed from consideration by every later
    stage (M2 fallback search only ever looks at settlements that are
    "orphan" w.r.t. known payment ids, which by construction excludes
    anything referenced here).
    """
    settlement_by_reference: Dict[str, NormalizedSettlement] = {}
    for s in settlements:
        # Dataset is constructed so a given settlement_reference identifies
        # at most one payment; first-seen is deterministic (settlements are
        # iterated in a fixed, caller-provided order) and never depends on
        # dict/set iteration order elsewhere in the pipeline.
        settlement_by_reference.setdefault(s.settlement_reference, s)

    matched: Dict[str, NormalizedSettlement] = {}
    unmatched_payments: List[NormalizedPayment] = []

    for p in payments:
        s = settlement_by_reference.get(p.payment_id)

        if s is None:
            unmatched_payments.append(p)
            continue

        amount_ok = abs(p.amount - s.net_amount) <= config.monetary_tolerance
        days_diff = abs((s.timestamp - p.timestamp).days)
        date_ok = days_diff <= config.date_tolerance_days

        if amount_ok and date_ok:
            matched[p.payment_id] = s
            audit.log_event(
                record_id=p.payment_id,
                stage="M1_EXACT_MATCH",
                rule_id="RULE_M1_EXACT_IDENTIFIER_MATCH",
                decision="MATCH",
                candidate_ids=[s.settlement_id],
                relevant_input_values={
                    "payment_amount": str(p.amount),
                    "settlement_net_amount": str(s.net_amount),
                    "days_diff": days_diff,
                },
                explanation=(
                    f"Strong identity match: settlement {s.settlement_id}.settlement_reference "
                    f"== payment_id, amount and date agree within tolerance."
                ),
            )
        else:
            # Identity is still proven by the reference match, but the
            # amount/date discrepancy needs M2's fee/GST/refund/conflict
            # reasoning - leave unresolved here on purpose.
            unmatched_payments.append(p)

    return matched, unmatched_payments
