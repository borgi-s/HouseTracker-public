import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { Settings } from '@/routes/Settings'
import { WORK, fail, makeCriterion, mockApi, renderApp, signedIn } from '@/test-utils'

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

test('each active criterion shows its share of the total weight', async () => {
  mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [
      makeCriterion({ weight: 3 }), makeCriterion({ id: 'noise', key: 'noise', label: 'Noise' })],
  }))
  renderApp(<Settings />)
  expect(await screen.findByText('75%')).toBeInTheDocument()
  expect(screen.getByText('25%')).toBeInTheDocument()
})

test('removing a criterion asks first, then deletes it', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [makeCriterion()],
    'DELETE /api/criteria/light': () => ({ deleted: 'light' }),
  }))
  renderApp(<Settings />)
  await userEvent.click(await screen.findByRole('button', { name: 'Remove Light' }))
  expect(window.confirm).toHaveBeenCalled()
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/criteria/light', body: undefined }))
})

test('a person is renamed when the field loses focus, and can be removed', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'PATCH /api/persons/sam': body => ({ id: 'sam', ...(body as object) }),
    'DELETE /api/persons/alex': () => ({ deleted: 'alex' }),
  }))
  renderApp(<Settings />)
  const sam = await screen.findByLabelText('Sam name')
  await userEvent.clear(sam)
  await userEvent.type(sam, 'Samantha')
  await userEvent.tab()
  await waitFor(() =>
    expect(calls).toContainEqual({ method: 'PATCH', path: '/api/persons/sam', body: { name: 'Samantha' } }))
  await userEvent.click(screen.getByRole('button', { name: 'Remove Alex' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/persons/alex', body: undefined }))
})

test('places: listed, added by address, removed', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'POST /api/anchors': body => ({ ...WORK, id: 'gym', ...(body as object) }),
    'DELETE /api/anchors/work': () => ({ deleted: 'work' }),
  }))
  renderApp(<Settings />)
  expect(await screen.findByText('Arbejdsvej 1, 2800 Kongens Lyngby')).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('Place name'), 'Gym')
  await userEvent.type(screen.getByLabelText('Place address'), 'Sportsvej 3, 2800')
  await userEvent.click(screen.getByRole('button', { name: 'Add place' }))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'POST', path: '/api/anchors', body: { label: 'Gym', address: 'Sportsvej 3, 2800' } }))
  await userEvent.click(screen.getByRole('button', { name: 'Remove Work' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/anchors/work', body: undefined }))
})

test('a place whose address is not found shows why', async () => {
  mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'POST /api/anchors': () => fail(422, "address not found: 'Nowhere 1' (include the postcode)"),
  }))
  renderApp(<Settings />)
  await userEvent.type(await screen.findByLabelText('Place name'), 'X')
  await userEvent.type(screen.getByLabelText('Place address'), 'Nowhere 1')
  await userEvent.click(screen.getByRole('button', { name: 'Add place' }))
  expect(await screen.findByText(/address not found/)).toBeInTheDocument()
})

test('notification switches save, and the sweep runs on demand with its summary', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'PATCH /api/settings': body => ({ notify_price_drops: true, notify_open_houses: true, discord_configured: true, ...(body as object) }),
    'POST /api/admin/lifecycle': () => ({ checked: 7, marked_sold: 1, priced: 0, repriced: 2, skipped: 0, open_new: 3 }),
  }))
  renderApp(<Settings />)
  await userEvent.click(await screen.findByLabelText('Open houses'))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'PATCH', path: '/api/settings', body: { notify_open_houses: false } }))
  await userEvent.click(screen.getByRole('button', { name: 'Check listings now' }))
  expect(await screen.findByText('Checked 7 · 1 sold · 2 price changes · 3 new open houses')).toBeInTheDocument()
})

test('without a webhook the switches say notifications are off', async () => {
  mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'GET /api/settings': () => ({ notify_price_drops: true, notify_open_houses: true, discord_configured: false }),
  }))
  renderApp(<Settings />)
  expect(await screen.findByText(/HT_DISCORD_WEBHOOK/)).toBeInTheDocument()
  expect(screen.getByLabelText('Price drops')).toBeDisabled()
})

test('a place is edited in place: name and address saved together', async () => {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=false': () => [],
    'PATCH /api/anchors/work': body => ({ ...WORK, ...(body as object) }),
  }))
  renderApp(<Settings />)
  await userEvent.click(await screen.findByRole('button', { name: 'Edit Work' }))
  const name = screen.getByLabelText('Work name')
  await userEvent.clear(name)
  await userEvent.type(name, 'Office')
  const address = screen.getByLabelText('Work address')
  await userEvent.clear(address)
  await userEvent.type(address, 'Nyvej 1, 2800')
  await userEvent.click(screen.getByRole('button', { name: 'Save Work' }))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'PATCH', path: '/api/anchors/work', body: { label: 'Office', address: 'Nyvej 1, 2800' } }))
  await waitFor(() => expect(screen.queryByLabelText('Work name')).not.toBeInTheDocument())
})
