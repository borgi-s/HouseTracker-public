import type { Overall } from '@/api/types'

export const DASH = '–'
const whole = new Intl.NumberFormat('da-DK', { maximumFractionDigits: 0 })
const upTo1 = new Intl.NumberFormat('da-DK', { maximumFractionDigits: 1 })
type N = number | null | undefined

export const money = (v: N) => (v == null ? DASH : `${whole.format(v)} kr`)
export const num = (v: N, unit = '') =>
  v == null ? DASH : unit ? `${upTo1.format(v)} ${unit}` : upTo1.format(v)
/** The API's overalls are 0..1; people think on the 1..5 scale they tap (spec §4.8). */
export const score5 = (v: N) => (v == null ? DASH : (v * 5).toFixed(1))
/** "2 + basement 32 m²" */
export const floorsText = (floors: N, basementM2: N) =>
  floors == null ? DASH : basementM2 ? `${floors} + basement ${num(basementM2, 'm²')}` : String(floors)
export const minutes = (v: N) => (v == null ? DASH : `${Math.round(v)} min`)
export const km = (metres: N) => (metres == null ? DASH : `${upTo1.format(metres / 1000)} km`)

export function pctChange(from: N, to: N): string {
  if (from == null || to == null || from === 0) return DASH
  const p = ((to - from) / from) * 100
  return `${p > 0 ? '+' : ''}${p.toFixed(1)} %`
}

/** Combined score = mean of the overalls that exist (spec §4.8). */
export function combined(overall: Overall, ids: string[]): number | null {
  const vs = ids.map(id => overall[id]).filter((v): v is number => v != null)
  return vs.length ? vs.reduce((s, v) => s + v, 0) / vs.length : null
}

/** OpenRouteService profile -> what we call it. */
export const MODE_LABEL: Record<string, string> = {
  'driving-car': 'Car',
  'cycling-regular': 'Bike',
  'foot-walking': 'Walk',
}
