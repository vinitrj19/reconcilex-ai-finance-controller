import { useSearchParams } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { ExceptionsSummaryCards } from '@/components/exceptions/ExceptionsSummary'
import { ExceptionsTable } from '@/components/exceptions/ExceptionsTable'
import { TransactionDrawer } from '@/components/reconciliation/TransactionDrawer'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { LoadingState, ErrorState } from '@/components/common/States'

export function ExceptionsPage() {
  const [params, setParams] = useSearchParams()
  const activeCase = params.get('case')

  const { data, loading, error, refetch } = useApi(() => api.getExceptions(), [])
  const activeItem = data?.items.find((i) => i.case_id === activeCase)

  return (
    <div>
      <TopBar title="Exceptions" subtitle="Cases requiring investigation because the controller could not safely resolve them." />

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {loading && <LoadingState label="Loading exceptions…" />}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {data && (
          <>
            <ExceptionsSummaryCards summary={data.summary} />
            <ExceptionsTable items={data.items} onSelect={(caseId) => setParams({ case: caseId })} />
          </>
        )}
      </main>

      {activeItem && (
        <TransactionDrawer paymentId={activeItem.payment_id} onClose={() => setParams({})} />
      )}
    </div>
  )
}
