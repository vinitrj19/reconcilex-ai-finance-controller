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
import { httpClient } from './client'

export const realApi = {
  getDashboard: () => httpClient.get<DashboardResponse>('/dashboard'),

  getReconciliation: (params: { page?: number; pageSize?: number; search?: string; status?: string }) => {
    const q = new URLSearchParams()
    if (params.page) q.set('page', String(params.page))
    if (params.pageSize) q.set('page_size', String(params.pageSize))
    if (params.search) q.set('search', params.search)
    if (params.status && params.status !== 'ALL') q.set('status', params.status)
    return httpClient.get<ReconciliationListResponse>(`/reconciliation?${q.toString()}`)
  },

  getReconciliationDetail: (paymentId: string) =>
    httpClient.get<ReconciliationDetailResponse>(`/reconciliation/${paymentId}`),

  getExceptions: () => httpClient.get<ExceptionsResponse>('/exceptions'),

  getExceptionDetail: (caseId: string) => httpClient.get<ExceptionDetailResponse>(`/exceptions/${caseId}`),

  getAudit: (paymentId: string) => httpClient.get<AuditResponse>(`/audit/${paymentId}`),

  getEvaluation: (dataset: 'DEV' | 'HOLDOUT' = 'DEV') =>
    httpClient.get<EvaluationResponse>(`/evaluation?dataset=${dataset}`),

  runReconciliation: () => httpClient.post<RunResponse>('/runs'),
}
