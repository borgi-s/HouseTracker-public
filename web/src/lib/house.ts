import type { Media, MediaKind } from '@/api/types'

export const ofKind = (media: Media[], kind: MediaKind) => media.filter(m => m.kind === kind)

/** Scraped photos first, then our own (the API orders media by kind, sort). */
export const photosOf = (media: Media[]) => [...ofKind(media, 'photo'), ...ofKind(media, 'user_photo')]

export const POLL_MS = 3000
export const POLL_LIMIT_MS = 90_000

/** After a scrape or a refresh the media download runs in the background; re-fetch until
 *  the house has exactly `pending` scraped media (a refresh first drops the old set) or
 *  90 s pass (spec §5: no job endpoint by design). */
export const shouldPoll = (scrapedCount: number, pending: number, startedAt: number, now: number) =>
  pending > 0 && scrapedCount !== pending && now - startedAt < POLL_LIMIT_MS

export const scrapedCount = (media: Media[]) => media.filter(m => m.kind !== 'user_photo').length
