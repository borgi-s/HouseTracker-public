import { DASH } from '@/lib/format'

type Point = { lat: number; lon: number }
const EARTH_KM = 6371

/** Straight-line ("as the crow flies") distance in km: no routing key needed. */
export function distanceKm(a: Point, b: Point): number {
  const rad = (d: number) => (d * Math.PI) / 180
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2
  return 2 * EARTH_KM * Math.asin(Math.sqrt(h))
}

const oneDecimal = new Intl.NumberFormat('da-DK', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** 8595000 -> "8,6 mio": short enough for a map pin. */
export const mio = (dkk: number | null) => (dkk == null ? DASH : `${oneDecimal.format(dkk / 1e6)} mio`)
