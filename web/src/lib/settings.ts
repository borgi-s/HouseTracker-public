import type { Criterion, CriterionIn, LifecycleSummary } from '@/api/types'

/** Spec §4.7 "Start with defaults": a starting point, edited in Settings from then on. */
export const DEFAULT_CRITERIA: CriterionIn[] = [
  { key: 'light', label: 'Light', kind: 'subjective', sort: 0 },
  { key: 'layout', label: 'Layout', kind: 'subjective', sort: 1 },
  { key: 'kitchen', label: 'Kitchen', kind: 'subjective', sort: 2 },
  { key: 'bathrooms', label: 'Bathrooms', kind: 'subjective', sort: 3 },
  { key: 'garden', label: 'Garden', kind: 'subjective', sort: 4 },
  { key: 'condition', label: 'Condition', kind: 'subjective', sort: 5 },
  { key: 'neighbourhood', label: 'Neighbourhood', kind: 'subjective', sort: 6 },
  { key: 'noise', label: 'Noise', kind: 'subjective', sort: 7 },
  { key: 'price_per_m2', label: 'Price per m²', kind: 'auto', auto_source: 'price_per_m2', higher_is_better: false, sort: 8 },
  { key: 'ejerudgift_dkk', label: 'Ejerudgift', kind: 'auto', auto_source: 'ejerudgift_dkk', higher_is_better: false, sort: 9 },
  { key: 'size_m2', label: 'Size', kind: 'auto', auto_source: 'size_m2', higher_is_better: true, sort: 10 },
]

/** Numeric house fields an automatic criterion can read (House.auto_value). */
export const AUTO_SOURCES = ['price_per_m2', 'price_dkk', 'ejerudgift_dkk', 'size_m2', 'lot_m2', 'rooms', 'build_year']

/** Move criterion `index` up (-1) or down (+1). Returns the PATCHes that make the
 *  list's sort values 0..n-1 in the new order — criteria added without a sort all sit
 *  at 0, so a plain swap of two values would not move anything. */
export function reorder(list: Criterion[], index: number, delta: -1 | 1): { id: string; sort: number }[] {
  const to = index + delta
  if (to < 0 || to >= list.length) return []
  const order = [...list]
  ;[order[index], order[to]] = [order[to], order[index]]
  return order.flatMap((c, i) => (c.sort === i ? [] : [{ id: c.id, sort: i }]))
}

export const keyFrom = (label: string) =>
  label.trim().toLowerCase()
    .replace(/æ/g, 'ae').replace(/ø/g, 'oe').replace(/å/g, 'aa')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')

/** Each active criterion's weight as a whole percent of the active total — what the
 *  number in the weight field actually means for the overall score. */
export function weightShares(list: Criterion[]): Record<string, number> {
  const active = list.filter(c => c.active)
  const total = active.reduce((n, c) => n + c.weight, 0)
  return Object.fromEntries(active.map(c => [c.id, total ? Math.round((c.weight / total) * 100) : 0]))
}

/** One line for what a lifecycle sweep did; zero counts are left out. */
export function sweepSummary(s: LifecycleSummary): string {
  const parts = [
    [s.marked_sold, 'sold'], [s.priced, 'sale prices found'],
    [s.repriced, 'price changes'], [s.open_new, 'new open houses'],
  ].filter(([n]) => n).map(([n, what]) => `${n} ${what}`)
  return [`Checked ${s.checked}`, ...(parts.length ? parts : ['nothing new'])].join(' · ')
}
