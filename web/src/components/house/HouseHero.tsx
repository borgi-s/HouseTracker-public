import { Camera, LayoutPanelLeft, type LucideIcon, MapPin, Maximize2 } from 'lucide-react'
import { useState } from 'react'
import type { Media } from '@/api/types'
import { DistrictMap } from '@/components/house/DistrictMap'
import type { ViewerTab } from '@/components/house/Viewer'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Location = { lat: number; lon: number } | null
type Open = (tab: ViewerTab, index: number) => void

const STAGES: { tab: ViewerTab; label: string; Icon: LucideIcon }[] = [
  { tab: 'photos', label: 'Photos', Icon: Camera },
  { tab: 'plans', label: 'Floor plan', Icon: LayoutPanelLeft },
  { tab: 'map', label: 'Map', Icon: MapPin },
]

function Picture({ m, label, onClick, plan = false, className }: {
  m: Media; label: string; onClick: () => void; plan?: boolean; className?: string
}) {
  return (
    <button type="button" aria-label={label} onClick={onClick}
      className={cn('group relative block size-full overflow-hidden bg-muted', className)}>
      <img src={m.url} alt={m.caption ?? ''}
        className={cn('size-full transition-transform duration-500 group-hover:scale-[1.04]',
          plan ? 'bg-white object-contain p-2' : 'object-cover')} />
    </button>
  )
}

/** Phone: every photo in one swipeable strip (CSS scroll-snap), with a counter. */
function PhotoStrip({ photos, onOpen }: { photos: Media[]; onOpen: (i: number) => void }) {
  const [at, setAt] = useState(0)
  return (
    <div className="relative size-full">
      <div onScroll={e => { const el = e.currentTarget; if (el.clientWidth) setAt(Math.round(el.scrollLeft / el.clientWidth)) }}
        className="flex size-full snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {photos.map((m, i) => (
          <button key={m.id} type="button" aria-label={`Open photo ${i + 1}`} onClick={() => onOpen(i)}
            className="size-full shrink-0 snap-center bg-muted">
            <img src={m.url} alt={m.caption ?? ''} loading={i === 0 ? 'eager' : 'lazy'} className="size-full object-contain" />
          </button>
        ))}
      </div>
      {photos.length > 1 && (
        <span className="pointer-events-none absolute right-3 bottom-9 rounded-full bg-black/70 px-2.5 py-0.5 text-xs font-semibold text-white">
          {at + 1} / {photos.length}
        </span>
      )}
    </div>
  )
}

/** Top of the house page: the photo, floor plan or map on the stage (the pill switches it)
 *  and, on a laptop, a mosaic of tiles beside it. Every picture opens the full-screen viewer. */
export function HouseHero({ photos, plans, location, desktop, onOpen }: {
  photos: Media[]; plans: Media[]; location: Location; desktop: boolean; onOpen: Open
}) {
  const stages = STAGES.filter(s =>
    s.tab === 'photos' ? photos.length > 0 : s.tab === 'plans' ? plans.length > 0 : location != null)
  const [picked, setPicked] = useState<ViewerTab>('photos')
  if (stages.length === 0) return null
  const stage = stages.some(s => s.tab === picked) ? picked : stages[0].tab

  const onStage = (
    <div className="relative size-full overflow-hidden bg-muted">
      {stage === 'photos' && (desktop
        ? <Picture m={photos[0]} label="Open photo 1" onClick={() => onOpen('photos', 0)} />
        : <PhotoStrip photos={photos} onOpen={i => onOpen('photos', i)} />)}
      {stage === 'plans' && <Picture m={plans[0]} label="Open floor plan 1" plan onClick={() => onOpen('plans', 0)} />}
      {stage === 'map' && location && (
        <>
          <DistrictMap lat={location.lat} lon={location.lon} className="h-full" />
          <Button size="sm" variant="outline" className={cn('absolute right-3 z-10 h-11', desktop ? 'bottom-3' : 'bottom-9')}
            onClick={() => onOpen('map', 0)}>
            <Maximize2 aria-hidden />Full screen
          </Button>
        </>
      )}
    </div>
  )
  const switcher = stages.length > 1 && (
    <div role="group" aria-label="Show on the stage"
      className={cn('absolute z-10 flex gap-0.5 rounded-full bg-background p-1 shadow-lg',
        desktop ? 'bottom-4 left-4' : '-bottom-6 phone-landscape:bottom-3 left-1/2 -translate-x-1/2')}>
      {stages.map(({ tab, label, Icon }) => (
        <button key={tab} type="button" aria-pressed={stage === tab} aria-label={desktop ? undefined : label}
          onClick={() => setPicked(tab)}
          className={cn('flex h-11 items-center justify-center gap-2 rounded-full text-sm font-semibold',
            desktop ? 'px-4' : 'w-14', stage === tab ? 'bg-primary text-primary-foreground' : 'text-foreground')}>
          <Icon aria-hidden className="size-[18px]" />{desktop && label}
        </button>
      ))}
    </div>
  )

  if (!desktop) {
    return (
      <div className="relative -mx-4 -mt-6 mb-4">
        <div className="h-72 phone-landscape:h-[calc(100dvh_-_11.875rem_-_env(safe-area-inset-bottom,0px))]">{onStage}</div>
        {switcher}
      </div>
    )
  }

  const tiles = [
    photos[1] && <Picture key="p2" m={photos[1]} label="Open photo 2" onClick={() => onOpen('photos', 1)} className="rounded-xl" />,
    plans[0] && <Picture key="fp" m={plans[0]} label="Open floor plan 1" plan onClick={() => onOpen('plans', 0)} className="rounded-xl border" />,
    photos[2] && <Picture key="p3" m={photos[2]} label="Open photo 3" onClick={() => onOpen('photos', 2)} className="rounded-xl" />,
    location && (
      <div key="map" className="relative size-full overflow-hidden rounded-xl">
        <DistrictMap lat={location.lat} lon={location.lon} interactive={false} className="h-full" />
        <button type="button" aria-label="Open map" onClick={() => onOpen('map', 0)} className="absolute inset-0 z-10" />
      </div>
    ),
  ].filter(Boolean).slice(0, 4)

  return (
    <div className="relative">
      <div className={cn('grid h-[30rem] gap-3', tiles.length ? 'grid-cols-[2fr_1fr_1fr] grid-rows-2' : 'grid-cols-1')}>
        <div className="relative row-span-2 overflow-hidden rounded-xl">{onStage}{switcher}</div>
        {tiles}
      </div>
      {photos.length > 1 && (
        <Button variant="outline" className="absolute right-3 bottom-3 z-10 shadow" onClick={() => onOpen('photos', 0)}>
          All {photos.length} photos
        </Button>
      )}
    </div>
  )
}
