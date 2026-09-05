import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { BaselineComparisonRow } from '@/types'

export function BaselineComparison({ rows }: { rows: BaselineComparisonRow[] }) {
  const chartData = rows.map((r) => ({
    metric: r.metric,
    Baseline: r.unit === 'percent' ? Math.round(r.baseline * 1000) / 10 : r.baseline,
    Controller: r.unit === 'percent' ? Math.round(r.controller * 1000) / 10 : r.controller,
  }))

  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-1 text-sm font-semibold text-ink">Baseline vs Controller</h3>
      <p className="mb-4 text-xs text-ink-muted">Naive baseline: exact payment ID → settlement reference match.</p>

      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} margin={{ left: -12, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4E7EC" vertical={false} />
          <XAxis dataKey="metric" tick={{ fontSize: 11, fill: '#475467' }} axisLine={{ stroke: '#E4E7EC' }} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#475467' }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 8, borderColor: '#E4E7EC', fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="Baseline" fill="#98A2B3" radius={[4, 4, 0, 0]} maxBarSize={28} />
          <Bar dataKey="Controller" fill="#1E3A5F" radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>

      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-ink-faint">
            <th className="py-1.5 font-medium">Metric</th>
            <th className="py-1.5 text-right font-medium">Baseline</th>
            <th className="py-1.5 text-right font-medium">Controller</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.metric} className="border-b border-border last:border-0">
              <td className="py-2 text-ink-muted">{r.metric}</td>
              <td className="py-2 text-right font-mono text-ink">
                {r.unit === 'percent' ? `${(r.baseline * 100).toFixed(1)}%` : r.baseline}
              </td>
              <td className="py-2 text-right font-mono font-medium text-ink">
                {r.unit === 'percent' ? `${(r.controller * 100).toFixed(1)}%` : r.controller}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
