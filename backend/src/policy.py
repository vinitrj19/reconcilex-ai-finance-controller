"""
M6 - Global Reconciliation Policy Layer.

M6 does NOT match anything. It takes:

    M1 exact-match decisions
    M2 deterministic decisions
    M3 candidate pairs
    M4 candidate scores
    M5 AI recommendations (optional - bounded reasoning only)

and turns them into one globally consistent final decision per payment,
enforcing invariants that no single earlier stage can see on its own
(most importantly: one settlement can never end up finally owned by more
than one payment).

M6 has final authority (spec section 10 / M6 prompt item 4). It never
trusts an earlier stage's self-validation blindly - in particular it
independently re-checks every M5 AI recommendation rather than assuming
M5's own pydantic/threshold checks were sufficient, because M5 output is
a *recommendation*, not a financial decision.

Design overview
----------------
Pass 1 - lock in every already-final decision unchanged:
    - M1 MATCH (identity-proven exact match)
    - M2 PROTECTED_STATUSES: MATCH, PARTIAL_MATCH, CONFLICT, REFUND,
      DUPLICATE, MISSING
  These are never touched by M6, per the deterministic-protection
  requirement. Their settlement ownership (if any) is recorded so later
  passes can never assign the same settlement to someone else.

Pass 2 - for every remaining (AMBIGUOUS / UNRESOLVED) payment, gather at
  most one *proposal* (a candidate settlement + score) from M4 (if it
  independently accepted a candidate) or, failing that, from M5 (if
  available and its output survives M6's own validation).

Pass 3 - drop any proposal that targets a settlement a protected/
  deterministic decision already owns.

Pass 4 - group the surviving proposals by settlement and resolve
  collisions deterministically (see ``resolve_collision``). A proposal
  only becomes a final MATCH when it is the sole, validated claim on its
  settlement, or it clearly beats every other claim by at least
  ``M6PolicyConfig.collision_margin``. Otherwise every claimant on that
  settlement is routed to review - ambiguity is preserved, never guessed
  away.

Pass 5 - anything left over (no candidates, rejected AI output, M5
  unavailable, lost a collision) keeps its original M2 status, unchanged.

Every pass writes to the repository's existing ``AuditLog`` (see
``src.audit``) - there is no second, disconnected audit system.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.audit import AuditLog
from src.candidates import CandidateRecord
from src.deterministic import M2Decision, ReconciliationStatus
from src.models import NormalizedPayment, NormalizedSettlement
from src.scoring import M4Scorer

# ---------------------------------------------------------------------------
# Status taxonomy used by M6 itself
# ---------------------------------------------------------------------------

# Statuses M6 must never override, per spec item 2 / 9. A protected
# decision's settlement ownership (if any) is authoritative and final.
PROTECTED_STATUSES = frozenset({
    ReconciliationStatus.MATCH,
    ReconciliationStatus.PARTIAL_MATCH,
    ReconciliationStatus.CONFLICT,
    ReconciliationStatus.REFUND,
    ReconciliationStatus.DUPLICATE,
    ReconciliationStatus.MISSING,
})

# Statuses M6 is actually allowed to try to resolve into a global MATCH,
# or otherwise leave as a safe review outcome.
RESOLVABLE_STATUSES = frozenset({
    ReconciliationStatus.AMBIGUOUS,
    ReconciliationStatus.UNRESOLVED,
})


# ---------------------------------------------------------------------------
# Configuration - explicit, versioned, no magic numbers buried in code
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class M6PolicyConfig:
    """
    ai_min_confidence
        M6's own floor for treating an AI MATCH recommendation as usable
        evidence. Deliberately mirrors the floor M5 already enforces
        internally (src.m5_reasoning: confidence < 0.80 is rejected) -
        M6 re-checks it independently rather than trusting M5's
        self-validation, per the "M6 has final authority" requirement.

    collision_margin
        The score gap required between the top and second claim on a
        contested settlement before M6 will pick a winner instead of
        routing everyone to review. Reuses M4's *existing* locked
        ``minimum_margin`` semantics (see ``from_m4_scorer``) rather than
        inventing a second, competing threshold system.
    """
    ai_min_confidence: float = 0.80
    collision_margin: float = 0.10
    policy_version: str = "v1.0.0-M6-DEV"

    @classmethod
    def from_m4_scorer(cls, scorer: M4Scorer, **overrides) -> "M6PolicyConfig":
        base: Dict[str, Any] = dict(collision_margin=scorer.margin)
        base.update(overrides)
        return cls(**base)

    @classmethod
    def from_file(cls, path: str) -> "M6PolicyConfig":
        with open(path, "r") as f:
            data = json.load(f)
        return cls(
            ai_min_confidence=float(data["ai_min_confidence"]),
            collision_margin=float(data["collision_margin"]),
            policy_version=str(data.get("policy_version", "unknown")),
        )


# ---------------------------------------------------------------------------
# Output record
# ---------------------------------------------------------------------------

@dataclass
class M6Decision:
    payment_id: str
    settlement_id: Optional[str]
    status: str
    confidence: Optional[float]
    decision_source: str  # "M1_EXACT_MATCH" | "M2_DETERMINISTIC" | "M6_GLOBAL_POLICY"
    reason: str

    def to_dict(self) -> dict:
        return {
            "payment_id": self.payment_id,
            "settlement_id": self.settlement_id,
            "status": self.status,
            "confidence": self.confidence,
            "decision_source": self.decision_source,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _Proposal:
    payment_id: str
    settlement_id: str
    score: float
    source: str  # "M4_SCORING" | "M5_AI"


@dataclass(frozen=True)
class _PaymentView:
    """Minimal duck-typed view M4Scorer.evaluate_payment / M5's
    evaluate_payment both already consume (see scripts/verify_foundation.py
    ``_PaymentView`` and tests/test_scoring.py ``MockPaymentRecord`` -
    same shape, reused here rather than inventing a third one)."""
    payment_id: str
    amount: Decimal
    candidates: List[CandidateRecord]


# ---------------------------------------------------------------------------
# Small, independently-testable policy functions
# ---------------------------------------------------------------------------

def is_protected_status(status: str) -> bool:
    """True for any M2 status M6 must pass through unchanged."""
    return status in PROTECTED_STATUSES


def is_eligible_owner(status: str, duplicate_of: Optional[str]) -> bool:
    """A payment may become a global settlement owner only if its status
    is one M6 is actually allowed to resolve, and it is not itself a
    duplicate. This is a *defensive* re-statement of the same rule
    ``is_protected_status`` already enforces one layer up - kept as its
    own function so it has its own test and callers never need to
    reason about protection and duplication as two separate checks."""
    if duplicate_of is not None:
        return False
    return status in RESOLVABLE_STATUSES


def validate_ai_recommendation(
    decision: Any,
    known_candidate_ids: List[str],
    config: M6PolicyConfig,
) -> Tuple[bool, str]:
    """Independent M6-side re-validation of an M5 ``AIDecision``-shaped
    object (duck-typed: ``.decision`` / ``.selected_candidate_id`` /
    ``.confidence``). M6 never treats M5's own schema/threshold checks as
    sufficient on their own - an AI recommendation only becomes usable
    evidence once it survives this second, independent check.

    Returns (is_valid, reason_code). ``decision`` may be ``None`` (M5
    provider failure, schema validation failure, or M5 unavailable) - that
    is always rejected, never crashes the caller.
    """
    if decision is None:
        return False, "AI_NO_DECISION"

    ai_decision = getattr(decision, "decision", None)
    if ai_decision != "MATCH":
        return False, f"AI_NOT_A_MATCH_RECOMMENDATION:{ai_decision!r}"

    candidate_id = getattr(decision, "selected_candidate_id", None)
    if not candidate_id:
        return False, "AI_MATCH_WITH_NULL_CANDIDATE"
    if candidate_id not in known_candidate_ids:
        return False, f"AI_INVALID_CANDIDATE:{candidate_id!r}"

    confidence = getattr(decision, "confidence", None)
    if confidence is None or confidence < config.ai_min_confidence:
        return False, f"AI_LOW_CONFIDENCE:{confidence!r}"

    return True, "AI_RECOMMENDATION_VALID"


def resolve_collision(
    claims: List[Tuple[str, float]],
    margin: float,
) -> Tuple[Optional[str], str]:
    """Deterministic, explainable, order-independent global collision
    resolution for a single contested settlement.

    ``claims`` is a list of (payment_id, score) pairs. Ranking is by
    (score desc, payment_id asc) - payment_id is a stable identifier
    drawn from the data itself, never CSV/dict/insertion order, so the
    result is identical no matter what order ``claims`` arrives in
    (verified in tests by feeding the same claims in different orders).

    A winner is returned only when:
      - there is exactly one claim, or
      - the top score beats the runner-up by at least ``margin``.

    Otherwise (score gap too small) no winner is returned - the caller
    must route every claimant to review rather than pick one arbitrarily.
    """
    if not claims:
        return None, "NO_CLAIMS"

    ranked = sorted(claims, key=lambda c: (-c[1], c[0]))
    if len(ranked) == 1:
        return ranked[0][0], "SOLE_CLAIMANT"

    top_pid, top_score = ranked[0]
    _, second_score = ranked[1]
    if (top_score - second_score) >= margin:
        return top_pid, "CLEAR_WINNER"
    return None, "INSUFFICIENT_MARGIN"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_m6_global_policy(
    payments: List[NormalizedPayment],
    m1_matched: Dict[str, NormalizedSettlement],
    m2_results: Dict[str, M2Decision],
    m3_candidates: Dict[str, List[CandidateRecord]],
    m4_scorer: Any,
    m5_engine: Optional[Any],
    audit_log: AuditLog,
    config: Optional[M6PolicyConfig] = None,
) -> Dict[str, M6Decision]:
    """Produce one final, globally-consistent ``M6Decision`` per payment.

    ``m4_scorer`` must expose ``evaluate_payment(payment_view) -> dict``
    with the same contract as ``src.scoring.M4Scorer`` (status
    ACCEPT/REVIEW_REQUIRED/NO_CANDIDATE, ``top``/``margin`` on ACCEPT).

    ``m5_engine`` must expose ``evaluate_payment(payment_view, m2_status,
    m4_status) -> dict`` with the same contract as
    ``src.m5_reasoning.M5ReasoningEngine``, or be ``None`` - M5 is
    optional bounded reasoning, not a required stage. When it is
    unavailable, M6 safely preserves the residual status instead of
    guessing (this is what happens in this environment, where the
    ``pydantic`` dependency real M5 needs is not installed - see
    scripts/run_m6.py).

    Pure/idempotent: given the same inputs and a fresh ``AuditLog``, two
    calls produce field-for-field identical ``M6Decision`` output (see
    tests/test_m6_policy.py::test_idempotent_across_runs).
    """
    config = config or M6PolicyConfig()
    payment_by_id = {p.payment_id: p for p in payments}

    final: Dict[str, M6Decision] = {}
    owned_settlements: Dict[str, str] = {}

    # ---- Pass 1: lock in every already-final decision verbatim --------
    for pid in sorted(payment_by_id):
        if pid in m1_matched:
            sid = m1_matched[pid].settlement_id
            final[pid] = M6Decision(
                pid, sid, ReconciliationStatus.MATCH, None,
                "M1_EXACT_MATCH", "Strong identity match locked in by M1; not revisited by M6.",
            )
            owned_settlements[sid] = pid
            continue

        status, sid, expl, dupof = m2_results[pid]
        if is_protected_status(status):
            final[pid] = M6Decision(pid, sid, status, None, "M2_DETERMINISTIC", expl)
            if sid:
                prior_owner = owned_settlements.get(sid)
                if prior_owner is not None and prior_owner != pid:
                    # Should be structurally impossible given M1/M2's own
                    # invariants - surfaced loudly rather than silently
                    # "fixed", because a protected decision is never
                    # overridden by M6 even to resolve a collision.
                    audit_log.log_event(
                        record_id=pid, stage="M6_GLOBAL_POLICY",
                        rule_id="RULE_M6_SETTLEMENT_OWNERSHIP_CONFLICT",
                        decision="SETTLEMENT_OWNERSHIP_CONFLICT",
                        candidate_ids=[sid],
                        relevant_input_values={"other_owner": prior_owner},
                        explanation=(
                            f"Protected decision for {pid} claims settlement {sid}, already "
                            f"owned by protected decision {prior_owner}. M6 does not override "
                            f"either - this indicates an upstream (M1/M2) defect."
                        ),
                    )
                else:
                    owned_settlements[sid] = pid

    # ---- Pass 2: gather at most one proposal per remaining payment ----
    proposals: Dict[str, _Proposal] = {}
    for pid in sorted(payment_by_id):
        if pid in final:
            continue
        p = payment_by_id[pid]
        status, sid0, expl, dupof = m2_results[pid]

        if not is_eligible_owner(status, dupof):
            # Defensive: pass 1 should already have removed every
            # protected/duplicate payment. Never silently drop a payment -
            # if this ever fires it is still finalized safely here.
            final[pid] = M6Decision(pid, sid0, status, None, "M2_DETERMINISTIC", expl)
            continue

        candidates = m3_candidates.get(pid, [])
        candidate_ids = [c.settlement_id for c in candidates]

        if not candidates:
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_NO_CANDIDATES",
                decision=status, candidate_ids=[],
                relevant_input_values={"m2_status": status},
                explanation="No M3 candidates available; M6 preserves the M2 status unchanged.",
            )
            continue

        view = _PaymentView(pid, p.amount, candidates)
        m4_result = m4_scorer.evaluate_payment(view)

        if m4_result.get("status") == "ACCEPT":
            top = m4_result["top"]
            proposals[pid] = _Proposal(
                pid, top["candidate"].settlement_id, float(top["score"]), "M4_SCORING",
            )
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_M4_PROPOSAL",
                decision="PROPOSAL_FROM_M4", candidate_ids=[top["candidate"].settlement_id],
                relevant_input_values={"score": top["score"], "margin": m4_result.get("margin")},
                explanation="M4 score cleared its locked acceptance threshold and margin; proposed as global candidate owner (not yet final).",
            )
            continue

        if m5_engine is None:
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_M5_UNAVAILABLE",
                decision=status, candidate_ids=candidate_ids,
                relevant_input_values={"m4_status": m4_result.get("status")},
                explanation="M5 AI reasoning unavailable; M6 safely preserves the residual status rather than guessing.",
            )
            continue

        m5_result = m5_engine.evaluate_payment(view, m2_status=status, m4_status=m4_result.get("status"))
        ai_decision = m5_result.get("decision")
        ok, why = validate_ai_recommendation(ai_decision, candidate_ids, config)

        if not ok:
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_AI_RECOMMENDATION_REJECTED",
                decision="AI_RECOMMENDATION_REJECTED", candidate_ids=candidate_ids,
                relevant_input_values={"m5_status": m5_result.get("status"), "reason": why},
                explanation=f"M5 output did not pass M6's independent validation ({why}); status preserved.",
            )
            continue

        proposals[pid] = _Proposal(
            pid, ai_decision.selected_candidate_id, float(ai_decision.confidence), "M5_AI",
        )
        audit_log.log_event(
            record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_AI_PROPOSAL_ACCEPTED",
            decision="PROPOSAL_FROM_M5", candidate_ids=[ai_decision.selected_candidate_id],
            relevant_input_values={"confidence": ai_decision.confidence},
            explanation="M5 AI recommendation passed M6's independent validation; proposed as global candidate owner (not yet final).",
        )

    # ---- Pass 3: drop proposals targeting an already-owned settlement -
    live_proposals: Dict[str, _Proposal] = {}
    for pid in sorted(proposals):
        prop = proposals[pid]
        prior_owner = owned_settlements.get(prop.settlement_id)
        if prior_owner is not None:
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_SETTLEMENT_ALREADY_OWNED",
                decision="AI_RECOMMENDATION_REJECTED", candidate_ids=[prop.settlement_id],
                relevant_input_values={"owner": prior_owner, "source": prop.source},
                explanation=(
                    f"Proposed settlement {prop.settlement_id} is already owned by protected/"
                    f"deterministic decision {prior_owner}; proposal rejected, status preserved."
                ),
            )
            continue
        live_proposals[pid] = prop

    # ---- Pass 4: resolve collisions per contested settlement ----------
    by_settlement: Dict[str, List[_Proposal]] = {}
    for pid in sorted(live_proposals):
        prop = live_proposals[pid]
        by_settlement.setdefault(prop.settlement_id, []).append(prop)

    for sid in sorted(by_settlement):
        props = by_settlement[sid]
        by_pid = {pr.payment_id: pr for pr in props}
        claims = [(pr.payment_id, pr.score) for pr in props]
        winner_pid, reason_code = resolve_collision(claims, config.collision_margin)

        if winner_pid is not None:
            winning_prop = by_pid[winner_pid]
            final[winner_pid] = M6Decision(
                winner_pid, sid, ReconciliationStatus.MATCH, winning_prop.score,
                "M6_GLOBAL_POLICY",
                f"Global policy assigned settlement {sid} "
                f"({winning_prop.source}, score={winning_prop.score:.3f}, {reason_code}).",
            )
            owned_settlements[sid] = winner_pid
            rule_id = "RULE_M6_SETTLEMENT_ASSIGNED" if reason_code == "SOLE_CLAIMANT" else "RULE_M6_GLOBAL_COLLISION_RESOLVED"
            decision_label = "SETTLEMENT_ASSIGNED" if reason_code == "SOLE_CLAIMANT" else "GLOBAL_COLLISION_RESOLVED"
            audit_log.log_event(
                record_id=winner_pid, stage="M6_GLOBAL_POLICY", rule_id=rule_id,
                decision=decision_label, candidate_ids=[sid],
                relevant_input_values={
                    "score": winning_prop.score,
                    "source": winning_prop.source,
                    "competing_payments": sorted(by_pid.keys()),
                },
                explanation="Validated global claim on this settlement; assigned as final MATCH.",
            )

            for pid in sorted(by_pid):
                if pid == winner_pid:
                    continue
                loser_prop = by_pid[pid]
                orig_status, _, _, _ = m2_results[pid]
                final[pid] = M6Decision(
                    pid, None, orig_status, loser_prop.score, "M6_GLOBAL_POLICY",
                    f"Lost global collision for settlement {sid} to {winner_pid}; "
                    f"original status ({orig_status}) preserved as the review outcome.",
                )
                audit_log.log_event(
                    record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_GLOBAL_COLLISION_LOST",
                    decision="SETTLEMENT_OWNERSHIP_CONFLICT", candidate_ids=[sid],
                    relevant_input_values={"winner": winner_pid, "score": loser_prop.score},
                    explanation="Did not clear the collision margin against the winning claim; routed to review.",
                )
            continue

        # No clear winner - every claimant on this settlement stays in
        # review. Ambiguity is preserved, never fabricated into a match.
        for pid in sorted(by_pid):
            prop = by_pid[pid]
            orig_status, _, _, _ = m2_results[pid]
            review_status = orig_status if orig_status in RESOLVABLE_STATUSES else ReconciliationStatus.AMBIGUOUS
            final[pid] = M6Decision(
                pid, None, review_status, prop.score, "M6_GLOBAL_POLICY",
                f"Global collision on settlement {sid} had no sufficiently clear winner "
                f"(required margin {config.collision_margin}); remains {review_status}.",
            )
            audit_log.log_event(
                record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_GLOBAL_COLLISION_REVIEW",
                decision="GLOBAL_COLLISION_REVIEW", candidate_ids=[sid],
                relevant_input_values={"competing_payments": sorted(by_pid.keys())},
                explanation="No claim exceeded the required margin over its closest competitor; genuine ambiguity preserved.",
            )

    # ---- Pass 5: anything still unresolved keeps its M2 status --------
    for pid in sorted(payment_by_id):
        if pid in final:
            continue
        status, sid, expl, dupof = m2_results[pid]
        final[pid] = M6Decision(pid, sid, status, None, "M2_DETERMINISTIC", expl)
        audit_log.log_event(
            record_id=pid, stage="M6_GLOBAL_POLICY", rule_id="RULE_M6_PROTECTED_STATUS_PRESERVED",
            decision="PROTECTED_STATUS_PRESERVED", candidate_ids=[],
            relevant_input_values={"status": status},
            explanation="No safe global resolution found; original status preserved unchanged.",
        )

    return final
