import { expect, test } from 'vitest'
import { makeMedia } from '@/test-utils'
import { photosOf, POLL_LIMIT_MS, scrapedCount, shouldPoll } from './house'

const fp = makeMedia({ id: 'fp', kind: 'floorplan' })
const p1 = makeMedia({ id: 'p1', kind: 'photo' })
const u1 = makeMedia({ id: 'u1', kind: 'user_photo', source: 'manual' })

test('photos are the scraped ones first, then ours', () => {
  expect(photosOf([u1, fp, p1]).map(m => m.id)).toEqual(['p1', 'u1'])
})

test('poll until the pending media arrived, for at most 90 s', () => {
  expect(shouldPoll(3, 12, 0, 1000)).toBe(true)
  expect(shouldPoll(12, 12, 0, 1000)).toBe(false)
  expect(shouldPoll(3, 12, 0, POLL_LIMIT_MS)).toBe(false)
  expect(shouldPoll(0, 0, 0, 1000)).toBe(false)
  expect(shouldPoll(15, 12, 0, 1000)).toBe(true)     // a refresh still swapping out the old set
})

test('only scraped media count toward what a scrape is waiting for', () => {
  expect(scrapedCount([u1, fp, p1])).toBe(2)
})
