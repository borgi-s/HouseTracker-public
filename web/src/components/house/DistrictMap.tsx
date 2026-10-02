import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { MapLayers } from '@/components/map/MapLayers'
import { cn } from '@/lib/utils'

/** OpenStreetMap around the house, pinned, with the school districts drawn over it (each
 *  labelled once, the house's own filled in) and, when interactive, the Layers menu.
 *  `layersTop` moves the Layers button below whatever sits over the map's top edge. */
export function DistrictMap({ lat, lon, className, interactive = true, layersTop }: {
  lat: number; lon: number; className?: string; interactive?: boolean; layersTop?: number
}) {
  const el = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<L.Map | null>(null)

  useEffect(() => {
    const m = L.map(el.current!, interactive
      ? { scrollWheelZoom: false }
      : { zoomControl: false, attributionControl: false, dragging: false, scrollWheelZoom: false,
          doubleClickZoom: false, touchZoom: false, boxZoom: false, keyboard: false })
      .setView([lat, lon], 14)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap · districts: GeoFA',
    }).addTo(m)
    L.circleMarker([lat, lon], { radius: 7, className: 'house-pin' }).bindTooltip('This house').addTo(m)
    setMap(m)
    return () => { m.remove() }
  }, [lat, lon, interactive])

  return (
    <div className={cn('relative', className && 'h-full')}>
      <div ref={el} className={cn('isolate w-full', className ?? 'h-[50dvh] rounded-2xl border bg-card lg:h-[70dvh]')} />
      <MapLayers map={map} focus={{ lat, lon }} menu={interactive} top={layersTop} />
    </div>
  )
}
