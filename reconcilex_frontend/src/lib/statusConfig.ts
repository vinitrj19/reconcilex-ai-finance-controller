import type { ReconciliationStatus, ExceptionPriority } from '@/types'
import { CheckCircle2, AlertTriangle, XCircle, Copy, HelpCircle, GitMerge } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface StatusVisual {
  label: string
  bg: string
  fg: string
  border: string
  icon: LucideIcon
  // Non-color signal so status is never communicated by color alone.
  glyph: string
}

export const STATUS_VISUALS: Record<ReconciliationStatus, StatusVisual> = {
  MATCH: { label: 'Match', bg: 'bg-status-matchBg', fg: 'text-status-matchFg', border: 'border-status-matchBorder', icon: CheckCircle2, glyph: '✓' },
  PARTIAL_MATCH: { label: 'Partial Match', bg: 'bg-status-partialBg', fg: 'text-status-partialFg', border: 'border-status-partialBorder', icon: GitMerge, glyph: '½' },
  REFUND: { label: 'Refund', bg: 'bg-status-partialBg', fg: 'text-status-partialFg', border: 'border-status-partialBorder', icon: CheckCircle2, glyph: '↺' },
  AMBIGUOUS: { label: 'Ambiguous', bg: 'bg-status-reviewBg', fg: 'text-status-reviewFg', border: 'border-status-reviewBorder', icon: AlertTriangle, glyph: '!' },
  CONFLICT: { label: 'Conflict', bg: 'bg-status-dangerBg', fg: 'text-status-dangerFg', border: 'border-status-dangerBorder', icon: XCircle, glyph: '×' },
  MISSING: { label: 'Missing', bg: 'bg-status-dangerBg', fg: 'text-status-dangerFg', border: 'border-status-dangerBorder', icon: XCircle, glyph: '×' },
  DUPLICATE: { label: 'Duplicate', bg: 'bg-status-dupBg', fg: 'text-status-dupFg', border: 'border-status-dupBorder', icon: Copy, glyph: '⧉' },
  UNRESOLVED: { label: 'Unresolved', bg: 'bg-status-neutralBg', fg: 'text-status-neutralFg', border: 'border-status-neutralBorder', icon: HelpCircle, glyph: '?' },
}

export const PRIORITY_VISUALS: Record<ExceptionPriority, { label: string; bg: string; fg: string }> = {
  HIGH: { label: 'High', bg: 'bg-status-dangerBg', fg: 'text-status-dangerFg' },
  MEDIUM: { label: 'Medium', bg: 'bg-status-reviewBg', fg: 'text-status-reviewFg' },
  LOW: { label: 'Low', bg: 'bg-status-neutralBg', fg: 'text-status-neutralFg' },
}

export const RECONCILIATION_FILTERS: { key: string; label: string; status?: ReconciliationStatus }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'MATCH', label: 'Match', status: 'MATCH' },
  { key: 'PARTIAL_MATCH', label: 'Partial', status: 'PARTIAL_MATCH' },
  { key: 'REVIEW', label: 'Review' },
  { key: 'AMBIGUOUS', label: 'Ambiguous', status: 'AMBIGUOUS' },
  { key: 'MISSING', label: 'Missing', status: 'MISSING' },
  { key: 'DUPLICATE', label: 'Duplicate', status: 'DUPLICATE' },
  { key: 'CONFLICT', label: 'Conflict', status: 'CONFLICT' },
  { key: 'UNRESOLVED', label: 'Unresolved', status: 'UNRESOLVED' },
]
