import { NavLink } from 'react-router-dom'
import { LayoutGrid, GitCompareArrows, AlertOctagon, LineChart, ScrollText } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutGrid },
  { to: '/reconciliation', label: 'Reconciliation', icon: GitCompareArrows },
  { to: '/exceptions', label: 'Exceptions', icon: AlertOctagon },
  { to: '/evaluation', label: 'Evaluation', icon: LineChart },
  { to: '/audit', label: 'Audit', icon: ScrollText },
]

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-surface md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-border px-5">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-500 text-[11px] font-bold text-white">
          R
        </div>
        <div className="leading-none">
          <div className="text-sm font-semibold text-ink">ReconcileX</div>
        </div>
      </div>

      <div className="px-5 pb-3 pt-4 text-[11px] font-medium text-ink-faint">
        Payment Reconciliation Controller
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-ink-muted hover:bg-canvas hover:text-ink',
              )
            }
          >
            <Icon size={16} strokeWidth={2} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-5 py-4">
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-status-matchFg opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-status-matchFg" />
          </span>
          System Operational
        </div>
      </div>
    </aside>
  )
}
