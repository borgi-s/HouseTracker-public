import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { OpenHouse } from '@/api/types'
import { OpenHouseBand, OpenHousePill } from '@/components/OpenHouse'

const oh = (starts_at: string, ends_at: string, signup: boolean | null = null): OpenHouse =>
  ({ starts_at, ends_at, signup, signup_url: null, cancelled: false })
const NOW = new Date('2026-10-01T10:00:00Z')
const SUN = oh('2026-10-04T13:30:00Z', '2026-10-04T13:50:00Z', true)
const NEXT = oh('2026-10-11T08:00:00Z', '2026-10-11T08:30:00Z', false)
const PAST = oh('2026-09-27T08:00:00Z', '2026-09-27T08:30:00Z')

test('band: the next slot, how many more, and whether to sign up', () => {
  const { container } = render(<OpenHouseBand slots={[NEXT, SUN, PAST]} now={NOW} />)
  expect(container).toHaveTextContent('Open house Sun 4 Oct 15:30 +1 more')
  expect(screen.getByText('Sign-up')).toBeInTheDocument()
  expect(container.firstChild).toHaveClass('bg-openhouse', 'pointer-events-none')
})

test('pill: the next slot only', () => {
  const { container } = render(<OpenHousePill slots={[NEXT]} now={NOW} />)
  expect(container).toHaveTextContent(/^Open house Sun 11 Oct 10:00$/)
})

test('nothing when no slot is coming', () => {
  expect(render(<OpenHouseBand slots={[PAST]} now={NOW} />).container).toBeEmptyDOMElement()
  expect(render(<OpenHousePill slots={[]} now={NOW} />).container).toBeEmptyDOMElement()
})
