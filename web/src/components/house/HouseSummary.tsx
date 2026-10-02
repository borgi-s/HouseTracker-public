import { ArrowUpRight } from 'lucide-react'
import { useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import type { HouseDetail } from '@/api/types'
import { NoteDialog } from '@/components/house/NoteDialog'
import { OpenHousePill } from '@/components/OpenHouse'
import { PriceDrop } from '@/components/PriceDrop'
import { Button, buttonVariants } from '@/components/ui/button'
import { splitDescription } from '@/lib/description'
import { DASH, money, num } from '@/lib/format'
import { openHouseLook } from '@/lib/openhouse'
import { cn } from '@/lib/utils'

// ponytail: length stands in for "overflows six lines" (jsdom has no layout). A short text
// is never clamped, so nothing is hidden without a Read more button.
const LONG_DESCRIPTION = 400

const jump = (id: string) => document.getElementById(id)?.scrollIntoView?.({ behavior: 'smooth' })
const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return 'the listing' } }

const still = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** A long description starts as a faded preview; tapping the text or Read more opens it.
 *  Opening and closing slide the height; closing scrolls back to the text's top when it
 *  is above the screen, so Show less never strands you further down the page. */
function Description({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const preview = useRef(0)                 // the preview's height, to slide back to
  const long = text.length > LONG_DESCRIPTION
  const collapsed = long && !open
  const toggle = () => {
    const el = box.current
    if (!el?.animate || still()) {          // jsdom, or reduced motion
      if (open) el?.scrollIntoView?.({ block: 'start' })
      return setOpen(o => !o)
    }
    const from = el.offsetHeight
    if (!open) {
      preview.current = from
      flushSync(() => setOpen(true))
      el.animate({ height: [`${from}px`, `${el.offsetHeight}px`] }, { duration: 300, easing: 'ease-out' })
    } else {
      if (el.getBoundingClientRect().top < 64) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      el.animate({ height: [`${from}px`, `${preview.current}px`] }, { duration: 300, easing: 'ease-in' })
        .onfinish = () => setOpen(false)
    }
  }
  return (
    <div ref={box} className="max-w-prose scroll-mt-20 overflow-hidden text-base leading-relaxed">
      <p onClick={collapsed ? toggle : undefined}
        className={cn('whitespace-pre-line',
          collapsed && 'line-clamp-6 cursor-pointer [mask-image:linear-gradient(to_bottom,black_40%,transparent)]')}>
        {text}
      </p>
      {long && (
        <Button variant="link" className="h-auto min-h-11 px-0 pt-2 font-bold" aria-expanded={open} onClick={toggle}>
          {open ? 'Show less' : 'Read more'}
        </Button>
      )}
    </div>
  )
}

/** Address, size and price; the listing's headline and text; what to do next; the key facts. */
export function HouseSummary({ detail }: { detail: HouseDetail }) {
  const h = detail.house
  const place = [h.postal_code, h.city].filter(Boolean).join(' ')
  const { lead, rest } = splitDescription(h.description ?? '')
  const facts: [string, string][] = [
    ['Ejerudgift / md', money(h.ejerudgift_dkk)],
    ['Kvm-pris', money(h.price_per_m2)],
    ['Lot', num(h.lot_m2, 'm²')],
    ['Rooms', num(h.rooms)],
    ['Built', h.build_year == null ? DASH : String(h.build_year)],
    ['Energimærke', h.energy_label ?? DASH],
  ]
  const listing = h.listing_url && (
    <a href={h.listing_url} target="_blank" rel="noreferrer" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
      Listing on {host(h.listing_url)}<ArrowUpRight aria-hidden />
    </a>
  )
  return (
    <section aria-label="Summary" className="space-y-8">
      <div className="flex flex-col gap-2 border-b pb-5 lg:flex-row lg:items-baseline lg:justify-between lg:gap-12">
        <div className="text-3xl font-bold tracking-tight lg:text-[1.75rem]">
          <h1 className="inline">{h.address}</h1>
          {place && (
            <span className="block font-normal text-muted-foreground lg:inline lg:font-bold lg:text-foreground">
              <span className="hidden lg:inline">, </span>{place}
            </span>
          )}
        </div>
        <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-lg lg:gap-12 lg:text-2xl">
          <span>{num(h.size_m2, 'm²')}</span>
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>Kontant <b className="font-bold">{money(h.price_dkk)}</b></span>
            <PriceDrop original={detail.price_history.original_price_dkk} price={h.price_dkk} />
            {openHouseLook(h.status) && <OpenHousePill slots={detail.open_houses} />}
          </span>
        </p>
      </div>
      {(lead || rest) && (
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-16">
          <div className="space-y-6">
            {lead && <p className="text-2xl leading-tight font-medium tracking-tight text-balance lg:text-[2.35rem]">{lead}</p>}
            <div className="hidden flex-wrap gap-2.5 lg:flex">
              <Button size="lg" variant={h.status === 'not_visited' ? 'outline' : 'default'} onClick={() => jump('our-take')}>
                Rate this house
              </Button>
              <NoteDialog houseId={h.id} trigger={<Button size="lg" variant="outline">Add note</Button>} />
              {listing}
            </div>
          </div>
          {rest && <Description text={rest} />}
        </div>
      )}
      <dl className="grid grid-cols-2 border-y sm:grid-cols-3 lg:grid-cols-6">
        {facts.map(([k, v], i) => (
          <div key={k} className={cn('space-y-1 py-4 pr-3 lg:px-5', i > 0 && 'lg:border-l', i === 0 && 'lg:pl-0')}>
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="text-xl lg:text-2xl">{v}</dd>
          </div>
        ))}
      </dl>
      {h.listing_url && <div className={lead || rest ? 'lg:hidden' : ''}>{listing}</div>}
    </section>
  )
}
