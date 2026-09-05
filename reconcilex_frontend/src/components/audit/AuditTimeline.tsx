import type { AuditEvent } from '@/types'
import { Mono } from '@/components/common/Monospace'
import { formatTimestamp } from '@/lib/utils'
import { EmptyState } from '@/components/common/States'

const STAGE_LABELS: Record<string, string> = {
  normalization: 'NORMALIZATION',
  N_FK_UNRESOLVED: 'NORMALIZATION',
  M1_EXACT_MATCH: 'EXACT MATCH',
  M2_DETERMINISTIC: 'DETERMINISTIC RULES',
  M3_CANDIDATE_GENERATION: 'CANDIDATE GENERATION',
  M4_SCORING: 'SCORING',
  M5_AI_REASONING: 'AI REASONING',
  M6_GLOBAL_POLICY: 'M6 POLICY',
}

export function AuditTimeline({ paymentId, events }: { paymentId: string; events: AuditEvent[] }) {
  if (events.length === 0) {
    return <EmptyState title="No audit trail found" description={`No events recorded for ${paymentId}.`} />
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm font-semibold text-ink">Audit Trail</span>
        <Mono className="text-ink-muted">{paymentId}</Mono>
      </div>

      <ol className="relative ml-2 space-y-5 border-l border-border pl-5">
        {events.map((e, i) => (
          <li key={i} className="relative">
            <span className="absolute -left-[25px] top-0.5 flex h-3 w-3 items-center justify-center rounded-full border-2 border-surface bg-brand-500" />
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-xs text-ink-faint">{formatTimestamp(e.timestamp)}</span>
              <span className="text-xs font-semibold tracking-wide text-brand-700">
                {STAGE_LABELS[e.stage] ?? STAGE_LABELS[e.rule_id ?? ''] ?? e.stage.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="mt-1 text-sm text-ink">{e.notes}</p>
            {e.candidate_ids.length > 0 && (
              <p className="mt-1 text-xs text-ink-muted">
                Candidates: <Mono className="text-ink-muted">{e.candidate_ids.join(', ')}</Mono>
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
