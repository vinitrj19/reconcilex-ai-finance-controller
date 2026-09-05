import { Loader2, AlertCircle, Inbox } from 'lucide-react'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-ink-muted">
      <Loader2 size={20} className="animate-spin" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-status-dangerBorder bg-status-dangerBg/40 py-16 text-center">
      <AlertCircle size={20} className="text-status-dangerFg" aria-hidden="true" />
      <div>
        <p className="text-sm font-medium text-ink">Couldn't load this data</p>
        <p className="mt-1 text-xs text-ink-muted">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md border border-border-strong bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-canvas"
        >
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <Inbox size={20} className="text-ink-faint" aria-hidden="true" />
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && <p className="max-w-sm text-xs text-ink-muted">{description}</p>}
    </div>
  )
}
