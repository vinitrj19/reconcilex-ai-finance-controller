import type { ExceptionsSummary } from '@/types'
import { MetricCard } from '@/components/common/MetricCard'
import { formatNumber } from '@/lib/utils'
import { ListTree, AlertTriangle, Eye, HelpCircle, Copy } from 'lucide-react'

export function ExceptionsSummaryCards({ summary }: { summary: ExceptionsSummary }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <MetricCard label="Total Exceptions" value={formatNumber(summary.total)} icon={ListTree} />
      <MetricCard label="High Priority" value={formatNumber(summary.high_priority)} icon={AlertTriangle} emphasis={summary.high_priority > 0 ? 'danger' : 'default'} />
      <MetricCard label="Review Required" value={formatNumber(summary.review_required)} icon={Eye} />
      <MetricCard label="Unresolved" value={formatNumber(summary.unresolved)} icon={HelpCircle} />
      <MetricCard label="Duplicates" value={formatNumber(summary.duplicates)} icon={Copy} />
    </div>
  )
}
