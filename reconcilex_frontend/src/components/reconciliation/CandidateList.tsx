import type { CandidateSettlement, DeterministicResult } from '@/types'
import { Mono } from '@/components/common/Monospace'
import { EvidenceBar } from '@/components/common/EvidenceBar'
import { formatCurrency, cn } from '@/lib/utils'

export function CandidateList({
  candidates,
  acceptedSettlementId,
  deterministic,
  currency,
}: {
  candidates: CandidateSettlement[]
  acceptedSettlementId: string | null
  deterministic: DeterministicResult
  currency: string
}) {
  if (candidates.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No plausible settlement candidates were found for this payment.
      </p>
    )
  }

  const top = candidates[0]
  const isTopAccepted = top.settlement_id === acceptedSettlementId

  return (
    <div className="space-y-3">
      {candidates.map((c, i) => {
        const isTop = i === 0
        const isAccepted = c.settlement_id === acceptedSettlementId
        return (
          <div
            key={c.settlement_id}
            className={cn(
              'rounded-md border p-3.5',
              isAccepted
                ? 'border-status-matchBorder bg-status-matchBg/40'
                : isTop
                  ? 'border-brand-500/40 bg-brand-50/50'
                  : 'border-border bg-canvas',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Mono className="text-sm font-medium">{c.settlement_id}</Mono>
                  {isTop && !isAccepted && (
                    <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                      Strongest candidate
                    </span>
                  )}
                  {isAccepted && (
                    <span className="rounded bg-status-matchBg px-1.5 py-0.5 text-[10px] font-medium text-status-matchFg">
                      Accepted
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-ink-muted">Ref: {c.settlement_reference} · {c.date}</div>
              </div>
              <div className="text-right">
                <div className="font-mono text-sm font-semibold text-ink">{formatCurrency(c.amount, currency)}</div>
                <div className="font-mono text-xs text-ink-faint">score {c.score.toFixed(2)}</div>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-3">
              <EvidenceBar label="Amount" value={c.evidence.amount_similarity} />
              <EvidenceBar label="Date" value={c.evidence.date_proximity} />
              <EvidenceBar label="Reference" value={c.evidence.reference_similarity} />
            </div>
          </div>
        )
      })}

      {deterministic.threshold !== null && (
        <div className="rounded-md border border-border bg-canvas p-3.5 text-xs">
          <div className="mb-2 grid grid-cols-2 gap-y-1.5 sm:grid-cols-4">
            <span className="text-ink-muted">Deterministic score</span>
            <span className="font-mono font-medium text-ink">{deterministic.score?.toFixed(2) ?? '—'}</span>
            <span className="text-ink-muted">Locked threshold</span>
            <span className="font-mono font-medium text-ink">{deterministic.threshold.toFixed(2)}</span>
            <span className="text-ink-muted">Runner-up</span>
            <span className="font-mono font-medium text-ink">{deterministic.runner_up_score?.toFixed(2) ?? '—'}</span>
            <span className="text-ink-muted">Required margin</span>
            <span className="font-mono font-medium text-ink">{deterministic.required_margin?.toFixed(2) ?? '—'}</span>
          </div>
          {deterministic.actual_margin !== null && deterministic.required_margin !== null && (
            <p className={cn('rounded border px-2.5 py-2', deterministic.margin_satisfied ? 'border-status-matchBorder bg-status-matchBg/40 text-status-matchFg' : 'border-status-reviewBorder bg-status-reviewBg/50 text-status-reviewFg')}>
              {deterministic.score !== null && deterministic.score > deterministic.threshold ? (
                <>Score {deterministic.score.toFixed(2)} clears the {deterministic.threshold.toFixed(2)} threshold, </>
              ) : (
                <>Score does not clear the {deterministic.threshold.toFixed(2)} threshold, </>
              )}
              but the actual margin ({deterministic.actual_margin.toFixed(2)}) is{' '}
              {deterministic.margin_satisfied ? 'above' : 'below'} the required margin (
              {deterministic.required_margin.toFixed(2)}) — automatic matching is{' '}
              {deterministic.margin_satisfied ? 'allowed.' : 'not allowed.'}
            </p>
          )}
        </div>
      )}
      {!isTopAccepted && acceptedSettlementId === null && top && (
        <p className="text-xs text-ink-faint">
          The strongest candidate above was not automatically accepted — see the policy decision below for why.
        </p>
      )}
    </div>
  )
}
