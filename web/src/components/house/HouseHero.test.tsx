import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { HouseHero } from '@/components/house/HouseHero'
import { districtsUrl } from '@/lib/districts'
import { makeMedia, mockApi, renderApp } from '@/test-utils'

const PHOTOS = ['p1', 'p2', 'p3'].map(id => makeMedia({ id, kind: 'photo' }))
const PLANS = [makeMedia({ id: 'fp', kind: 'floorplan' })]
const HERE = { lat: 55.79, lon: 12.47 }
const geofa = () => mockApi({ [`GET ${districtsUrl(HERE.lat, HERE.lon)}`]: () => ({ type: 'FeatureCollection', features: [] }) })

test('laptop: the stage shows the first photo; tiles and All photos open the viewer where they point', async () => {
  const onOpen = vi.fn()
  renderApp(<HouseHero photos={PHOTOS} plans={PLANS} location={null} desktop onOpen={onOpen} />)
  await userEvent.click(screen.getByRole('button', { name: 'Open photo 1' }))
  await userEvent.click(screen.getByRole('button', { name: 'Open photo 2' }))
  await userEvent.click(screen.getByRole('button', { name: 'All 3 photos' }))
  expect(onOpen.mock.calls).toEqual([['photos', 0], ['photos', 1], ['photos', 0]])
})

test('the switcher puts the floor plan on the stage; tapping it opens the plans', async () => {
  const onOpen = vi.fn()
  renderApp(<HouseHero photos={PHOTOS} plans={PLANS} location={null} desktop onOpen={onOpen} />)
  await userEvent.click(screen.getByRole('button', { name: 'Floor plan' }))
  expect(screen.getByRole('button', { name: 'Floor plan' })).toHaveAttribute('aria-pressed', 'true')
  const stage = screen.getAllByRole('button', { name: 'Open floor plan 1' })[0]
  await userEvent.click(stage)
  expect(onOpen).toHaveBeenCalledWith('plans', 0)
})

test('the map on the stage has a Full screen button; the map tile opens the map', async () => {
  geofa()
  const onOpen = vi.fn()
  renderApp(<HouseHero photos={PHOTOS} plans={[]} location={HERE} desktop onOpen={onOpen} />)
  await userEvent.click(screen.getByRole('button', { name: 'Open map' }))
  await userEvent.click(screen.getByRole('button', { name: 'Map' }))
  await userEvent.click(screen.getByRole('button', { name: 'Full screen' }))
  expect(onOpen.mock.calls).toEqual([['map', 0], ['map', 0]])
})

test('phone: every photo is in the swipe strip; the icon switcher has names', () => {
  renderApp(<HouseHero photos={PHOTOS} plans={PLANS} location={null} desktop={false} onOpen={vi.fn()} />)
  expect(screen.getAllByRole('button', { name: /^Open photo/ })).toHaveLength(3)
  expect(screen.getByRole('button', { name: 'Photos' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Floor plan' })).toBeInTheDocument()
})

test('phone: strip photos are object-contain, never cropped', () => {
  const { container } = renderApp(<HouseHero photos={PHOTOS} plans={[]} location={null} desktop={false} onOpen={vi.fn()} />)
  const imgs = container.querySelectorAll('img')
  expect(imgs.length).toBeGreaterThan(0)
  for (const img of imgs) {
    expect(img).toHaveClass('object-contain')
  }
})

test('only what exists: no switcher without floor plans or a location, nothing without media', () => {
  const { rerender } = renderApp(<HouseHero photos={PHOTOS} plans={[]} location={null} desktop onOpen={vi.fn()} />)
  expect(screen.queryByRole('button', { name: 'Floor plan' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Map' })).not.toBeInTheDocument()
  rerender(<HouseHero photos={[]} plans={[]} location={null} desktop onOpen={vi.fn()} />)
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
