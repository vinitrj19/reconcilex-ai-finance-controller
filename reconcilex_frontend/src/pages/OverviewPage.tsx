import { TopBar } from '@/components/layout/TopBar'
import { KpiRow } from '@/components/dashboard/KpiRow'
import { PipelineDiagram } from '@/components/dashboard/PipelineDiagram'
import { StatusDistributionChart } from '@/components/dashboard/StatusDistributionChart'
import { RecentExceptions } from '@/components/dashboard/RecentExceptions'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { LoadingState, ErrorState } from '@/components/common/States'

export function OverviewPage() {
  const { data, loading, error, refetch } = useApi(() => api.getDashboard(), [])

  return (
    <div>
      <TopBar
        title="Reconciliation Overview"
        subtitle="Multi-source payment reconciliation control center"
        runId={data?.run_id}
        dataset={data?.dataset}
      />

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {loading && <LoadingState label="Loading reconciliation overview…" />}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {data && (
          <>
            <KpiRow metrics={data.metrics} />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
              <div className="lg:col-span-3">
                <PipelineDiagram stages={data.pipeline} />
              </div>
              <div className="lg:col-span-2">
                <StatusDistributionChart data={data.status_breakdown} />
              </div>
            </div>

            <RecentExceptions items={data.recent_exceptions} />
          </>
        )}
      </main>
    </div>
  )
}
