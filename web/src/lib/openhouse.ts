import type { OpenHouse, Status } from '@/api/types'

const TZ = 'Europe/Copenhagen'
const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })
const hm = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' })
const short = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' })
const long = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })

const soonest = (a: OpenHouse, b: OpenHouse) => a.starts_at.localeCompare(b.starts_at)

/** Slots still to come, soonest first: not cancelled and not over yet (spec D7). */
export const upcoming = (slots: OpenHouse[], now: Date) =>
  slots.filter(s => !s.cancelled && new Date(s.ends_at) > now).sort(soonest)

/** Held or cancelled slots, newest first (spec D10). */
export const previous = (slots: OpenHouse[], now: Date) =>
  slots.filter(s => s.cancelled || new Date(s.ends_at) <= now).sort((a, b) => soonest(b, a))

/** "Today" / "Tomorrow" / "Sun 4 Oct", by the Danish calendar. */
export function dayLabel(iso: string, now: Date): string {
  const day = ymd.format(new Date(iso))
  const today = ymd.format(now)
  const [y, m, d] = today.split('-').map(Number)
  const tomorrow = new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10)
  return day === today ? 'Today' : day === tomorrow ? 'Tomorrow' : short.format(new Date(iso))
}

/** "15:30" in Danish time. */
export const clock = (iso: string) => hm.format(new Date(iso))
/** "Sun, 4 Oct 2026": for past slots, where Today/Tomorrow make no sense. */
export const fullDay = (iso: string) => long.format(new Date(iso))
/** The band's and the pill's text: "Sun 4 Oct 15:30". */
export const slotLabel = (s: OpenHouse, now: Date) => `${dayLabel(s.starts_at, now)} ${clock(s.starts_at)}`
export const signupLabel = (s: OpenHouse) => (s.signup == null ? null : s.signup ? 'Sign-up' : 'Drop-in')

/** How the lists show a house's next open house (spec D3). */
export function openHouseLook(status: Status): 'band' | 'pill' | null {
  if (status === 'not_visited') return 'band'
  return status === 'visited' || status === 'shortlist' || status === 'offer' ? 'pill' : null
}
