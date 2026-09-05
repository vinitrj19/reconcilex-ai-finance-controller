import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { FilterBar } from '@/components/reconciliation/FilterBar'
import { ReconciliationTable } from '@/components/reconciliation/ReconciliationTable'
import { TransactionDrawer } from '@/components/reconciliation/TransactionDrawer'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { LoadingState, ErrorState } from '@/components/common/States'

export function ReconciliationPage() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('ALL')
  const [page, setPage] = useState(1)
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('payment')

  const { data, loading, error, refetch } = useApi(
    () => api.getReconciliation({ page, pageSize: 20, search, status: filter }),
    [page, search, filter],
  )

  return (
    <div>
      <TopBar title="Reconciliation" subtitle="Review payment-to-settlement decisions and supporting evidence." />

      <main className="mx-auto max-w-7xl space-y-4 px-6 py-6">
        <FilterBar
          search={search}
          onSearchChange={(v) => { setSearch(v); setPage(1) }}
          activeFilter={filter}
          onFilterChange={(v) => { setFilter(v); setPage(1) }}
        />

        {loading && <LoadingState label="Loading reconciliation results…" />}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {data && (
          <>
            <ReconciliationTable
              items={data.items}
              onSelect={(id) => setParams({ payment: id })}
            />

            <div className="flex items-center justify-between text-xs text-ink-muted">
              <span>
                Showing {data.items.length} of {data.pagination.total} transactions
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  disabled={page >= data.pagination.pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </main>

      {selectedId && <TransactionDrawer paymentId={selectedId} onClose={() => setParams({})} />}
    </div>
  )
}
