import { List } from 'lucide-react'
import { type ReactNode, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useAnchors } from '@/api/queries'
import type { Anchor, HouseListItem, Person } from '@/api/types'
import { HousesMap } from '@/components/HousesMap'
import { OpenHousePill } from '@/components/OpenHouse'
import { PriceDrop } from '@/components/PriceDrop'
import { Button } from '@/components/ui/button'
import { mainAnchor } from '@/lib/compare'
import { km, money, num, score5 } from '@/lib/format'
import { distanceKm } from '@/lib/geo'
import { openHouseLook } from '@/lib/openhouse'
import { useIsDesktop } from '@/lib/useIsDesktop'
import { cn } from '@/lib/utils'

type SheetStop = 'down' | 'peek' | 'open'
const STOP_PX = { down: 44, peek: 224 } as const

/** Snap height to the nearest of the three stops. Exported for testing. */
export function snapStop(heightPx: number, areaH: number): SheetStop {
  const stops = [44, 224, areaH * 0.85] as const
  const names: SheetStop[] = ['down', 'peek', 'open']
  return names[stops.reduce((best, h, i) =>
    Math.abs(h - heightPx) < Math.abs(stops[best] - heightPx) ? i : best, 0)]
}

function away(h: HouseListItem, anchor: Anchor | null): string | null {
  if (!anchor || anchor.lat == null || anchor.lon == null) return null
  if (h.lat == null || h.lon == null) return 'No location yet'
  return `${km(distanceKm({ lat: h.lat, lon: h.lon }, { lat: anchor.lat, lon: anchor.lon }) * 1000)} to ${anchor.label}`
}

function scoreLine(h: HouseListItem, pair: Person[]): string {
  return pair.some(p => h.overall[p.id] != null)
    ? pair.map(p => `${p.name} ${score5(h.overall[p.id])}`).join(' · ')
    : 'Not rated yet'
}

function Row({ house: h, pair, anchor, active, onSelect }: {
  house: HouseListItem; pair: Person[]; anchor: Anchor | null; active: boolean; onSelect: () => void
}) {
  return (
    <li className={cn('relative grid grid-cols-[8.5rem_1fr] items-center gap-4 rounded-2xl p-2.5 hover:bg-muted',
      active && 'bg-muted ring-2 ring-person-a')}>
      <button type="button" aria-label={`Show ${h.address} on the map`} onClick={onSelect} className="absolute inset-0 rounded-2xl" />
      {h.cover_url
        ? <img src={h.cover_url} alt="" loading="lazy" className="aspect-[4/3] w-full rounded-xl object-cover" />
        : <div className="aspect-[4/3] w-full rounded-xl bg-muted" />}
      <div className="min-w-0 space-y-0.5">
        <p className="flex flex-wrap items-center gap-2 text-lg font-bold">{money(h.price_dkk)}<PriceDrop original={h.original_price_dkk} price={h.price_dkk} />{openHouseLook(h.status) && <OpenHousePill slots={h.open_houses} />}</p>
        <Link to={`/house/${encodeURIComponent(h.id)}`} className="relative z-10 block truncate font-semibold hover:underline">{h.address}</Link>
        <p className="text-[13px] text-muted-foreground" title="Straight-line distance">
          {[num(h.size_m2, 'm²'), h.energy_label && `Energi ${h.energy_label}`, away(h, anchor)].filter(Boolean).join(' · ')}
        </p>
        <p className="text-[13px]">{scoreLine(h, pair)}</p>
      </div>
    </li>
  )
}

/** Card shown above a price pin in a Leaflet popup. */
function PopupCard({ house: h, pair, anchor }: { house: HouseListItem; pair: Person[]; anchor: Anchor | null }) {
  return (
    <Link to={`/house/${encodeURIComponent(h.id)}`} className="block w-72">
      {h.cover_url && <img src={h.cover_url} alt="" className="h-32 w-full object-cover" />}
      <div className="space-y-0.5 p-3.5">
        <p className="flex flex-wrap items-center gap-2 font-bold">{money(h.price_dkk)}<PriceDrop original={h.original_price_dkk} price={h.price_dkk} />{openHouseLook(h.status) && <OpenHousePill slots={h.open_houses} />}</p>
        <p className="font-semibold">{h.address}</p>
        <p className="text-[13px] text-muted-foreground">
          {[num(h.size_m2, 'm²'), h.energy_label && `Energi ${h.energy_label}`, away(h, anchor)].filter(Boolean).join(' · ')}
        </p>
        <p className="text-[13px]">{scoreLine(h, pair)}</p>
      </div>
    </Link>
  )
}

/** The list as a map: list beside it on a laptop; a pull-up list over it on the phone,
 *  with the list's filters in a scrolling row along the top (the page's are covered). */
export function HousesMapView({ houses, pair, toolbar, filters, onList }: {
  houses: HouseListItem[]; pair: Person[]; toolbar?: ReactNode; filters?: ReactNode; onList: () => void
}) {
  const desktop = useIsDesktop()
  const anchor = mainAnchor(useAnchors().data)
  const [selected, setSelected] = useState<string | null>(null)
  const [stop, setStop] = useState<SheetStop>('peek')
  const [liveH, setLiveH] = useState<number | null>(null)
  const dragRef = useRef<{ startY: number; startH: number } | null>(null)
  const sectionRef = useRef<HTMLElement>(null)
  const pairIds = pair.map(p => p.id)
  const pick = houses.find(h => h.id === selected)

  function containerH() { return sectionRef.current?.parentElement?.clientHeight ?? 600 }
  function stopH(s: SheetStop) { return s === 'open' ? containerH() * 0.85 : STOP_PX[s] }

  function handlePinSelect(id: string | null) {
    setSelected(id)
    if (!desktop && id !== null) setStop('down')
  }

  function handlePointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    dragRef.current = { startY: e.clientY, startH: sectionRef.current?.clientHeight ?? stopH(stop) }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function handlePointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    if (!dragRef.current) return
    const delta = dragRef.current.startY - e.clientY
    setLiveH(Math.max(44, Math.min(dragRef.current.startH + delta, containerH())))
  }
  function handlePointerUp(e: React.PointerEvent<HTMLButtonElement>) {
    if (!dragRef.current) return
    const delta = Math.abs(e.clientY - dragRef.current.startY)
    const newStop = delta < 6
      ? (stop === 'open' ? 'peek' : 'open')
      : snapStop(liveH ?? stopH(stop), containerH())
    dragRef.current = null
    setLiveH(null)
    setStop(newStop)
  }
  function handlePointerCancel() {
    if (!dragRef.current) return
    const startH = dragRef.current.startH
    dragRef.current = null
    setLiveH(null)
    setStop(snapStop(startH, containerH()))
  }

  const rows = houses.map(h => (
    <Row key={h.id} house={h} pair={pair} anchor={anchor} active={h.id === selected}
      onSelect={() => { setSelected(h.id); if (!desktop) setStop('down') }} />
  ))

  const popupCard = pick ? <PopupCard house={pick} pair={pair} anchor={anchor} /> : undefined

  if (desktop) {
    return (
      <div className="grid h-[calc(100dvh-19rem)] min-h-[32rem] grid-cols-[32rem_1fr] gap-6">
        <ul aria-label="Houses on the map" className="space-y-1.5 overflow-y-auto pr-1">{rows}</ul>
        <div className="overflow-hidden rounded-2xl">
          <HousesMap houses={houses} pairIds={pairIds} anchor={anchor} selected={selected}
            onSelect={setSelected} card={popupCard} centerCard className="size-full" />
        </div>
      </div>
    )
  }

  const isDragging = liveH !== null
  const heightClass = stop === 'open' ? 'h-[85%]' : stop === 'peek' ? 'h-56' : 'h-11'
  const map = <HousesMap houses={houses} pairIds={pairIds} anchor={anchor} selected={selected}
    onSelect={handlePinSelect} card={popupCard} className="size-full" />

  return (
    <div className={cn('map-under-bar fixed inset-x-0 top-16 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20',
      filters && 'map-under-bar-open')}>
      {map}
      <div className="absolute inset-x-0 top-3 z-[500] space-y-2">
        <div className="flex gap-2 px-3">
          <Button variant="outline" onClick={onList} className="h-11 shrink-0 shadow-lg"><List aria-hidden />List</Button>
          {toolbar}
        </div>
        {filters && <div className="flex gap-2 overflow-x-auto px-3 pb-1">{filters}</div>}
      </div>
      <section ref={sectionRef} aria-label="Houses on the map"
        style={isDragging && liveH !== null ? { height: `${liveH}px` } : undefined}
        className={cn('absolute inset-x-0 bottom-0 z-[500] flex flex-col rounded-t-3xl bg-background shadow-2xl',
          !isDragging && 'transition-[height] duration-300',
          !isDragging && heightClass)}>
        <button type="button"
          aria-expanded={stop === 'open'}
          aria-label={stop === 'open' ? 'Collapse list' : 'Expand list'}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          className="touch-none grid h-11 shrink-0 place-items-center">
          <span className="h-1.5 w-10 rounded-full bg-input" />
        </button>
        <ul className="space-y-1 overflow-y-auto px-3 pb-4">{rows}</ul>
      </section>
    </div>
  )
}
