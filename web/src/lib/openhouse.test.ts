import { expect, test } from 'vitest'
import type { OpenHouse } from '@/api/types'
import {
  clock, dayLabel, fullDay, openHouseLook, previous, signupLabel, slotLabel, upcoming,
} from '@/lib/openhouse'

const oh = (starts_at: string, ends_at: string, over: Partial<OpenHouse> = {}): OpenHouse =>
  ({ starts_at, ends_at, signup: null, signup_url: null, cancelled: false, ...over })

const SUN = oh('2026-10-04T13:30:00Z', '2026-10-04T13:50:00Z', { signup: true })
const NEXT = oh('2026-10-11T08:00:00Z', '2026-10-11T08:30:00Z', { signup: false })
const GONE = oh('2026-10-05T08:00:00Z', '2026-10-05T08:30:00Z', { cancelled: true })
const NOW = new Date('2026-10-01T10:00:00Z')

test('upcoming: not cancelled, not over, soonest first; previous: the rest, newest first', () => {
  expect(upcoming([NEXT, GONE, SUN], NOW)).toEqual([SUN, NEXT])
  const during = new Date('2026-10-04T13:40:00Z')
  expect(upcoming([SUN, NEXT], during)).toEqual([SUN, NEXT])               // still on
  const after = new Date('2026-10-04T13:51:00Z')
  expect(upcoming([SUN, NEXT], after)).toEqual([NEXT])
  expect(previous([SUN, NEXT, GONE], after)).toEqual([GONE, SUN])
})

test('labels are in Danish time', () => {
  expect(clock(SUN.starts_at)).toBe('15:30')
  expect(dayLabel(SUN.starts_at, NOW)).toBe('Sun 4 Oct')
  expect(slotLabel(SUN, NOW)).toBe('Sun 4 Oct 15:30')
  expect(fullDay(SUN.starts_at)).toBe('Sun, 4 Oct 2026')
  expect(clock('2026-11-01T12:00:00Z')).toBe('13:00')                       // winter time
})

test('Today and Tomorrow follow the Danish calendar, also across the clock change', () => {
  expect(dayLabel(SUN.starts_at, new Date('2026-10-04T06:00:00Z'))).toBe('Today')
  expect(dayLabel(SUN.starts_at, new Date('2026-10-03T22:01:00Z'))).toBe('Today')      // 00:01 on the 4th in Denmark
  expect(dayLabel(SUN.starts_at, new Date('2026-10-03T21:59:00Z'))).toBe('Tomorrow')   // 23:59 on the 3rd
  expect(dayLabel(SUN.starts_at, new Date('2026-10-03T12:00:00Z'))).toBe('Tomorrow')
  // 25 Oct 00:30 CEST → a slot on 26 Oct 00:30 CET is tomorrow, though 25 hours away
  expect(dayLabel('2026-10-25T23:30:00Z', new Date('2026-10-24T22:30:00Z'))).toBe('Tomorrow')
})

test('sign-up label and which look a status gets', () => {
  expect([SUN, NEXT, oh('x', 'y')].map(signupLabel)).toEqual(['Sign-up', 'Drop-in', null])
  expect(openHouseLook('not_visited')).toBe('band')
  expect((['visited', 'shortlist', 'offer'] as const).map(openHouseLook)).toEqual(['pill', 'pill', 'pill'])
  expect(openHouseLook('rejected')).toBeNull()
  expect(openHouseLook('sold')).toBeNull()
})
