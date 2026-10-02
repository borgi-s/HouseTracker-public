import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { PriceHistoryPanel } from '@/components/house/PriceHistoryPanel'
import { makeDetail, makeHouse } from '@/test-utils'

const DETAIL = makeDetail({
  house: makeHouse({ price_dkk: 8_595_000, created_at: '2026-09-22' }),
  price_history: {
    events: [
      { price_dkk: 8_995_000, at: '2026-09-22', source: 'added' },
      { price_dkk: 8_595_000, at: '2026-09-26', source: 'boligsiden' },
    ],
    listing: { listed_price_dkk: 9_195_000, listed_date: '2026-08-25', days_on_market: 32,
      total_days_on_market: 32, realtor: 'Estate Virum', checked_at: '2026-09-26' },
    sales: [{ date: '2021-09-08', price_dkk: 6_350_000, type: 'normal' },
      { date: '2010-03-16', price_dkk: 3_100_000, type: 'family' }],
    original_price_dkk: 9_195_000,
  },
})

test('lists the price story newest first, with the day we added it', () => {
  render(<PriceHistoryPanel detail={DETAIL} />)
  const rows = screen.getAllByRole('listitem').map(li => li.textContent)
  expect(rows).toEqual([
    expect.stringMatching(/Asking 8\.595\.000 kr .400\.000 kr \(-4\.4 %\)$/),
    expect.stringMatching(/Added to our list$/),
    expect.stringMatching(/^before .*Asking 9\.195\.000 kr → 8\.995\.000 kr .200\.000 kr \(-2\.2 %\)$/),
    expect.stringMatching(/Listed at 9\.195\.000 kr · Estate Virum$/),
    expect.stringMatching(/Sold for 6\.350\.000 kr$/),
    expect.stringMatching(/Sold for 3\.100\.000 kr \(family\)$/),
  ])
  expect(screen.getByText(/^32 days on market · Checked daily · last checked /)).toBeInTheDocument()
})

test('says when a house was relisted, and when it has not been checked yet', () => {
  render(<PriceHistoryPanel detail={makeDetail({ price_history: {
    events: [], sales: [], original_price_dkk: null,
    listing: { listed_price_dkk: 5e6, listed_date: '2026-09-01', days_on_market: 20,
      total_days_on_market: 200, realtor: null, checked_at: null } } })} />)
  expect(screen.getByText('20 days on market (200 in total, relisted) · Not checked online yet')).toBeInTheDocument()
})

test('a rise shows a + prefix on the kr amount', () => {
  render(<PriceHistoryPanel detail={makeDetail({
    house: makeHouse({ price_dkk: 5_200_000, created_at: '2026-09-22' }),
    price_history: {
      events: [
        { price_dkk: 5_000_000, at: '2026-09-22', source: 'added' },
        { price_dkk: 5_200_000, at: '2026-09-26', source: 'boligsiden' },
      ],
      listing: null,
      sales: [],
      original_price_dkk: 5_000_000,
    },
  })} />)
  const rows = screen.getAllByRole('listitem').map(li => li.textContent)
  expect(rows[0]).toMatch(/\+200\.000 kr \(\+4\.0 %\)$/)
})
