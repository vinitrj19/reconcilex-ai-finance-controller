// Types mirror the FastAPI response contract documented in
// reconciliation-controller-spec.md. The frontend never invents fields
// that aren't part of this contract, and the mock API (mockApi.ts)
// returns data typed identically to what the real backend returns.

export type ReconciliationStatus =
  | 'MATCH'
  | 'PARTIAL_MATCH'
  | 'REFUND'
  | 'CONFLICT'
  | 'MISSING'
  | 'DUPLICATE'
  | 'AMBIGUOUS'
  | 'UNRESOLVED';

export type AnomalyType =
  | 'exact_match'
  | 'date_shift'
  | 'fee_adjusted'
  | 'duplicate'
  | 'missing_settlement'
  | 'missing_payment'
  | 'refund'
  | 'partial_settlement'
  | 'ambiguous'
  | 'unrelated';

export type DecisionSource =
  | 'M1_EXACT_MATCH'
  | 'M2_DETERMINISTIC'
  | 'M4_SCORING'
  | 'M5_AI_REASONING'
  | 'M6_GLOBAL_POLICY';

export type Dataset = 'DEV' | 'HOLDOUT';

export type PolicyOutcome = 'MATCH_APPROVED' | 'MATCH_REJECTED' | 'REVIEW_REQUIRED';

// ---------------------------------------------------------------------------
// Shared record shapes
// ---------------------------------------------------------------------------

export interface PaymentRecord {
  payment_id: string;
  order_id: string | null;
  amount: number;
  currency: string;
  timestamp: string;
  payment_method: string;
  customer_reference: string;
  description: string;
}

export interface OrderRecord {
  order_id: string;
  order_timestamp: string;
  expected_amount: number;
  order_status: string;
  payment_reference: string | null;
  invoice_reference: string | null;
}

export interface SettlementRecord {
  settlement_id: string;
  settlement_reference: string;
  timestamp: string;
  gross_amount: number;
  fee: number;
  tax: number;
  net_amount: number;
  bank_reference: string;
  status: string;
}

export interface EvidenceScore {
  amount_similarity: number; // 0-1
  date_proximity: number; // 0-1
  reference_similarity: number; // 0-1
}

export interface CandidateSettlement {
  settlement_id: string;
  settlement_reference: string;
  amount: number;
  date: string;
  evidence: EvidenceScore;
  score: number;
}

export interface DeterministicResult {
  status: ReconciliationStatus;
  score: number | null;
  threshold: number | null;
  runner_up_score: number | null;
  required_margin: number | null;
  actual_margin: number | null;
  margin_satisfied: boolean | null;
  reason: string;
  rule_id: string | null;
}

export interface AiReasoning {
  invoked: boolean;
  provider: string | null;
  decision: 'MATCH' | 'NO_MATCH' | 'AMBIGUOUS' | null;
  confidence: number | null;
  reasoning: string | null;
  missing_evidence: string[];
  recommended_action: 'ACCEPT' | 'ESCALATE' | 'REQUEST_MORE_DATA' | null;
  unavailable_reason: string | null;
}

export interface FinalDecision {
  status: ReconciliationStatus;
  settlement_id: string | null;
  confidence: number | null;
  decision_source: DecisionSource;
  policy_outcome: PolicyOutcome;
  reason: string;
}

// ---------------------------------------------------------------------------
// GET /api/v1/dashboard
// ---------------------------------------------------------------------------

export interface DashboardMetrics {
  transactions_processed: number;
  reconciled: number;
  safe_automation_rate: number;
  financial_false_positives: number;
}

export interface PipelineStageCount {
  stage: string;
  label: string;
  count: number | null;
  detail?: string;
}

export interface StatusBreakdownEntry {
  status: ReconciliationStatus;
  count: number;
}

export interface DashboardResponse {
  run_id: string;
  dataset: Dataset;
  generated_at: string;
  metrics: DashboardMetrics;
  pipeline: PipelineStageCount[];
  status_breakdown: StatusBreakdownEntry[];
  recent_exceptions: ExceptionSummaryItem[];
}

// ---------------------------------------------------------------------------
// GET /api/v1/reconciliation
// ---------------------------------------------------------------------------

export interface ReconciliationListItem {
  payment_id: string;
  order_id: string | null;
  settlement_id: string | null;
  payment_amount: number;
  settlement_amount: number | null;
  payment_date: string;
  settlement_date: string | null;
  currency: string;
  source: string;
  status: ReconciliationStatus;
  confidence: number | null;
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface ReconciliationListResponse {
  items: ReconciliationListItem[];
  pagination: Pagination;
}

export interface ReconciliationDetailResponse {
  payment: PaymentRecord;
  order: OrderRecord | null;
  settlement: SettlementRecord | null;
  candidates: CandidateSettlement[];
  deterministic: DeterministicResult;
  ai: AiReasoning;
  final_decision: FinalDecision;
}

// ---------------------------------------------------------------------------
// GET /api/v1/exceptions
// ---------------------------------------------------------------------------

export type ExceptionType =
  | 'MISSING_SETTLEMENT'
  | 'MISSING_PAYMENT'
  | 'AMBIGUOUS'
  | 'DUPLICATE'
  | 'CONFLICT'
  | 'UNRESOLVED';

export type ExceptionPriority = 'HIGH' | 'MEDIUM' | 'LOW';

export interface ExceptionSummaryItem {
  case_id: string;
  payment_id: string;
  type: ExceptionType;
  amount: number;
  currency: string;
  reason: string;
  status: ReconciliationStatus;
}

export interface ExceptionListItem extends ExceptionSummaryItem {
  priority: ExceptionPriority;
  candidate_count: number;
  top_candidate_id: string | null;
  ai_invoked: boolean;
  recommended_action: string;
}

export interface ExceptionsSummary {
  total: number;
  high_priority: number;
  review_required: number;
  unresolved: number;
  duplicates: number;
}

export interface ExceptionsResponse {
  items: ExceptionListItem[];
  summary: ExceptionsSummary;
}

export interface ExceptionDetailResponse extends ReconciliationDetailResponse {
  case_id: string;
  investigation_prompts: string[];
}

// ---------------------------------------------------------------------------
// GET /api/v1/audit/{payment_id}
// ---------------------------------------------------------------------------

export interface AuditEvent {
  timestamp: string;
  stage: string;
  rule_id: string | null;
  decision: string;
  notes: string;
  candidate_ids: string[];
}

export interface AuditResponse {
  payment_id: string;
  events: AuditEvent[];
}

// ---------------------------------------------------------------------------
// GET /api/v1/evaluation
// ---------------------------------------------------------------------------

export interface HeadlineEvalMetrics {
  match_rate: number;
  precision: number;
  recall: number;
  f1: number;
  financial_false_positives: number;
  safe_automation_rate: number;
  unresolved_rate: number;
  review_rate: number;
}

export interface BaselineComparisonRow {
  metric: string;
  baseline: number;
  controller: number;
  unit: 'percent' | 'count';
}

export interface PerClassRow {
  anomaly_type: AnomalyType;
  support: number;
  correct: number;
  rate: number;
}

export interface ConfusionMatrixCell {
  expected: ReconciliationStatus;
  predicted: ReconciliationStatus;
  count: number;
}

export interface EvaluationResponse {
  dataset: Dataset;
  evaluation_type: 'FROZEN_HOLDOUT' | 'DEV';
  run_id: string;
  metrics: HeadlineEvalMetrics;
  baseline: BaselineComparisonRow[];
  per_class: PerClassRow[];
  confusion_matrix: ConfusionMatrixCell[];
  statuses: ReconciliationStatus[];
  methodology: string[];
}

// ---------------------------------------------------------------------------
// POST /api/v1/runs
// ---------------------------------------------------------------------------

export interface RunStep {
  key: string;
  label: string;
  status: 'PENDING' | 'RUNNING' | 'DONE';
}

export interface RunSummary {
  run_id: string;
  execution_time_seconds: number;
  records_processed: number;
  matches: number;
  exceptions: number;
}

export interface RunResponse {
  run_id: string;
  status: 'COMPLETED';
  steps: RunStep[];
  summary: RunSummary;
}
