import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Media } from '@/api/types'
import { DistrictMap } from '@/components/house/DistrictMap'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

export type ViewerTab = 'photos' | 'plans' | 'map'
export interface ViewerState { tab: ViewerTab; index: number }

const TAB_LABEL: Record<ViewerTab, string> = { photos: 'Photos', plans: 'Plans', map: 'Map' }
// The viewer is black in both themes, so its controls are white on translucent black.
const glass = 'bg-black/55 text-white backdrop-blur-sm hover:bg-black/70 hover:text-white'

/** One swipeable row of images. Swiping scrolls natively (CSS scroll-snap); Previous/Next
 *  and the arrow keys change `index`, which scrolls the row there. Each image is scaled to
 *  fit the screen whole (object-contain), so nothing is cropped in portrait or landscape. */
function Slides({ items, index, onIndex, label, onTap }: {
  items: Media[]; index: number; onIndex: (i: number) => void; label: string; onTap: () => void
}) {
  const row = useRef<HTMLDivElement>(null)
  const shown = () => {
    const el = row.current
    return el && el.clientWidth ? Math.round(el.scrollLeft / el.clientWidth) : null
  }
  useEffect(() => {
    const el = row.current
    const at = shown()
    // Scroll only when the row shows another slide than `index` (a button or key moved
    // it). After a swipe they already agree, so a finger is never fought.
    if (el && at != null && at !== index) el.scrollTo?.({ left: index * el.clientWidth, behavior: 'instant' })
  }, [index])
  return (
    <div ref={row} onClick={onTap}
      onScroll={() => { const at = shown(); if (at != null && at !== index) onIndex(at) }}
      className="flex size-full snap-x snap-mandatory overflow-x-auto overscroll-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {items.map((m, i) => (
        <div key={m.id} className="grid size-full shrink-0 snap-center place-items-center">
          <img src={m.url} alt={m.caption ?? `${label} ${i + 1} of ${items.length}`}
            loading={Math.abs(i - index) <= 1 ? 'eager' : 'lazy'}
            className="max-h-full max-w-full object-contain" />
        </div>
      ))}
    </div>
  )
}

/** Photos, floor plans and the district map, edge to edge. Turn the phone and the picture
 *  fills the width instead; the controls move into the black side margins. */
export function Viewer({ state, photos, plans, location, onChange, onClose, onDelete }: {
  state: ViewerState | null
  photos: Media[]; plans: Media[]; location: { lat: number; lon: number } | null
  onChange: (s: ViewerState) => void; onClose: () => void; onDelete?: (m: Media) => void
}) {
  const [chrome, setChrome] = useState(true)
  const tabs = (['photos', 'plans', 'map'] as const).filter(t =>
    t === 'photos' ? photos.length > 0 : t === 'plans' ? plans.length > 0 : location != null)
  const tab = state?.tab ?? 'photos'
  const items = tab === 'plans' ? plans : photos
  const index = Math.min(state?.index ?? 0, Math.max(items.length - 1, 0))
  const current = tab === 'map' ? undefined : items[index]
  const go = (d: number) => { if (state && tab !== 'map' && items.length) onChange({ tab, index: (index + d + items.length) % items.length }) }
  const counter = tab === 'map' ? 'Map' : `${index + 1} / ${items.length}`
  const hide = chrome ? '' : 'hidden'

  return (
    <Dialog open={state != null} onOpenChange={open => { if (!open) { setChrome(true); onClose() } }}>
      <DialogContent aria-describedby={undefined} showCloseButton={false}
        onKeyDown={e => { if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1) }}
        className="top-0 left-0 block h-dvh w-dvw max-w-none translate-x-0 translate-y-0 gap-0 rounded-none bg-viewer p-0 text-white ring-0 sm:max-w-none">
        <DialogTitle className="sr-only">{tab === 'map' ? 'Map' : `${TAB_LABEL[tab]} ${counter}`}</DialogTitle>

        {tab === 'map' && location
          ? <div className="viewer-map"><DistrictMap lat={location.lat} lon={location.lon} className="h-dvh" layersTop={64} /></div>
          : <Slides items={items} index={index} label={tab === 'plans' ? 'Floor plan' : 'Photo'}
              onIndex={i => onChange({ tab, index: i })} onTap={() => setChrome(c => !c)} />}

        <DialogClose asChild>
          <Button variant="ghost" size="icon-lg" aria-label="Close" className={cn('absolute top-3 left-3', glass, hide)}><X /></Button>
        </DialogClose>
        <span className={cn('absolute top-5 right-3 rounded-full px-3 py-1 text-sm font-semibold', glass, hide)}>{counter}</span>

        {tabs.length > 1 && (
          <div role="tablist" aria-label="Show"
            className={cn('absolute top-3 left-1/2 flex -translate-x-1/2 gap-0.5 rounded-full p-1', glass,
              'phone-landscape:top-auto phone-landscape:right-2 phone-landscape:bottom-3 phone-landscape:left-auto phone-landscape:w-16 phone-landscape:translate-x-0 phone-landscape:flex-col',
              hide)}>
            {tabs.map(t => (
              <button key={t} type="button" role="tab" aria-selected={t === tab} onClick={() => onChange({ tab: t, index: 0 })}
                className={cn('h-11 rounded-full px-4 text-sm font-semibold phone-landscape:px-0 phone-landscape:text-xs',
                  t === tab ? 'bg-white text-black' : 'text-white')}>
                {TAB_LABEL[t]}
              </button>
            ))}
          </div>
        )}

        {tab !== 'map' && items.length > 1 && (
          <>
            <Button variant="ghost" size="icon-lg" aria-label="Previous" onClick={() => go(-1)}
              className={cn('absolute top-1/2 left-3 -translate-y-1/2 phone-landscape:left-10', glass, hide)}><ChevronLeft /></Button>
            <Button variant="ghost" size="icon-lg" aria-label="Next" onClick={() => go(1)}
              className={cn('absolute top-1/2 right-3 -translate-y-1/2 phone-landscape:right-10', glass, hide)}><ChevronRight /></Button>
          </>
        )}

        {tab === 'plans' && plans.length > 1 && (
          <div className={cn('absolute bottom-6 left-1/2 flex -translate-x-1/2 gap-1 rounded-full p-1', glass,
            'phone-landscape:top-1/2 phone-landscape:bottom-auto phone-landscape:left-2 phone-landscape:w-16 phone-landscape:translate-x-0 phone-landscape:-translate-y-1/2 phone-landscape:flex-col',
            hide)}>
            {plans.map((m, i) => (
              <button key={m.id} type="button" aria-pressed={i === index} onClick={() => onChange({ tab, index: i })}
                className={cn('h-11 rounded-full px-4 text-sm font-semibold phone-landscape:px-0 phone-landscape:text-xs',
                  i === index ? 'bg-white text-black' : 'text-white')}>
                {m.caption ?? `Floor ${i + 1}`}
              </button>
            ))}
          </div>
        )}

        {tab === 'photos' && photos.length > 1 && (
          <div className={cn('absolute inset-x-0 bottom-0 space-y-2 bg-linear-to-t from-black/85 to-transparent px-3 pt-10 pb-[max(1rem,env(safe-area-inset-bottom))] phone-landscape:hidden', hide)}>
            <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]">
              {photos.map((m, i) => (
                <button key={m.id} type="button" aria-label={`Show photo ${i + 1}`} onClick={() => onChange({ tab, index: i })}
                  className={cn('h-14 w-20 shrink-0 overflow-hidden rounded-lg', i === index ? 'ring-2 ring-white' : 'opacity-50')}>
                  <img src={m.url} alt="" loading="lazy" className="size-full object-cover" />
                </button>
              ))}
            </div>
            <p className="text-center text-xs text-white/70 lg:hidden">Swipe for the next · pinch to zoom · turn the phone for landscape</p>
          </div>
        )}

        {current?.source === 'manual' && onDelete && (
          <Button variant="destructive" size="sm" onClick={() => onDelete(current)}
            className={cn('absolute bottom-28 left-3 phone-landscape:bottom-3 h-11', hide)}>Delete photo</Button>
        )}
      </DialogContent>
    </Dialog>
  )
}
