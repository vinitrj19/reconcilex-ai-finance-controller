"""
M2 Deterministic Reconciliation.

Consumes the payments M1 could NOT immediately resolve and produces one of:

    MATCH | PARTIAL_MATCH | CONFLICT | REFUND | DUPLICATE | MISSING |
    UNRESOLVED | AMBIGUOUS

for every one of them. Zero LLM/AI calls. Every decision is driven by
business evidence actually present in the normalized records - never by
event/anomaly IDs.

Decision order per payment (see module sections below for why):

  1. Duplicate detection (dataset-wide, before anything else).
  2. If the payment has a *direct* settlement reference (settlement_reference
     == payment_id) that M1 left unresolved (amount differed): classify via
     refund / partial-match-fee-band / conflict / (rare) exact match logic
     against that specific settlement. This is still "identity-proven",
     just amount-imperfect.
  3. If there is no direct reference at all:
       a. a dangling order_id (points to an order that does not exist) means
          the system cannot safely establish any relationship -> UNRESOLVED.
       b. otherwise, search unclaimed ("orphan") settlements for a plausible
          amount/date match:
            - zero candidates                                -> MISSING
            - 2+ candidates that are mutually indistinguishable
              in amount                                       -> AMBIGUOUS
            - anything else (a single weak, reference-less
              candidate) is NOT enough evidence for MATCH      -> UNRESOLVED
"""

from typing import Dict, List, Optional, Set, Tuple
from decimal import Decimal
from datetime import timedelta

from src.models import NormalizedPayment, NormalizedSettlement, NormalizedOrder
from src.audit import AuditLog
from src.config import ReconciliationConfig


class ReconciliationStatus:
    """Plain string constants (not an Enum) so downstream code and JSON
    serialization stay simple. Kept as a class purely for a stable,
    importable namespace: ReconciliationStatus.MATCH etc."""

    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    CONFLICT = "CONFLICT"
    REFUND = "REFUND"
    DUPLICATE = "DUPLICATE"
    MISSING = "MISSING"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


# (status, settlement_id_or_None, explanation, duplicate_of_or_None)
M2Decision = Tuple[str, Optional[str], str, Optional[str]]


class DeterministicReconciliationEngine:
    def __init__(self, config: ReconciliationConfig, audit_log: AuditLog):
        self.config = config
        self.audit_log = audit_log

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def reconcile_unmatched(
        self,
        all_payments: List[NormalizedPayment],
        unmatched_payments: List[NormalizedPayment],
        all_settlements: List[NormalizedSettlement],
        m1_matched_settlement_ids: Set[str],
        orders: List[NormalizedOrder],
    ) -> Dict[str, M2Decision]:
        order_map: Dict[str, NormalizedOrder] = {o.order_id: o for o in orders if o.order_id}
        known_payment_ids: Set[str] = {p.payment_id for p in all_payments}

        # Direct settlement_reference lookup over ALL settlements. A
        # settlement M1 already claimed will only ever be looked up here by
        # the SAME payment_id (settlement_reference is that payment_id), so
        # this can never hand a settlement to the wrong payment.
        settlement_by_reference: Dict[str, NormalizedSettlement] = {}
        for s in all_settlements:
            settlement_by_reference.setdefault(s.settlement_reference, s)

        # Settlements with no direct reference to any known payment_id are
        # "orphans" - the only pool eligible for the weaker, amount/date
        # fallback search. A settlement that DOES directly reference some
        # payment_id is never up for grabs by a different payment via
        # fuzzy evidence (order links are not proof of identity - see
        # module docstring / spec section 7).
        orphan_settlements = [
            s for s in all_settlements if s.settlement_reference not in known_payment_ids
        ]

        duplicate_of_map = self._detect_duplicates(all_payments)

        results: Dict[str, M2Decision] = {}
        fallback_bucket: List[NormalizedPayment] = []

        for p in unmatched_payments:
            pid = p.payment_id

            # 1. Duplicate detection takes priority over everything else,
            # including MISSING - a duplicate must never independently
            # claim (or be flagged as lacking) a settlement.
            if pid in duplicate_of_map:
                canonical_id = duplicate_of_map[pid]
                self.audit_log.increment_fact("N_DUPLICATES_DETECTED")
                expl = (
                    f"Duplicate of payment {canonical_id}: same order/customer "
                    f"and amount within the duplicate detection window."
                )
                self.audit_log.log_event(
                    record_id=pid,
                    stage="M2_DETERMINISTIC",
                    rule_id="RULE_M2_DUPLICATE_PAYMENT",
                    decision=ReconciliationStatus.DUPLICATE,
                    candidate_ids=[canonical_id],
                    relevant_input_values={"canonical_payment_id": canonical_id},
                    explanation=expl,
                )
                results[pid] = (ReconciliationStatus.DUPLICATE, None, expl, canonical_id)
                continue

            direct_s = settlement_by_reference.get(pid)
            if direct_s is not None:
                results[pid] = self._classify_direct_reference(p, direct_s, order_map)
                continue

            # No direct reference at all.
            if p.order_id is not None and p.order_id not in order_map:
                expl = (
                    f"Unresolved: payment.order_id={p.order_id!r} does not resolve to any "
                    f"known order, and no settlement directly references this payment. "
                    f"Relationship cannot be safely established."
                )
                self.audit_log.log_event(
                    record_id=pid,
                    stage="M2_DETERMINISTIC",
                    rule_id="RULE_M2_DANGLING_REFERENCE_UNRESOLVED",
                    decision=ReconciliationStatus.UNRESOLVED,
                    candidate_ids=[],
                    relevant_input_values={"order_id": p.order_id},
                    explanation=expl,
                )
                results[pid] = (ReconciliationStatus.UNRESOLVED, None, expl, None)
                continue

            # Everything left needs the fallback amount/date search, and that
            # search must see ALL of these payments together - the ambiguity
            # this dataset actually contains is two different payments both
            # plausibly claiming the SAME orphan settlement (a cross-payment
            # collision), not one payment seeing several settlements. See
            # _classify_fallback_batch for why this can't be decided payment
            # by payment.
            fallback_bucket.append(p)

        results.update(self._classify_fallback_batch(fallback_bucket, orphan_settlements))
        return results

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------
    def _detect_duplicates(self, payments: List[NormalizedPayment]) -> Dict[str, str]:
        """Dataset-wide, deterministic. Canonical = chronologically earliest
        of a duplicate cluster (tie-broken by payment_id, never CSV/dict
        insertion order). A payment already marked as a duplicate is never
        itself treated as a canonical for a later payment (no chaining)."""
        ordered = sorted(payments, key=lambda p: (p.timestamp, p.payment_id))
        duplicate_of: Dict[str, str] = {}
        window = timedelta(seconds=self.config.duplicate_window_seconds)

        n = len(ordered)
        for i in range(n):
            p1 = ordered[i]
            if p1.payment_id in duplicate_of:
                continue
            for j in range(i + 1, n):
                p2 = ordered[j]
                if (p2.timestamp - p1.timestamp) > window:
                    break
                if p2.payment_id in duplicate_of:
                    continue
                amount_close = abs(p1.amount - p2.amount) <= self.config.monetary_tolerance
                if not amount_close:
                    continue
                same_order = (
                    p1.order_id is not None and p2.order_id is not None and p1.order_id == p2.order_id
                )
                same_customer = (
                    p1.customer_reference is not None
                    and p2.customer_reference is not None
                    and p1.customer_reference == p2.customer_reference
                )
                if same_order or same_customer:
                    duplicate_of[p2.payment_id] = p1.payment_id

        return duplicate_of

    # ------------------------------------------------------------------
    # Classification against a directly-referenced settlement
    # ------------------------------------------------------------------
    def _classify_direct_reference(
        self,
        p: NormalizedPayment,
        s: NormalizedSettlement,
        order_map: Dict[str, NormalizedOrder],
    ) -> M2Decision:
        is_refund_signal = p.payment_status in ("refunded", "refund") or p.amount < Decimal("0.00")

        if is_refund_signal:
            settlement_corroborates = s.net_amount < Decimal("0.00") or s.status in ("refunded", "refund")
            linked_order = order_map.get(p.order_id) if p.order_id else None
            order_corroborates = bool(linked_order and linked_order.order_status in ("refunded", "cancelled"))

            if settlement_corroborates or order_corroborates:
                self.audit_log.increment_fact("N_REFUNDS_CORROBORATED")
                expl = (
                    f"Corroborated refund: payment_status={p.payment_status!r}, "
                    f"settlement {s.settlement_id} status={s.status!r}/net_amount={s.net_amount}, "
                    f"order_status={linked_order.order_status if linked_order else 'N/A'!r}."
                )
                self.audit_log.log_event(
                    record_id=p.payment_id,
                    stage="M2_DETERMINISTIC",
                    rule_id="RULE_M2_CORROBORATED_REFUND",
                    decision=ReconciliationStatus.REFUND,
                    candidate_ids=[s.settlement_id],
                    relevant_input_values={
                        "payment_amount": str(p.amount),
                        "payment_status": p.payment_status,
                        "settlement_net_amount": str(s.net_amount),
                    },
                    explanation=expl,
                )
                return (ReconciliationStatus.REFUND, s.settlement_id, expl, None)

            self.audit_log.increment_fact("N_REFUNDS_UNCORROBORATED")
            self.audit_log.log_event(
                record_id=p.payment_id,
                stage="M2_DETERMINISTIC",
                rule_id="RULE_M2_UNCORROBORATED_REFUND_SIGNAL",
                decision="FLAG_UNCORROBORATED_REFUND",
                candidate_ids=[s.settlement_id],
                relevant_input_values={"payment_status": p.payment_status, "payment_amount": str(p.amount)},
                explanation=(
                    f"payment_status/amount suggests refund but neither the referenced settlement "
                    f"nor the linked order corroborates it - not classified as REFUND on weak signal alone."
                ),
            )
            # Falls through to ordinary shortfall evaluation below.

        shortfall = p.amount - s.net_amount

        if abs(shortfall) <= self.config.monetary_tolerance:
            expl = f"Deterministic match against directly-referenced settlement {s.settlement_id}."
            self.audit_log.log_event(
                record_id=p.payment_id,
                stage="M2_DETERMINISTIC",
                rule_id="RULE_M2_REFERENCED_MATCH",
                decision=ReconciliationStatus.MATCH,
                candidate_ids=[s.settlement_id],
                relevant_input_values={"payment_amount": str(p.amount), "settlement_net_amount": str(s.net_amount)},
                explanation=expl,
            )
            return (ReconciliationStatus.MATCH, s.settlement_id, expl, None)

        min_deduction = p.amount * self.config.fee_rate_min * (Decimal("1") + self.config.gst_rate)
        max_deduction = p.amount * self.config.fee_rate_max * (Decimal("1") + self.config.gst_rate)
        tol = self.config.monetary_tolerance

        if (min_deduction - tol) <= shortfall <= (max_deduction + tol):
            expl = (
                f"Partial match: shortfall {shortfall} against settlement {s.settlement_id} "
                f"is within the plausible fee ({self.config.fee_rate_min * 100}-"
                f"{self.config.fee_rate_max * 100}%) + GST ({self.config.gst_rate * 100}%) band."
            )
            self.audit_log.log_event(
                record_id=p.payment_id,
                stage="M2_DETERMINISTIC",
                rule_id="RULE_M2_FEE_GST_PARTIAL_MATCH",
                decision=ReconciliationStatus.PARTIAL_MATCH,
                candidate_ids=[s.settlement_id],
                relevant_input_values={
                    "payment_amount": str(p.amount),
                    "settlement_net_amount": str(s.net_amount),
                    "shortfall": str(shortfall),
                },
                explanation=expl,
            )
            return (ReconciliationStatus.PARTIAL_MATCH, s.settlement_id, expl, None)

        expl = (
            f"Conflict: shortfall {shortfall} against settlement {s.settlement_id} is not explained "
            f"by the fee/GST band and is not a refund - material unexplained discrepancy."
        )
        self.audit_log.log_event(
            record_id=p.payment_id,
            stage="M2_DETERMINISTIC",
            rule_id="RULE_M2_UNEXPLAINED_SHORTFALL_CONFLICT",
            decision=ReconciliationStatus.CONFLICT,
            candidate_ids=[s.settlement_id],
            relevant_input_values={
                "payment_amount": str(p.amount),
                "settlement_net_amount": str(s.net_amount),
                "shortfall": str(shortfall),
            },
            explanation=expl,
        )
        return (ReconciliationStatus.CONFLICT, s.settlement_id, expl, None)

    # ------------------------------------------------------------------
    # Fallback search when there is no direct reference at all
    # ------------------------------------------------------------------
    def _candidate_settlements(
        self, p: NormalizedPayment, orphan_settlements: List[NormalizedSettlement]
    ) -> List[Tuple[Decimal, NormalizedSettlement]]:
        window = timedelta(days=self.config.candidate_date_window_days)
        max_deduction = p.amount * self.config.fee_rate_max * (Decimal("1") + self.config.gst_rate)
        tol = self.config.monetary_tolerance

        scored: List[Tuple[Decimal, NormalizedSettlement]] = []
        for s in orphan_settlements:
            # NormalizedSettlement carries no currency field - single
            # currency dataset per MANIFEST, so no currency check here.
            if abs(s.timestamp - p.timestamp) > window:
                continue
            amount_diff = abs(p.amount - s.net_amount)
            if amount_diff <= (max_deduction + tol):
                scored.append((amount_diff, s))

        scored.sort(key=lambda t: (t[0], t[1].settlement_id))
        return scored

    def _classify_fallback_batch(
        self,
        payments: List[NormalizedPayment],
        orphan_settlements: List[NormalizedSettlement],
    ) -> Dict[str, M2Decision]:
        """Payments with no direct settlement reference and no dangling FK.

        The genuine ambiguity in this data is a CROSS-payment collision:
        two different payments both plausibly (by amount/date, with no
        reference evidence) claim the same orphan settlement. That can only
        be seen by looking at every such payment's candidates together, not
        one payment at a time - a payment with a single, seemingly-clean
        candidate is still unsafe to call MATCH if another payment has an
        equal claim on that same settlement. Business rule: reference-less
        amount/date proximity is never strong enough evidence to arbitrate
        that contention, so ALL contesting payments become AMBIGUOUS.
        """
        tol = self.config.monetary_tolerance
        candidates_by_payment: Dict[str, List[Tuple[Decimal, NormalizedSettlement]]] = {
            p.payment_id: self._candidate_settlements(p, orphan_settlements) for p in payments
        }

        # settlement_id -> set of payment_ids for which it is a plausible candidate
        contenders: Dict[str, Set[str]] = {}
        for pid, scored in candidates_by_payment.items():
            for _, s in scored:
                contenders.setdefault(s.settlement_id, set()).add(pid)

        results: Dict[str, M2Decision] = {}
        for p in payments:
            pid = p.payment_id
            scored = candidates_by_payment[pid]

            if not scored:
                expl = "Missing: no directly-referenced or amount/date-plausible settlement candidate found."
                self.audit_log.log_event(
                    record_id=pid,
                    stage="M2_DETERMINISTIC",
                    rule_id="RULE_M2_MISSING_SETTLEMENT",
                    decision=ReconciliationStatus.MISSING,
                    candidate_ids=[],
                    relevant_input_values={"payment_amount": str(p.amount)},
                    explanation=expl,
                )
                results[pid] = (ReconciliationStatus.MISSING, None, expl, None)
                continue

            # Ambiguous if: this payment itself has 2+ indistinguishable
            # candidates, OR any of its candidate settlements is contested
            # by another payment in this same bucket.
            own_ambiguous = len(scored) >= 2 and (scored[1][0] - scored[0][0]) <= tol
            contested_settlement_ids = [
                s.settlement_id for _, s in scored if len(contenders[s.settlement_id]) >= 2
            ]

            if own_ambiguous or contested_settlement_ids:
                cand_ids = sorted({s.settlement_id for _, s in scored})
                self.audit_log.increment_fact("N_AMBIGUOUS_CASES")
                expl = (
                    f"Ambiguous: settlement candidate(s) {cand_ids} cannot be safely assigned - "
                    f"{'multiple equally-plausible candidates for this payment' if own_ambiguous else 'contested by another payment with an equal claim'}, "
                    f"and no reference evidence exists to arbitrate."
                )
                self.audit_log.log_event(
                    record_id=pid,
                    stage="M2_DETERMINISTIC",
                    rule_id="RULE_M2_AMBIGUOUS_CANDIDATES",
                    decision=ReconciliationStatus.AMBIGUOUS,
                    candidate_ids=cand_ids,
                    relevant_input_values={
                        "candidate_count": len(cand_ids),
                        "cross_payment_contention": bool(contested_settlement_ids),
                    },
                    explanation=expl,
                )
                results[pid] = (ReconciliationStatus.AMBIGUOUS, None, expl, None)
                continue

            # Exactly one weak, reference-less, uncontested candidate.
            # Amount/date proximity alone is still not identity proof.
            top_id = scored[0][1].settlement_id
            expl = (
                f"Unresolved: only weak, reference-less evidence available (closest candidate "
                f"{top_id}); insufficient to safely classify as MATCH."
            )
            self.audit_log.log_event(
                record_id=pid,
                stage="M2_DETERMINISTIC",
                rule_id="RULE_M2_WEAK_EVIDENCE_UNRESOLVED",
                decision=ReconciliationStatus.UNRESOLVED,
                candidate_ids=[top_id],
                relevant_input_values={"payment_amount": str(p.amount)},
                explanation=expl,
            )
            results[pid] = (ReconciliationStatus.UNRESOLVED, None, expl, None)

        return results
