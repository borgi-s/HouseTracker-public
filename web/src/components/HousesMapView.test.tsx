import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { vi } from 'vitest'
import { HousesMapView, snapStop } from '@/components/HousesMapView'
import { WORK, ALEX, SAM, makeListItem, mockApi, renderApp } from '@/test-utils'

const PAIR = [ALEX, SAM]
const HOUSES = [
  makeListItem({ id: 'g', address: 'Grøndalvej 133A', lat: 55.79, lon: 12.47, price_dkk: 8595000 }),
]

// ── snapStop unit tests ──────────────────────────────────────────────────────

test('snapStop: height near 44 → down', () => expect(snapStop(50, 800)).toBe('down'))
test('snapStop: height near 224 → peek', () => expect(snapStop(200, 800)).toBe('peek'))
test('snapStop: height near 85% → open', () => expect(snapStop(660, 800)).toBe('open'))
test('snapStop: just past midpoint between down and peek → peek', () => expect(snapStop(135, 800)).toBe('peek'))

// ── phone: pin tap shows card + sheet collapses ──────────────────────────────

test('phone: tapping a pin collapses sheet to down', async () => {
  mockApi({ 'GET /api/anchors': () => [WORK] })
  renderApp(<HousesMapView houses={HOUSES} pair={PAIR} onList={vi.fn()} />)
  // jsdom matchMedia returns false → phone layout
  // initial: sheet at peek
  expect(screen.getByRole('region', { name: 'Houses on the map' })).toHaveClass('h-56')
  // the price pin has aria-label "address, price" e.g. "Grøndalvej 133A, 8,6 mio"
  const pin = await screen.findByRole('button', { name: /Grøndalvej 133A, / })
  await userEvent.click(pin)
  // sheet collapses to down
  expect(screen.getByRole('region', { name: 'Houses on the map' })).toHaveClass('h-11')
  // house link is in the popup card (not just the always-present list row)
  expect(document.querySelector('.leaflet-popup a[href="/house/g"]')).not.toBeNull()
})

// ── phone: handle drag snaps to down ─────────────────────────────────────────

test('phone: dragging the handle down snaps to the down stop', async () => {
  mockApi({ 'GET /api/anchors': () => [WORK] })
  renderApp(<HousesMapView houses={HOUSES} pair={PAIR} onList={vi.fn()} />)
  const handle = await screen.findByRole('button', { name: 'Expand list' })
  // Drag > 6 px downward (decreases sheet height)
  fireEvent.pointerDown(handle, { clientY: 100 })
  fireEvent.pointerMove(handle, { clientY: 300 })
  fireEvent.pointerUp(handle, { clientY: 300 })
  // after a big downward drag from peek (224px), height becomes 224-200=24 → nearest is down (44)
  expect(handle).toHaveAttribute('aria-expanded', 'false')
  expect(handle).toHaveAttribute('aria-label', 'Expand list')
})

// ── laptop: pin card, list stays put ─────────────────────────────────────────

test('laptop: picking a house from the list opens the card on its pin', async () => {
  vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: true, media: '', onchange: null,
    addEventListener() {}, removeEventListener() {},
    addListener() {}, removeListener() {}, dispatchEvent: () => false,
  } as MediaQueryList)
  mockApi({ 'GET /api/anchors': () => [WORK] })
  renderApp(<HousesMapView houses={HOUSES} pair={PAIR} onList={vi.fn()} />)
  const listBtn = await screen.findByRole('button', { name: /Show Grøndalvej 133A on the map/ })
  await userEvent.click(listBtn)
  expect(document.querySelector('.leaflet-popup a[href="/house/g"]')).not.toBeNull()
  expect(listBtn.closest('li')).toHaveClass('ring-2')                   // still highlighted
  expect(screen.queryByRole('button', { name: /Expand list|Collapse list/ })).toBeNull()  // no sheet
})

test('the map list shows the ↓% bubble too', async () => {
  mockApi({ 'GET /api/anchors': () => [WORK] })
  const cut = makeListItem({ id: 'g', address: 'Grøndalvej 133A', lat: 55.79, lon: 12.47,
    price_dkk: 9_500_000, original_price_dkk: 10_000_000 })
  renderApp(<HousesMapView houses={[cut]} pair={PAIR} onList={vi.fn()} />)
  expect(await screen.findByText('Price reduced 5% from 10.000.000 kr')).toBeInTheDocument()
})

test('the map list shows an open-house pill', async () => {
  mockApi({ 'GET /api/anchors': () => [WORK] })
  const slot = { starts_at: '2099-10-04T13:30:00Z', ends_at: '2099-10-04T13:50:00Z', signup: true, signup_url: null, cancelled: false }
  renderApp(<HousesMapView houses={[{ ...HOUSES[0], status: 'not_visited', open_houses: [slot] }]} pair={PAIR} onList={vi.fn()} />)
  expect((await screen.findAllByText('Open house Sun 4 Oct 15:30'))[0]).toBeInTheDocument()
})

test('the map list measures to the first fixed anchor, whatever its id', async () => {
  mockApi({ 'GET /api/anchors': () => [{ ...WORK, id: 'school', kind: 'dynamic', label: 'School' },
                                       { ...WORK, id: 'office', label: 'Office' }] })
  renderApp(<HousesMapView houses={HOUSES} pair={PAIR} onList={vi.fn()} />)
  expect((await screen.findAllByText(/km to Office/))[0]).toBeInTheDocument()
})

test('no anchors, no distance line and no crash', async () => {
  mockApi({ 'GET /api/anchors': () => [] })
  renderApp(<HousesMapView houses={HOUSES} pair={PAIR} onList={vi.fn()} />)
  await screen.findByRole('button', { name: /Grøndalvej 133A, / })
  expect(screen.queryByText(/km to/)).toBeNull()
})
