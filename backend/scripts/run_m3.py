"""DEV-only M3 runner. Re-executes M1/M2, then generates candidates for
residual (MISSING / AMBIGUOUS / UNRESOLVED) payments."""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ReconciliationConfig
from src.audit import AuditLog
from src.normalization import load_payments, load_settlements, load_orders, resolve_references
from src.matching import run_stage1_exact_matching
from src.deterministic import DeterministicReconciliationEngine, ReconciliationStatus
from src.candidates import CandidateConfig, generate_candidates

root = Path(__file__).resolve().parent.parent
dev = root / "data" / "dev"

audit = AuditLog()
payments = load_payments(str(dev / "payments.csv"), audit)
settlements = load_settlements(str(dev / "settlements.csv"), audit)
orders = load_orders(str(dev / "orders.csv"), audit)
resolve_references(payments, orders, audit)

config = ReconciliationConfig()
m1_matched, unmatched = run_stage1_exact_matching(payments, settlements, config, audit)
engine = DeterministicReconciliationEngine(config, audit)
m2 = engine.reconcile_unmatched(
    payments, unmatched, settlements, {s.settlement_id for s in m1_matched.values()}, orders
)

claimed = {s.settlement_id for s in m1_matched.values()}
residual_ids = set()
for pid, (status, sid, expl, dupof) in m2.items():
    if sid:
        claimed.add(sid)
    if status in (ReconciliationStatus.MISSING, ReconciliationStatus.AMBIGUOUS, ReconciliationStatus.UNRESOLVED):
        residual_ids.add(pid)

cfg = CandidateConfig.from_reconciliation_config(config)
result = generate_candidates(payments, settlements, orders, residual_ids, claimed, cfg, audit)

m2_status_by_pid = {}
for p in payments:
    if p.payment_id in m1_matched:
        m2_status_by_pid[p.payment_id] = ReconciliationStatus.MATCH
    else:
        st, sid, expl, dupof = m2[p.payment_id]
        m2_status_by_pid[p.payment_id] = st

(dev / "m2_output.json").write_text(json.dumps(
    {pid: status for pid, status in m2_status_by_pid.items()}, indent=2
))
(dev / "m3_candidates.json").write_text(json.dumps(
    {
        pid: [
            {
                "payment_id": c.payment_id,
                "settlement_id": c.settlement_id,
                "amount_difference": str(c.amount_difference),
                "date_difference_days": c.date_difference,
                "matched_reference_fields": c.matched_reference_fields,
                "candidate_generation_rule": c.candidate_generation_rule,
                "evidence": c.evidence,
            }
            for c in cs
        ]
        for pid, cs in result.items()
    },
    indent=2,
))

counts = Counter(len(v) for v in result.values())
rule_counts = Counter(c.candidate_generation_rule for cs in result.values() for c in cs)
print("DEV payments:", len(payments))
print("DEV settlements:", len(settlements))
print("DEV orders:", len(orders))
print("M2 statuses:", dict(Counter(m2_status_by_pid.values())))
print("M3 inputs (residual payments):", len(residual_ids))
print("candidate pairs:", sum(len(v) for v in result.values()))
print("avg candidates/payment:", round(sum(len(v) for v in result.values()) / len(residual_ids), 3) if residual_ids else 0)
print("zero/exactly-one/multiple:", counts[0], counts[1], sum(v for k, v in counts.items() if k >= 2))
print("rule counts:", dict(rule_counts))
print("truncations:", sum(1 for pid in residual_ids if len(result[pid]) > cfg.max_candidates_per_payment))
print("audit M3 events:", sum(1 for e in audit.events if e.stage == "M3_CANDIDATE_GENERATION"))
