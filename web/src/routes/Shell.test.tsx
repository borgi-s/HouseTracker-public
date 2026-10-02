import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { toast } from 'sonner'
import { expect, test, vi } from 'vitest'
import { Shell } from '@/routes/Shell'
import { fail, mockApi, renderApp, signedIn } from '@/test-utils'

test('shows navigation and who is signed in; the chip signs out', async () => {
  const calls = mockApi(signedIn({ 'DELETE /api/session': () => ({ person: null }) }))
  renderApp(<Shell />)
  expect(screen.getAllByRole('link', { name: 'Houses' }).length).toBeGreaterThan(0)
  expect(screen.getAllByRole('link', { name: 'Settings' }).length).toBeGreaterThan(0)
  await userEvent.click(await screen.findByRole('button', { name: 'Alex' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Alex' })).not.toBeInTheDocument())
  expect(calls).toContainEqual({ method: 'DELETE', path: '/api/session', body: undefined })
})

test('a failed sign-out says so and keeps the person signed in', async () => {
  const spy = vi.spyOn(toast, 'error')
  mockApi(signedIn({ 'DELETE /api/session': () => fail(500, 'database is locked') }))
  renderApp(<Shell />)
  await userEvent.click(await screen.findByRole('button', { name: 'Alex' }))
  await waitFor(() => expect(spy).toHaveBeenCalledWith('database is locked'))
  expect(screen.getByRole('button', { name: 'Alex' })).toBeInTheDocument()
})

test('the header links Add house; the phone tab bar has Houses, Add and Settings', async () => {
  mockApi(signedIn())
  renderApp(<Shell />)
  expect(await screen.findByRole('link', { name: 'Add house' })).toHaveAttribute('href', '/add')
  const phone = screen.getByRole('navigation', { name: 'Phone' })
  expect(within(phone).getAllByRole('link').map(a => a.textContent)).toEqual(['Houses', 'Add', 'Settings'])
})

test('following a link opens the new page at the top', async () => {
  mockApi(signedIn())
  const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  renderApp(<Shell />)
  scrollTo.mockClear()
  await userEvent.click((await screen.findAllByRole('link', { name: 'Settings' }))[0])
  expect(scrollTo).toHaveBeenCalledWith(0, 0)
})
