import type { ConfusionMatrixCell, ReconciliationStatus } from '@/types'
import { cn } from '@/lib/utils'

export function ConfusionMatrix({ cells, statuses }: { cells: ConfusionMatrixCell[]; statuses: ReconciliationStatus[] }) {
  const lookup = new Map<string, number>()
  cells.forEach((c) => lookup.set(`${c.expected}|${c.predicted}`, c.count))
  const maxCount = Math.max(1, ...cells.map((c) => c.count))

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-1 text-sm font-semibold text-ink">Confusion Matrix</h3>
      <p className="mb-4 text-xs text-ink-muted">Rows: expected · Columns: predicted</p>
      <table className="min-w-[640px] border-collapse text-xs">
        <thead>
          <tr>
            <th className="w-28 px-2 py-1.5 text-left font-medium text-ink-faint"></th>
            {statuses.map((s) => (
              <th key={s} className="px-2 py-1.5 text-center font-medium text-ink-faint">
                {s.replace('_', ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {statuses.map((exp) => (
            <tr key={exp}>
              <td className="whitespace-nowrap px-2 py-1.5 font-medium text-ink-muted">{exp.replace('_', ' ')}</td>
              {statuses.map((pred) => {
                const count = lookup.get(`${exp}|${pred}`) ?? 0
                const isDiagonal = exp === pred
                const intensity = count === 0 ? 0 : 0.15 + 0.65 * (count / maxCount)
                return (
                  <td
                    key={pred}
                    className={cn(
                      'px-2 py-1.5 text-center font-mono',
                      count === 0 ? 'text-ink-faint' : isDiagonal ? 'font-semibold text-status-matchFg' : 'font-semibold text-status-dangerFg',
                    )}
                    style={{
                      backgroundColor: count === 0 ? 'transparent' : isDiagonal ? `rgba(15,122,87,${intensity})` : `rgba(180,35,24,${intensity})`,
                    }}
                  >
                    {count}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
