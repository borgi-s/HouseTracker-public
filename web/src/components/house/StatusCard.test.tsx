import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { toast } from 'sonner'
import { expect, test, vi } from 'vitest'
import { StatusCard } from '@/components/house/StatusCard'
import { fail, makeDetail, makeHouse, mockApi, never, renderApp, signedIn } from '@/test-utils'

const PATCH = 'PATCH /api/houses/lindevej-14/status'

test('a visited house offers Shortlist, which saves the new status', async () => {
  const calls = mockApi(signedIn({ [PATCH]: () => ({}) }))
  renderApp(<StatusCard detail={makeDetail()} />)
  expect(screen.getByText('Visited on 21 September')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Shortlist' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'PATCH', path: '/api/houses/lindevej-14/status', body: { status: 'shortlist' } }))
})

test('while saving, the card already reads like the new status', async () => {
  mockApi(signedIn({ [PATCH]: never }))
  renderApp(<StatusCard detail={makeDetail()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Shortlist' }))
  expect(screen.getByText('On the shortlist')).toBeInTheDocument()
  expect(screen.getByLabelText('Status')).toHaveValue('shortlist')
})

test('a house not visited yet nudges to book a viewing and links the listing', async () => {
  mockApi(signedIn())
  renderApp(<StatusCard detail={makeDetail({ house: makeHouse({ status: 'not_visited', listing_url: 'https://www.edc.dk/x' }) })} />)
  expect(screen.getByText('Not yet visited')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Mark visited' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Open the listing/ })).toHaveAttribute('href', 'https://www.edc.dk/x')
})

test('a failed change goes back and says why', async () => {
  const spy = vi.spyOn(toast, 'error')
  mockApi(signedIn({ [PATCH]: () => fail(500, 'database is locked'), 'GET /api/houses/lindevej-14': () => makeDetail(), 'GET /api/houses': () => [] }))
  renderApp(<StatusCard detail={makeDetail()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
  await waitFor(() => expect(spy).toHaveBeenCalledWith('database is locked'))
  expect(screen.getByLabelText('Status')).toHaveValue('visited')
})
