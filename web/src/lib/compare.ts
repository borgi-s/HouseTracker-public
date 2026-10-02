import type { Anchor, Commute } from '@/api/types'

export type Better = 'low' | 'high'

/** Indices of the best value in a row. None when fewer than two values exist or all
 *  are equal — nothing stands out then. */
export function bestIndices(values: (number | null)[], better: Better): number[] {
  const present = values.filter((v): v is number => v != null)
  if (present.length < 2) return []
  const best = better === 'low' ? Math.min(...present) : Math.max(...present)
  if (present.every(v => v === best)) return []
  return values.flatMap((v, i) => (v === best ? [i] : []))
}

/** The anchor the map measures to and Compare times: the first fixed one, if any. */
export function mainAnchor(anchors: Anchor[] | undefined): Anchor | null {
  return anchors?.find(a => a.kind === 'fixed') ?? null
}

export function fastestTo(commutes: Commute[], anchorRef: string): number | null {
  const ms = commutes.filter(c => c.anchor_ref === anchorRef && c.minutes != null).map(c => c.minutes as number)
  return ms.length ? Math.min(...ms) : null
}

export function mean(values: (number | undefined)[]): number | null {
  const vs = values.filter((v): v is number => v != null)
  return vs.length ? vs.reduce((s, v) => s + v, 0) / vs.length : null
}
