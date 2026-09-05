import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { OverviewPage } from '@/pages/OverviewPage'
import { ReconciliationPage } from '@/pages/ReconciliationPage'
import { ExceptionsPage } from '@/pages/ExceptionsPage'
import { EvaluationPage } from '@/pages/EvaluationPage'
import { AuditPage } from '@/pages/AuditPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/reconciliation" element={<ReconciliationPage />} />
          <Route path="/exceptions" element={<ExceptionsPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
