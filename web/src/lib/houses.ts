import type { HouseListItem, Status } from '@/api/types'
import { STATUS_LABELS } from '@/api/types'
import { combined } from './format'

export type HouseFilter = 'active' | Status
export const ACTIVE_STATUSES: Status[] = ['not_visited', 'visited', 'shortlist', 'offer']
export const ARCHIVE_STATUSES: Status[] = ['rejected', 'sold']

export function filterHouses(houses: HouseListItem[], filter: HouseFilter): HouseListItem[] {
  if (filter === 'active') return houses.filter(h => ACTIVE_STATUSES.includes(h.status))
  return houses.filter(h => h.status === filter)
}

export interface Chip { filter: HouseFilter; label: string; count: number }

/** The list's status chips: Active always, then each status that holds a house (an empty
 *  Offer chip would sit there for months) or is the one picked. */
export function statusChips(houses: HouseListItem[], picked?: HouseFilter): Chip[] {
  const chip = (filter: HouseFilter, label: string): Chip => ({ filter, label, count: filterHouses(houses, filter).length })
  return [
    chip('active', 'Active'),
    ...[...ACTIVE_STATUSES, ...ARCHIVE_STATUSES].map(s => chip(s, STATUS_LABELS[s])),
  ].filter((c, i) => i === 0 || c.count > 0 || c.filter === picked)
}

export interface Narrow {
  area?: string | null; maxPrice?: number | null; minSize?: number | null
  minRooms?: number | null; minBaths?: number | null; openHouse?: boolean
}

/** A house missing the number being filtered on stays in: hiding it would read as lost. */
const within = (v: number | null, min?: number | null, max?: number | null) =>
  v == null || ((!min || v >= min) && (!max || v <= max))

/** Area (a postal code), price ceiling, size/rooms/bathroom floors, an open house coming up. */
export const narrow = (houses: HouseListItem[], f: Narrow) => houses.filter(h =>
  (!f.area || h.postal_code === f.area) && within(h.price_dkk, null, f.maxPrice)
  && within(h.size_m2, f.minSize) && within(h.rooms, f.minRooms) && within(h.bathrooms, f.minBaths)
  && (!f.openHouse || h.open_houses.some(s => !s.cancelled)))

/** The Area picker: each postal code we have a house in, with its town. */
export function areas(houses: HouseListItem[]): { code: string; label: string }[] {
  const towns = new Map(houses.filter(h => h.postal_code).map(h => [h.postal_code!, h.city]))
  return [...towns].sort(([a], [b]) => a.localeCompare(b))
    .map(([code, city]) => ({ code, label: city ? `${code} ${city}` : code }))
}

/** The Max price picker: half-million steps from the cheapest house up to the dearest. */
export function priceSteps(houses: HouseListItem[], step = 500_000): number[] {
  const prices = houses.flatMap(h => (h.price_dkk == null ? [] : [h.price_dkk]))
  if (!prices.length) return []
  const lo = Math.ceil(Math.min(...prices) / step)
  const hi = Math.ceil(Math.max(...prices) / step)
  return Array.from({ length: hi - lo + 1 }, (_, i) => (lo + i) * step)
}

export type SortKey = 'combined' | 'mine' | 'price' | 'ppm2' | 'newest' | 'disagreement'
export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'combined', label: 'Combined score' },
  { key: 'mine', label: 'My score' },
  { key: 'price', label: 'Price' },
  { key: 'ppm2', label: 'Price per m²' },
  { key: 'newest', label: 'Newest' },
  { key: 'disagreement', label: 'Most disagreement' },
]

/** [largest single gap, sum of gaps]; houses nobody disagrees on sort last. */
export function disagreementKey(d: Record<string, number>): [number, number] {
  const gaps = Object.values(d)
  return gaps.length ? [Math.max(...gaps), gaps.reduce((s, g) => s + g, 0)] : [-1, -1]
}

/** Sorts a copy. Missing values always go last; scores high-first, prices low-first. */
export function sortHouses(houses: HouseListItem[], key: SortKey, meId: string | null,
                           pairIds: string[]): HouseListItem[] {
  if (key === 'disagreement') {
    return [...houses].sort((x, y) => {
      const [x1, x2] = disagreementKey(x.disagreement)
      const [y1, y2] = disagreementKey(y.disagreement)
      return y1 - x1 || y2 - x2
    })
  }
  const position = new Map(houses.map((h, i) => [h.id, i]))
  const value = (h: HouseListItem): number | null => {
    switch (key) {
      case 'combined': return combined(h.overall, pairIds)
      case 'mine': return meId ? (h.overall[meId] ?? null) : null
      case 'price': return h.price_dkk
      case 'ppm2': return h.price_per_m2
      case 'newest': return position.get(h.id) ?? null     // later in API order = newer
      default: return null
    }
  }
  const highFirst = key !== 'price' && key !== 'ppm2'
  return [...houses].sort((x, y) => {
    const a = value(x)
    const b = value(y)
    if (a == null || b == null) return a == null ? (b == null ? 0 : 1) : -1
    return highFirst ? b - a : a - b
  })
}
