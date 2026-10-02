import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { expect, test } from 'vitest'
import type { House } from '@/api/types'
import { AddHouse } from '@/routes/AddHouse'
import { fail, LocationProbe, makeHouse, mockApi, renderApp, signedIn } from '@/test-utils'

const URL_ = 'https://www.nybolig.dk/villa/2800/lindevej-14'

function renderAdd() {
  return renderApp(
    <Routes>
      <Route path="/add" element={<AddHouse />} />
      <Route path="/house/:id" element={<LocationProbe />} />
    </Routes>, { route: '/add' })
}

test('a scraped link opens the new house, kicks off enrich and passes media_pending', async () => {
  const calls = mockApi(signedIn({
    'POST /api/houses/scrape': () => ({ ...makeHouse(), media_pending: 12 }),
    'POST /api/houses/lindevej-14/enrich': () => ({}),
  }))
  renderAdd()
  await userEvent.type(screen.getByLabelText('Link to the listing'), URL_)
  await userEvent.click(screen.getByRole('button', { name: 'Add from link' }))
  expect(await screen.findByTestId('location')).toHaveTextContent('/house/lindevej-14 {"mediaPending":12}')
  expect(calls).toContainEqual({ method: 'POST', path: '/api/houses/scrape', body: { url: URL_, use_browser: false } })
  await waitFor(() => expect(calls.map(c => c.path)).toContain('/api/houses/lindevej-14/enrich'))
})

test('a failed fetch offers a retry with the browser', async () => {
  let n = 0
  const calls = mockApi(signedIn({
    'POST /api/houses/scrape': () => (n++ === 0 ? fail(502, 'fetch failed: 403') : { ...makeHouse(), media_pending: 0 }),
    'POST /api/houses/lindevej-14/enrich': () => ({}),
  }))
  renderAdd()
  await userEvent.type(screen.getByLabelText('Link to the listing'), URL_)
  await userEvent.click(screen.getByRole('button', { name: 'Add from link' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Try with browser' }))
  expect(await screen.findByTestId('location')).toHaveTextContent('/house/lindevej-14')
  expect(calls.filter(c => c.path === '/api/houses/scrape').map(c => (c.body as { use_browser: boolean }).use_browser))
    .toEqual([false, true])
})

test('an unreadable page falls back to the manual form with the link filled in', async () => {
  const calls = mockApi(signedIn({
    'POST /api/houses/scrape': () => fail(422, 'could not parse an address'),
    'POST /api/houses': body => makeHouse(body as Partial<House>),
    'POST /api/houses/lindevej-14/enrich': () => ({}),
  }))
  renderAdd()
  await userEvent.type(screen.getByLabelText('Link to the listing'), URL_)
  await userEvent.click(screen.getByRole('button', { name: 'Add from link' }))
  expect(await screen.findByLabelText('Listing URL')).toHaveValue(URL_)
  await userEvent.type(screen.getByLabelText('Address'), 'Lindevej 14')
  await userEvent.click(screen.getByRole('button', { name: 'Add house' }))
  expect(await screen.findByTestId('location')).toHaveTextContent('/house/lindevej-14')
  expect(calls).toContainEqual({ method: 'POST', path: '/api/houses', body: { address: 'Lindevej 14', listing_url: URL_ } })
})

test('a house we already track is not added again: it says where it is and links to it', async () => {
  const tracked = { id: 'abakken-245', address: 'Åbakken 245', status: 'rejected' }
  mockApi(signedIn({
    'POST /api/houses/scrape': () => new Response(JSON.stringify({ detail: {
      message: 'Åbakken 245 is already tracked (status: rejected)', house: tracked } }), { status: 409 }),
  }))
  renderAdd()
  await userEvent.type(screen.getByLabelText('Link to the listing'), URL_)
  await userEvent.click(screen.getByRole('button', { name: 'Add from link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Åbakken 245 is already tracked · Rejected')
  await userEvent.click(screen.getByRole('link', { name: 'Open it' }))
  expect(screen.getByTestId('location')).toHaveTextContent('/house/abakken-245')
})
