import type { AiReasoning } from '@/types'
import { Bot, CircleOff } from 'lucide-react'

export function AiReasoningPanel({ ai }: { ai: AiReasoning }) {
  if (!ai.invoked) {
    return (
      <div className="flex items-start gap-2.5 rounded-md border border-border bg-canvas p-3.5 text-sm text-ink-muted">
        <CircleOff size={15} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />
        <div>
          <p className="font-medium text-ink">AI reasoning not invoked</p>
          <p className="mt-0.5 text-xs">
            {ai.unavailable_reason ?? 'This record was resolved deterministically before reaching the AI layer.'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-md border border-border bg-canvas p-3.5">
      <div className="mb-3 flex items-center gap-2">
        <Bot size={14} className="text-brand-500" aria-hidden="true" />
        <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">AI Provider</span>
        <span className="font-mono text-xs text-ink">{ai.provider}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-ink-muted">AI Recommendation</div>
          <div className="font-mono font-semibold text-ink">{ai.decision}</div>
        </div>
        <div>
          <div className="text-xs text-ink-muted">Confidence</div>
          <div className="font-mono font-semibold text-ink">
            {ai.confidence !== null ? `${Math.round(ai.confidence * 100)}%` : '—'}
          </div>
        </div>
      </div>

      {ai.reasoning && (
        <div className="mt-3">
          <div className="text-xs text-ink-muted">Reasoning</div>
          <p className="mt-1 text-sm text-ink">{ai.reasoning}</p>
        </div>
      )}

      {ai.missing_evidence.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-ink-muted">Missing evidence</div>
          <p className="mt-1 text-sm text-ink">{ai.missing_evidence.join(', ')}</p>
        </div>
      )}

      {ai.recommended_action && (
        <div className="mt-3">
          <div className="text-xs text-ink-muted">Recommended action</div>
          <p className="mt-1 text-sm text-ink">{ai.recommended_action}</p>
        </div>
      )}

      <p className="mt-3 border-t border-border pt-2.5 text-[11px] text-ink-faint">
        This is a recommendation only. The M6 policy layer below makes the final decision and can decline to follow it.
      </p>
    </div>
  )
}
