import type { HouseDetail } from '@/api/types'
import { money, pctChange } from '@/lib/format'
import { timeline, type TimelineRow } from '@/lib/price'
import { cn } from '@/lib/utils'

const DAY = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
const day = (iso: string) => DAY.format(new Date(`${iso}T12:00:00`))

function Change({ from, to }: { from: number; to: number }) {
  return <span className={cn('font-semibold', to < from && 'text-drop')}>{to > from ? '+' : ''}{money(to - from)} ({pctChange(from, to)})</span>
}

function What({ row }: { row: TimelineRow }) {
  switch (row.kind) {
    case 'asking': return <>Asking {money(row.to)} <Change from={row.from} to={row.to} /></>
    case 'added': return <b>Added to our list</b>
    case 'before': return <>Asking {money(row.from)} → {money(row.to)} <Change from={row.from} to={row.to} /></>
    case 'listed': return <>Listed at {money(row.price)}{row.realtor && ` · ${row.realtor}`}</>
    case 'sold': return <>Sold for {money(row.price)}{row.type && row.type !== 'normal' && ` (${row.type})`}</>
  }
}

/** The house's price story, newest first, and how fresh it is. */
export function PriceHistoryPanel({ detail }: { detail: HouseDetail }) {
  const l = detail.price_history.listing
  const onMarket = l?.days_on_market != null && `${l.days_on_market} days on market${
    l.total_days_on_market != null && l.total_days_on_market > l.days_on_market
      ? ` (${l.total_days_on_market} in total, relisted)` : ''}`
  const checked = l?.checked_at ? `Checked daily · last checked ${day(l.checked_at)}` : 'Not checked online yet'
  return (
    <div className="space-y-3">
      <ol className="divide-y border-y">
        {timeline(detail.price_history, detail.house.created_at).map((r, i) => (
          <li key={i} className="grid grid-cols-[7.5rem_1fr] gap-3 py-2.5 text-sm sm:grid-cols-[9rem_1fr] sm:text-base">
            <span className="text-muted-foreground">{r.kind === 'before' ? `before ${day(r.date)}` : day(r.date)}</span>
            <span><What row={r} /></span>
          </li>
        ))}
      </ol>
      <p className="text-sm text-muted-foreground">{[onMarket, checked].filter(Boolean).join(' · ')}</p>
    </div>
  )
}
