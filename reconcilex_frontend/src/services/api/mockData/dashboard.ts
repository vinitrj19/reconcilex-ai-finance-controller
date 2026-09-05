// Generated from a real DEV run of the reconciliation_controller project.
import type { DashboardResponse } from '@/types'

export const dashboardData: DashboardResponse = {
  "run_id": "RUN_20260904_DEV_017",
  "dataset": "DEV",
  "generated_at": "2026-09-04T21:24:43Z",
  "metrics": {
    "transactions_processed": 129,
    "reconciled": 129,
    "safe_automation_rate": 86.0,
    "financial_false_positives": 0
  },
  "pipeline": [
    {
      "stage": "sources",
      "label": "Payments",
      "count": 129
    },
    {
      "stage": "sources",
      "label": "Settlements",
      "count": 111
    },
    {
      "stage": "sources",
      "label": "Orders",
      "count": 120
    },
    {
      "stage": "normalization",
      "label": "Normalization",
      "count": null,
      "detail": "References resolved across sources"
    },
    {
      "stage": "deterministic",
      "label": "Deterministic Resolution",
      "count": 111,
      "detail": "M1 identity + M2/M4 rules"
    },
    {
      "stage": "ai",
      "label": "AI Review",
      "count": 12,
      "detail": "residual ambiguous cases only"
    },
    {
      "stage": "policy",
      "label": "Policy Controlled",
      "count": null,
      "detail": "M6 global safety invariants"
    },
    {
      "stage": "final",
      "label": "Final Decision",
      "count": 129,
      "detail": "18 sent to review"
    }
  ],
  "status_breakdown": [
    {
      "status": "AMBIGUOUS",
      "count": 12
    },
    {
      "status": "CONFLICT",
      "count": 9
    },
    {
      "status": "DUPLICATE",
      "count": 9
    },
    {
      "status": "MATCH",
      "count": 60
    },
    {
      "status": "MISSING",
      "count": 9
    },
    {
      "status": "PARTIAL_MATCH",
      "count": 15
    },
    {
      "status": "REFUND",
      "count": 9
    },
    {
      "status": "UNRESOLVED",
      "count": 6
    }
  ],
  "recent_exceptions": [
    {
      "case_id": "CASE_00005",
      "payment_id": "PAY_00005",
      "type": "UNRESOLVED",
      "amount": 27192.08,
      "currency": "INR",
      "reason": "Unresolved: payment.order_id='ORD_00006' does not resolve to any known order, and no settlement directly references this payment. Relationship cannot be safely established.",
      "status": "UNRESOLVED"
    },
    {
      "case_id": "CASE_00007",
      "payment_id": "PAY_00007",
      "type": "DUPLICATE",
      "amount": 33831.55,
      "currency": "INR",
      "reason": "Duplicate of payment PAY_00006: same order/customer and amount within the duplicate detection window.",
      "status": "DUPLICATE"
    },
    {
      "case_id": "CASE_00016",
      "payment_id": "PAY_00016",
      "type": "MISSING_SETTLEMENT",
      "amount": 31159.38,
      "currency": "INR",
      "reason": "Missing: no directly-referenced or amount/date-plausible settlement candidate found.",
      "status": "MISSING"
    },
    {
      "case_id": "CASE_00021",
      "payment_id": "PAY_00021",
      "type": "MISSING_SETTLEMENT",
      "amount": 46977.04,
      "currency": "INR",
      "reason": "Missing: no directly-referenced or amount/date-plausible settlement candidate found.",
      "status": "MISSING"
    },
    {
      "case_id": "CASE_00027",
      "payment_id": "PAY_00027",
      "type": "MISSING_SETTLEMENT",
      "amount": 33513.2,
      "currency": "INR",
      "reason": "Missing: no directly-referenced or amount/date-plausible settlement candidate found.",
      "status": "MISSING"
    }
  ]
} as unknown as DashboardResponse
