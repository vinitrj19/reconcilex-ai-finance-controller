// Generated from evaluation/results_dev.json + confusion_matrix_dev.csv of a real DEV run.
import type { EvaluationResponse } from '@/types'

export const evaluationData: EvaluationResponse = {
  "dataset": "DEV",
  "evaluation_type": "DEV",
  "run_id": "RUN_20260904_DEV_017",
  "metrics": {
    "match_rate": 1.0,
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "financial_false_positives": 0,
    "safe_automation_rate": 0.8604651162790697,
    "unresolved_rate": 0.046511627906976744,
    "review_rate": 0.13953488372093023
  },
  "baseline": [
    {
      "metric": "Precision",
      "baseline": 0.6451612903225806,
      "controller": 1.0,
      "unit": "percent"
    },
    {
      "metric": "Recall",
      "baseline": 0.6451612903225806,
      "controller": 1.0,
      "unit": "percent"
    },
    {
      "metric": "F1",
      "baseline": 0.6451612903225806,
      "controller": 1.0,
      "unit": "percent"
    },
    {
      "metric": "Match rate",
      "baseline": 0.6451612903225806,
      "controller": 1.0,
      "unit": "percent"
    },
    {
      "metric": "False positives",
      "baseline": 33,
      "controller": 0,
      "unit": "count"
    }
  ],
  "per_class": [
    {
      "anomaly_type": "exact_match",
      "support": 60,
      "correct": 60,
      "rate": 1.0
    },
    {
      "anomaly_type": "duplicate",
      "support": 9,
      "correct": 9,
      "rate": 1.0
    },
    {
      "anomaly_type": "missing_settlement",
      "support": 9,
      "correct": 9,
      "rate": 1.0
    },
    {
      "anomaly_type": "refund",
      "support": 9,
      "correct": 9,
      "rate": 1.0
    },
    {
      "anomaly_type": "partial_settlement",
      "support": 15,
      "correct": 15,
      "rate": 1.0
    },
    {
      "anomaly_type": "ambiguous",
      "support": 12,
      "correct": 12,
      "rate": 1.0
    }
  ],
  "confusion_matrix": [
    {
      "expected": "MATCH",
      "predicted": "MATCH",
      "count": 60
    },
    {
      "expected": "MATCH",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "MATCH",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "PARTIAL_MATCH",
      "count": 15
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "PARTIAL_MATCH",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "DUPLICATE",
      "count": 9
    },
    {
      "expected": "DUPLICATE",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "DUPLICATE",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "MISSING",
      "count": 9
    },
    {
      "expected": "MISSING",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "MISSING",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "REFUND",
      "count": 9
    },
    {
      "expected": "REFUND",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "REFUND",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "CONFLICT",
      "count": 9
    },
    {
      "expected": "CONFLICT",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "CONFLICT",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "AMBIGUOUS",
      "count": 12
    },
    {
      "expected": "AMBIGUOUS",
      "predicted": "UNRESOLVED",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "MATCH",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "PARTIAL_MATCH",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "DUPLICATE",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "MISSING",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "REFUND",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "CONFLICT",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "AMBIGUOUS",
      "count": 0
    },
    {
      "expected": "UNRESOLVED",
      "predicted": "UNRESOLVED",
      "count": 6
    }
  ],
  "statuses": [
    "MATCH",
    "PARTIAL_MATCH",
    "DUPLICATE",
    "MISSING",
    "REFUND",
    "CONFLICT",
    "AMBIGUOUS",
    "UNRESOLVED"
  ],
  "methodology": [
    "Matching thresholds and scoring weights were tuned only on the DEV split.",
    "Configuration (config/m4_thresholds.json, config/m6_policy.json) is frozen before evaluation.",
    "HOLDOUT data is kept completely untouched until the frozen system is run against it.",
    "Predictions are generated and written to disk before holdout ground truth is loaded.",
    "Metrics are calculated only after predictions are frozen \u2014 never used to adjust the system.",
    "Row-order shuffling and repeat runs produce identical results (reproducibility verified)."
  ]
} as unknown as EvaluationResponse
