import type { OpenHouse } from '@/api/types'
import { signupLabel, slotLabel, upcoming } from '@/lib/openhouse'
import { cn } from '@/lib/utils'

/** The next open house as a strip across the bottom of a card photo, for houses we have
 *  not visited (spec D3). Clicks fall through to the photo's link. */
export function OpenHouseBand({ slots, now = new Date() }: { slots: OpenHouse[]; now?: Date }) {
  const next = upcoming(slots, now)
  if (!next.length) return null
  const kind = signupLabel(next[0])
  return (
    <p className="pointer-events-none absolute inset-x-0 bottom-0 flex items-baseline justify-between gap-2 bg-openhouse px-3 py-2 text-sm text-openhouse-foreground">
      <span>
        <b className="font-bold tracking-wide uppercase">Open house</b> {slotLabel(next[0], now)}
        {next.length > 1 && ` +${next.length - 1} more`}
      </span>
      {kind && <span className="text-xs font-semibold">{kind}</span>}
    </p>
  )
}

/** The small version, beside a price. */
export function OpenHousePill({ slots, now = new Date(), className }: {
  slots: OpenHouse[]; now?: Date; className?: string
}) {
  const next = upcoming(slots, now)
  if (!next.length) return null
  return (
    <span className={cn('inline-flex shrink-0 items-center rounded-full bg-openhouse px-2 py-0.5 text-xs font-bold leading-tight text-openhouse-foreground', className)}>
      Open house {slotLabel(next[0], now)}{next.length > 1 && ` +${next.length - 1}`}
    </span>
  )
}
