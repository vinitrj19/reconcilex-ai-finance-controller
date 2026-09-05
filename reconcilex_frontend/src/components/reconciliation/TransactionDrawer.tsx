import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { X } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Mono } from '@/components/common/Monospace'
import { LoadingState, ErrorState } from '@/components/common/States'
import { CandidateList } from './CandidateList'
import { AiReasoningPanel } from './AiReasoningPanel'
import { PolicyDecisionPanel } from './PolicyDecisionPanel'
import { formatCurrency } from '@/lib/utils'

export function TransactionDrawer({ paymentId, onClose }: { paymentId: string; onClose: () => void }) {
  const { data, loading, error, refetch } = useApi(() => api.getReconciliationDetail(paymentId), [paymentId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden="true" />

      <div className="drawer-panel relative flex h-full w-full max-w-xl flex-col border-l border-border bg-surface shadow-drawer sm:w-[36rem]">
        {loading && <LoadingState label="Loading transaction evidence…" />}
        {error && (
          <div className="p-6">
            <ErrorState message={error} onRetry={refetch} />
          </div>
        )}

        {data && (
          <>
            <div className="flex items-start justify-between border-b border-border px-6 py-4">
              <div>
                <Mono className="text-base font-semibold">{data.payment.payment_id}</Mono>
                <div className="mt-1.5">
                  <StatusBadge status={data.final_decision.status} />
                </div>
              </div>
              <button onClick={onClose} className="rounded-md p-1.5 text-ink-faint hover:bg-canvas hover:text-ink" aria-label="Close drawer">
                <X size={18} />
              </button>
            </div>

            <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">
              {/* Section 1 — Payment */}
              <Section title="Payment">
                <Field label="Payment ID"><Mono>{data.payment.payment_id}</Mono></Field>
                <Field label="Amount">{formatCurrency(data.payment.amount, data.payment.currency)}</Field>
                <Field label="Currency">{data.payment.currency}</Field>
                <Field label="Payment date">{new Date(data.payment.timestamp).toLocaleString()}</Field>
                <Field label="Reference">{data.payment.customer_reference}</Field>
                <Field label="Payment method">{data.payment.payment_method}</Field>
              </Section>

              {/* Section 2 — Order */}
              <Section title="Order">
                {data.order ? (
                  <>
                    <Field label="Order ID"><Mono>{data.order.order_id}</Mono></Field>
                    <Field label="Order amount">{formatCurrency(data.order.expected_amount, data.payment.currency)}</Field>
                    <Field label="Order date">{new Date(data.order.order_timestamp).toLocaleDateString()}</Field>
                    <Field label="Order reference">{data.order.invoice_reference ?? '—'}</Field>
                  </>
                ) : (
                  <p className="text-sm text-ink-muted">No order linked.</p>
                )}
              </Section>

              {/* Section 3 — Settlement */}
              <Section title="Settlement">
                {data.settlement ? (
                  <>
                    <Field label="Settlement ID"><Mono>{data.settlement.settlement_id}</Mono></Field>
                    <Field label="Settlement amount">{formatCurrency(data.settlement.gross_amount, data.payment.currency)}</Field>
                    <Field label="Settlement date">{new Date(data.settlement.timestamp).toLocaleDateString()}</Field>
                    <Field label="Settlement reference">{data.settlement.settlement_reference}</Field>
                  </>
                ) : (
                  <p className="text-sm font-medium text-ink-muted">No settlement linked</p>
                )}
              </Section>

              {/* Section 4 — Candidate matches + evidence */}
              <Section title="Candidate Matches & Evidence">
                <CandidateList
                  candidates={data.candidates}
                  acceptedSettlementId={data.final_decision.settlement_id}
                  deterministic={data.deterministic}
                  currency={data.payment.currency}
                />
              </Section>

              {/* AI reasoning */}
              <Section title="AI Reasoning">
                <AiReasoningPanel ai={data.ai} />
              </Section>

              {/* Final policy decision */}
              <Section title="" noBorder>
                <PolicyDecisionPanel decision={data.final_decision} />
              </Section>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Section({ title, children, noBorder }: { title: string; children: ReactNode; noBorder?: boolean }) {
  return (
    <div className={noBorder ? 'mb-2' : 'mb-6 border-b border-border pb-6'}>
      {title && <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">{title}</h3>}
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink-muted">{label}</span>
      <span className="text-ink">{children}</span>
    </div>
  )
}
