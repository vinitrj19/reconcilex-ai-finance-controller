# Synthetic Dataset Manifest

Total events: 200  
Dev events: 120  
Holdout events: 80

## Anomaly type counts (dev / holdout)

| Anomaly type | Total | Dev | Holdout |
|---|---|---|---|
| exact_match | 60 | 36 | 24 |
| date_shift | 25 | 15 | 10 |
| fee_adjusted | 25 | 15 | 10 |
| duplicate | 15 | 9 | 6 |
| missing_settlement | 15 | 9 | 6 |
| missing_payment | 10 | 6 | 4 |
| refund | 15 | 9 | 6 |
| partial_settlement | 15 | 9 | 6 |
| ambiguous | 10 | 6 | 4 |
| unrelated | 10 | 6 | 4 |

## Row counts per file

**dev**: 129 payments, 111 settlements, 120 orders
**holdout**: 86 payments, 74 settlements, 80 orders

## Rules
- Ground truth files are NOT inputs to the reconciliation engine. The engine only ever reads payments.csv / settlements.csv / orders.csv.
- `ground_truth_dev.json` may be used while building and tuning the engine (threshold sweeps, debugging match logic).
- `ground_truth_holdout.json` must not be opened, printed, or used to adjust any threshold or rule. It is read exactly once, at the end, purely to score the already-locked engine.
- `ambiguous` events deliberately have NO single correct pairing recorded - the engine is expected to return AMBIGUOUS/REVIEW_REQUIRED for both candidates, not to guess.