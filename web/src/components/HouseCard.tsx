import { Link } from 'react-router'
import type { HouseListItem, Person } from '@/api/types'
import { STATUS_LABELS } from '@/api/types'
import { OpenHouseBand, OpenHousePill } from '@/components/OpenHouse'
import { PriceDrop } from '@/components/PriceDrop'
import { ScoreRing } from '@/components/ScoreRing'
import { combined, money, num, score5 } from '@/lib/format'
import { openHouseLook } from '@/lib/openhouse'
import { cn } from '@/lib/utils'

export function HouseCard({ house: h, pair, selected, onToggle }: {
  house: HouseListItem; pair: Person[]; selected: boolean; onToggle: () => void
}) {
  const to = `/house/${encodeURIComponent(h.id)}`
  const place = [h.postal_code, h.city].filter(Boolean).join(' ')
  const facts = [num(h.size_m2, 'm²'), h.rooms != null && `${num(h.rooms)} vær.`,
    h.bathrooms != null && `${h.bathrooms} bad`, h.floors != null && `${h.floors} plan`,
    h.energy_label && `Energi ${h.energy_label}`, h.build_year].filter(Boolean).join(' · ')
  const rated = pair.some(p => h.overall[p.id] != null)
  const look = openHouseLook(h.status)
  return (
    <article className="group flex flex-col rounded-2xl transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-muted">
        <Link to={to} tabIndex={-1} aria-hidden className="block size-full">
          {h.cover_url
            ? <img src={h.cover_url} alt="" loading="lazy" className="size-full object-cover transition-transform duration-700 group-hover:scale-105" />
            : <div className="grid size-full place-items-center text-sm text-muted-foreground">No photo yet</div>}
        </Link>
        <span className={cn('absolute top-3 left-3 rounded-full px-3 py-1 text-xs font-semibold',
          h.status === 'not_visited' ? 'bg-sand' : 'bg-background')}>
          {STATUS_LABELS[h.status]}
        </span>
        <label className="absolute top-3 right-3 flex h-11 items-center gap-1.5 rounded-full bg-background px-3 text-xs font-semibold">
          <input type="checkbox" aria-label={`Compare ${h.address}`} checked={selected} onChange={onToggle} className="size-4 accent-primary" />
          Compare
        </label>
        {look === 'band' && <OpenHouseBand slots={h.open_houses} />}
      </div>
      <div className="flex flex-1 flex-col gap-1 px-1 pt-4">
        <div className="flex items-baseline justify-between gap-2">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[22px] font-bold tracking-tight">{money(h.price_dkk)}</span>
            <PriceDrop original={h.original_price_dkk} price={h.price_dkk} />
            {look === 'pill' && <OpenHousePill slots={h.open_houses} />}
          </span>
          {h.price_per_m2 != null && <span className="text-sm text-muted-foreground">{money(h.price_per_m2)}/m²</span>}
        </div>
        <h2 className="text-base font-semibold"><Link to={to} className="hover:underline">{h.address}</Link></h2>
        <p className="text-sm text-muted-foreground">{[place, facts].filter(Boolean).join(' · ')}</p>
        <div className="mt-2 flex min-h-14 items-center gap-4 border-t pt-3 text-sm">
          {rated ? (
            <>
              {pair.map((p, i) => <ScoreRing key={p.id} size="sm" name={p.name} value={h.overall[p.id]} tone={i === 0 ? 'a' : 'b'} />)}
              {pair.length === 2 && (
                <span className="ml-auto">Together <b className="text-xl font-semibold">{score5(combined(h.overall, pair.map(p => p.id)))}</b></span>
              )}
            </>
          ) : (
            <span className="text-muted-foreground">
              {h.status === 'not_visited' ? 'Not rated yet · rate it after the viewing' : 'Not rated yet'}
            </span>
          )}
        </div>
      </div>
    </article>
  )
}
