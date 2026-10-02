import { expect, test } from 'vitest'
import { since, statusCard } from '@/lib/status'

const history = [
  { status: 'not_visited' as const, at: '2026-09-20' },
  { status: 'visited' as const, at: '2026-09-22' },
]

test('since is the day the house last entered that status', () => {
  expect(since(history, 'visited')).toBe('22 September')
  expect(since(history, 'offer')).toBeNull()
})

test('each status has its own card; the first action is the likely next step', () => {
  expect(statusCard('not_visited', history)).toEqual({
    title: 'Not yet visited', text: 'Book a viewing through the listing, then mark it visited.',
    actions: [{ label: 'Mark visited', to: 'visited' }, { label: 'Not for us', to: 'rejected' }],
  })
  expect(statusCard('visited', history).title).toBe('Visited on 22 September')
  expect(statusCard('visited', history).actions.map(a => a.to)).toEqual(['shortlist', 'offer', 'rejected'])
  expect(statusCard('shortlist', history).actions[0]).toEqual({ label: 'Make an offer', to: 'offer' })
  expect(statusCard('offer', history).title).toBe('Offer made')
  expect(statusCard('rejected', history).actions).toEqual([{ label: 'Undo', to: 'visited' }])
  expect(statusCard('sold', history).actions).toEqual([])
})

test('a visited house with no history entry still gets a title', () => {
  expect(statusCard('visited', []).title).toBe('Visited')
})
