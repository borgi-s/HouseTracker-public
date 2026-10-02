import { screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Compare } from '@/routes/Compare'
import {
  WORK, makeCriterion, makeDetail, makeFigure, makeHouse, makeSchool, makeSchools, mockApi, renderApp, signedIn,
} from '@/test-utils'

const A = makeDetail({ house: makeHouse({ id: 'a', address: 'Avej 1', price_dkk: 6e6 }),
  scores: { alex: { light: 4 }, sam: { light: 2 } } })
const B = makeDetail({ house: makeHouse({ id: 'b', address: 'Bvej 2', price_dkk: 4e6 }),
  scores: { alex: { light: 5 }, sam: { light: 5 } } })

const row = (name: string) => screen.getByRole('rowheader', { name }).closest('tr')!

test('one column per house; the best cell of each row is marked', async () => {
  mockApi(signedIn({
    'GET /api/criteria?active_only=true': () => [makeCriterion()],
    'GET /api/houses/a': () => A,
    'GET /api/houses/b': () => B,
  }))
  renderApp(<Compare />, { route: '/compare?ids=a,b' })
  expect(await screen.findByRole('link', { name: 'Avej 1' })).toHaveAttribute('href', '/house/a')
  const [priceA, priceB] = within(row('Price')).getAllByRole('cell')
  expect(priceA).not.toHaveAttribute('data-best')
  expect(priceB).toHaveAttribute('data-best')
  const [lightA, lightB] = within(row('Light')).getAllByRole('cell')
  expect(lightA).toHaveTextContent('42')          // Alex 4, Sam 2
  expect(lightB).toHaveAttribute('data-best')
})

test('fewer than two houses explains what to do', async () => {
  mockApi(signedIn())
  renderApp(<Compare />, { route: '/compare?ids=a' })
  expect(await screen.findByText(/Pick 2–4 houses/)).toBeInTheDocument()
})

test('school rows come last: nearest school, walk, bike and every figure with its year', async () => {
  const withSchool = (id: string, name: string, walk: number, grade: number, pupils: number) => makeDetail({
    house: makeHouse({ id, address: `${id}vej` }),
    schools: makeSchools([{ schools: [makeSchool({ name, walk_min: walk, figures: [
      makeFigure({ value: grade }),
      makeFigure({ key: 'pupils', label: 'Pupils', better: null, value: pupils }),
    ] })] }]),
  })
  mockApi(signedIn({
    'GET /api/houses/a': () => withSchool('a', 'Fuglsanggårdsskolen', 8, 8.8, 744),
    'GET /api/houses/b': () => withSchool('b', 'Virum Skole', 12, 7.8, 1033),
  }))
  renderApp(<Compare />, { route: '/compare?ids=a,b' })
  await screen.findByRole('link', { name: 'avej' })
  const names = screen.getAllByRole('rowheader').map(h => h.textContent)
  expect(names.slice(-5)).toEqual(['School', 'Walk to school', 'Bike to school', 'Grade average', 'Pupils'])
  expect(within(row('School')).getAllByRole('cell').map(c => c.textContent)).toEqual(['Fuglsanggårdsskolen', 'Virum Skole'])
  expect(within(row('Walk to school')).getAllByRole('cell')[0]).toHaveAttribute('data-best')
  const [gradeA, gradeB] = within(row('Grade average')).getAllByRole('cell')
  expect(gradeA).toHaveTextContent('8,8 · 2024/25')
  expect(gradeA).toHaveAttribute('data-best')
  expect(gradeB).not.toHaveAttribute('data-best')
  expect(within(row('Pupils')).getAllByRole('cell').filter(c => c.hasAttribute('data-best'))).toEqual([])
})

test('no school rows when no house has school data', async () => {
  mockApi(signedIn({ 'GET /api/houses/a': () => A, 'GET /api/houses/b': () => B }))
  renderApp(<Compare />, { route: '/compare?ids=a,b' })
  await screen.findByRole('link', { name: 'Avej 1' })
  expect(screen.queryByRole('rowheader', { name: 'School' })).not.toBeInTheDocument()
})

const commute = (ref: string, minutes: number) =>
  ({ house_id: 'x', anchor_ref: ref, mode: 'driving-car', minutes, distance_m: 1000, computed_at: '2026-09-21' })

test('the commute row times the fixed anchor and is named after it', async () => {
  mockApi(signedIn({
    'GET /api/anchors': () => [{ ...WORK, id: 'office', label: 'Office' }],
    'GET /api/houses/a': () => ({ ...A, commutes: [commute('office', 20)] }),
    'GET /api/houses/b': () => ({ ...B, commutes: [commute('office', 12)] }),
  }))
  renderApp(<Compare />, { route: '/compare?ids=a,b' })
  const header = await screen.findByRole('rowheader', { name: 'Office commute' })
  const [ca, cb] = within(header.closest('tr')!).getAllByRole('cell')
  expect(ca).not.toHaveAttribute('data-best')
  expect(cb).toHaveAttribute('data-best')
})

test('without a fixed anchor there is no commute row', async () => {
  mockApi(signedIn({
    'GET /api/anchors': () => [],
    'GET /api/houses/a': () => A,
    'GET /api/houses/b': () => B,
  }))
  renderApp(<Compare />, { route: '/compare?ids=a,b' })
  await screen.findByRole('rowheader', { name: 'Price' })
  expect(screen.queryByRole('rowheader', { name: /commute/i })).toBeNull()
})
