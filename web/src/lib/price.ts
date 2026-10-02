import type { PriceHistory } from '@/api/types'

/** Whole-percent drop from `original` to `price`, rounded up so any cut shows (≥ 1).
 *  Null when there is no drop to show. */
export function dropPct(original: number | null, price: number | null): number | null {
  if (original == null || price == null || original <= 0 || price >= original) return null
  // Whole kr in, so the percent is exact for round cuts; the epsilon keeps a float a
  // hair above N from showing N + 1.
  return Math.ceil(((original - price) * 100) / original - 1e-9)
}

export type TimelineRow =
  | { kind: 'asking'; date: string; from: number; to: number }
  | { kind: 'added'; date: string }
  | { kind: 'before'; date: string; from: number; to: number }
  | { kind: 'listed'; date: string; price: number; realtor: string | null }
  | { kind: 'sold'; date: string; price: number; type: string | null }

// Same-day rows read top to bottom: a change, the day we added it, what came before.
const ORDER: Record<TimelineRow['kind'], number> = { asking: 0, added: 1, before: 2, listed: 3, sold: 4 }

/** The house's price story, newest first: our dated price changes, the day we added it,
 *  the cuts made before that (one step: Boligsiden only gives the total), the day it was
 *  listed, and every earlier tinglyst sale. */
export function timeline(ph: PriceHistory, addedAt: string | null): TimelineRow[] {
  const ev = ph.events
  const rows: TimelineRow[] = ev.slice(1).map((e, i) =>
    ({ kind: 'asking', date: e.at, from: ev[i].price_dkk, to: e.price_dkk }))
  const added = addedAt ?? ev[0]?.at ?? null
  if (added) rows.push({ kind: 'added', date: added })
  const l = ph.listing
  if (l?.listed_date && l.listed_price_dkk != null) {
    if (ev[0] && added && l.listed_date < added && ev[0].price_dkk !== l.listed_price_dkk)
      rows.push({ kind: 'before', date: added, from: l.listed_price_dkk, to: ev[0].price_dkk })
    rows.push({ kind: 'listed', date: l.listed_date, price: l.listed_price_dkk, realtor: l.realtor })
  }
  for (const s of ph.sales) rows.push({ kind: 'sold', date: s.date, price: s.price_dkk, type: s.type })
  return rows.sort((a, b) => b.date.localeCompare(a.date) || ORDER[a.kind] - ORDER[b.kind])
}
