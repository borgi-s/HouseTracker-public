import type { Criterion } from '@/api/types'

export interface Apart { label: string; gap: number }
type Scores = Record<string, number>

const both = (c: Criterion, mine: Scores, theirs: Scores) =>
  c.kind === 'subjective' && mine[c.id] != null && theirs[c.id] != null

/** Subjective criteria we both scored and differ on, biggest gap first. */
export function apartOn(criteria: Criterion[], mine: Scores = {}, theirs: Scores = {}): Apart[] {
  return criteria
    .filter(c => both(c, mine, theirs) && mine[c.id] !== theirs[c.id])
    .map(c => ({ label: c.label, gap: Math.abs(mine[c.id] - theirs[c.id]) }))
    .sort((a, b) => b.gap - a.gap)
}

/** "Apart on kitchen (1), noise (1) and garden (1). You agree on the rest you have both scored." */
export function apartSentence(criteria: Criterion[], mine: Scores = {}, theirs: Scores = {}): string {
  if (!criteria.some(c => both(c, mine, theirs))) return 'Nothing scored by both of you yet.'
  const parts = apartOn(criteria, mine, theirs).map(a => `${a.label.toLowerCase()} (${a.gap})`)
  if (parts.length === 0) return 'You agree on everything you have both scored.'
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
  return `Apart on ${list}. You agree on the rest you have both scored.`
}
