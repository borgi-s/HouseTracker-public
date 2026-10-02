import type { HouseDetail, Status } from '@/api/types'

export interface StatusAction { label: string; to: Status }
export interface StatusCardContent { title: string; text: string; actions: StatusAction[] }

const DAY = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long' })

/** The day the house last entered `status` (history is oldest first), e.g. "22 September". */
export function since(history: HouseDetail['status_history'], status: Status): string | null {
  const entry = [...history].reverse().find(e => e.status === status)
  return entry ? DAY.format(new Date(`${entry.at}T12:00:00`)) : null
}

/** What the sand status card says for each status, and its quick actions. */
export function statusCard(status: Status, history: HouseDetail['status_history']): StatusCardContent {
  switch (status) {
    case 'not_visited':
      return { title: 'Not yet visited', text: 'Book a viewing through the listing, then mark it visited.',
        actions: [{ label: 'Mark visited', to: 'visited' }, { label: 'Not for us', to: 'rejected' }] }
    case 'visited': {
      const on = since(history, 'visited')
      return { title: on ? `Visited on ${on}` : 'Visited', text: 'Shortlist it, make an offer, or let it go?',
        actions: [{ label: 'Shortlist', to: 'shortlist' }, { label: 'Make an offer', to: 'offer' },
          { label: 'Reject', to: 'rejected' }] }
    }
    case 'shortlist':
      return { title: 'On the shortlist', text: 'Ready to make an offer?',
        actions: [{ label: 'Make an offer', to: 'offer' }, { label: 'Reject', to: 'rejected' }] }
    case 'offer':
      return { title: 'Offer made', text: 'Waiting to hear back.',
        actions: [{ label: 'Back to shortlist', to: 'shortlist' }, { label: 'Rejected', to: 'rejected' }] }
    case 'rejected':
      return { title: 'Not for us', text: 'Hidden from Active. Find it under Archive.',
        actions: [{ label: 'Undo', to: 'visited' }] }
    case 'sold':
      return { title: 'Sold', text: 'Sold to someone else. Find it under Archive.', actions: [] }
  }
}
