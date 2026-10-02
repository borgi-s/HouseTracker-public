import { expect, test } from 'vitest'
import { apartOn, apartSentence } from '@/lib/apart'
import { makeCriterion } from '@/test-utils'

const C = [
  makeCriterion({ id: 'kitchen', label: 'Kitchen' }),
  makeCriterion({ id: 'noise', label: 'Noise' }),
  makeCriterion({ id: 'garden', label: 'Garden' }),
  makeCriterion({ id: 'size', label: 'Size', kind: 'auto' }),
]

test('apartOn lists criteria we both scored differently, biggest gap first', () => {
  expect(apartOn(C, { kitchen: 3, noise: 4, garden: 2 }, { kitchen: 4, noise: 4, garden: 5 }))
    .toEqual([{ label: 'Garden', gap: 3 }, { label: 'Kitchen', gap: 1 }])
})

test('apartSentence reads as one line', () => {
  expect(apartSentence(C, { kitchen: 3, garden: 2 }, { kitchen: 4, garden: 5 }))
    .toBe('Apart on garden (3) and kitchen (1). You agree on the rest you have both scored.')
  expect(apartSentence(C, { kitchen: 3, noise: 2, garden: 1 }, { kitchen: 4, noise: 3, garden: 2 }))
    .toBe('Apart on kitchen (1), noise (1) and garden (1). You agree on the rest you have both scored.')
  expect(apartSentence(C, { kitchen: 4 }, { kitchen: 4 })).toBe('You agree on everything you have both scored.')
  expect(apartSentence(C, { kitchen: 4 }, {})).toBe('Nothing scored by both of you yet.')
})
