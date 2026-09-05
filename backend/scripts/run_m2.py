"""
M2 Runner Script: Executes M1 exact matching followed by M2 deterministic
rules. Processes the DEV dataset only.
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ReconciliationConfig
from src.audit import AuditLog
from src.normalization import load_payments, load_settlements, load_orders, resolve_references
from src.matching import run_stage1_exact_matching
from src.deterministic import DeterministicReconciliationEngine, ReconciliationStatus


def run_m2_pipeline():
    project_root = Path(__file__).resolve().parent.parent
    dev_data_dir = project_root / "data" / "dev"

    audit = AuditLog()
    payments = load_payments(str(dev_data_dir / "payments.csv"), audit)
    settlements = load_settlements(str(dev_data_dir / "settlements.csv"), audit)
    orders = load_orders(str(dev_data_dir / "orders.csv"), audit)

    resolve_references(payments, orders, audit)

    config = ReconciliationConfig()

    m1_matched, unmatched_payments = run_stage1_exact_matching(payments, settlements, config, audit)
    m1_settlement_ids = {s.settlement_id for s in m1_matched.values()}

    engine = DeterministicReconciliationEngine(config, audit)
    m2_results = engine.reconcile_unmatched(
        all_payments=payments,
        unmatched_payments=unmatched_payments,
        all_settlements=settlements,
        m1_matched_settlement_ids=m1_settlement_ids,
        orders=orders,
    )

    row_level_decisions = {}
    for p in payments:
        if p.payment_id in m1_matched:
            row_level_decisions[p.payment_id] = ReconciliationStatus.MATCH
        else:
            st, _, _, _ = m2_results[p.payment_id]
            row_level_decisions[p.payment_id] = st

    status_counts = Counter(row_level_decisions.values())

    print("=" * 65)
    print(f" ROW-LEVEL RECONCILIATION SUMMARY ({len(payments)} Payment Records)")
    print("=" * 65)
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<20}: {count:3d}")
    print("-" * 65)
    print(f"  TOTAL PAYMENTS      : {len(row_level_decisions):3d}")

    print("\n" + "=" * 65)
    print(" EVENT-LEVEL AUDIT SUMMARY")
    print("=" * 65)
    for rule_id, count in sorted(audit.get_event_counts_by_rule().items()):
        print(f"  {rule_id:<42}: {count:3d} events")

    print("-" * 65)
    for fact_key, count in audit.audit_facts.items():
        print(f"  {fact_key:<42}: {count:3d}")

    out_file = project_root / "audit_log_m2.jsonl"
    audit.export_jsonl(str(out_file))
    print(f"\nAudit log written to {out_file}")


if __name__ == "__main__":
    run_m2_pipeline()
