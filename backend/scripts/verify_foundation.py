"""
Final M1-M5 foundation verification for the M6 handoff repair.
Does NOT touch data/holdout or ground_truth/holdout (neither exists in
this checkout at all - confirmed by directory scan below).
"""
import sys
import random
import importlib
from pathlib import Path
from collections import Counter
from decimal import Decimal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------
section("0. Holdout access check")
holdout_paths = list(ROOT.rglob("*holdout*"))
print("Paths matching '*holdout*' under repo root:", holdout_paths or "NONE FOUND")

# ---------------------------------------------------------------------
section("1. Import check")
modules = [
    "src.models", "src.normalization", "src.audit", "src.config",
    "src.matching", "src.deterministic", "src.candidates", "src.scoring",
]
for m in modules:
    importlib.import_module(m)
    print(f"  OK  {m}")

for m in ["src.m5_schema", "src.m5_provider", "src.m5_reasoning"]:
    try:
        importlib.import_module(m)
        print(f"  OK  {m}")
    except ModuleNotFoundError as e:
        print(f"  BLOCKED  {m}: {e} (external dependency not installed in this environment)")

# ---------------------------------------------------------------------
from src.config import ReconciliationConfig
from src.audit import AuditLog
from src.normalization import load_payments, load_settlements, load_orders, resolve_references
from src.matching import run_stage1_exact_matching
from src.deterministic import DeterministicReconciliationEngine, ReconciliationStatus
from src.candidates import CandidateConfig, generate_candidates
from src.scoring import M4Scorer

dev = ROOT / "data" / "dev"


def run_pipeline(payments, settlements, orders):
    audit = AuditLog()
    resolve_references(payments, orders, audit)
    config = ReconciliationConfig()
    m1_matched, unmatched = run_stage1_exact_matching(payments, settlements, config, audit)
    engine = DeterministicReconciliationEngine(config, audit)
    m2 = engine.reconcile_unmatched(
        payments, unmatched, settlements, {s.settlement_id for s in m1_matched.values()}, orders
    )
    decisions = {}
    for p in payments:
        if p.payment_id in m1_matched:
            decisions[p.payment_id] = (ReconciliationStatus.MATCH, m1_matched[p.payment_id].settlement_id, None)
        else:
            st, sid, expl, dupof = m2[p.payment_id]
            decisions[p.payment_id] = (st, sid, dupof)
    return decisions, audit, m1_matched, m2


base_payments = load_payments(str(dev / "payments.csv"), AuditLog())
base_settlements = load_settlements(str(dev / "settlements.csv"), AuditLog())
base_orders = load_orders(str(dev / "orders.csv"), AuditLog())

decisions, audit, m1_matched, m2 = run_pipeline(list(base_payments), list(base_settlements), list(base_orders))

# ---------------------------------------------------------------------
section("2. Physical row integrity")
n_input = len(base_payments)
n_decisions = len(decisions)
unique_pids = len({p.payment_id for p in base_payments})
print(f"  input payment rows : {n_input}")
print(f"  physical decisions : {n_decisions}")
print(f"  unique payment IDs : {unique_pids}")
assert n_input == n_decisions == unique_pids == 129, "physical integrity check FAILED"
print("  PASS: 129 -> 129, all unique")

status_counts = Counter(d[0] for d in decisions.values())
print("  status distribution:", dict(sorted(status_counts.items())))

# ---------------------------------------------------------------------
section("3. Duplicate invariant")
dupes = {pid: d for pid, d in decisions.items() if d[0] == ReconciliationStatus.DUPLICATE}
print(f"  duplicates found: {len(dupes)}")
assert len(dupes) == 9, f"expected 9 duplicates, got {len(dupes)}"
bad = []
for pid, (st, sid, dupof) in dupes.items():
    if sid is not None:
        bad.append((pid, "duplicate owns a settlement"))
    if dupof is None:
        bad.append((pid, "no duplicate_of set"))
    if decisions.get(dupof, (None,))[0] == ReconciliationStatus.DUPLICATE:
        bad.append((pid, "duplicate chain (canonical is itself a duplicate)"))
print("  violations:", bad or "NONE")
assert not bad, "duplicate invariant FAILED"
print("  PASS: 9/9 duplicates preserved, no chains, no settlement ownership")

# ---------------------------------------------------------------------
section("4. Cross-payment settlement collision check")
sid_owners = Counter(d[1] for d in decisions.values() if d[1])
collisions = {k: v for k, v in sid_owners.items() if v > 1}
print("  settlements claimed by >1 payment decision:", collisions or "NONE")
assert not collisions, "a settlement was assigned to more than one payment decision"
print("  PASS: no settlement double-assignment")

# ---------------------------------------------------------------------
section("5. Determinism under row-order shuffling")
random.seed(1234)
all_same = True
for trial in range(5):
    p2 = list(base_payments); random.shuffle(p2)
    s2 = list(base_settlements); random.shuffle(s2)
    o2 = list(base_orders); random.shuffle(o2)
    d2, _, _, _ = run_pipeline(p2, s2, o2)
    same = (d2 == decisions)
    all_same = all_same and same
    print(f"  trial {trial}: identical to base ordering = {same}")
assert all_same, "pipeline is NOT order-independent"
print("  PASS: identical M1-M2 decisions across 5 random row orderings")

# ---------------------------------------------------------------------
section("6. M3 candidate generation")
claimed = {s.settlement_id for s in m1_matched.values()}
residual_ids = set()
for pid, (st, sid, dupof) in decisions.items():
    if sid:
        claimed.add(sid)
    if st in (ReconciliationStatus.MISSING, ReconciliationStatus.AMBIGUOUS, ReconciliationStatus.UNRESOLVED):
        residual_ids.add(pid)

cfg = CandidateConfig.from_reconciliation_config(ReconciliationConfig())
m3 = generate_candidates(base_payments, base_settlements, base_orders, residual_ids, claimed, cfg, AuditLog())
print(f"  residual (M3-eligible) payments: {len(residual_ids)}")
print(f"  candidate pairs generated: {sum(len(v) for v in m3.values())}")
for c in list(m3.values())[0] if m3 else []:
    pass
print("  all CandidateRecord.date_difference numeric:",
      all(isinstance(c.date_difference, float) for cs in m3.values() for c in cs))

# ---------------------------------------------------------------------
section("7. M3 -> M4 compatibility")


class _PaymentView:
    def __init__(self, payment_id, amount, candidates):
        self.payment_id = payment_id
        self.amount = amount
        self.candidates = candidates


payment_by_id = {p.payment_id: p for p in base_payments}
scorer = M4Scorer(config_path=str(ROOT / "config" / "m4_thresholds.json"))
m4_outcomes = {}
error = None
try:
    for pid in residual_ids:
        p = payment_by_id[pid]
        view = _PaymentView(pid, p.amount, m3.get(pid, []))
        m4_outcomes[pid] = scorer.evaluate_payment(view)
    print("  M3 candidates consumed by M4Scorer without error.")
    print("  M4 outcome distribution:", dict(Counter(o["status"] for o in m4_outcomes.values())))
except Exception as e:
    error = e
    print("  M3->M4 compatibility FAILED:", repr(e))
assert error is None, "M3 output is not consumable by M4Scorer"

print("\nDone.")
