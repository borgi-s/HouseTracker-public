import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { Anchor, HouseListItem } from '@/api/types'
import { MapLayers } from '@/components/map/MapLayers'
import { combined, score5 } from '@/lib/format'
import { mio } from '@/lib/geo'
import { dropPct } from '@/lib/price'
import { cn } from '@/lib/utils'

const located = (h: HouseListItem) => h.lat != null && h.lon != null

/** A pin's text: the price, and the combined score once someone has scored the house. */
export function pinText(h: HouseListItem, pairIds: string[]): string {
  const c = combined(h.overall, pairIds)
  return c == null ? mio(h.price_dkk) : `${mio(h.price_dkk)} · ${score5(c)}`
}

/** OpenStreetMap with a price pin per house and the main anchor, framed to fit them all.
 *  Pins are buttons; clicking one selects its house.
 *  Pass `card` to show a Leaflet popup anchored above the selected pin;
 *  `centerCard` (laptop) also pans so the card sits mid-map on each new selection. */
export function HousesMap({ houses, pairIds, anchor, selected, onSelect, card, centerCard, className }: {
  houses: HouseListItem[]; pairIds: string[]; anchor: Anchor | null
  selected: string | null; onSelect: (id: string | null) => void; card?: ReactNode; centerCard?: boolean; className?: string
}) {
  const el = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<L.Map | null>(null)
  // Stable container for the popup content; React portals into it
  const [popupContainer] = useState(() => document.createElement('div'))
  const popupRef = useRef<L.Popup | null>(null)
  const onSelectRef = useRef(onSelect)
  useEffect(() => { onSelectRef.current = onSelect })
  const pairKey = pairIds.join()
  const framedFor = houses.filter(located).map(h => h.id).join()

  useEffect(() => {
    const m = L.map(el.current!, { scrollWheelZoom: true }).setView([55.77, 12.5], 12)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(m)
    const popup = L.popup({
      className: 'house-popup',
      autoPan: true,
      autoPanPaddingTopLeft: L.point(12, 128),   // clear List button + zoom controls
      autoPanPaddingBottomRight: L.point(12, 56), // clear handle-only sheet
      offset: L.point(0, -21),                    // tip touches price-pin top (measured)
      closeButton: false,                         // owner closes by tapping map; × fails 44px rule
      closeOnClick: false,                        // disable preclick→close; we handle it below
    }).setContent(popupContainer)
    popupRef.current = popup
    m.on('popupclose', () => onSelectRef.current(null))
    // Close on map tap (not pin tap — pins call stopPropagation, blocking this handler).
    // Using explicit click instead of closeOnClick/preclick prevents the re-selection race:
    // on touch, Leaflet fires preclick on the map before the pin's click handler runs,
    // which would call onSelect(null) right as the user taps a different pin.
    m.on('click', () => { if (popupRef.current) m.closePopup(popupRef.current) })
    setMap(m)
    return () => { m.remove() }
  }, [popupContainer])

  // Open or close the popup when selected or card changes
  useEffect(() => {
    if (!map || !popupRef.current || !card) return
    if (selected) {
      const h = houses.find(h => h.id === selected)
      if (h?.lat != null && h?.lon != null) {
        popupRef.current.setLatLng([h.lat!, h.lon!]).openOn(map)
      }
    } else {
      map.closePopup(popupRef.current)
    }
  }, [selected, map, houses, card])

  // Centre the card, not the pin. Keyed on the selection only, so re-renders don't yank
  // the map back after the user pans away.
  useEffect(() => {
    const el = popupRef.current?.getElement()
    if (!map || !centerCard || !selected || !el || map.getSize().x === 0) return  // jsdom has no layout
    const c = el.getBoundingClientRect(), m = map.getContainer().getBoundingClientRect()
    map.panBy([c.left + c.width / 2 - (m.left + m.width / 2), c.top + c.height / 2 - (m.top + m.height / 2)])
  }, [map, selected, centerCard])

  useEffect(() => {
    if (!map) return
    const layer = L.layerGroup().addTo(map)
    for (const h of houses.filter(located)) {
      const pin = document.createElement('button')
      pin.type = 'button'
      pin.className = cn('price-pin', h.status === 'not_visited' && 'price-pin-todo', h.id === selected && 'price-pin-on')
      pin.textContent = pinText(h, pairKey.split(','))           // textContent: the address is third-party data
      const drop = dropPct(h.original_price_dkk, h.price_dkk)
      pin.setAttribute('aria-label', `${h.address}, ${pin.textContent}${drop ? `, price reduced ${drop}%` : ''}`)
      if (drop) pin.append(Object.assign(document.createElement('span'), { className: 'price-drop', textContent: `↓${drop}%` }))
      pin.addEventListener('click', e => { e.stopPropagation(); onSelectRef.current(h.id) })
      L.marker([h.lat!, h.lon!], { icon: L.divIcon({ html: pin, className: 'pin-anchor', iconSize: [0, 0] }), keyboard: false })
        .addTo(layer)
    }
    if (anchor?.lat != null && anchor.lon != null) {
      const a = Object.assign(document.createElement('span'), { className: 'anchor-pin', textContent: anchor.label })
      L.marker([anchor.lat, anchor.lon], { icon: L.divIcon({ html: a, className: 'pin-anchor', iconSize: [0, 0] }), interactive: false })
        .addTo(layer)
    }
    return () => { layer.remove() }
  }, [map, houses, selected, anchor, pairKey])

  // Frame all pins when the set of houses changes, not on every selection.
  useEffect(() => {
    if (!map || map.getSize().x === 0) return                      // jsdom has no layout
    const pts = houses.filter(located).map(h => [h.lat!, h.lon!] as L.LatLngTuple)
    if (anchor?.lat != null && anchor.lon != null) pts.push([anchor.lat, anchor.lon])
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [56, 56], maxZoom: 14 })
  }, [map, framedFor, anchor?.id])

  const picked = houses.find(h => h.id === selected && located(h))
  return (
    <div className={cn('relative', className)}>
      <div ref={el} className="isolate size-full" />
      <MapLayers map={map} focus={picked ? { lat: picked.lat!, lon: picked.lon! } : null} around="view" />
      {card && createPortal(card, popupContainer)}
    </div>
  )
}
