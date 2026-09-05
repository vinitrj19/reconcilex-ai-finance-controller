import type { ReconciliationStatus } from '@/types'
import { STATUS_VISUALS } from '@/lib/statusConfig'
import { cn } from '@/lib/utils'

export function StatusBadge({ status, className }: { status: ReconciliationStatus; className?: string }) {
  const v = STATUS_VISUALS[status]
  const Icon = v.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium',
        v.bg,
        v.fg,
        v.border,
        className,
      )}
    >
      <Icon size={12} strokeWidth={2.5} aria-hidden="true" />
      {v.label}
    </span>
  )
}
