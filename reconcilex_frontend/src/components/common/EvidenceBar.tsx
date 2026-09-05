export function EvidenceBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-ink-muted">{label}</span>
        <span className="font-mono font-medium text-ink">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="h-1.5 rounded-full bg-brand-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
