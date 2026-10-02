import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { useHouse } from '@/api/queries'
import { ScoreRow, ScoresPanel, withScore } from '@/components/house/ScoresPanel'
import { fail, makeCriterion, makeDetail, mockApi, never, renderApp, signedIn } from '@/test-utils'

const LIGHT = makeCriterion()
const PPM2 = makeCriterion({
  id: 'price_per_m2', key: 'price_per_m2', label: 'Price per m²', kind: 'auto',
  auto_source: 'price_per_m2', higher_is_better: false, sort: 1,
})

/** The panel reads its data from the house query, like the real page. */
function Harness() {
  const q = useHouse('lindevej-14')
  return q.data ? <ScoresPanel detail={q.data} /> : null
}

function renderPanel(detail = makeDetail(), extra = {}) {
  const calls = mockApi(signedIn({
    'GET /api/criteria?active_only=true': () => [LIGHT, PPM2],
    'GET /api/houses/lindevej-14': () => detail,
    ...extra,
  }))
  renderApp(<Harness />)
  return calls
}

test('ScoreRow: my value pressed, the other person marked, a gap of 2+ tinted', () => {
  render(<ScoreRow label="Kitchen" mine={1} other={4} meSlot="a" otherSlot="b" onPick={vi.fn()} />)
  const mine = screen.getByRole('button', { name: 'Kitchen 1' })
  expect(mine).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Kitchen 4' })).toHaveAttribute('data-other')
  expect(mine.closest('[data-disagree]')).not.toBeNull()
})

test('ScoreRow: no tint for a gap of 1 or when one of us has not scored', () => {
  const { rerender } = render(<ScoreRow label="Light" mine={3} other={4} meSlot="a" otherSlot="b" onPick={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Light 3' }).closest('[data-disagree]')).toBeNull()
  rerender(<ScoreRow label="Light" mine={1} meSlot="a" otherSlot="b" onPick={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Light 1' }).closest('[data-disagree]')).toBeNull()
})

test('ScoreRow: tapping my value clears it, tapping another sets it', async () => {
  const onPick = vi.fn()
  render(<ScoreRow label="Light" mine={4} meSlot="a" otherSlot="b" onPick={onPick} />)
  await userEvent.click(screen.getByRole('button', { name: 'Light 4' }))
  await userEvent.click(screen.getByRole('button', { name: 'Light 2' }))
  expect(onPick.mock.calls).toEqual([[null], [2]])
})

test('withScore sets and clears one value without touching the rest', () => {
  const d = makeDetail({ scores: { alex: { light: 2 }, sam: { light: 5 } } })
  expect(withScore(d, 'alex', 'light', 4).scores).toEqual({ alex: { light: 4 }, sam: { light: 5 } })
  expect(withScore(d, 'alex', 'light', null).scores).toEqual({ alex: {}, sam: { light: 5 } })
})

test('a tap shows at once, before the server answers', async () => {
  const calls = renderPanel(makeDetail(), { 'PUT /api/houses/lindevej-14/scores/light': never })
  await userEvent.click(await screen.findByRole('button', { name: 'Light 4' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Light 4' })).toHaveAttribute('aria-pressed', 'true'))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'PUT', path: '/api/houses/lindevej-14/scores/light', body: { value: 4 } }))
})

test('tapping my current value clears it on the server', async () => {
  const calls = renderPanel(makeDetail({ scores: { alex: { light: 4 } } }),
    { 'DELETE /api/houses/lindevej-14/scores/light': () => ({ deleted: true }) })
  await userEvent.click(await screen.findByRole('button', { name: 'Light 4' }))
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'DELETE', path: '/api/houses/lindevej-14/scores/light', body: undefined }))
})

test('a failed save puts the old value back', async () => {
  let failNow = () => {}
  renderPanel(makeDetail(), {
    'PUT /api/houses/lindevej-14/scores/light': () =>
      new Promise<Response>(resolve => { failNow = () => resolve(fail(500, 'database is locked')) }),
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Light 4' }))
  const four = () => screen.getByRole('button', { name: 'Light 4' })
  await waitFor(() => expect(four()).toHaveAttribute('aria-pressed', 'true'))
  failNow()
  await waitFor(() => expect(four()).toHaveAttribute('aria-pressed', 'false'))
})

test('automatic criteria show their value with its unit, read-only', async () => {
  const SIZE = makeCriterion({ id: 'size_m2', key: 'size_m2', label: 'Size', kind: 'auto', auto_source: 'size_m2', sort: 2 })
  renderPanel(makeDetail(), { 'GET /api/criteria?active_only=true': () => [LIGHT, PPM2, SIZE] })
  expect(await screen.findByText('38.697 kr')).toBeInTheDocument()
  expect(screen.getByText('142 m²')).toBeInTheDocument()
  expect(screen.queryByText(/is better/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Price per m²/ })).not.toBeInTheDocument()
})
