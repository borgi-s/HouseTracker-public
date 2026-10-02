import { expect, test } from 'vitest'
import type { Anchor } from '@/api/types'
import { bestIndices, fastestTo, mainAnchor, mean } from './compare'

test('best is the min or max; ties all win; blanks are ignored', () => {
  expect(bestIndices([6e6, 4e6, 5e6], 'low')).toEqual([1])
  expect(bestIndices([3, 5, 5], 'high')).toEqual([1, 2])
  expect(bestIndices([null, 4, 2], 'high')).toEqual([1])
})

test('nothing stands out with fewer than two values or when all are equal', () => {
  expect(bestIndices([null, 4], 'high')).toEqual([])
  expect(bestIndices([3, 3], 'high')).toEqual([])
})

test('fastestTo picks the quickest mode to one anchor', () => {
  const c = (anchor_ref: string, mode: string, minutes: number | null) =>
    ({ house_id: 'h', anchor_ref, mode, minutes, distance_m: null, computed_at: null })
  expect(fastestTo([c('work', 'cycling-regular', 18), c('work', 'driving-car', 11), c('school', 'foot-walking', 6)], 'work')).toBe(11)
  expect(fastestTo([c('work', 'driving-car', null)], 'work')).toBeNull()
})

test('mean ignores blanks', () => {
  expect(mean([4, undefined, 2])).toBe(3)
  expect(mean([undefined])).toBeNull()
})

test('mainAnchor is the first fixed anchor, or null', () => {
  const a = (id: string, kind: string): Anchor => ({ id, label: id, address: null, lat: 1, lon: 1, kind })
  expect(mainAnchor([a('school', 'dynamic'), a('office', 'fixed'), a('gym', 'fixed')])?.id).toBe('office')
  expect(mainAnchor([a('school', 'dynamic')])).toBeNull()
  expect(mainAnchor([])).toBeNull()
  expect(mainAnchor(undefined)).toBeNull()
})
