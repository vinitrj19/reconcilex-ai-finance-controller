import { useEffect, useState } from 'react'
import { X, CheckCircle2, Loader2 } from 'lucide-react'
import { api } from '@/services/api'
import type { RunResponse } from '@/types'
import { formatNumber } from '@/lib/utils'

const STEP_LABELS = [
  'Loading sources',
  'Normalizing records',
  'Generating candidates',
  'Running deterministic rules',
  'Evaluating residual ambiguity',
  'Applying policy',
  'Writing audit records',
]

export function RunReconciliationModal({ onClose }: { onClose: () => void }) {
  const [running, setRunning] = useState(true)
  const [result, setResult] = useState<RunResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    api.runReconciliation().then((res) => {
      if (cancelled) return
      setResult(res)
      setRunning(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-surface shadow-drawer">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="text-sm font-semibold text-ink">Run Reconciliation</h2>
          <button onClick={onClose} className="text-ink-faint hover:text-ink" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-5">
          {running ? (
            <div className="space-y-3">
              {STEP_LABELS.map((label) => (
                <div key={label} className="flex items-center gap-2.5 text-sm text-ink-muted">
                  <Loader2 size={14} className="animate-spin text-brand-500" aria-hidden="true" />
                  {label}
                </div>
              ))}
              <p className="pt-1 text-xs text-ink-faint">
                The backend executes this pipeline synchronously — steps are shown together rather than
                simulated as independent background jobs.
              </p>
            </div>
          ) : result ? (
            <div>
              <div className="mb-4 flex items-center gap-2 text-status-matchFg">
                <CheckCircle2 size={18} aria-hidden="true" />
                <span className="text-sm font-semibold">Run completed</span>
              </div>
              <dl className="grid grid-cols-2 gap-y-3 text-sm">
                <dt className="text-ink-muted">Run ID</dt>
                <dd className="text-right font-mono text-xs text-ink">{result.run_id}</dd>
                <dt className="text-ink-muted">Execution time</dt>
                <dd className="text-right font-mono text-ink">{result.summary.execution_time_seconds}s</dd>
                <dt className="text-ink-muted">Records processed</dt>
                <dd className="text-right font-mono text-ink">{formatNumber(result.summary.records_processed)}</dd>
                <dt className="text-ink-muted">Matches</dt>
                <dd className="text-right font-mono text-ink">{formatNumber(result.summary.matches)}</dd>
                <dt className="text-ink-muted">Exceptions</dt>
                <dd className="text-right font-mono text-ink">{formatNumber(result.summary.exceptions)}</dd>
              </dl>
            </div>
          ) : null}
        </div>

        <div className="flex justify-end border-t border-border px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-md bg-brand-500 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
