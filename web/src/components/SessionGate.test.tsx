import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import type { Person } from '@/api/types'
import { SessionGate } from '@/components/SessionGate'
import { mockApi, renderApp, ALEX, SAM } from '@/test-utils'

test('without a session it asks who you are; picking signs you in', async () => {
  const calls = mockApi({
    'GET /api/session': () => ({ person: null }),
    'GET /api/persons': () => [ALEX, SAM],
    'POST /api/session': () => ({ person: ALEX }),
  })
  renderApp(<SessionGate><p>inside</p></SessionGate>)
  expect(await screen.findByRole('heading', { name: 'Who are you?' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Alex' }))
  expect(await screen.findByText('inside')).toBeInTheDocument()
  expect(calls).toContainEqual({ method: 'POST', path: '/api/session', body: { person_id: 'alex' } })
})

test('first run: add a person, then they can be picked', async () => {
  let persons: Person[] = []
  const calls = mockApi({
    'GET /api/session': () => ({ person: null }),
    'GET /api/persons': () => persons,
    'POST /api/persons': () => { persons = [ALEX]; return ALEX },
  })
  renderApp(<SessionGate><p>inside</p></SessionGate>)
  await userEvent.type(await screen.findByLabelText('New person'), 'Alex')
  await userEvent.click(screen.getByRole('button', { name: 'Add' }))
  expect(await screen.findByRole('button', { name: 'Alex' })).toBeInTheDocument()
  expect(calls).toContainEqual({ method: 'POST', path: '/api/persons', body: { name: 'Alex' } })
})

test('with a session it renders the app', async () => {
  mockApi({ 'GET /api/session': () => ({ person: ALEX }), 'GET /api/persons': () => [ALEX] })
  renderApp(<SessionGate><p>inside</p></SessionGate>)
  expect(await screen.findByText('inside')).toBeInTheDocument()
})
