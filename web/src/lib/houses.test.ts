import { expect, test } from 'vitest'
import { makeListItem } from '@/test-utils'
import { areas, disagreementKey, filterHouses, narrow, priceSteps, sortHouses, statusChips } from './houses'

const a = makeListItem({ id: 'a', price_dkk: 6e6, price_per_m2: 40000, status: 'visited',
  overall: { alex: 0.9, sam: 0.5 }, disagreement: { light: 3 } })
const b = makeListItem({ id: 'b', price_dkk: 4e6, price_per_m2: 50000, status: 'shortlist',
  overall: { alex: 0.6, sam: 0.7 }, disagreement: { light: 1, noise: 1 } })
const c = makeListItem({ id: 'c', price_dkk: null, price_per_m2: null, status: 'rejected',
  overall: { alex: null, sam: null }, disagreement: {} })
const nv = makeListItem({ id: 'nv', status: 'not_visited', overall: {}, disagreement: {} })
const ids = (hs: { id: string }[]) => hs.map(h => h.id)
const pair = ['alex', 'sam']

test('active hides rejected and sold; a status filters to it', () => {
  expect(ids(filterHouses([a, b, c], 'active'))).toEqual(['a', 'b'])
  expect(ids(filterHouses([a, b, c], 'rejected'))).toEqual(['c'])
})

test('active filter includes not_visited houses', () => {
  expect(ids(filterHouses([nv, a, c], 'active'))).toEqual(['nv', 'a'])
  expect(ids(filterHouses([nv, c], 'not_visited'))).toEqual(['nv'])
})

test('scores sort high-first, prices low-first, missing values last', () => {
  expect(ids(sortHouses([c, b, a], 'mine', 'alex', pair))).toEqual(['a', 'b', 'c'])
  expect(ids(sortHouses([c, a, b], 'combined', 'alex', pair))).toEqual(['a', 'b', 'c'])   // 0.7 vs 0.65
  expect(ids(sortHouses([a, c, b], 'price', 'alex', pair))).toEqual(['b', 'a', 'c'])
  expect(ids(sortHouses([b, c, a], 'ppm2', 'alex', pair))).toEqual(['a', 'b', 'c'])
})

test('newest reverses API order (the API lists oldest first)', () => {
  expect(ids(sortHouses([a, b, c], 'newest', null, pair))).toEqual(['c', 'b', 'a'])
})

test('most disagreement: largest single gap first, then the total', () => {
  expect(disagreementKey({ light: 1, noise: 1 })).toEqual([1, 2])
  expect(disagreementKey({})).toEqual([-1, -1])
  expect(ids(sortHouses([c, b, a], 'disagreement', null, pair))).toEqual(['a', 'b', 'c'])
})

test('chips: Active always; each status only when it holds a house or is the one picked', () => {
  const hs = [
    makeListItem({ id: 'a', status: 'visited' }),
    makeListItem({ id: 'b', status: 'visited' }),
    makeListItem({ id: 'c', status: 'not_visited' }),
    makeListItem({ id: 'd', status: 'rejected' }),
  ]
  expect(statusChips(hs)).toEqual([
    { filter: 'active', label: 'Active', count: 3 },
    { filter: 'not_visited', label: 'Not visited', count: 1 },
    { filter: 'visited', label: 'Visited', count: 2 },
    { filter: 'rejected', label: 'Rejected', count: 1 },
  ])
  expect(statusChips(hs, 'offer').map(c => c.filter)).toContain('offer')
})

test('narrow: area, price, size, rooms, bathrooms, open house; a missing number stays in', () => {
  const slot = { starts_at: '2099-10-04T08:00:00Z', ends_at: '2099-10-04T09:00:00Z', signup: null, signup_url: null, cancelled: false }
  const x = makeListItem({ id: 'x', postal_code: '2830', price_dkk: 6e6, size_m2: 110, rooms: 4, bathrooms: 1, open_houses: [slot] })
  const y = makeListItem({ id: 'y', postal_code: '2800', price_dkk: 8e6, size_m2: 140, rooms: 5, bathrooms: 2 })
  const z = makeListItem({ id: 'z', postal_code: '2830', price_dkk: null, size_m2: null, rooms: null, bathrooms: null,
    open_houses: [{ ...slot, cancelled: true }] })
  expect(ids(narrow([x, y, z], { area: '2830' }))).toEqual(['x', 'z'])
  expect(ids(narrow([x, y, z], { maxPrice: 7e6 }))).toEqual(['x', 'z'])
  expect(ids(narrow([x, y, z], { minSize: 120 }))).toEqual(['y', 'z'])
  expect(ids(narrow([x, y, z], { minRooms: 5, minBaths: 2 }))).toEqual(['y', 'z'])
  expect(ids(narrow([x, y, z], { openHouse: true }))).toEqual(['x'])
  expect(ids(narrow([x, y, z], {}))).toEqual(['x', 'y', 'z'])
})

test('areas list each postal code once, sorted, with its town; price steps span the prices', () => {
  const hs = [
    makeListItem({ id: 'x', postal_code: '2830', city: 'Virum', price_dkk: 5_750_000 }),
    makeListItem({ id: 'y', postal_code: '2800', city: 'Kongens Lyngby', price_dkk: 6_900_000 }),
    makeListItem({ id: 'z', postal_code: '2830', city: 'Virum', price_dkk: null }),
    makeListItem({ id: 'w', postal_code: null, price_dkk: null }),
  ]
  expect(areas(hs)).toEqual([{ code: '2800', label: '2800 Kongens Lyngby' }, { code: '2830', label: '2830 Virum' }])
  expect(priceSteps(hs)).toEqual([6e6, 6.5e6, 7e6])
  expect(priceSteps([])).toEqual([])
})
