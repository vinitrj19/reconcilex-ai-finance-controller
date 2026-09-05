// Mock API surface. Every export here matches the shape and typing of the
// real backend call it stands in for (see realApi.ts / client.ts). Data
// comes from src/services/api/mockData, which was generated from a real,
// independently-verified DEV run of the reconciliation_controller project
// (see /evaluation/results_dev.json in the backend repo) — never hand-typed
// numbers. This file is the ONLY place mock data is assembled; components
// never import mockData/* directly.

import type {
  DashboardResponse,
  ReconciliationListResponse,
  ReconciliationDetailResponse,
  ExceptionsResponse,
  ExceptionDetailResponse,
  AuditResponse,
  EvaluationResponse,
  RunResponse,
} from '@/types'
import { dashboardData } from './mockData/dashboard'
import { reconciliationItems, reconciliationDetails } from './mockData/reconciliation'
import { exceptionsData } from './mockData/exceptions'
import { auditByPayment } from './mockData/audit'
import { evaluationData } from './mockData/evaluation'

const LATENCY_MS = 220

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS))
}

export const mockApi = {
  async getDashboard(): Promise<DashboardResponse> {
    return delay(dashboardData)
  },

  async getReconciliation(params: {
    page?: number
    pageSize?: number
    search?: string
    status?: string
  }): Promise<ReconciliationListResponse> {
    const { page = 1, pageSize = 20, search = '', status = 'ALL' } = params
    let items = reconciliationItems

    if (status !== 'ALL') {
      if (status === 'REVIEW') {
        items = items.filter((i) => i.status === 'AMBIGUOUS' || i.status === 'UNRESOLVED')
      } else {
        items = items.filter((i) => i.status === status)
      }
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter(
        (i) =>
          i.payment_id.toLowerCase().includes(q) ||
          (i.order_id ?? '').toLowerCase().includes(q) ||
          (i.settlement_id ?? '').toLowerCase().includes(q),
      )
    }

    const total = items.length
    const pages = Math.max(1, Math.ceil(total / pageSize))
    const start = (page - 1) * pageSize
    const pageItems = items.slice(start, start + pageSize)

    return delay({
      items: pageItems,
      pagination: { page, page_size: pageSize, total, pages },
    })
  },

  async getReconciliationDetail(paymentId: string): Promise<ReconciliationDetailResponse> {
    const detail = reconciliationDetails[paymentId]
    if (!detail) throw new Error(`No reconciliation record for ${paymentId}`)
    return delay(detail)
  },

  async getExceptions(): Promise<ExceptionsResponse> {
    return delay(exceptionsData)
  },

  async getExceptionDetail(caseId: string): Promise<ExceptionDetailResponse> {
    const item = exceptionsData.items.find((e) => e.case_id === caseId)
    if (!item) throw new Error(`No exception case ${caseId}`)
    const detail = reconciliationDetails[item.payment_id]
    return delay({
      ...detail,
      case_id: item.case_id,
      investigation_prompts: [
        'What direct references (order ID, settlement reference) exist between these records?',
        'Do the amounts differ by a fee, tax, or currency-rounding delta that would explain a mismatch?',
        'Is another payment contesting the same settlement candidate?',
        'Is there a plausible settlement in a wider date window that the deterministic rules excluded?',
      ],
    })
  },

  async getAudit(paymentId: string): Promise<AuditResponse> {
    const events = auditByPayment[paymentId] ?? []
    return delay({ payment_id: paymentId, events })
  },

  async getEvaluation(_dataset: 'DEV' | 'HOLDOUT' = 'DEV'): Promise<EvaluationResponse> {
    return delay(evaluationData)
  },

  async runReconciliation(): Promise<RunResponse> {
    const steps = [
      { key: 'load', label: 'Loading sources', status: 'DONE' as const },
      { key: 'normalize', label: 'Normalizing records', status: 'DONE' as const },
      { key: 'candidates', label: 'Generating candidates', status: 'DONE' as const },
      { key: 'deterministic', label: 'Running deterministic rules', status: 'DONE' as const },
      { key: 'ai', label: 'Evaluating residual ambiguity', status: 'DONE' as const },
      { key: 'policy', label: 'Applying policy', status: 'DONE' as const },
      { key: 'audit', label: 'Writing audit records', status: 'DONE' as const },
    ]
    return delay({
      run_id: `RUN_${Date.now()}`,
      status: 'COMPLETED' as const,
      steps,
      summary: {
        run_id: `RUN_${Date.now()}`,
        execution_time_seconds: 0.014,
        records_processed: dashboardData.metrics.transactions_processed,
        matches: dashboardData.metrics.reconciled,
        exceptions: exceptionsData.summary.total,
      },
    })
  },
}
