"""
M6 DEV runner and validator.

Executes the full pipeline (M1 -> M2 -> M3 -> M4 -> M5(if available) -> M6)
against data/dev/ only, then verifies every invariant the M6 milestone
requires: physical row integrity, one-settlement-one-owner, duplicate
ownership, ambiguity preservation, row-order independence, and
idempotency. Writes data/dev/m6_final.json and audit_log_m6.jsonl.

HOLDOUT IS NEVER ACCESSED. This script only ever opens files under
data/dev/ and ground_truth/dev/, and does not read the latter either
(dev ground truth is for a separate scoring step, not for M6 itself).
"""
import importlib
import json
import random
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit import AuditLog
from src.candidates import CandidateConfig, generate_candidates
from src.config import ReconciliationConfig
from src.deterministic import DeterministicReconciliationEngine, ReconciliationStatus
from src.matching import run_stage1_exact_matching
from src.normalization import load_orders, load_payments, load_settlements, resolve_references
from src.policy import M6PolicyConfig, run_m6_global_policy
from src.scoring import M4Scorer

DEV = ROOT / "data" / "dev"


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def try_load_m5_engine():
    """M9 fix (see M9_CHANGELOG.md): this used to hardcode
    ``m5_provider.MockProvider()`` with no response configured, which made
    every M5 call fail internally (M8 defect - see M9_CHANGELOG.md for the
    full root-cause writeup). It now asks ``src.m5_provider.build_provider()``
    for a real, dependency-injected provider based on environment
    configuration (AI_PROVIDER / AI_API_KEY / AI_MODEL).

    If pydantic itself is unavailable, or no real provider is configured
    (no AI_API_KEY - the case in this sandbox), this returns
    ``(None, reason)`` exactly as before: M6 runs with m5_engine=None and
    safely preserves residual statuses instead of guessing (see
    src/policy.py's M5-unavailable path). The difference from M8 is that
    "unavailable" now means "unavailable", not "wired to a provider that
    is silently guaranteed to fail on every call"."""
    try:
        m5_provider = importlib.import_module("src.m5_provider")
        m5_reasoning = importlib.import_module("src.m5_reasoning")
    except ModuleNotFoundError as e:
        return None, f"M5 modules unavailable: {e}"

    provider = m5_provider.build_provider()
    if provider is None:
        return None, (
            "no AI provider configured (set AI_PROVIDER=anthropic and AI_API_KEY "
            "to enable live inference); M5 skipped, residual statuses preserved safely"
        )
    return m5_reasoning.M5ReasoningEngine(provider=provider, audit_log=[]), None


def run_pipeline(payments, settlements, orders, m5_engine):
    """One full M1->M6 pass. Returns (final_decisions, audit_log)."""
    audit = AuditLog()
    resolve_references(payments, orders, audit)
    config = ReconciliationConfig()

    m1_matched, unmatched = run_stage1_exact_matching(payments, settlements, config, audit)
    engine = DeterministicReconciliationEngine(config, audit)
    m2_results = engine.reconcile_unmatched(
        payments, unmatched, settlements, {s.settlement_id for s in m1_matched.values()}, orders,
    )

    claimed = {s.settlement_id for s in m1_matched.values()}
    residual_ids = set()
    for pid, (status, sid, expl, dupof) in m2_results.items():
        if sid:
            claimed.add(sid)
        if status in (ReconciliationStatus.MISSING, ReconciliationStatus.AMBIGUOUS, ReconciliationStatus.UNRESOLVED):
            residual_ids.add(pid)

    cand_cfg = CandidateConfig.from_reconciliation_config(config)
    m3_candidates = generate_candidates(payments, settlements, orders, residual_ids, claimed, cand_cfg, audit)

    m4_scorer = M4Scorer(config_path=str(ROOT / "config" / "m4_thresholds.json"))
    m6_config = M6PolicyConfig.from_m4_scorer(m4_scorer)

    final = run_m6_global_policy(
        payments, m1_matched, m2_results, m3_candidates, m4_scorer, m5_engine, audit, m6_config,
    )
    return final, audit


def main():
    # -----------------------------------------------------------------
    section("0. Holdout access check")
    holdout_paths = list(ROOT.rglob("*holdout*"))
    print("Paths matching '*holdout*' under repo root:", holdout_paths or "NONE FOUND (HOLDOUT WAS NOT ACCESSED)")

    # -----------------------------------------------------------------
    section("1. Load DEV data + M5 availability")
    base_payments = load_payments(str(DEV / "payments.csv"), AuditLog())
    base_settlements = load_settlements(str(DEV / "settlements.csv"), AuditLog())
    base_orders = load_orders(str(DEV / "orders.csv"), AuditLog())
    print(f"  payments={len(base_payments)} settlements={len(base_settlements)} orders={len(base_orders)}")

    m5_engine, m5_error = try_load_m5_engine()
    if m5_engine is None:
        print(f"  M5 unavailable in this environment: {m5_error}")
        print("  M6 will run with m5_engine=None (safe preservation, no guessing).")
    else:
        print("  M5 available - real M5ReasoningEngine wired in.")

    # -----------------------------------------------------------------
    section("2. Full M1-M6 pipeline (base row order)")
    final, audit = run_pipeline(list(base_payments), list(base_settlements), list(base_orders), m5_engine)

    n_input = len(base_payments)
    n_decisions = len(final)
    unique_pids = len({p.payment_id for p in base_payments})
    print(f"  input payment rows : {n_input}")
    print(f"  final decisions     : {n_decisions}")
    print(f"  unique payment IDs  : {unique_pids}")
    assert n_input == n_decisions == unique_pids == 129, "physical row integrity FAILED"
    print("  PASS: 129 -> 129, all unique")

    status_counts = Counter(d.status for d in final.values())
    print("  final status distribution:", dict(sorted(status_counts.items())))

    source_counts = Counter(d.decision_source for d in final.values())
    print("  decision source distribution:", dict(sorted(source_counts.items())))

    # -----------------------------------------------------------------
    section("3. One-settlement-one-owner invariant")
    sid_owners = Counter(d.settlement_id for d in final.values() if d.settlement_id)
    collisions = {k: v for k, v in sid_owners.items() if v > 1}
    print("  settlements with >1 final owner:", collisions or "NONE")
    assert not collisions, "settlement double-ownership FAILED"
    print(f"  PASS: 0 settlement IDs with >1 final owner ({len(sid_owners)} settlements owned total)")

    # -----------------------------------------------------------------
    section("4. Duplicate-ownership invariant")
    dup_owners = [d for d in final.values() if d.status == ReconciliationStatus.DUPLICATE and d.settlement_id]
    n_dupes = sum(1 for d in final.values() if d.status == ReconciliationStatus.DUPLICATE)
    print(f"  duplicate payments: {n_dupes}")
    print("  duplicates owning a settlement:", dup_owners or "NONE")
    assert not dup_owners, "duplicate ownership invariant FAILED"
    print(f"  PASS: {n_dupes} duplicate relationships preserved, 0 own a settlement")

    # -----------------------------------------------------------------
    section("5. Protected statuses never overridden")
    from src.policy import PROTECTED_STATUSES
    bad_overrides = [
        d.payment_id for d in final.values()
        if d.status in PROTECTED_STATUSES and d.decision_source not in ("M1_EXACT_MATCH", "M2_DETERMINISTIC")
    ]
    print("  protected-status decisions not sourced from M1/M2:", bad_overrides or "NONE")
    assert not bad_overrides, "a protected status was produced by M6 itself instead of being passed through"
    print("  PASS: every protected-status decision is a verbatim M1/M2 pass-through")

    # -----------------------------------------------------------------
    section("6. Ambiguous cases preserved (not fabricated into matches)")
    n_ambiguous = sum(1 for d in final.values() if d.status == ReconciliationStatus.AMBIGUOUS)
    n_review = sum(1 for d in final.values() if d.status == ReconciliationStatus.UNRESOLVED)
    print(f"  final AMBIGUOUS : {n_ambiguous}")
    print(f"  final UNRESOLVED: {n_review}")

    # -----------------------------------------------------------------
    section("7. Determinism / row-order independence (full pipeline)")
    random.seed(4242)
    base_decisions = {pid: d.to_dict() for pid, d in final.items()}
    all_same = True
    for trial in range(5):
        p2 = list(base_payments); random.shuffle(p2)
        s2 = list(base_settlements); random.shuffle(s2)
        o2 = list(base_orders); random.shuffle(o2)
        m5_trial, _ = try_load_m5_engine()
        d2, _ = run_pipeline(p2, s2, o2, m5_trial)
        d2_dicts = {pid: d.to_dict() for pid, d in d2.items()}
        same = d2_dicts == base_decisions
        all_same = all_same and same
        print(f"  trial {trial}: identical to base ordering = {same}")
    assert all_same, "M1-M6 pipeline is NOT order-independent"
    print("  PASS: identical final decisions across 5 random row orderings")

    # -----------------------------------------------------------------
    section("8. Idempotency (M6 run twice on the same M1-M5 outputs)")
    m5_a, _ = try_load_m5_engine()
    final_a, audit_a = run_pipeline(list(base_payments), list(base_settlements), list(base_orders), m5_a)
    m5_b, _ = try_load_m5_engine()
    final_b, audit_b = run_pipeline(list(base_payments), list(base_settlements), list(base_orders), m5_b)
    a_dicts = {pid: d.to_dict() for pid, d in final_a.items()}
    b_dicts = {pid: d.to_dict() for pid, d in final_b.items()}
    idempotent = a_dicts == b_dicts
    print(f"  identical decisions across two independent full runs: {idempotent}")
    print(f"  audit event count run A: {len(audit_a.events)}  run B: {len(audit_b.events)}")
    assert idempotent, "M6 is NOT idempotent"
    print("  PASS: M6(input) == M6(input)")

    # -----------------------------------------------------------------
    section("9. Decimal precision spot-check")
    all_decimal = all(isinstance(p.amount, Decimal) for p in base_payments)
    all_decimal &= all(isinstance(s.net_amount, Decimal) for s in base_settlements)
    print("  all payment/settlement monetary fields remain Decimal:", all_decimal)
    assert all_decimal, "Decimal precision FAILED"
    scores_are_float = all(
        isinstance(d.confidence, float) for d in final.values() if d.confidence is not None
    )
    print("  M6 confidence/score fields are float (matches existing M4 convention):", scores_are_float)

    # -----------------------------------------------------------------
    section("10. Audit trail summary")
    m6_events = [e for e in audit.events if e.stage == "M6_GLOBAL_POLICY"]
    print(f"  total audit events (all stages): {len(audit.events)}")
    print(f"  M6_GLOBAL_POLICY events: {len(m6_events)}")
    rule_counts = Counter(e.rule_id for e in m6_events)
    for rule_id, count in sorted(rule_counts.items()):
        print(f"    {rule_id:<40}: {count:3d}")

    # -----------------------------------------------------------------
    section("11. Writing outputs")
    out_json = DEV / "m6_final.json"
    out_json.write_text(json.dumps({pid: d.to_dict() for pid, d in sorted(final.items())}, indent=2))
    print(f"  wrote {out_json}")

    out_audit = ROOT / "audit_log_m6.jsonl"
    audit.export_jsonl(str(out_audit))
    print(f"  wrote {out_audit}")

    print("\nDone. HOLDOUT WAS NOT ACCESSED.")


if __name__ == "__main__":
    main()
