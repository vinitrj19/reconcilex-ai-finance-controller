import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: string
  helpText?: string
  icon?: LucideIcon
  emphasis?: 'default' | 'success' | 'danger'
  className?: string
}

const emphasisStyles: Record<NonNullable<MetricCardProps['emphasis']>, string> = {
  default: 'text-ink',
  success: 'text-status-matchFg',
  danger: 'text-status-dangerFg',
}

export function MetricCard({ label, value, helpText, icon: Icon, emphasis = 'default', className }: MetricCardProps) {
  return (
    <div className={cn('rounded-lg border border-border bg-surface p-4 shadow-card', className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</span>
        {Icon && <Icon size={15} className="text-ink-faint" strokeWidth={2} aria-hidden="true" />}
      </div>
      <div className={cn('mt-2 font-mono text-2xl font-semibold tabular-nums', emphasisStyles[emphasis])}>
        {value}
      </div>
      {helpText && <div className="mt-1 text-xs text-ink-muted">{helpText}</div>}
    </div>
  )
}
