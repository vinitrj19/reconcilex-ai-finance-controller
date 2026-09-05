import type { PipelineStageCount } from '@/types'
import { formatNumber } from '@/lib/utils'
import { Database, Wand2, GitBranch, Bot, ShieldCheck, FlagTriangleRight } from 'lucide-react'

const STAGE_ICONS: Record<string, typeof Database> = {
  sources: Database,
  normalization: Wand2,
  deterministic: GitBranch,
  ai: Bot,
  policy: ShieldCheck,
  final: FlagTriangleRight,
}

export function PipelineDiagram({ stages }: { stages: PipelineStageCount[] }) {
  // Group consecutive "sources" stages into one row, rest as individual steps.
  const sourceStages = stages.filter((s) => s.stage === 'sources')
  const restStages = stages.filter((s) => s.stage !== 'sources')

  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-4 text-sm font-semibold text-ink">Reconciliation Pipeline</h3>

      <div className="flex flex-col items-stretch">
        <div className="grid grid-cols-3 gap-3">
          {sourceStages.map((s) => {
            const Icon = STAGE_ICONS[s.stage]
            return (
              <div key={s.label} className="rounded-md border border-border bg-canvas px-3 py-2.5 text-center">
                <Icon size={14} className="mx-auto mb-1 text-ink-faint" aria-hidden="true" />
                <div className="font-mono text-lg font-semibold text-ink">{s.count !== null ? formatNumber(s.count) : '—'}</div>
                <div className="text-[11px] text-ink-muted">{s.label}</div>
              </div>
            )
          })}
        </div>

        {restStages.map((s, i) => {
          const Icon = STAGE_ICONS[s.stage]
          return (
            <div key={s.label} className="flex flex-col items-center">
              <div className="h-5 w-px bg-border-strong" aria-hidden="true" />
              <div className="flex w-full max-w-md items-center gap-3 rounded-md border border-border bg-canvas px-3.5 py-2.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                  <Icon size={14} aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-ink">{s.label}</div>
                  {s.detail && <div className="truncate text-xs text-ink-muted">{s.detail}</div>}
                </div>
                {s.count !== null && (
                  <div className="font-mono text-sm font-semibold text-ink">{formatNumber(s.count)}</div>
                )}
              </div>
              {i === restStages.length - 1 && <div className="h-1" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
