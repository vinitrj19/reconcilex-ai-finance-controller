import { useSearchParams } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { AuditSearch } from '@/components/audit/AuditSearch'
import { AuditTimeline } from '@/components/audit/AuditTimeline'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { LoadingState, ErrorState, EmptyState } from '@/components/common/States'

export function AuditPage() {
  const [params, setParams] = useSearchParams()
  const paymentId = params.get('id')

  const { data, loading, error, refetch } = useApi(
    () => (paymentId ? api.getAudit(paymentId) : Promise.resolve(null)),
    [paymentId],
  )

  return (
    <div>
      <TopBar title="Audit Trail" subtitle="Trace every reconciliation decision from input to final policy outcome." />

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-6">
        <AuditSearch initial={paymentId ?? ''} onSearch={(id) => setParams({ id })} />

        {!paymentId && (
          <EmptyState
            title="Search for a transaction"
            description="Enter a Payment ID, Order ID, or Settlement ID to trace its full decision chain — from normalization through the final M6 policy outcome."
          />
        )}

        {paymentId && loading && <LoadingState label="Loading audit trail…" />}
        {paymentId && error && <ErrorState message={error} onRetry={refetch} />}
        {data && <AuditTimeline paymentId={data.payment_id} events={data.events} />}
      </main>
    </div>
  )
}
