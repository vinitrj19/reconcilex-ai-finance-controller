import type { ReconciliationListItem } from '@/types'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Mono } from '@/components/common/Monospace'
import { formatCurrency } from '@/lib/utils'
import { EmptyState } from '@/components/common/States'

interface ReconciliationTableProps {
  items: ReconciliationListItem[]
  onSelect: (paymentId: string) => void
}

export function ReconciliationTable({ items, onSelect }: ReconciliationTableProps) {
  if (items.length === 0) {
    return <EmptyState title="No transactions match these filters" description="Try clearing the search or filter." />
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-card">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-border bg-canvas/60 text-left text-xs text-ink-faint">
            <th className="px-4 py-2.5 font-medium">Payment ID</th>
            <th className="px-3 py-2.5 font-medium">Order ID</th>
            <th className="px-3 py-2.5 font-medium">Settlement ID</th>
            <th className="px-3 py-2.5 font-medium text-right">Payment Amount</th>
            <th className="px-3 py-2.5 font-medium text-right">Settlement Amount</th>
            <th className="px-3 py-2.5 font-medium">Payment Date</th>
            <th className="px-3 py-2.5 font-medium">Settlement Date</th>
            <th className="px-3 py-2.5 font-medium">Decision</th>
            <th className="px-3 py-2.5 font-medium text-right">Confidence</th>
            <th className="px-4 py-2.5 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.payment_id}
              className="cursor-pointer border-b border-border last:border-0 hover:bg-canvas"
              onClick={() => onSelect(item.payment_id)}
            >
              <td className="px-4 py-2.5">
                <Mono>{item.payment_id}</Mono>
              </td>
              <td className="px-3 py-2.5">
                <Mono className="text-ink-muted">{item.order_id ?? '—'}</Mono>
              </td>
              <td className="px-3 py-2.5">
                <Mono className="text-ink-muted">{item.settlement_id ?? '—'}</Mono>
              </td>
              <td className="px-3 py-2.5 text-right font-mono text-ink">
                {formatCurrency(item.payment_amount, item.currency)}
              </td>
              <td className="px-3 py-2.5 text-right font-mono text-ink-muted">
                {item.settlement_amount !== null ? formatCurrency(item.settlement_amount, item.currency) : '—'}
              </td>
              <td className="px-3 py-2.5 text-ink-muted">{item.payment_date}</td>
              <td className="px-3 py-2.5 text-ink-muted">{item.settlement_date ?? '—'}</td>
              <td className="px-3 py-2.5">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-3 py-2.5 text-right font-mono text-ink-muted">
                {item.confidence !== null ? `${Math.round(item.confidence * 100)}%` : '—'}
              </td>
              <td className="px-4 py-2.5 text-right">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelect(item.payment_id)
                  }}
                  className="rounded-md border border-border-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-canvas"
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
