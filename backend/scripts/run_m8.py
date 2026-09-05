import json, random, hashlib, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.audit import AuditLog
from src.normalization import load_orders, load_payments, load_settlements
from src import evaluation as ev
from scripts.run_m6 import run_pipeline, try_load_m5_engine

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'/'holdout'; GT=ROOT/'ground_truth'/'holdout'/'ground_truth_holdout.json'; OUT=ROOT/'evaluation'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def jdump(x): return json.dumps(x,indent=2,sort_keys=True,default=str)

def main():
    OUT.mkdir(exist_ok=True)
    payments=list(load_payments(str(DATA/'payments.csv'),AuditLog()))
    settlements=list(load_settlements(str(DATA/'settlements.csv'),AuditLog()))
    orders=list(load_orders(str(DATA/'orders.csv'),AuditLog()))
    print(f'INPUT holdout: payments={len(payments)} settlements={len(settlements)} orders={len(orders)}')
    m5,err=try_load_m5_engine(); print('M5:', 'available' if m5 else f'unavailable: {err}')
    def run(): return run_pipeline(list(payments),list(settlements),list(orders),m5)
    (final,audit),throughput=ev.measure_throughput(run,payments,settlements)
    preds=ev.predictions_from_final_decisions(final)
    # Raw predictions are frozen BEFORE scoring/GT access in this runner.
    (OUT/'predictions_holdout.json').write_text(jdump({k:v.__dict__ for k,v in sorted(preds.items())}))
    print(f'FROZEN predictions: {len(preds)} -> {OUT/"predictions_holdout.json"}')
    # Final scoring step: GT is loaded only after predictions are persisted.
    events=ev.load_ground_truth_events(str(GT))
    pgt=ev.build_payment_ground_truth(events)
    headline=ev.compute_headline_metrics(pgt,preds); per=ev.per_class_metrics(pgt,preds); matrix=ev.confusion_matrix(pgt,preds)
    event_eval=ev.evaluate_events(events,pgt,preds); safe=ev.compute_safe_automation_rate(pgt,preds)
    rates=ev.compute_deterministic_and_ai_rates(preds,audit.events); cov=ev.compute_audit_coverage(preds,audit.events)
    exc=ev.build_exception_list(preds,audit.events,pgt); excc=ev.exception_category_counts(exc)
    baseline=ev.summarize_baseline(pgt,ev.run_baseline(payments,settlements))
    # determinism/idempotency
    base={k:v.to_dict() for k,v in final.items()}; shuffles=[]
    random.seed(4242)
    for i in range(5):
        p=list(payments);s=list(settlements);o=list(orders);random.shuffle(p);random.shuffle(s);random.shuffle(o)
        m,_=try_load_m5_engine(); f,_a=run_pipeline(p,s,o,m); shuffles.append({k:v.to_dict() for k,v in f.items()}==base)
    m2,_=try_load_m5_engine(); f2,_=run_pipeline(list(payments),list(settlements),list(orders),m2)
    idem={k:v.to_dict() for k,v in f2.items()}==base
    results={'dataset':{'payments':len(payments),'settlements':len(settlements),'orders':len(orders),'logical_events':len(events)},'full_controller':{'headline':headline.to_dict(),'event_level':event_eval,'safe_automation_rate':safe,'deterministic_and_ai_rates':rates,'audit_coverage':cov,'throughput':throughput.to_dict(),'per_class_metrics':{k:v.to_dict() for k,v in sorted(per.items())}},'baseline':baseline,'exceptions':{'count':len(exc),'by_category':excc},'determinism':{'row_shuffle_trials':5,'all_identical':all(shuffles),'trial_results':shuffles},'idempotency':{'identical':idem},'m5_runtime':{'available':m5 is not None,'error':err},'integrity':{'holdout_input_hashes':{p.name:sha(p) for p in [DATA/'payments.csv',DATA/'settlements.csv',DATA/'orders.csv']},'ground_truth_hash':sha(GT)}}
    (OUT/'results_holdout.json').write_text(jdump(results))
    with (OUT/'confusion_matrix_holdout.csv').open('w') as f:
        f.write('expected_status,predicted_status,count\n');
        for r in ev.confusion_matrix_rows(matrix): f.write(f"{r['expected_status']},{r['predicted_status']},{r['count']}\n")
    (OUT/'exceptions_holdout.json').write_text(jdump(exc))
    lines=['# M8 Holdout Evaluation','',f"- Payments: {len(payments)}",f"- Settlements: {len(settlements)}",f"- Orders: {len(orders)}",f"- Logical events: {len(events)}",'', '## Headline',f"- Match rate: {headline.match_rate_numerator}/{headline.match_rate_denominator} = {headline.match_rate:.4f}",f"- Precision / Recall / F1: {headline.precision} / {headline.recall} / {headline.f1}",f"- False positives: {headline.fp}",f"- Overall correct: {headline.overall_correct}/{headline.total} = {headline.overall_correct_rate:.4f}",f"- Safe automation: {safe['safe_automated']}/{safe['total']} = {safe['rate']:.4f}",f"- Review: {headline.review_count}; Ambiguous: {headline.ambiguous_count}; Unresolved: {headline.unresolved_count}",f"- Event match: {event_eval['correct_events']}/{event_eval['total_events']} = {event_eval['event_match_rate']:.4f}",f"- Deterministic resolution: {rates['deterministic_resolution_rate']}",f"- AI invocation: {rates['ai_invocation_rate']}",f"- Audit coverage: {cov['audit_coverage_pct']:.2f}%",f"- Throughput: {throughput.to_dict()}",'','## Baseline',f"- Match rate: {baseline['match_rate']:.4f}; Precision: {baseline['precision']}; Recall: {baseline['recall']}; FP: {baseline['false_positives']}; Unresolved: {baseline['unresolved_rate']:.4f}",'','## Per anomaly type']
    for t,d in event_eval['by_anomaly_type'].items(): lines.append(f"- {t}: {d['correct']}/{d['total']} = {d['rate']:.4f}")
    lines += ['', '## Exceptions',f"- Count: {len(exc)}",f"- Categories: {excc}",'', '## Safety / reproducibility',f"- Row-order invariant across 5 shuffles: {all(shuffles)}",f"- Idempotent: {idem}",f"- M5 available: {m5 is not None}"]
    (OUT/'report_holdout.md').write_text('\n'.join(lines))
    print('\nRESULTS')
    print(f'MATCH RATE {headline.match_rate:.4f}  PRECISION {headline.precision}  RECALL {headline.recall}  F1 {headline.f1}  FP {headline.fp}')
    print(f'OVERALL {headline.overall_correct}/{headline.total}  SAFE_AUTO {safe["safe_automated"]}/{safe["total"]}={safe["rate"]:.4f}')
    print(f'EVENT {event_eval["correct_events"]}/{event_eval["total_events"]}={event_eval["event_match_rate"]:.4f}')
    print('PER_CLASS', {k:(v.tp,v.fp,v.fn,v.precision,v.recall,v.f1) for k,v in sorted(per.items())})
    print('EXCEPTIONS',len(exc),excc)
    print('BASELINE',baseline)
    print('DETERMINISM',all(shuffles),'IDEMPOTENT',idem)
if __name__=='__main__': main()
