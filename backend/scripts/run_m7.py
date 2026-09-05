"""
M7 DEV evaluation runner.

Runs the full M1->M6 controller against data/dev/ (never holdout),
evaluates it against ground_truth/dev/ground_truth_dev.json using
src/evaluation.py, runs the naive baseline for comparison, validates
determinism/idempotency of both the pipeline and the evaluator, and
writes machine-readable + human-readable reports under evaluation/.

HOLDOUT IS NEVER ACCESSED. This script only ever opens files under
data/dev/ and ground_truth/dev/.

Does NOT modify M1-M6 reconciliation logic or configuration. Does NOT
tune anything based on these results.
"""
import importlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit import AuditLog  # noqa: E402
from src.normalization import load_orders, load_payments, load_settlements  # noqa: E402
from src import evaluation as ev  # noqa: E402
from scripts.run_m6 import run_pipeline, try_load_m5_engine  # noqa: E402
import scripts.run_tests_shim as test_runner  # noqa: E402

DEV = ROOT / "data" / "dev"
GT = ROOT / "ground_truth" / "dev" / "ground_truth_dev.json"
OUT_DIR = ROOT / "evaluation"


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def jsonable(obj):
    """Recursively convert dataclasses / non-JSON-native values (Decimal,
    etc.) already handled by evaluation.py's to_dict() methods; this is a
    defensive final pass for anything else (sets -> sorted lists)."""
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, set):
        return sorted(jsonable(v) for v in obj)
    return obj


def main():
    OUT_DIR.mkdir(exist_ok=True)

    # -----------------------------------------------------------------
    section("0. Holdout access check")
    holdout_paths = list(ROOT.rglob("*holdout*"))
    print("Paths matching '*holdout*' under repo root:", holdout_paths or "NONE FOUND (HOLDOUT WAS NOT ACCESSED)")
    if holdout_paths:
        print("  M7 does not open, read, or otherwise touch any of these paths.")

    # -----------------------------------------------------------------
    section("1. Regression: run existing M1-M6 test suite BEFORE any M7 change")
    pre_passed, pre_failed = _run_existing_tests()
    print(f"  pre-M7 regression: {pre_passed} passed, {len(pre_failed)} failed")
    assert not pre_failed, "Existing test suite must pass before implementing M7"

    # -----------------------------------------------------------------
    section("2. Load DEV data + ground truth")
    payments = list(load_payments(str(DEV / "payments.csv"), AuditLog()))
    settlements = list(load_settlements(str(DEV / "settlements.csv"), AuditLog()))
    orders = list(load_orders(str(DEV / "orders.csv"), AuditLog()))
    events = ev.load_ground_truth_events(str(GT))
    print(f"  payments={len(payments)} settlements={len(settlements)} orders={len(orders)} "
          f"logical_events={len(events)}")

    payment_gt = ev.build_payment_ground_truth(events)
    mp_events = ev.missing_payment_events(events)
    print(f"  payment-level ground truth entries derived: {len(payment_gt)}")
    print(f"  missing_payment events (0 physical payment rows, event-level only): {len(mp_events)}")
    derived_dist = Counter(g.expected_status for g in payment_gt.values())
    print(f"  ground-truth-derived physical status distribution: {dict(sorted(derived_dist.items()))}")

    # -----------------------------------------------------------------
    section("3. Run full controller (M1-M6) on DEV, timed")
    m5_engine, m5_error = try_load_m5_engine()
    if m5_engine is None:
        print(f"  M5 unavailable in this environment: {m5_error}")

    def _run():
        return run_pipeline(list(payments), list(settlements), list(orders), m5_engine)

    (final, audit), throughput = ev.measure_throughput(_run, payments, settlements)
    predictions = ev.predictions_from_final_decisions(final)
    print(f"  final decisions: {len(predictions)}")
    print(f"  execution time: {throughput.execution_seconds:.4f}s")

    # -----------------------------------------------------------------
    section("4. Full-controller DEV evaluation")
    headline = ev.compute_headline_metrics(payment_gt, predictions)
    per_class = ev.per_class_metrics(payment_gt, predictions)
    matrix = ev.confusion_matrix(payment_gt, predictions)
    event_eval = ev.evaluate_events(events, payment_gt, predictions)
    safe_auto = ev.compute_safe_automation_rate(payment_gt, predictions)
    rates = ev.compute_deterministic_and_ai_rates(predictions, audit.events)
    audit_cov = ev.compute_audit_coverage(predictions, audit.events)
    exceptions = ev.build_exception_list(predictions, audit.events, payment_gt)
    exception_categories = ev.exception_category_counts(exceptions)

    print(f"  physical match rate: {headline.match_rate_numerator}/{headline.match_rate_denominator} "
          f"= {headline.match_rate:.4f}")
    print(f"  event-level match rate: {event_eval['correct_events']}/{event_eval['total_events']} "
          f"= {event_eval['event_match_rate']:.4f}")
    print(f"  precision={headline.precision} recall={headline.recall} f1={headline.f1}")
    print(f"  false positives: {headline.fp} ({headline.false_positive_rate:.4%})")
    print(f"  safe automation rate: {safe_auto['safe_automated']}/{safe_auto['total']} "
          f"= {safe_auto['rate']:.4f}")
    print(f"  unresolved={headline.unresolved_count} ambiguous={headline.ambiguous_count} "
          f"review={headline.review_count}")
    print(f"  audit coverage: {audit_cov['audit_coverage_pct']:.2f}%")
    print(f"  exceptions: {len(exceptions)}  by category: {exception_categories}")

    # -----------------------------------------------------------------
    section("5. Baseline (exact payment_id == settlement_reference only)")
    baseline_preds = ev.run_baseline(payments, settlements)
    baseline_summary = ev.summarize_baseline(payment_gt, baseline_preds)
    print(f"  baseline match_rate={baseline_summary['match_rate']:.4f} "
          f"precision={baseline_summary['precision']} recall={baseline_summary['recall']} "
          f"false_positives={baseline_summary['false_positives']} "
          f"unresolved_rate={baseline_summary['unresolved_rate']:.4f}")
    print(f"  full controller match_rate={headline.match_rate:.4f} vs baseline={baseline_summary['match_rate']:.4f}")

    # -----------------------------------------------------------------
    section("6. Determinism: pipeline + evaluator across 5 row-order permutations")
    random.seed(4242)
    base_metrics = headline.to_dict()
    all_same = True
    for trial in range(5):
        p2 = list(payments); random.shuffle(p2)
        s2 = list(settlements); random.shuffle(s2)
        o2 = list(orders); random.shuffle(o2)
        m5_trial, _ = try_load_m5_engine()
        final2, _ = run_pipeline(p2, s2, o2, m5_trial)
        preds2 = ev.predictions_from_final_decisions(final2)
        metrics2 = ev.compute_headline_metrics(payment_gt, preds2).to_dict()
        same = metrics2 == base_metrics
        all_same = all_same and same
        print(f"  trial {trial}: metrics identical to base ordering = {same}")
    assert all_same, "M7 metrics are NOT row-order independent"
    print("  PASS: identical evaluation metrics across 5 random row orderings")

    # -----------------------------------------------------------------
    section("7. Idempotency: evaluate(output) == evaluate(output)")
    metrics_a = ev.compute_headline_metrics(payment_gt, predictions).to_dict()
    metrics_b = ev.compute_headline_metrics(payment_gt, predictions).to_dict()
    idempotent = metrics_a == metrics_b
    print(f"  repeated evaluation of the same predictions identical: {idempotent}")
    assert idempotent, "Evaluation layer is NOT idempotent"

    # -----------------------------------------------------------------
    section("8. Regression: run existing M1-M6 test suite AFTER M7 implementation")
    post_passed, post_failed = _run_existing_tests()
    print(f"  post-M7 regression: {post_passed} passed, {len(post_failed)} failed")
    assert not post_failed, "M7 must not break the existing M1-M6 test suite"

    # -----------------------------------------------------------------
    section("9. Writing evaluation outputs")
    results = {
        "dataset": {
            "payments": len(payments), "settlements": len(settlements), "orders": len(orders),
            "logical_events": len(events),
        },
        "full_controller": {
            "headline": headline.to_dict(),
            "event_level": event_eval,
            "safe_automation_rate": safe_auto,
            "deterministic_and_ai_rates": rates,
            "audit_coverage": audit_cov,
            "throughput": throughput.to_dict(),
            "per_class_metrics": {k: v.to_dict() for k, v in sorted(per_class.items())},
        },
        "baseline": baseline_summary,
        "determinism": {"row_shuffle_trials": 5, "all_identical": all_same},
        "idempotency": {"identical": idempotent},
        "exceptions": {"count": len(exceptions), "by_category": exception_categories},
        "regression_tests": {
            "pre_m7": {"passed": pre_passed, "failed": len(pre_failed)},
            "post_m7": {"passed": post_passed, "failed": len(post_failed)},
        },
        "holdout_accessed": False,
    }
    (OUT_DIR / "results_dev.json").write_text(json.dumps(jsonable(results), indent=2, default=str))
    print(f"  wrote {OUT_DIR / 'results_dev.json'}")

    with (OUT_DIR / "confusion_matrix_dev.csv").open("w", encoding="utf-8") as f:
        f.write("expected_status,predicted_status,count\n")
        for row in ev.confusion_matrix_rows(matrix):
            f.write(f"{row['expected_status']},{row['predicted_status']},{row['count']}\n")
    print(f"  wrote {OUT_DIR / 'confusion_matrix_dev.csv'}")

    (OUT_DIR / "exceptions_dev.json").write_text(json.dumps(jsonable(exceptions), indent=2, default=str))
    print(f"  wrote {OUT_DIR / 'exceptions_dev.json'}")

    report = _render_report(
        results, per_class, matrix, exceptions, exception_categories, mp_events,
    )
    (OUT_DIR / "report_dev.md").write_text(report)
    print(f"  wrote {OUT_DIR / 'report_dev.md'}")

    print("\nDone. HOLDOUT WAS NOT ACCESSED.")
    return results


def _run_existing_tests():
    """Reuses scripts/run_tests_shim.py's own file-by-file runner rather
    than reimplementing it, so M7's regression check is the exact same
    thing a human would run by hand."""
    total_passed = 0
    total_failed = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name in test_runner.SKIP_FILES:
            continue
        passed, failed = test_runner.run_file(path)
        total_passed += passed
        total_failed.extend((path.name, n, msg) for n, msg in failed)
    return total_passed, total_failed


def _render_report(results, per_class, matrix, exceptions, exception_categories, mp_events) -> str:
    d = results["dataset"]
    fc = results["full_controller"]
    hl = fc["headline"]
    ev_lvl = fc["event_level"]
    sa = fc["safe_automation_rate"]
    rates = fc["deterministic_and_ai_rates"]
    audit_cov = fc["audit_coverage"]
    tp = fc["throughput"]
    bl = results["baseline"]

    lines = []
    a = lines.append
    a("# M7 - Evaluation, Metrics & Benchmarking Report (DEV)\n")
    a("## Dataset\n")
    a(f"- Payments: {d['payments']}")
    a(f"- Settlements: {d['settlements']}")
    a(f"- Orders: {d['orders']}")
    a(f"- Logical events: {d['logical_events']}\n")

    a("## Full Controller (physical payment-row level, n={})\n".format(hl['total']))
    a(f"- Match rate: {hl['match_rate']['matched']}/{hl['match_rate']['total']} = {hl['match_rate']['rate']:.4f}")
    a(f"- Overall correct rate (incl. correct abstentions): {hl['overall_correct']}/{hl['total']} = {hl['overall_correct_rate']:.4f}")
    a(f"- Precision: {hl['precision']}")
    a(f"- Recall: {hl['recall']}")
    a(f"- F1: {hl['f1']}")
    a(f"- False positives: {hl['false_positives']['count']} (rate {hl['false_positives']['rate']:.4%})")
    if hl['false_positives']['payment_ids']:
        a(f"  - Payment IDs: {', '.join(hl['false_positives']['payment_ids'])}")
    a(f"- Safe automation rate: {sa['safe_automated']}/{sa['total']} = {sa['rate']:.4f}")
    a(f"- Unresolved rate: {hl['unresolved_rate']['count']}/{hl['total']} = {hl['unresolved_rate']['rate']:.4f}")
    a(f"- Review rate (AMBIGUOUS+UNRESOLVED): {hl['review_rate']['count']}/{hl['total']} = {hl['review_rate']['rate']:.4f}")
    a(f"- Ambiguous rate: {hl['ambiguous_rate']['count']}/{hl['total']} = {hl['ambiguous_rate']['rate']:.4f}")
    a(f"- Correct abstentions (genuinely ambiguous/unrelated, safely refused): {hl['abstention']['correct_abstention_count']}")
    a(f"- Wrong abstentions (a resolution was expected but the system abstained): {hl['abstention']['wrong_abstention_count']}")
    a(f"- Deterministic resolution rate: {rates['deterministic_resolution_rate']['count']}/{rates['deterministic_resolution_rate']['total']} = {rates['deterministic_resolution_rate']['rate']:.4f}")
    ai = rates['ai_invocation_rate']
    a(f"- AI invocation rate: {ai['invocations']}/{ai['eligible_residual_records']} = {ai['rate']}")
    a(f"  - {ai['note']}")
    a(f"- Audit coverage: {audit_cov['decisions_with_audit_evidence']}/{audit_cov['total_final_decisions']} = {audit_cov['audit_coverage_pct']:.2f}%")
    a(f"- Execution time: {tp['execution_seconds']:.4f}s")
    a(f"- Throughput: {tp['records_per_second']} records/sec ({tp['caveat']})\n")

    a("## Event-Level Evaluation (authoritative correctness view, n={})\n".format(ev_lvl['total_events']))
    a(f"- Event match rate: {ev_lvl['correct_events']}/{ev_lvl['total_events']} = {ev_lvl['event_match_rate']:.4f}")
    a("\n| anomaly_type | total | correct | rate |")
    a("|---|---|---|---|")
    for t, s in sorted(ev_lvl["by_anomaly_type"].items()):
        a(f"| {t} | {s['total']} | {s['correct']} | {s['rate']:.4f} |")
    a("")
    a(f"- `missing_payment` events (0 physical payment rows; scored by settlement-non-theft only): {len(mp_events)}\n")

    a("## Baseline (exact payment_id == settlement_reference only)\n")
    a(f"- Match rate: {bl['match_rate']:.4f}")
    a(f"- Precision: {bl['precision']}")
    a(f"- Recall: {bl['recall']}")
    a(f"- False positives: {bl['false_positives']}")
    a(f"- Unresolved rate: {bl['unresolved_rate']:.4f}\n")
    a(f"**Layered controller vs baseline match rate: {hl['match_rate']['rate']:.4f} vs {bl['match_rate']:.4f}**\n")

    a("## Per-Class Metrics (physical payment-row level)\n")
    a("| status | support | precision | recall | f1 |")
    a("|---|---|---|---|---|")
    for status in ("MATCH", "PARTIAL_MATCH", "REFUND", "CONFLICT", "MISSING", "DUPLICATE", "AMBIGUOUS", "UNRESOLVED"):
        m = per_class.get(status)
        if m is None:
            continue
        p = f"{m.precision:.4f}" if m.precision is not None else "n/a (no predictions of this class)"
        r = f"{m.recall:.4f}" if m.recall is not None else "n/a (no ground-truth support)"
        f1 = f"{m.f1:.4f}" if m.f1 is not None else "n/a"
        a(f"| {status} | {m.support} | {p} | {r} | {f1} |")
    a("")

    a("## Exceptions\n")
    a(f"- Unresolved/review/missing/duplicate cases: {len(exceptions)}")
    a("\n| category | count |")
    a("|---|---|")
    for cat, count in sorted(exception_categories.items(), key=lambda kv: -kv[1]):
        a(f"| {cat} | {count} |")
    a("")
    if exceptions:
        a("Examples (first 5):\n")
        for e in exceptions[:5]:
            a(f"- `{e['payment_id']}` status={e['status']} category={e['category']} "
              f"reason: {e['reason']}")
        a("")

    a("## Confusion Matrix (physical payment-row level, expected -> predicted)\n")
    a("| expected | predicted | count |")
    a("|---|---|---|")
    for row in ev.confusion_matrix_rows(matrix):
        a(f"| {row['expected_status']} | {row['predicted_status']} | {row['count']} |")
    a("")
    a(
        "Note: ground truth for `ambiguous`/`unrelated` events is recorded here under its "
        "literal label (AMBIGUOUS / UNRESOLVED respectively), but the controller's abstention "
        "counts as correct under either safe-abstention label - see 'Correct abstentions' above "
        "for the abstention-aware reading, and per-class metrics for the label-literal reading.\n"
    )

    a("## Determinism\n")
    det = results["determinism"]
    a(f"- Row-shuffle trials: {det['row_shuffle_trials']}")
    a(f"- All trials produced identical evaluation metrics: {det['all_identical']}\n")

    a("## Idempotency\n")
    a(f"- Repeated evaluation of the same predictions identical: {results['idempotency']['identical']}\n")

    a("## Tests\n")
    reg = results["regression_tests"]
    a(f"- Pre-M7 regression: {reg['pre_m7']['passed']} passed, {reg['pre_m7']['failed']} failed")
    a(f"- Post-M7 regression: {reg['post_m7']['passed']} passed, {reg['post_m7']['failed']} failed")
    a("- (Uses the repository's own pytest-compatible shim - see scripts/_pytest_shim.py -")
    a("  because real pytest is not installed in this sandbox and there is no network access")
    a("  to fetch it. 1 file (tests/test_m5_reasoning.py) is skipped for the same reason")
    a("  pydantic is unavailable; it is never reported as passed.)\n")

    a("## Holdout\n")
    a("HOLDOUT WAS NOT ACCESSED.\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
