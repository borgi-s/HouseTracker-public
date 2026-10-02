import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import { Layers, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { mimTiles, utmLayer } from '@/components/map/utmLayer'
import { type DistrictProps, districtsUrl } from '@/lib/districts'
import { clock, compass, danishTime, sunDay, sunPosition, towards, UP } from '@/lib/sun'

const LABEL_MIN_ZOOM = 13     // below this the district labels crowd each other; the outlines stay
// Miljøstyrelsen's noise map, in the pairs Boliga shows (a-g: the source; 1: the Lden map).
const NOISE = [
  { key: 'roads', label: 'Roads', layers: ['a1', 'b1'] },
  { key: 'trains', label: 'Trains', layers: ['c1', 'd1'] },
  { key: 'planes', label: 'Planes', layers: ['e1', 'g1'] },
]
// Miljøstyrelsen's national bands (Lden, dB), the colours read off its tiles.
const NOISE_BANDS = [['#98fd00', '53'], ['#fdfd00', '58'], ['#fd9800', '63'], ['#fd3200', '68'], ['#9832ca', '73+']]
const pad3 = (n: number) => String(n).padStart(3, '0')
// Cloudburst and the plots need our Dataforsyningen token, which /api/wms adds.
const KDS = { format: 'image/png', transparent: true, attribution: 'Klimadatastyrelsen' }
const FLOOD = {
  rain: {
    label: 'Cloudburst', min: 15, max: 150, step: 15, start: 60, text: (v: number) => `Where ${v} mm of rain pools`,
    layer: (v: number) => L.tileLayer.wms('/api/wms/elevation',
      { ...KDS, layers: 'dhm_bluespot_ekstremregn', styles: `bluespot_ekstremregn_0_${pad3(v)}`, opacity: 0.7, zIndex: 2 }),
  },
  sea: {
    label: 'Sea level rise', min: 10, max: 300, step: 10, start: 50, text: (v: number) => `Water ${v} cm higher`,
    layer: (v: number) => utmLayer(mimTiles(`theme-klimatilp-raster-hav${pad3(v)}cm`), { maxLevel: 11, opacity: 0.65 }),
  },
  streams: {
    label: 'Streams and lakes rise', min: 10, max: 100, step: 10, start: 50, text: (v: number) => `Water ${v} cm higher`,
    layer: (v: number) => utmLayer(mimTiles(`theme-klimatilp-raster-vandlob${pad3(v)}cm`), { maxLevel: 11, opacity: 0.65 }),
  },
}
type Flood = keyof typeof FLOOD | 'off'

/** The noise colours as a bar, each band labelled with the dB it starts at. */
function NoiseScale() {
  return (
    <div role="img" aria-label="Noise: green 53, yellow 58, orange 63, red 68, violet 73 dB and up">
      <div className="flex h-2.5 overflow-hidden rounded-full">
        {NOISE_BANDS.map(([colour]) => <span key={colour} className="flex-1" style={{ background: colour }} />)}
      </div>
      <div className="flex pt-0.5 text-[11px] font-semibold tabular-nums">
        {NOISE_BANDS.map(([, db]) => <span key={db} className="flex-1">{db}</span>)}<span>dB</span>
      </div>
    </div>
  )
}
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

type Point = { lat: number; lon: number }

/** School districts as outlined polygons, each labelled once; `here` fills the house's. */
function useDistricts(map: L.Map | null, at: Point | null, radiusM: number, highlight: boolean) {
  const districts = useQuery({
    queryKey: ['districts', at?.lat, at?.lon, radiusM],
    queryFn: async () => {
      const res = await fetch(districtsUrl(at!.lat, at!.lon, radiusM))
      if (!res.ok) throw new Error(`GeoFA ${res.status}`)
      return (await res.json()) as GeoJSON.FeatureCollection<GeoJSON.Geometry, DistrictProps>
    },
    enabled: at != null,
    staleTime: Infinity,
  })
  useEffect(() => {
    if (!map || !at || !districts.data) return
    const layer = L.layerGroup().addTo(map)
    districts.data.features.forEach((f, i) => {
      const { name, lx, ly } = f.properties
      const here = highlight && f.properties.here
      const colour = `dc${i % 8}`          // index.css: dc0..dc7
      L.geoJSON(f, { style: { className: `district ${colour}${here ? ' district-here' : ''}` } }).addTo(layer)
      // textContent, not HTML: the name is third-party data
      const label = Object.assign(document.createElement('span'), { textContent: name })
      if (here) label.className = 'district-label-here'
      L.tooltip({ permanent: true, direction: 'center', className: `district-label ${colour}` })
        .setLatLng([ly, lx]).setContent(label).addTo(layer)
    })
    const labels = () => map.getContainer().classList.toggle('district-labels-off', map.getZoom() < LABEL_MIN_ZOOM)
    map.on('zoomend', labels)
    labels()
    return () => { map.off('zoomend', labels); layer.remove() }
  }, [map, at?.lat, at?.lon, districts.data, highlight]) // eslint-disable-line react-hooks/exhaustive-deps
  return districts.isError
}

/** The map's centre, rounded to ~1 km so panning a street over refetches nothing; null when
 *  zoomed out too far for districts to read. */
function useViewCentre(map: L.Map | null, on: boolean): Point | null {
  const [centre, setCentre] = useState<Point | null>(null)
  useEffect(() => {
    if (!map || !on) return
    const update = () => {
      const c = map.getCenter()
      const lat = +c.lat.toFixed(2), lon = +c.lng.toFixed(2)
      setCentre(prev => (map.getZoom() < LABEL_MIN_ZOOM ? null
        : prev?.lat === lat && prev.lon === lon ? prev : { lat, lon }))
    }
    update()
    map.on('moveend', update)
    return () => { map.off('moveend', update) }
  }, [map, on])
  return on ? centre : null
}

/** Sun track around `at` on the 21st of the month: the arc of directions it shines from,
 *  rise and set, and where it stands at the chosen clock time with the shadow it casts. */
function useSun(map: L.Map | null, at: Point | null, month: number, minutes: number) {
  useEffect(() => {
    if (!map || !at) return
    const { lat, lon } = at
    const year = new Date().getFullYear()
    const group = L.layerGroup().addTo(map)
    const draw = () => {
      group.clearLayers()
      const r = (110 * 156543.03 * Math.cos((lat * Math.PI) / 180)) / 2 ** map.getZoom()    // ~110 px
      const line = (az: number, className: string, len = r) =>
        L.polyline([[lat, lon], towards(lat, lon, az, len)], { className, interactive: false }).addTo(group)
      const day = sunDay(year, month, lat, lon)
      if (day.points.length) {
        L.polyline(day.points.map(p => towards(lat, lon, p.azimuth, r)), { className: 'sun-arc', interactive: false }).addTo(group)
        line(day.points[0].azimuth, 'sun-edge')
        line(day.points.at(-1)!.azimuth, 'sun-edge')
      }
      const now = sunPosition(danishTime(year, month, minutes), lat, lon)
      if (now.altitude > UP) {
        // a 3 m wall's shadow, on the 110 px ≈ 10 m scale of the arc
        line(now.azimuth + 180, 'sun-shadow', Math.min(r, (r * 0.3) / Math.tan((Math.max(now.altitude, 1) * Math.PI) / 180)))
        line(now.azimuth, 'sun-ray')
        L.circleMarker(towards(lat, lon, now.azimuth, r), { radius: 10, className: 'sun-dot', interactive: false }).addTo(group)
      }
    }
    draw()
    map.on('zoomend', draw)
    return () => { map.off('zoomend', draw); group.remove() }
  }, [map, at?.lat, at?.lon, month, minutes]) // eslint-disable-line react-hooks/exhaustive-deps
}

/** A Layers button over a map, and what it turns on: school districts, noise from roads,
 *  trains and planes, flooding as the water rises, and the sun's path for a chosen month
 *  and hour. `focus` is the house the sun is drawn around. On a house's map the districts
 *  are the house's (on from the start); on the all-houses map (`around="view"`) they
 *  follow the view. */
export function MapLayers({ map, focus, around = 'house', menu = true, top = 12 }: {
  map: L.Map | null; focus: Point | null; around?: 'house' | 'view'; menu?: boolean; top?: number
}) {
  const now = new Date()
  const [open, setOpen] = useState(false)
  const [districts, setDistricts] = useState(around === 'house')
  const [noise, setNoise] = useState<string[]>([])
  const [flood, setFlood] = useState<Flood>('off')
  const [level, setLevel] = useState(50)
  const [plots, setPlots] = useState(false)
  const [sun, setSun] = useState(false)
  const [month, setMonth] = useState(now.getMonth())
  const [minutes, setMinutes] = useState(Math.round((now.getHours() * 60 + now.getMinutes()) / 15) * 15)

  const view = useViewCentre(map, districts && around === 'view')
  const failed = useDistricts(map, !districts ? null : around === 'house' ? focus : view,
    around === 'house' ? 3000 : 4000, around === 'house')
  useSun(map, sun ? focus : null, month, minutes)

  useEffect(() => {
    if (!map) return
    const added = NOISE.filter(n => noise.includes(n.key)).flatMap(n => n.layers.map(l =>
      utmLayer(mimTiles(`theme-pg-noisedataarea-${l}`), { maxLevel: 15, opacity: 0.5 }).addTo(map)))
    return () => added.forEach(l => l.remove())
  }, [map, noise])

  useEffect(() => {
    if (!map || flood === 'off') return
    let layer: L.Layer | undefined
    const wait = setTimeout(() => { layer = FLOOD[flood].layer(level).addTo(map) }, 250)  // draw where the slider stops
    return () => { clearTimeout(wait); layer?.remove() }
  }, [map, flood, level])

  useEffect(() => {
    if (!map || !plots) return
    const layer = L.tileLayer.wms('/api/wms/plots', {
      ...KDS, layers: 'MatrikelSkel_Gaeldende,Centroide_Gaeldende', styles: 'Roede_skel,Sorte_centroider',
      minZoom: 15, maxZoom: 19, zIndex: 3,
    }).addTo(map)
    return () => { layer.remove() }
  }, [map, plots])

  const on = [districts, plots, noise.length > 0, flood !== 'off', sun && !!focus].filter(Boolean).length
  const day = focus ? sunDay(now.getFullYear(), month, focus.lat, focus.lon) : null
  const pos = focus ? sunPosition(danishTime(now.getFullYear(), month, minutes), focus.lat, focus.lon) : null
  const heading = 'mb-1.5 text-xs font-extrabold uppercase tracking-wide text-muted-foreground'
  const row = 'flex min-h-9 items-center gap-3'

  return (
    <>
      {failed && (
        <p className="absolute bottom-2 left-2 z-[500] rounded bg-background/90 px-2 text-xs text-destructive">
          Couldn't load the school districts.
        </p>
      )}
      {menu && (
        <button type="button" aria-expanded={open} onClick={() => setOpen(o => !o)} style={{ top }}
          className="absolute right-3 z-[600] flex h-11 items-center gap-2 rounded-full border border-input bg-background px-4 text-sm font-semibold text-foreground shadow-lg">
          {open ? <X aria-hidden className="size-4" /> : <Layers aria-hidden className="size-4" />}Layers{on > 0 && ` · ${on}`}
        </button>
      )}
      {menu && !open && noise.length > 0 && (
        <div style={{ top: top + 52 }} className="absolute right-3 z-[600] w-48 rounded-xl bg-background/90 px-2.5 py-2 text-foreground shadow-lg">
          <NoiseScale />
        </div>
      )}
      {menu && open && (
        <div role="group" aria-label="Map layers" style={{ top: top + 52, maxHeight: `calc(100% - ${top + 64}px)` }}
          className="absolute right-3 z-[600] w-72 max-w-[calc(100%-1.5rem)] space-y-4 overflow-y-auto rounded-2xl border bg-background p-4 text-sm text-foreground shadow-xl">
          <label className={row}>
            <input type="checkbox" checked={districts} onChange={e => setDistricts(e.target.checked)} className="size-4" />
            School districts
          </label>
          <label className={row}>
            <input type="checkbox" checked={plots} onChange={e => setPlots(e.target.checked)} className="size-4" />
            <span>Plots (matrikler)<span className="block text-xs text-muted-foreground">Shown when zoomed in close</span></span>
          </label>
          <fieldset>
            <legend className={heading}>Noise</legend>
            {NOISE.map(n => (
              <label key={n.key} className={row}>
                <input type="checkbox" checked={noise.includes(n.key)} className="size-4"
                  onChange={e => setNoise(ns => e.target.checked ? [...ns, n.key] : ns.filter(k => k !== n.key))} />
                {n.label}
              </label>
            ))}
            <div className="space-y-1 pt-1">
              <NoiseScale />
              <p className="text-xs text-muted-foreground">Yearly average, evening and night weighted (Lden). Limits for homes: roads 58, trains 64, planes 55 dB.</p>
            </div>
          </fieldset>
          <fieldset>
            <legend className={heading}>Flooding</legend>
            {(['off', 'rain', 'sea', 'streams'] as const).map(f => (
              <label key={f} className={row}>
                <input type="radio" name="flood" checked={flood === f} className="size-4"
                  onChange={() => { setFlood(f); if (f !== 'off') setLevel(FLOOD[f].start) }} />
                {f === 'off' ? 'Off' : FLOOD[f].label}
              </label>
            ))}
            {flood !== 'off' && (
              <label className="block space-y-1 pt-1">
                <span>{FLOOD[flood].text(level)}</span>
                <input type="range" min={FLOOD[flood].min} max={FLOOD[flood].max} step={FLOOD[flood].step} value={level}
                  aria-label="How much water" onChange={e => setLevel(Number(e.target.value))} className="w-full" />
              </label>
            )}
          </fieldset>
          <fieldset>
            <legend className={heading}>Sun</legend>
            <label className={row}>
              <input type="checkbox" checked={sun} disabled={!focus} onChange={e => setSun(e.target.checked)} className="size-4" />
              {focus ? 'Sun around the house' : 'Pick a house on the map'}
            </label>
            {sun && focus && day && pos && (
              <div className="space-y-2 pt-1">
                <label className="block space-y-1">
                  <span>{MONTHS[month]} 21</span>
                  <input type="range" min={0} max={11} value={month} aria-label="Month"
                    onChange={e => setMonth(Number(e.target.value))} className="w-full" />
                </label>
                <label className="block space-y-1">
                  <span>{clock(minutes)}</span>
                  <input type="range" min={0} max={1425} step={15} value={minutes} aria-label="Time of day"
                    onChange={e => setMinutes(Number(e.target.value))} className="w-full" />
                </label>
                <p className="text-xs text-muted-foreground">
                  {day.rise != null && `Sunrise ${clock(day.rise)} · sunset ${clock(day.set!)}. `}
                  {pos.altitude > UP ? `The sun is ${Math.max(0, Math.round(pos.altitude))}° up in the ${compass(pos.azimuth)}.` : 'The sun is down.'}
                </p>
              </div>
            )}
          </fieldset>
        </div>
      )}
    </>
  )
}
