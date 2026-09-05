import { FileStack, CheckCircle2, ShieldCheck, ShieldAlert } from 'lucide-react'
import { MetricCard } from '@/components/common/MetricCard'
import type { DashboardMetrics } from '@/types'
import { formatNumber } from '@/lib/utils'

export function KpiRow({ metrics }: { metrics: DashboardMetrics }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard
        label="Transactions Processed"
        value={formatNumber(metrics.transactions_processed)}
        icon={FileStack}
        helpText="Payments in this reconciliation run"
      />
      <MetricCard
        label="Successfully Reconciled"
        value={formatNumber(metrics.reconciled)}
        icon={CheckCircle2}
        emphasis="success"
        helpText="Correctly resolved against ground truth"
      />
      <MetricCard
        label="Safe Automation"
        value={`${metrics.safe_automation_rate.toFixed(1)}%`}
        icon={ShieldCheck}
        helpText="Resolved without review, correctly, with no ownership conflicts"
      />
      <MetricCard
        label="Financial False Positives"
        value={formatNumber(metrics.financial_false_positives)}
        icon={ShieldAlert}
        emphasis={metrics.financial_false_positives === 0 ? 'success' : 'danger'}
        helpText="Unjustified financial matches — the core safety metric"
      />
    </div>
  )
}
