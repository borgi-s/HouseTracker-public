import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { Settings } from '@/routes/Settings'
import { makeCriterion, mockApi, renderApp, signedIn } from '@/test-utils'

test('with no criteria, "Start with defaults" creates the 11 defaults in order', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'POST /api/criteria': body => body,
  }))
  renderApp(<Settings />)
  await userEvent.click(await screen.findByRole('button', { name: 'Start with defaults' }))
  const posts = () => calls.filter(c => c.method === 'POST' && c.path === '/api/criteria')
  await waitFor(() => expect(posts()).toHaveLength(11))
  expect(posts()[0].body).toMatchObject({ key: 'light', kind: 'subjective', sort: 0 })
})

test('a weight is saved when the field loses focus', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [makeCriterion()],
    'PATCH /api/criteria/light': body => ({ ...makeCriterion(), ...(body as object) }),
  }))
  renderApp(<Settings />)
  const weight = await screen.findByLabelText('Light weight')
  await userEvent.clear(weight)
  await userEvent.type(weight, '2.5')
  await userEvent.tab()
  await waitFor(() =>
    expect(calls).toContainEqual({ method: 'PATCH', path: '/api/criteria/light', body: { weight: 2.5 } }))
})

test('moving a criterion down renumbers the sort order', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [
      makeCriterion(), makeCriterion({ id: 'noise', key: 'noise', label: 'Noise' })],
    'PATCH /api/criteria/light': () => makeCriterion({ sort: 1 }),
  }))
  renderApp(<Settings />)
  await userEvent.click(await screen.findByRole('button', { name: 'Move Light down' }))
  await waitFor(() =>
    expect(calls).toContainEqual({ method: 'PATCH', path: '/api/criteria/light', body: { sort: 1 } }))
})

test('an automatic criterion is added with its source and direction', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'POST /api/criteria': body => body,
  }))
  renderApp(<Settings />)
  await userEvent.type(await screen.findByLabelText('New criterion'), 'Lot')
  await userEvent.selectOptions(screen.getByLabelText('Kind'), 'auto')
  await userEvent.selectOptions(screen.getByLabelText('Source'), 'lot_m2')
  await userEvent.click(screen.getByLabelText('Higher is better'))
  await userEvent.click(screen.getByRole('button', { name: 'Add criterion' }))
  await waitFor(() => expect(calls).toContainEqual({
    method: 'POST', path: '/api/criteria',
    body: { key: 'lot', label: 'Lot', kind: 'auto', sort: 0, auto_source: 'lot_m2', higher_is_better: true },
  }))
})
