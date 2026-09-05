# ReconcileX — Payment Reconciliation Controller (Frontend)

A finance-operations console for the Multi-Source Payment Reconciliation
Controller. Deterministic-first, AI-assisted-only-for-residual-ambiguity,
policy-controlled, fully auditable.

## Stack

React + TypeScript + Vite + Tailwind CSS + Recharts + Lucide icons.

## Getting started

```bash
npm install
cp .env.example .env
npm run dev
```

By default the app runs against a bundled mock API (`VITE_USE_MOCK_API=true`)
whose fixture data in `src/services/api/mockData/` was generated from a real,
independently-verified DEV evaluation run of the backend project — not
hand-typed numbers. Flip `VITE_USE_MOCK_API=false` and set
`VITE_API_BASE_URL` to point at a running FastAPI backend implementing the
contract in `src/services/api/realApi.ts` / `src/types/index.ts`; no
component code needs to change.

## Structure

```
src/
  components/
    layout/         Sidebar, TopBar, AppShell
    common/          StatusBadge, MetricCard, EvidenceBar, loading/error/empty states
    dashboard/       Overview page building blocks
    reconciliation/  Table, filters, and the transaction evidence drawer
    exceptions/      Exceptions center building blocks
    evaluation/      Metrics, baseline comparison, confusion matrix
    audit/           Audit trail search + timeline
    runs/            Run Reconciliation modal
  pages/             One file per route
  services/api/      client.ts (fetch), realApi.ts, mockApi.ts, index.ts (switch)
  types/             Shared TypeScript contract types
  hooks/             useApi data-fetching hook
  lib/               Formatting helpers, status color/label config
```

## Design principles

- Deterministic-first, AI-only-for-residual-ambiguity is the product's core
  story — the drawer always shows deterministic evidence and margin math
  before any AI recommendation, and the AI panel is explicitly labeled a
  recommendation, never a final decision.
- M6 policy is the sole financial authority. The UI never implies AI moves
  money.
- No fabricated metrics: every number in Overview/Evaluation comes from the
  API layer (mock or real) via typed responses — never hardcoded in a
  component.
- Status is never communicated by color alone (icon + text label on every
  badge).
