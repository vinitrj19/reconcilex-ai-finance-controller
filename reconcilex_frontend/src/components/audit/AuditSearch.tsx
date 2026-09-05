import { useState } from 'react'
import { Search } from 'lucide-react'

export function AuditSearch({ onSearch, initial }: { onSearch: (id: string) => void; initial?: string }) {
  const [value, setValue] = useState(initial ?? '')

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (value.trim()) onSearch(value.trim())
      }}
      className="flex gap-2"
    >
      <div className="relative w-full max-w-md">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Search by Payment ID, Order ID, or Settlement ID…"
          className="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500"
        />
      </div>
      <button type="submit" className="rounded-md bg-brand-500 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-brand-600">
        Trace
      </button>
    </form>
  )
}
