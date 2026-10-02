import type { HouseDetail, OpenHouse } from '@/api/types'
import { clock, dayLabel, fullDay, previous, upcoming } from '@/lib/openhouse'

/** Upcoming open houses with how to get in, then the ones that were held or cancelled,
 *  folded away (spec D5, D10). */
export function OpenHousePanel({ detail, now = new Date() }: { detail: HouseDetail; now?: Date }) {
  const next = upcoming(detail.open_houses, now)
  const past = previous(detail.open_houses, now)
  const span = (s: OpenHouse) => `${clock(s.starts_at)}–${clock(s.ends_at)}`
  const link = (s: OpenHouse) => s.signup_url ?? detail.house.listing_url
  return (
    <div className="space-y-3">
      {next.length ? (
        <ul className="divide-y border-y">
          {next.map(s => (
            <li key={s.starts_at} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
              <span><b className="font-semibold">{dayLabel(s.starts_at, now)}</b> {span(s)}</span>
              <span className="text-sm">
                {s.signup === true && (link(s)
                  ? <a href={link(s)!} target="_blank" rel="noreferrer" className="font-semibold underline">Sign up</a>
                  : 'Sign-up')}
                {s.signup === false && 'Drop-in'}
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="text-muted-foreground">No open house planned.</p>}
      {past.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-semibold">Previous open houses ({past.length})</summary>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {past.map(s => (
              <li key={s.starts_at}>{fullDay(s.starts_at)} {span(s)} · {s.cancelled ? 'cancelled' : 'held'}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
