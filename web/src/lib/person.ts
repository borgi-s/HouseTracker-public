import type { Person } from '@/api/types'

export type Slot = 'a' | 'b'

/** Person colour classes — views take person colours from here, never hard-coded. */
export const PERSON = {
  a: { solid: 'bg-person-a text-background', soft: 'bg-person-a-soft text-person-a', text: 'text-person-a', dot: 'bg-person-a', ring: 'ring-person-a' },
  b: { solid: 'bg-person-b text-background', soft: 'bg-person-b-soft text-person-b', text: 'text-person-b', dot: 'bg-person-b', ring: 'ring-person-b' },
} as const

/** Person A/B = the first two persons in API order — the pair the API's
 *  `disagreement` is computed for (spec §4). */
export function slotOf(persons: Person[], id: string | null | undefined): Slot | null {
  const i = persons.slice(0, 2).findIndex(p => p.id === id)
  return i === 0 ? 'a' : i === 1 ? 'b' : null
}

export const DISAGREE_GAP = 2
export const disagrees = (a: number | undefined, b: number | undefined) =>
  a != null && b != null && Math.abs(a - b) >= DISAGREE_GAP
