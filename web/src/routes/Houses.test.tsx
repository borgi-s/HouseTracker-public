import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { expect, test, vi } from 'vitest'
import { Houses } from '@/routes/Houses'
import { LocationProbe, makeListItem, mockApi, renderApp, signedIn } from '@/test-utils'

const HOUSES = [
  makeListItem({ id: 'a', address: 'Avej 1', price_dkk: 6e6, overall: { alex: 0.9 } }),
  makeListItem({ id: 'b', address: 'Bvej 2', price_dkk: 4e6, overall: { alex: 0.5 } }),
  makeListItem({ id: 'c', address: 'Cvej 3', status: 'rejected' }),
]

function renderHouses() {
  return renderApp(
    <Routes>
      <Route path="/" element={<Houses />} />
      <Route path="*" element={<LocationProbe />} />
    </Routes>)
}

const openFilters = () => userEvent.click(screen.getByRole('button', { name: /^Filters/ }))
const addresses = () => screen.getAllByRole('article').map(a => within(a).getByRole('heading').textContent)

test('shows active houses best-combined first; Rejected shows the rejected one', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderHouses()
  await screen.findByText('Avej 1')
  await openFilters()
  expect(addresses()).toEqual(['Avej 1', 'Bvej 2'])
  expect(screen.queryByRole('button', { name: /^Offer/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Rejected · 1' }))
  expect(addresses()).toEqual(['Cvej 3'])
})

test('a house not visited yet gets a Not visited chip and a sand status label', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => [...HOUSES, makeListItem({ id: 'd', address: 'Dvej 4', status: 'not_visited' })] }))
  renderHouses()
  await screen.findAllByRole('article')
  await openFilters()
  await userEvent.click(screen.getByRole('button', { name: 'Not visited · 1' }))
  expect(addresses()).toEqual(['Dvej 4'])
  expect(screen.getByText('Not visited')).toHaveClass('bg-sand')
  expect(within(screen.getByRole('article')).getByText(/Not rated yet/)).toBeInTheDocument()
})

test('Not rated yet only when neither of us scored', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderHouses()
  await screen.findByText('Avej 1')
  const card = (a: string) => screen.getByText(a).closest('article')!
  expect(within(card('Avej 1')).getByRole('img', { name: 'Alex 4.5' })).toBeInTheDocument()
  expect(within(card('Avej 1')).getByRole('img', { name: 'Sam –' })).toBeInTheDocument()
  expect(within(card('Avej 1')).queryByText(/Not rated yet/)).not.toBeInTheDocument()
})

test('sorting by price puts the cheapest first', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderHouses()
  await screen.findByText('Avej 1')
  await userEvent.selectOptions(screen.getByLabelText('Sort'), 'price')
  expect(addresses()).toEqual(['Bvej 2', 'Avej 1'])
})

test('ticking two houses offers Compare, which opens the compare view', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderHouses()
  await screen.findByText('Avej 1')
  expect(screen.queryByRole('button', { name: /Compare/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByLabelText('Compare Avej 1'))
  await userEvent.click(screen.getByLabelText('Compare Bvej 2'))
  await userEvent.click(screen.getByRole('button', { name: 'Compare 2' }))
  expect(screen.getByTestId('location')).toHaveTextContent('/compare?ids=a,b')
})

test('with no houses it points at Add', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => [] }))
  renderHouses()
  expect(await screen.findByRole('link', { name: 'Add the first one' })).toHaveAttribute('href', '/add')
})

test('Map shows the houses on a map; picking one from the list shows its card', async () => {
  vi.spyOn(window, 'matchMedia').mockImplementation(query => ({
    matches: true, media: query, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
    dispatchEvent: () => false,
  }) as MediaQueryList)
  mockApi(signedIn({ 'GET /api/houses': () => [makeListItem({ id: 'a', address: 'Avej 1', lat: 55.76, lon: 12.49 })] }))
  renderHouses()
  await userEvent.click(await screen.findByRole('button', { name: 'Map' }))
  expect(await screen.findByRole('button', { name: /^Avej 1, / })).toHaveClass('price-pin')
  expect(screen.getByText(/km to Work/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Show Avej 1 on the map' }))
  expect(document.querySelector('.leaflet-popup a[href="/house/a"]')).toHaveTextContent('Avej 1')  // the card on its pin
})

test('a house without a location is listed but has no pin', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => [makeListItem({ id: 'a', address: 'Avej 1' })] }))
  renderHouses()
  await userEvent.click(await screen.findByRole('button', { name: 'Map' }))
  expect(await screen.findByText(/No location yet/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Avej 1, / })).not.toBeInTheDocument()
})

test('a card shows the ↓% bubble next to a reduced price', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => [
    makeListItem({ id: 'a', address: 'Avej 1', price_dkk: 9_500_000, original_price_dkk: 10_000_000 })] }))
  renderHouses()
  const card = (await screen.findByText('Avej 1')).closest('article')!
  expect(within(card).getByText('↓5%')).toBeInTheDocument()
})

test('open houses: a band on houses not visited, a pill on seen ones, nothing on rejected', async () => {
  const slot = { starts_at: '2099-10-04T13:30:00Z', ends_at: '2099-10-04T13:50:00Z', signup: false, signup_url: null, cancelled: false }
  mockApi(signedIn({ 'GET /api/houses': () => [
    makeListItem({ id: 'n', address: 'Nyvej 1', status: 'not_visited', open_houses: [slot] }),
    makeListItem({ id: 's', address: 'Svej 2', status: 'shortlist', open_houses: [slot] }),
    makeListItem({ id: 'r', address: 'Rvej 3', status: 'rejected', open_houses: [slot] }),
  ] }))
  renderHouses()
  await screen.findAllByRole('article')
  await openFilters()
  await userEvent.click(screen.getByRole('button', { name: 'Not visited · 1' }))
  const card = () => screen.getByRole('article')
  expect(card()).toHaveTextContent('Open house Sun 4 Oct 15:30')
  expect(within(card()).getByText('Drop-in')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Shortlist · 1' }))
  expect(card()).toHaveTextContent('Open house Sun 4 Oct 15:30')
  expect(within(card()).queryByText('Drop-in')).not.toBeInTheDocument()     // the pill, not the band
  await userEvent.click(screen.getByRole('button', { name: 'Rejected · 1' }))
  expect(card()).not.toHaveTextContent('Open house')
})

test('area and price narrow the list and its chip counts, and the filters live in the URL', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => [
    makeListItem({ id: 'v1', address: 'Virumvej 1', postal_code: '2830', city: 'Virum', price_dkk: 6e6 }),
    makeListItem({ id: 'v2', address: 'Virumvej 2', postal_code: '2830', city: 'Virum', price_dkk: 8e6 }),
    makeListItem({ id: 'v3', address: 'Virumvej 3', postal_code: '2830', city: 'Virum', status: 'rejected' }),
    makeListItem({ id: 'h1', address: 'Holtevej 1', postal_code: '2840', city: 'Holte', price_dkk: 6e6 }),
  ] }))
  renderApp(
    <Routes>
      <Route path="/" element={<Houses />} />
      <Route path="*" element={<LocationProbe />} />
    </Routes>, { route: '/?area=2830' })        // e.g. coming back from a house page
  await screen.findByText('Virumvej 1')
  await openFilters()
  expect(addresses()).toEqual(['Virumvej 1', 'Virumvej 2'])
  expect(screen.getByLabelText('Area')).toHaveValue('2830')
  expect(screen.getByRole('button', { name: 'Rejected · 1' })).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Max price'), 'Up to 6 mio')
  expect(addresses()).toEqual(['Virumvej 1'])
  await userEvent.selectOptions(screen.getByLabelText('Area'), 'All areas')
  expect(addresses()).toEqual(['Virumvej 1', 'Holtevej 1'])
})

test('on the phone the map carries the status chips and filters', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderHouses()
  await userEvent.click(await screen.findByRole('button', { name: 'Map' }))
  await openFilters()
  const sheet = () => within(screen.getByRole('region', { name: 'Houses on the map' }))
  expect(sheet().getByText('Avej 1')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Rejected · 1' }))
  expect(sheet().getByText('Cvej 3')).toBeInTheDocument()
  expect(sheet().queryByText('Avej 1')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Area')).toBeInTheDocument()
})

test('size, rooms, bathrooms and open house narrow the list', async () => {
  const slot = { starts_at: '2099-10-04T08:00:00Z', ends_at: '2099-10-04T09:00:00Z', signup: null, signup_url: null, cancelled: false }
  mockApi(signedIn({ 'GET /api/houses': () => [
    makeListItem({ id: 's', address: 'Smallvej 1', size_m2: 90, rooms: 3, bathrooms: 1, open_houses: [slot] }),
    makeListItem({ id: 'b', address: 'Bigvej 2', size_m2: 150, rooms: 5, bathrooms: 2 }),
  ] }))
  renderHouses()
  await screen.findByText('Smallvej 1')
  await openFilters()
  await userEvent.selectOptions(screen.getByLabelText('Min size'), '120+ m²')
  expect(addresses()).toEqual(['Bigvej 2'])
  await userEvent.selectOptions(screen.getByLabelText('Min size'), 'Any size')
  await userEvent.selectOptions(screen.getByLabelText('Min bathrooms'), '2+ bathrooms')
  expect(addresses()).toEqual(['Bigvej 2'])
  await userEvent.selectOptions(screen.getByLabelText('Min bathrooms'), 'Any bathrooms')
  await userEvent.click(screen.getByRole('button', { name: 'Open house' }))
  expect(addresses()).toEqual(['Smallvej 1'])
})

test('on the phone the filters start hidden behind a Filters button that counts the active ones', async () => {
  mockApi(signedIn({ 'GET /api/houses': () => HOUSES }))
  renderApp(
    <Routes>
      <Route path="/" element={<Houses />} />
    </Routes>, { route: '/?status=rejected&size=120' })
  await screen.findByText('Cvej 3')
  expect(screen.queryByLabelText('Min size')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Filters · 2' }))
  expect(screen.getByLabelText('Min size')).toHaveValue('120')
})
