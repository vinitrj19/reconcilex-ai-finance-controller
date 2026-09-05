import { useState } from 'react'
import { Play } from 'lucide-react'
import { RunReconciliationModal } from '@/components/runs/RunReconciliationModal'

interface TopBarProps {
  title: string
  subtitle?: string
  runId?: string
  dataset?: 'DEV' | 'HOLDOUT'
}

export function TopBar({ title, subtitle, runId, dataset }: TopBarProps) {
  const [runOpen, setRunOpen] = useState(false)

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-border bg-surface/95 px-6 backdrop-blur">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-ink">{title}</h1>
        {subtitle && <p className="truncate text-xs text-ink-muted">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {dataset && (
          <span className="rounded-md border border-border-strong bg-canvas px-2 py-1 font-mono text-[11px] font-medium text-ink-muted">
            {dataset}
          </span>
        )}
        {runId && (
          <span className="hidden font-mono text-xs text-ink-faint sm:inline">{runId}</span>
        )}
        <button
          onClick={() => setRunOpen(true)}
          className="flex items-center gap-1.5 rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
        >
          <Play size={13} fill="currentColor" aria-hidden="true" />
          Run Reconciliation
        </button>
      </div>

      {runOpen && <RunReconciliationModal onClose={() => setRunOpen(false)} />}
    </header>
  )
}
