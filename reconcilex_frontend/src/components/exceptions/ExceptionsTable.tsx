import type { ExceptionListItem } from '@/types'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Mono } from '@/components/common/Monospace'
import { PRIORITY_VISUALS } from '@/lib/statusConfig'
import { formatCurrency, cn } from '@/lib/utils'
import { EmptyState } from '@/components/common/States'

const TYPE_LABELS: Record<string, string> = {
  MISSING_SETTLEMENT: 'Missing Settlement',
  MISSING_PAYMENT: 'Missing Payment',
  AMBIGUOUS: 'Ambiguous',
  DUPLICATE: 'Duplicate',
  CONFLICT: 'Conflict',
  UNRESOLVED: 'Unresolved',
}

export function ExceptionsTable({
  items,
  onSelect,
}: {
  items: ExceptionListItem[]
  onSelect: (caseId: string) => void
}) {
  if (items.length === 0) {
    return <EmptyState title="No exceptions" description="Nothing requires investigation right now." />
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-card">
      <table className="w-full min-w-[820px] text-sm">
        <thead>
          <tr className="border-b border-border bg-canvas/60 text-left text-xs text-ink-faint">
            <th className="px-4 py-2.5 font-medium">Case ID</th>
            <th className="px-3 py-2.5 font-medium">Type</th>
            <th className="px-3 py-2.5 font-medium">Payment</th>
            <th className="px-3 py-2.5 font-medium text-right">Amount</th>
            <th className="px-3 py-2.5 font-medium">Priority</th>
            <th className="px-3 py-2.5 font-medium">Reason</th>
            <th className="px-3 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => {
            const pv = PRIORITY_VISUALS[e.priority]
            return (
              <tr key={e.case_id} className="cursor-pointer border-b border-border last:border-0 hover:bg-canvas" onClick={() => onSelect(e.case_id)}>
                <td className="px-4 py-2.5"><Mono>{e.case_id}</Mono></td>
                <td className="px-3 py-2.5 text-ink-muted">{TYPE_LABELS[e.type] ?? e.type}</td>
                <td className="px-3 py-2.5"><Mono className="text-ink-muted">{e.payment_id}</Mono></td>
                <td className="px-3 py-2.5 text-right font-mono text-ink">{formatCurrency(e.amount, e.currency)}</td>
                <td className="px-3 py-2.5">
                  <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium', pv.bg, pv.fg)}>{pv.label}</span>
                </td>
                <td className="max-w-xs truncate px-3 py-2.5 text-ink-muted">{e.reason}</td>
                <td className="px-3 py-2.5"><StatusBadge status={e.status} /></td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={(ev) => { ev.stopPropagation(); onSelect(e.case_id) }}
                    className="rounded-md border border-border-strong px-2.5 py-1 text-xs font-medium text-ink hover:bg-canvas"
                  >
                    Investigate
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
