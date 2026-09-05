import { Link } from 'react-router-dom'
import type { ExceptionSummaryItem } from '@/types'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Mono } from '@/components/common/Monospace'
import { formatCurrency } from '@/lib/utils'
import { EmptyState } from '@/components/common/States'

export function RecentExceptions({ items }: { items: ExceptionSummaryItem[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface shadow-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
        <h3 className="text-sm font-semibold text-ink">Recent Exceptions</h3>
        <Link to="/exceptions" className="text-xs font-medium text-brand-500 hover:underline">
          View all
        </Link>
      </div>

      {items.length === 0 ? (
        <EmptyState title="No exceptions" description="Every payment resolved cleanly in this run." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-ink-faint">
              <th className="px-5 py-2 font-medium">Payment ID</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Amount</th>
              <th className="px-3 py-2 font-medium">Reason</th>
              <th className="px-5 py-2 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.case_id} className="border-b border-border last:border-0 hover:bg-canvas">
                <td className="px-5 py-3">
                  <Mono>{e.payment_id}</Mono>
                </td>
                <td className="px-3 py-3">
                  <StatusBadge status={e.status} />
                </td>
                <td className="px-3 py-3 font-mono text-ink">{formatCurrency(e.amount, e.currency)}</td>
                <td className="max-w-xs truncate px-3 py-3 text-ink-muted">{e.reason}</td>
                <td className="px-5 py-3 text-right">
                  <Link
                    to={`/exceptions?case=${e.case_id}`}
                    className="rounded-md border border-border-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-canvas"
                  >
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
