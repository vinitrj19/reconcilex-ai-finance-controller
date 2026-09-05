import type { PerClassRow } from '@/types'

const LABELS: Record<string, string> = {
  exact_match: 'Exact Match',
  date_shift: 'Date Shift',
  fee_adjusted: 'Fee Adjusted',
  duplicate: 'Duplicate',
  missing_settlement: 'Missing Settlement',
  missing_payment: 'Missing Payment',
  refund: 'Refund',
  partial_settlement: 'Partial Settlement',
  ambiguous: 'Ambiguous',
  unrelated: 'Unrelated',
}

export function PerClassTable({ rows }: { rows: PerClassRow[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-4 text-sm font-semibold text-ink">Per-Class Performance</h3>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.anomaly_type} className="flex items-center gap-3">
            <span className="w-36 shrink-0 text-xs text-ink-muted">{LABELS[r.anomaly_type] ?? r.anomaly_type}</span>
            <div className="h-2 flex-1 rounded-full bg-border">
              <div className="h-2 rounded-full bg-brand-500" style={{ width: `${r.rate * 100}%` }} />
            </div>
            <span className="w-20 shrink-0 text-right font-mono text-xs text-ink">
              {r.correct}/{r.support}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
