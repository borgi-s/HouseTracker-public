import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { DistrictMap } from '@/components/house/DistrictMap'
import { districtsUrl } from '@/lib/districts'
import { mockApi, renderApp } from '@/test-utils'

const square = (x: number, y: number) =>
  ({ type: 'Polygon', coordinates: [[[x, y], [x + 0.01, y], [x + 0.01, y + 0.01], [x, y + 0.01], [x, y]]] })
const district = (name: string, here: boolean, x: number) =>
  ({ type: 'Feature', properties: { name, here, lx: x + 0.005, ly: 55.795 }, geometry: square(x, 55.79) })

test('labels each school district once and marks the one the house is in', async () => {
  mockApi({
    [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({
      type: 'FeatureCollection',
      features: [district('Virum Skole', false, 12.45), district('Fuglsanggårdsskolen', true, 12.465)],
    }),
  })
  renderApp(<DistrictMap lat={55.79} lon={12.47} />)
  expect(await screen.findByText('Fuglsanggårdsskolen')).toHaveClass('district-label-here')
  expect(screen.getAllByText('Virum Skole')).toHaveLength(1)
  expect(screen.getByText('Virum Skole')).not.toHaveClass('district-label-here')
  const colour = (name: string) => screen.getByText(name).closest('.district-label')!.className
  expect(colour('Virum Skole')).not.toBe(colour('Fuglsanggårdsskolen'))
})

test('a district name is text, never markup', async () => {
  const name = '<img src=x onerror=alert(1)>'
  mockApi({
    [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [district(name, false, 12.45)] }),
  })
  renderApp(<DistrictMap lat={55.79} lon={12.47} />)
  expect(await screen.findByText(name)).toBeInTheDocument()
})

test('the Layers menu turns the districts off and shows the sun for a chosen month and hour', async () => {
  mockApi({
    [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [district('Virum Skole', true, 12.465)] }),
  })
  renderApp(<DistrictMap lat={55.79} lon={12.47} />)
  await screen.findByText('Virum Skole')
  await userEvent.click(screen.getByRole('button', { name: 'Layers · 1' }))
  await userEvent.click(screen.getByRole('checkbox', { name: 'School districts' }))
  expect(screen.queryByText('Virum Skole')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('checkbox', { name: 'Sun around the house' }))
  fireEvent.change(screen.getByRole('slider', { name: 'Month' }), { target: { value: '5' } })
  fireEvent.change(screen.getByRole('slider', { name: 'Time of day' }), { target: { value: '780' } })
  expect(screen.getByText(/Sunrise 04:\d\d · sunset 21:\d\d\. The sun is 5\d° up in the S\./)).toBeInTheDocument()
})

test('a map that only shows (the desktop mosaic tile) has no Layers menu', () => {
  mockApi({ [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [] }) })
  renderApp(<DistrictMap lat={55.79} lon={12.47} interactive={false} />)
  expect(screen.queryByRole('button', { name: /Layers/ })).not.toBeInTheDocument()
})

test('noise shows its dB colour bar on the map; plots and cloudburst are layers too', async () => {
  mockApi({ [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [] }) })
  renderApp(<DistrictMap lat={55.79} lon={12.47} />)
  await userEvent.click(screen.getByRole('button', { name: /^Layers/ }))
  await userEvent.click(screen.getByRole('checkbox', { name: 'Roads' }))
  await userEvent.click(screen.getByRole('checkbox', { name: /Plots \(matrikler\)/ }))
  await userEvent.click(screen.getByRole('radio', { name: 'Cloudburst' }))
  expect(screen.getByText('Where 60 mm of rain pools')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Layers · 4' }))       // close the menu
  expect(screen.getByRole('img', { name: /Noise: green 53, yellow 58/ })).toBeInTheDocument()
})
