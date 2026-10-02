import { expect, test } from 'vitest'
import { dropPct, timeline } from '@/lib/price'
import type { PriceHistory } from '@/api/types'

test('dropPct rounds any cut up to a whole percent', () => {
  expect(dropPct(10_000_000, 9_500_000)).toBe(5)
  expect(dropPct(8_000_000, 7_950_000)).toBe(1)      // 0.6 %
  expect(dropPct(9_195_000, 8_595_000)).toBe(7)      // 6.5 %
})

test('dropPct is null when there is no drop to show', () => {
  expect(dropPct(null, 5e6)).toBeNull()
  expect(dropPct(5e6, null)).toBeNull()
  expect(dropPct(5e6, 5e6)).toBeNull()
  expect(dropPct(5e6, 5.2e6)).toBeNull()
  expect(dropPct(0, 5e6)).toBeNull()
})

const PH: PriceHistory = {
  events: [
    { price_dkk: 8_995_000, at: '2026-09-22', source: 'added' },
    { price_dkk: 8_595_000, at: '2026-09-26', source: 'boligsiden' },
  ],
  listing: { listed_price_dkk: 9_195_000, listed_date: '2026-08-25', days_on_market: 32,
    total_days_on_market: 32, realtor: 'Estate Virum', checked_at: '2026-09-26' },
  sales: [{ date: '2021-09-08', price_dkk: 6_350_000, type: 'normal' }],
  original_price_dkk: 9_195_000,
}

test('timeline tells the price story newest first', () => {
  expect(timeline(PH, '2026-09-22')).toEqual([
    { kind: 'asking', date: '2026-09-26', from: 8_995_000, to: 8_595_000 },
    { kind: 'added', date: '2026-09-22' },
    { kind: 'before', date: '2026-09-22', from: 9_195_000, to: 8_995_000 },
    { kind: 'listed', date: '2026-08-25', price: 9_195_000, realtor: 'Estate Virum' },
    { kind: 'sold', date: '2021-09-08', price: 6_350_000, type: 'normal' },
  ])
})

test('no "before" step when we added it at the listing price', () => {
  const ph = { ...PH, events: [{ price_dkk: 9_195_000, at: '2026-09-22', source: 'added' as const }] }
  expect(timeline(ph, '2026-09-22').map(r => r.kind)).toEqual(['added', 'listed', 'sold'])
})

test('a relisting after we added it sorts above the added marker, with no "before" step', () => {
  const ph = { ...PH, events: PH.events.slice(0, 1),
    listing: { ...PH.listing!, listed_date: '2026-10-01', listed_price_dkk: 8_500_000 } }
  expect(timeline(ph, '2026-09-22').map(r => r.kind)).toEqual(['listed', 'added', 'sold'])
})

test('a house never checked shows only the day we added it', () => {
  expect(timeline({ events: [], listing: null, sales: [], original_price_dkk: null }, '2026-09-22'))
    .toEqual([{ kind: 'added', date: '2026-09-22' }])
})
