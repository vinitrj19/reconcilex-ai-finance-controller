import { Search } from 'lucide-react'
import { RECONCILIATION_FILTERS } from '@/lib/statusConfig'
import { cn } from '@/lib/utils'

interface FilterBarProps {
  search: string
  onSearchChange: (v: string) => void
  activeFilter: string
  onFilterChange: (v: string) => void
}

export function FilterBar({ search, onSearchChange, activeFilter, onFilterChange }: FilterBarProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-xs">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search payment, order, settlement ID…"
          className="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500"
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {RECONCILIATION_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => onFilterChange(f.key)}
            className={cn(
              'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
              activeFilter === f.key
                ? 'border-brand-500 bg-brand-50 text-brand-700'
                : 'border-border bg-surface text-ink-muted hover:bg-canvas',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>
    </div>
  )
}
