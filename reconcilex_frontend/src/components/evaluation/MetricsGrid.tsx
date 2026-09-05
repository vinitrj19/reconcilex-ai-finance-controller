import type { HeadlineEvalMetrics } from '@/types'
import { MetricCard } from '@/components/common/MetricCard'
import { formatPercent } from '@/lib/utils'

export function MetricsGrid({ metrics }: { metrics: HeadlineEvalMetrics }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <MetricCard label="Match Rate" value={formatPercent(metrics.match_rate)} />
      <MetricCard label="Precision" value={formatPercent(metrics.precision)} />
      <MetricCard label="Recall" value={formatPercent(metrics.recall)} />
      <MetricCard label="F1" value={formatPercent(metrics.f1)} />
      <MetricCard
        label="Financial False Positives"
        value={String(metrics.financial_false_positives)}
        emphasis={metrics.financial_false_positives === 0 ? 'success' : 'danger'}
      />
      <MetricCard label="Safe Automation" value={formatPercent(metrics.safe_automation_rate)} />
      <MetricCard label="Unresolved Rate" value={formatPercent(metrics.unresolved_rate)} />
      <MetricCard label="Review Rate" value={formatPercent(metrics.review_rate)} />
    </div>
  )
}
