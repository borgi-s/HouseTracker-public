import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, test } from 'vitest'
import type { Media } from '@/api/types'
import { Viewer, type ViewerState } from '@/components/house/Viewer'
import { districtsUrl } from '@/lib/districts'
import { makeMedia, mockApi, renderApp } from '@/test-utils'

const PHOTOS = ['a', 'b', 'c'].map(id => makeMedia({ id, kind: 'photo' }))
const PLANS = ['f1', 'f2'].map(id => makeMedia({ id, kind: 'floorplan' }))

function Harness({ plans = [], location = null, start = { tab: 'photos', index: 0 } }: {
  plans?: Media[]; location?: { lat: number; lon: number } | null; start?: ViewerState
}) {
  const [state, setState] = useState<ViewerState | null>(start)
  return <Viewer state={state} photos={PHOTOS} plans={plans} location={location} onChange={setState} onClose={() => setState(null)} />
}
const dialog = () => screen.getByRole('dialog')

test('Next and Previous step through the photos and wrap around', async () => {
  renderApp(<Harness />)
  expect(within(dialog()).getByText('1 / 3')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(within(dialog()).getByText('2 / 3')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Previous' }))
  await userEvent.click(screen.getByRole('button', { name: 'Previous' }))
  expect(within(dialog()).getByText('3 / 3')).toBeInTheDocument()
})

test('the arrow keys step too', async () => {
  renderApp(<Harness />)
  await userEvent.keyboard('{ArrowRight}')
  expect(within(dialog()).getByText('2 / 3')).toBeInTheDocument()
})

test('a swipe that settles on another photo moves the counter', () => {
  renderApp(<Harness />)
  const row = screen.getByAltText('Photo 1 of 3').closest('.snap-x')!
  Object.defineProperty(row, 'clientWidth', { value: 390 })
  Object.defineProperty(row, 'scrollLeft', { value: 780, writable: true })
  fireEvent.scroll(row)
  expect(within(dialog()).getByText('3 / 3')).toBeInTheDocument()
})

test('images fit the screen whole: contained, never cropped', () => {
  renderApp(<Harness />)
  expect(screen.getByAltText('Photo 1 of 3')).toHaveClass('object-contain', 'max-h-full', 'max-w-full')
})

test('a thumbnail jumps straight to its photo', async () => {
  renderApp(<Harness />)
  await userEvent.click(screen.getByRole('button', { name: 'Show photo 3' }))
  expect(within(dialog()).getByText('3 / 3')).toBeInTheDocument()
})

test('Plans shows the floor plans, one button per floor', async () => {
  renderApp(<Harness plans={PLANS} />)
  await userEvent.click(screen.getByRole('tab', { name: 'Plans' }))
  expect(within(dialog()).getByText('1 / 2')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Floor 2' }))
  expect(within(dialog()).getByText('2 / 2')).toBeInTheDocument()
})

test('no Plans or Map tab without floor plans or a location', () => {
  renderApp(<Harness />)
  expect(screen.queryByRole('tab')).not.toBeInTheDocument()
})

test('Map shows the district map full screen', async () => {
  mockApi({ [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [] }) })
  renderApp(<Harness location={{ lat: 55.79, lon: 12.47 }} />)
  await userEvent.click(screen.getByRole('tab', { name: 'Map' }))
  expect(dialog().querySelector('.leaflet-container')).not.toBeNull()
})

test('tapping the image hides the controls; tapping again brings them back', async () => {
  renderApp(<Harness />)
  await userEvent.click(screen.getByAltText('Photo 1 of 3'))
  expect(screen.getByRole('button', { name: 'Next' })).toHaveClass('hidden')
  await userEvent.click(screen.getByAltText('Photo 1 of 3'))
  expect(screen.getByRole('button', { name: 'Next' })).not.toHaveClass('hidden')
})

test('Close closes it', async () => {
  renderApp(<Harness />)
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
