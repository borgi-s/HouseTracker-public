import { expect, test } from 'vitest'
import { disagrees, slotOf } from './person'

const pair = [{ id: 'alex', name: 'Alex' }, { id: 'sam', name: 'Sam' }]

test('A and B are the first two persons in API order', () => {
  expect(slotOf(pair, 'alex')).toBe('a')
  expect(slotOf(pair, 'sam')).toBe('b')
  expect(slotOf([...pair, { id: 'guest', name: 'Guest' }], 'guest')).toBeNull()
  expect(slotOf(pair, null)).toBeNull()
})

test('a gap of 2 or more is a disagreement; a blank never is', () => {
  expect(disagrees(4, 2)).toBe(true)
  expect(disagrees(4, 3)).toBe(false)
  expect(disagrees(4, undefined)).toBe(false)
})
