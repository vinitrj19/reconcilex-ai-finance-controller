import { TopBar } from '@/components/layout/TopBar'
import { MetricsGrid } from '@/components/evaluation/MetricsGrid'
import { BaselineComparison } from '@/components/evaluation/BaselineComparison'
import { PerClassTable } from '@/components/evaluation/PerClassTable'
import { ConfusionMatrix } from '@/components/evaluation/ConfusionMatrix'
import { MethodologyPanel } from '@/components/evaluation/MethodologyPanel'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { LoadingState, ErrorState } from '@/components/common/States'

export function EvaluationPage() {
  const { data, loading, error, refetch } = useApi(() => api.getEvaluation('DEV'), [])

  return (
    <div>
      <TopBar title="Evaluation Center" subtitle="Performance, safety and reconciliation quality." dataset={data?.dataset} />

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {loading && <LoadingState label="Loading evaluation results…" />}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {data && (
          <>
            <div className="flex items-center gap-2 rounded-md border border-border-strong bg-canvas px-3 py-2 text-xs text-ink-muted">
              <span className="font-mono font-semibold text-ink">{data.dataset}</span>
              — ground truth is available only in this evaluation context, never during normal production operation.
            </div>

            <MetricsGrid metrics={data.metrics} />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <BaselineComparison rows={data.baseline} />
              <PerClassTable rows={data.per_class} />
            </div>

            <ConfusionMatrix cells={data.confusion_matrix} statuses={data.statuses} />
            <MethodologyPanel steps={data.methodology} />
          </>
        )}
      </main>
    </div>
  )
}
