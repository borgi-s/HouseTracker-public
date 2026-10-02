import { expect, test } from 'vitest'
import { makeCriterion } from '@/test-utils'
import { DEFAULT_CRITERIA, keyFrom, reorder, weightShares } from './settings'

test('defaults: 8 subjective + 3 automatic, price and ejerudgift lower-is-better', () => {
  expect(DEFAULT_CRITERIA.filter(c => c.kind === 'subjective').map(c => c.key)).toEqual(
    ['light', 'layout', 'kitchen', 'bathrooms', 'garden', 'condition', 'neighbourhood', 'noise'])
  const auto = DEFAULT_CRITERIA.filter(c => c.kind === 'auto')
  expect(auto.map(c => [c.auto_source, c.higher_is_better])).toEqual(
    [['price_per_m2', false], ['ejerudgift_dkk', false], ['size_m2', true]])
  expect(DEFAULT_CRITERIA.every(c => (c.weight ?? 1) === 1)).toBe(true)
})

test('reorder swaps neighbours and renumbers only what changed', () => {
  const list = ['a', 'b', 'c'].map(id => makeCriterion({ id, key: id, sort: 0 }))
  expect(reorder(list, 0, 1)).toEqual([{ id: 'a', sort: 1 }, { id: 'c', sort: 2 }])
  expect(reorder(list, 0, -1)).toEqual([])
  expect(reorder(list, 2, 1)).toEqual([])
})

test('keyFrom makes a stable key from a label, Danish letters included', () => {
  expect(keyFrom('Støj & larm')).toBe('stoej_larm')
  expect(keyFrom('  Garden ')).toBe('garden')
})

test('weightShares: each active criterion as a whole percent of the active total', () => {
  const list = [
    makeCriterion({ id: 'a', weight: 2 }), makeCriterion({ id: 'b', weight: 1 }),
    makeCriterion({ id: 'c', weight: 1 }), makeCriterion({ id: 'off', weight: 5, active: false }),
  ]
  expect(weightShares(list)).toEqual({ a: 50, b: 25, c: 25 })
  expect(weightShares([makeCriterion({ id: 'z', weight: 0 })])).toEqual({ z: 0 })
})
