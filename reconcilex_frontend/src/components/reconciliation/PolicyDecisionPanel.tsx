import type { FinalDecision } from '@/types'
import { ShieldCheck, ShieldX, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

const OUTCOME_CONFIG = {
  MATCH_APPROVED: {
    icon: ShieldCheck,
    headline: 'Match Approved',
    style: 'border-status-matchBorder bg-status-matchBg/50 text-status-matchFg',
    note: 'Policy checks passed.',
  },
  MATCH_REJECTED: {
    icon: ShieldX,
    headline: 'Match Rejected',
    style: 'border-status-dangerBorder bg-status-dangerBg/50 text-status-dangerFg',
    note: 'Policy layer prevented automatic assignment.',
  },
  REVIEW_REQUIRED: {
    icon: ShieldAlert,
    headline: 'Review Required',
    style: 'border-status-reviewBorder bg-status-reviewBg/50 text-status-reviewFg',
    note: 'No automatic financial action taken.',
  },
} as const

export function PolicyDecisionPanel({ decision }: { decision: FinalDecision }) {
  const cfg = OUTCOME_CONFIG[decision.policy_outcome]
  const Icon = cfg.icon

  return (
    <div className={cn('rounded-md border p-4', cfg.style)}>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide opacity-80">Policy Decision</span>
      </div>
      <div className="flex items-center gap-2">
        <Icon size={18} aria-hidden="true" />
        <span className="text-base font-semibold">{cfg.headline}</span>
      </div>
      <p className="mt-1 text-sm font-medium opacity-90">{cfg.note}</p>
      <p className="mt-2 text-sm leading-relaxed opacity-90">{decision.reason}</p>
    </div>
  )
}
