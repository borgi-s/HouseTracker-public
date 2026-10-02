import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render as rtlRender, screen } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { HousesMap } from '@/components/HousesMap'
import { WORK, makeListItem } from '@/test-utils'

// The map's Layers menu fetches school districts through react-query.
const render = (ui: ReactElement) => rtlRender(ui, {
  wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>,
})

const PAIR = ['alex', 'sam']
const HOUSES = [
  makeListItem({ id: 'g', address: 'Grøndalvej 133A', lat: 55.79, lon: 12.47, price_dkk: 8595000, overall: { alex: 0.78, sam: 0.86 } }),
  makeListItem({ id: 'e', address: 'Egelundsvej 61', lat: 55.76, lon: 12.54, price_dkk: 9995000, status: 'not_visited' }),
  makeListItem({ id: 'x', address: 'Nowhere 1', lat: null, lon: null }),
]

test('one price pin per house with a location, plus the anchor', () => {
  render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={WORK} selected={null} onSelect={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Grøndalvej 133A, 8,6 mio · 4.1' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Egelundsvej 61, 10,0 mio' })).toHaveClass('price-pin-todo')
  expect(screen.queryByRole('button', { name: /Nowhere/ })).not.toBeInTheDocument()
  expect(screen.getByText('Work')).toHaveClass('anchor-pin')
})

test('clicking a pin selects its house; the selected pin stands out', async () => {
  const onSelect = vi.fn()
  const { rerender } = render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null} selected={null} onSelect={onSelect} />)
  await userEvent.click(screen.getByRole('button', { name: /Grøndalvej/ }))
  expect(onSelect).toHaveBeenCalledWith('g')
  rerender(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null} selected="g" onSelect={onSelect} />)
  expect(screen.getByRole('button', { name: /Grøndalvej/ })).toHaveClass('price-pin-on')
})

test('an address is text, never markup', () => {
  const evil = makeListItem({ id: 'h', address: '<img src=x onerror=alert(1)>', lat: 55.7, lon: 12.5 })
  render(<HousesMap houses={[evil]} pairIds={PAIR} anchor={null} selected={null} onSelect={vi.fn()} />)
  expect(screen.getByRole('button', { name: /<img src=x/ })).toBeInTheDocument()
  expect(document.querySelector('img[src="x"]')).toBeNull()
})

test('popup card appears in the document when selected and card are provided', () => {
  render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null} selected="g"
    onSelect={vi.fn()} card={<a href="/house/g">House Link</a>} />)
  expect(document.querySelector('a[href="/house/g"]')).not.toBeNull()
})

test('popup has no Leaflet close button (owner taps map to close; × fails 44px rule)', () => {
  render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null} selected="g"
    onSelect={vi.fn()} card={<a href="/house/g">House Link</a>} />)
  // closeButton: false — the × is gone; map click closes (not simulatable in jsdom)
  expect(document.querySelector('.leaflet-popup-close-button')).toBeNull()
})

// TDD for issue 1: re-selection race — passes in jsdom (Leaflet's preclick/touch race
// only manifests on real touch devices), but guards against regressions and documents intent.
test('selecting a different pin moves the popup card without calling onSelect(null)', () => {
  const hA = makeListItem({ id: 'g', address: 'Grøndalvej 133A', lat: 55.79, lon: 12.47 })
  const hB = makeListItem({ id: 'e', address: 'Egelundsvej 61', lat: 55.76, lon: 12.54 })
  const onSelect = vi.fn()
  const { rerender } = render(
    <HousesMap houses={[hA, hB]} pairIds={PAIR} anchor={null}
      selected="g" onSelect={onSelect} card={<span>Card A</span>} />
  )
  rerender(
    <HousesMap houses={[hA, hB]} pairIds={PAIR} anchor={null}
      selected="e" onSelect={onSelect} card={<span>Card B</span>} />
  )
  expect(document.querySelector('.leaflet-popup')?.textContent).toContain('Card B')
  expect(onSelect).not.toHaveBeenCalledWith(null)
})

// TDD for issue 4: map tap closes popup and calls onSelect(null).
// fireEvent.click on the container triggers Leaflet's _handleDOMEvent → map click → closePopup.
test('tapping the map (not a pin) closes the popup and calls onSelect(null)', () => {
  const onSelect = vi.fn()
  render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null}
    selected="g" onSelect={onSelect} card={<span>House G Card</span>} />)
  expect(document.querySelector('.leaflet-popup')).not.toBeNull()
  fireEvent.click(document.querySelector('.leaflet-container')!)
  expect(onSelect).toHaveBeenCalledWith(null)
})

test('card address with markup renders as text, not HTML', () => {
  const evilCard = <span>{'<img src=x onerror=alert(1)>'}</span>
  render(<HousesMap houses={HOUSES} pairIds={PAIR} anchor={null} selected="g"
    onSelect={vi.fn()} card={evilCard} />)
  expect(document.querySelector('img[src="x"]')).toBeNull()
  expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>')
})

test('a pin carries a ↓% badge while the price is below the original', () => {
  const cut = makeListItem({ id: 'c', address: 'Cutvej 1', lat: 55.7, lon: 12.5,
    price_dkk: 9_500_000, original_price_dkk: 10_000_000 })
  render(<HousesMap houses={[cut]} pairIds={PAIR} anchor={null} selected={null} onSelect={vi.fn()} />)
  const pin = screen.getByRole('button', { name: 'Cutvej 1, 9,5 mio, price reduced 5%' })
  expect(pin.querySelector('.price-drop')).toHaveTextContent('↓5%')
})
