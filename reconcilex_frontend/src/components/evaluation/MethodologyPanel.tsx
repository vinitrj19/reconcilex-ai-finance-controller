import { CheckCircle2 } from 'lucide-react'

export function MethodologyPanel({ steps }: { steps: string[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-1 text-sm font-semibold text-ink">Evaluation Protocol</h3>
      <p className="mb-4 text-xs text-ink-muted">
        Ground truth is only available in this evaluation context — never during normal production
        operation.
      </p>
      <ol className="space-y-2.5">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm text-ink-muted">
            <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-status-matchFg" aria-hidden="true" />
            <span>{step}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
