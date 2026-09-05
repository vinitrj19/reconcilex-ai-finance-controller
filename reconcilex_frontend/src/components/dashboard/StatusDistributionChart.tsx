import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { StatusBreakdownEntry } from '@/types'
import { STATUS_VISUALS } from '@/lib/statusConfig'

const HEX: Record<string, string> = {
  MATCH: '#0F7A57',
  PARTIAL_MATCH: '#1D4ED8',
  REFUND: '#1D4ED8',
  AMBIGUOUS: '#B45309',
  CONFLICT: '#B42318',
  MISSING: '#B42318',
  DUPLICATE: '#6941C6',
  UNRESOLVED: '#475467',
}

export function StatusDistributionChart({ data }: { data: StatusBreakdownEntry[] }) {
  const chartData = data.map((d) => ({ name: STATUS_VISUALS[d.status].label, status: d.status, count: d.count }))

  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <h3 className="mb-4 text-sm font-semibold text-ink">Status Distribution</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={92}
            tick={{ fontSize: 12, fill: '#475467' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: '#F6F7F9' }}
            contentStyle={{ borderRadius: 8, borderColor: '#E4E7EC', fontSize: 12 }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16}>
            {chartData.map((entry) => (
              <Cell key={entry.status} fill={HEX[entry.status]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
