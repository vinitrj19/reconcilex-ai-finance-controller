"""
M5 - bounded AI reasoning over residual (UNRESOLVED/AMBIGUOUS) payments.

External contract is unchanged from M8 (``M5ReasoningEngine(provider,
audit_log).evaluate_payment(payment_record, m2_status, m4_status) -> dict``)
so M6 (src/policy.py) and the existing M8 test suite (tests/test_m5_
reasoning.py) did not need to change for this fix - only *what provider is
injected* and *how much legitimate evidence the provider receives*
changed. See M9_CHANGELOG.md for the M8 defect this replaces.

Evidence-assembly principle (M9 section 3): the provider receives payment
and candidate evidence that M1-M4 already computed deterministically -
amounts, date gaps, reference-match signals - and nothing else. It never
receives labels reserved for scoring (the expected status/pairs/category a
record belongs to, or anything from the evaluation-only dataset split).
See tests/test_m5_integration.py for the dedicated leakage checks.
"""

import datetime
from typing import Any, List

from pydantic import ValidationError

from src.m5_provider import ReasoningProvider
from src.m5_schema import AIDecision

# M2 statuses M5 must never be asked to reason over - they are already
# final, protected decisions (mirrors src.policy.PROTECTED_STATUSES; kept
# as its own literal here, not an import, so M5 has no dependency on M6 -
# M5 must be usable/testable standalone).
_M2_PROTECTED_STATUSES = frozenset({
    "MATCH", "PARTIAL_MATCH", "CONFLICT", "REFUND", "DUPLICATE", "MISSING",
})


def _candidate_evidence(candidate: Any) -> dict:
    """Duck-typed extraction of whatever evidence a candidate object
    exposes. Works with the real ``src.candidates.CandidateRecord`` (which
    carries amount_difference/date_difference/matched_reference_fields/
    evidence) and degrades gracefully for lightweight test stubs that only
    define ``settlement_id`` (see tests/test_m5_reasoning.py) - a fixed
    contract test would otherwise force every existing M8 test to change
    for an M9 change that has nothing to do with them."""
    entry = {"settlement_id": candidate.settlement_id}
    amount_difference = getattr(candidate, "amount_difference", None)
    if amount_difference is not None:
        entry["amount_difference"] = str(amount_difference)
    date_difference = getattr(candidate, "date_difference", None)
    if date_difference is not None:
        entry["date_difference_days"] = date_difference
    matched_reference_fields = getattr(candidate, "matched_reference_fields", None)
    if matched_reference_fields:
        entry["matched_reference_fields"] = list(matched_reference_fields)
    extra_evidence = getattr(candidate, "evidence", None)
    if extra_evidence:
        # Already-deterministic, already-computed evidence (M3's own
        # audit fields) - never anything derived from ground truth.
        entry["deterministic_evidence"] = dict(extra_evidence)
    return entry


def _missing_evidence_hints(candidate_entries: List[dict]) -> List[str]:
    """Cheap, deterministic hints about what evidence is thin - purely a
    convenience for the AI prompt, computed from already-visible candidate
    evidence, never from anything the AI shouldn't see."""
    hints: List[str] = []
    if not candidate_entries:
        hints.append("no_candidates_available")
        return hints
    if not any(c.get("matched_reference_fields") for c in candidate_entries):
        hints.append("no_candidate_has_a_reference_id_match")
    if len(candidate_entries) > 1:
        hints.append("multiple_plausible_candidates")
    return hints


class M5ReasoningEngine:
    def __init__(self, provider: ReasoningProvider, audit_log: list):
        self.provider = provider
        self.audit_log = audit_log

    def evaluate_payment(self, payment_record, m2_status: str, m4_status: str) -> dict:
        # 1. Strict boundary: never reason over an already-protected M2
        #    decision (spec section 8 / "AI should NOT be called for
        #    already deterministic MATCH/PARTIAL_MATCH/REFUND/DUPLICATE").
        if m2_status in _M2_PROTECTED_STATUSES:
            return {"status": "SKIPPED", "reason": "M2_DETERMINISTIC"}

        # 2. Strict boundary: never reason when M4 already accepted a
        #    candidate deterministically, or when there is genuinely
        #    nothing to reason about.
        if m4_status == "ACCEPT":
            return {"status": "SKIPPED", "reason": "M4_ACCEPTED"}
        candidates = getattr(payment_record, "candidates", [])
        if m4_status == "NO_CANDIDATE" or not candidates:
            return {"status": "SKIPPED", "reason": "NO_CANDIDATE"}

        # 3. Assemble bounded, leakage-free evidence. Only fields already
        #    computed deterministically by M1-M4 are included - see the
        #    module docstring and the dedicated leakage test.
        candidate_entries = [_candidate_evidence(c) for c in candidates]
        evidence_payload = {
            "payment_id": payment_record.payment_id,
            "amount": float(payment_record.amount),
            "m2_status": m2_status,
            "m4_status": m4_status,
            "candidates": candidate_entries,
            "candidate_ids": [c["settlement_id"] for c in candidate_entries],
            "missing_evidence_hints": _missing_evidence_hints(candidate_entries),
        }
        candidate_ids = evidence_payload["candidate_ids"]

        audit_entry = {
            "payment_id": payment_record.payment_id,
            "candidate_ids_considered": candidate_ids,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "provider_identifier": self.provider.__class__.__name__,
            "evidence_sent": evidence_payload,
        }

        # 4. Invoke AI and safely handle every failure mode uniformly.
        try:
            decision: AIDecision = self.provider.reason(evidence_payload)

            # 5. Post-validation: hallucination & confidence checks. This
            #    is M5's OWN floor; M6 independently re-checks confidence
            #    and candidate membership again before ever treating this
            #    as usable evidence (src.policy.validate_ai_recommendation)
            #    - M5's self-validation is never trusted as sufficient on
            #    its own.
            if decision.decision == "MATCH":
                if decision.selected_candidate_id not in candidate_ids:
                    raise ValueError(f"Hallucinated ID: {decision.selected_candidate_id}")
                if decision.confidence < 0.80:
                    raise ValueError(f"Confidence too low: {decision.confidence}")

            audit_entry.update({
                "structured_decision": decision.model_dump(),
                "confidence": decision.confidence,
                "status": "SUCCESS",
            })
            self.audit_log.append(audit_entry)

            return {"status": decision.recommended_action, "decision": decision}

        except ValidationError:
            audit_entry.update({"status": "VALIDATION_FAILED", "escalation_reason": "Pydantic Schema Error"})
            self.audit_log.append(audit_entry)
            return {"status": "ESCALATE", "reason": "VALIDATION_FAILED"}

        except Exception as e:
            audit_entry.update({"status": "PROVIDER_FAILED", "escalation_reason": str(e)})
            self.audit_log.append(audit_entry)
            return {"status": "ESCALATE", "reason": "PROVIDER_FAILED"}
