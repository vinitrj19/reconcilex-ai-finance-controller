# M7 - Evaluation, Metrics & Benchmarking Report (DEV)

## Dataset

- Payments: 129
- Settlements: 111
- Orders: 120
- Logical events: 120

## Full Controller (physical payment-row level, n=129)

- Match rate: 93/93 = 1.0000
- Overall correct rate (incl. correct abstentions): 129/129 = 1.0000
- Precision: 1.0
- Recall: 1.0
- F1: 1.0
- False positives: 0 (rate 0.0000%)
- Safe automation rate: 111/129 = 0.8605
- Unresolved rate: 6/129 = 0.0465
- Review rate (AMBIGUOUS+UNRESOLVED): 18/129 = 0.1395
- Ambiguous rate: 12/129 = 0.0930
- Correct abstentions (genuinely ambiguous/unrelated, safely refused): 18
- Wrong abstentions (a resolution was expected but the system abstained): 0
- Deterministic resolution rate: 129/129 = 1.0000
- AI invocation rate: 0/13 = 0.0
  - M5 runtime evaluation was unavailable in this environment (pydantic not installed, no network access); all AI-eligible residual records fell back to safe status preservation instead of a real AI decision. This is NOT evidence of AI performance - it is the honestly-reported absence of an AI run.
- Audit coverage: 129/129 = 100.00%
- Execution time: 0.0026s
- Throughput: 49632.660599291026 records/sec (Single small-dataset run (129 payments); not a reliable throughput estimate at production scale - reported for reference only.)

## Event-Level Evaluation (authoritative correctness view, n=120)

- Event match rate: 120/120 = 1.0000

| anomaly_type | total | correct | rate |
|---|---|---|---|
| ambiguous | 6 | 6 | 1.0000 |
| date_shift | 15 | 15 | 1.0000 |
| duplicate | 9 | 9 | 1.0000 |
| exact_match | 36 | 36 | 1.0000 |
| fee_adjusted | 15 | 15 | 1.0000 |
| missing_payment | 6 | 6 | 1.0000 |
| missing_settlement | 9 | 9 | 1.0000 |
| partial_settlement | 9 | 9 | 1.0000 |
| refund | 9 | 9 | 1.0000 |
| unrelated | 6 | 6 | 1.0000 |

- `missing_payment` events (0 physical payment rows; scored by settlement-non-theft only): 6

## Baseline (exact payment_id == settlement_reference only)

- Match rate: 0.6452
- Precision: 0.6451612903225806
- Recall: 0.6451612903225806
- False positives: 33
- Unresolved rate: 0.2791

**Layered controller vs baseline match rate: 1.0000 vs 0.6452**

## Per-Class Metrics (physical payment-row level)

| status | support | precision | recall | f1 |
|---|---|---|---|---|
| MATCH | 60 | 1.0000 | 1.0000 | 1.0000 |
| PARTIAL_MATCH | 15 | 1.0000 | 1.0000 | 1.0000 |
| REFUND | 9 | 1.0000 | 1.0000 | 1.0000 |
| CONFLICT | 9 | 1.0000 | 1.0000 | 1.0000 |
| MISSING | 9 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE | 9 | 1.0000 | 1.0000 | 1.0000 |
| AMBIGUOUS | 12 | 1.0000 | 1.0000 | 1.0000 |
| UNRESOLVED | 6 | 1.0000 | 1.0000 | 1.0000 |

## Exceptions

- Unresolved/review/missing/duplicate cases: 36

| category | count |
|---|---|
| ai_unavailable | 13 |
| duplicate | 9 |
| missing_settlement_or_payment | 9 |
| no_candidate | 5 |

Examples (first 5):

- `PAY_00005` status=UNRESOLVED category=no_candidate reason: Unresolved: payment.order_id='ORD_00006' does not resolve to any known order, and no settlement directly references this payment. Relationship cannot be safely established.
- `PAY_00007` status=DUPLICATE category=duplicate reason: Duplicate of payment PAY_00006: same order/customer and amount within the duplicate detection window.
- `PAY_00016` status=MISSING category=missing_settlement_or_payment reason: Missing: no directly-referenced or amount/date-plausible settlement candidate found.
- `PAY_00021` status=MISSING category=missing_settlement_or_payment reason: Missing: no directly-referenced or amount/date-plausible settlement candidate found.
- `PAY_00027` status=MISSING category=missing_settlement_or_payment reason: Missing: no directly-referenced or amount/date-plausible settlement candidate found.

## Confusion Matrix (physical payment-row level, expected -> predicted)

| expected | predicted | count |
|---|---|---|
| AMBIGUOUS | AMBIGUOUS | 12 |
| CONFLICT | CONFLICT | 9 |
| DUPLICATE | DUPLICATE | 9 |
| MATCH | MATCH | 60 |
| MISSING | MISSING | 9 |
| PARTIAL_MATCH | PARTIAL_MATCH | 15 |
| REFUND | REFUND | 9 |
| UNRESOLVED | UNRESOLVED | 6 |

Note: ground truth for `ambiguous`/`unrelated` events is recorded here under its literal label (AMBIGUOUS / UNRESOLVED respectively), but the controller's abstention counts as correct under either safe-abstention label - see 'Correct abstentions' above for the abstention-aware reading, and per-class metrics for the label-literal reading.

## Determinism

- Row-shuffle trials: 5
- All trials produced identical evaluation metrics: True

## Idempotency

- Repeated evaluation of the same predictions identical: True

## Tests

- Pre-M7 regression: 93 passed, 0 failed
- Post-M7 regression: 93 passed, 0 failed
- (Uses the repository's own pytest-compatible shim - see scripts/_pytest_shim.py -
  because real pytest is not installed in this sandbox and there is no network access
  to fetch it. 1 file (tests/test_m5_reasoning.py) is skipped for the same reason
  pydantic is unavailable; it is never reported as passed.)

## Holdout

HOLDOUT WAS NOT ACCESSED.
