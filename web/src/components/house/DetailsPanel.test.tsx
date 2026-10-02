import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { DetailsPanel } from '@/components/house/DetailsPanel'
import { makeDetail, makeHouse, mockApi, renderApp, signedIn } from '@/test-utils'

test('facts use the Danish terms with an English hint', () => {
  mockApi(signedIn())
  renderApp(<DetailsPanel detail={makeDetail()} />)
  expect(screen.getByText('Ejerudgift')).toBeInTheDocument()
  expect(screen.getByText('monthly owner costs')).toBeInTheDocument()
  expect(screen.getByText('3.850 kr/md')).toBeInTheDocument()
  expect(screen.getByText('Energimærke')).toBeInTheDocument()
})

test('editing sends only the fields that changed', async () => {
  const calls = mockApi(signedIn({ 'PATCH /api/houses/lindevej-14': () => makeHouse({ price_dkk: 5000000 }) }))
  renderApp(<DetailsPanel detail={makeDetail()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Edit details' }))
  const price = await screen.findByLabelText('Price (kr)')
  await userEvent.clear(price)
  await userEvent.type(price, '5000000')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'PATCH', path: '/api/houses/lindevej-14', body: { price_dkk: 5000000 } }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(calls.map(c => c.path)).not.toContain('/api/houses/lindevej-14/enrich')   // same address, same place
})

test('a corrected address re-runs the location lookup, even when one exists', async () => {
  const calls = mockApi(signedIn({
    'PATCH /api/houses/lindevej-14': () => makeHouse({ address: 'Lindevej 16' }),
    'POST /api/houses/lindevej-14/enrich': () => ({}),
  }))
  renderApp(<DetailsPanel detail={makeDetail({ house: makeHouse({ lat: 55.78, lon: 12.52 }) })} />)
  await userEvent.click(screen.getByRole('button', { name: 'Edit details' }))
  const address = await screen.findByLabelText('Address')
  await userEvent.clear(address)
  await userEvent.type(address, 'Lindevej 16')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(calls.map(c => `${c.method} ${c.path}`)).toEqual(expect.arrayContaining([
    'PATCH /api/houses/lindevej-14', 'POST /api/houses/lindevej-14/enrich'])))
})

test('without a location it offers a retry', async () => {
  const calls = mockApi(signedIn({ 'POST /api/houses/lindevej-14/enrich': () => ({}) }))
  renderApp(<DetailsPanel detail={makeDetail()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Retry location' }))
  await waitFor(() => expect(calls.map(c => c.path)).toContain('/api/houses/lindevej-14/enrich'))
})

test('the commute table names the anchor and shows minutes and km', async () => {
  mockApi(signedIn())
  renderApp(<DetailsPanel detail={makeDetail({
    house: makeHouse({ lat: 55.78, lon: 12.52 }),
    commutes: [{ house_id: 'lindevej-14', anchor_ref: 'work', mode: 'cycling-regular',
                 minutes: 14.2, distance_m: 5230, computed_at: '2026-09-21' }],
  })} />)
  expect(await screen.findByText('Work')).toBeInTheDocument()
  expect(screen.getByText('14 min · 5,2 km')).toBeInTheDocument()
})

test('a sold house shows the realised price against the asking price', () => {
  mockApi(signedIn())
  renderApp(<DetailsPanel detail={makeDetail({
    house: makeHouse({ status: 'sold', sold_price_dkk: 5700000, sold_date: '2026-11-02' }) })} />)
  expect(screen.getByText('5.700.000 kr')).toBeInTheDocument()
  expect(screen.getByText('+3.7 %')).toBeInTheDocument()
})
