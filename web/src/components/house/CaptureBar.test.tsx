import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { toast } from 'sonner'
import { expect, test, vi } from 'vitest'
import { CaptureBar } from '@/components/house/CaptureBar'
import { fail, makeMedia, mockApi, renderApp, signedIn } from '@/test-utils'

test('photos upload one by one; a rejected file toasts and the rest continue', async () => {
  const toastError = vi.spyOn(toast, 'error')
  let n = 0
  const calls = mockApi(signedIn({
    'POST /api/houses/lindevej-14/media': () =>
      n++ === 0 ? fail(415, 'only JPEG, PNG, WebP or HEIC images are accepted')
                : makeMedia({ id: 'u2', kind: 'user_photo', source: 'manual' }),
  }))
  renderApp(<CaptureBar houseId="lindevej-14" status="visited" />)
  await userEvent.upload(screen.getByLabelText('Add photos'), [
    new File(['a'], 'a.gif', { type: 'image/gif' }),
    new File(['b'], 'b.jpg', { type: 'image/jpeg' }),
  ])
  await waitFor(() => expect(calls.filter(c => c.method === 'POST')).toHaveLength(2))
  expect(calls.filter(c => c.method === 'POST').every(c => c.body instanceof FormData)).toBe(true)
  await waitFor(() => expect(toastError).toHaveBeenCalledWith('a.gif: only JPEG, PNG, WebP or HEIC images are accepted'))
})

test('Rate scrolls to Where we stand', async () => {
  mockApi(signedIn())
  renderApp(<><section id="our-take" /><CaptureBar houseId="lindevej-14" status="visited" /></>)
  const scroll = vi.fn()
  document.getElementById('our-take')!.scrollIntoView = scroll
  await userEvent.click(screen.getByRole('button', { name: 'Rate' }))
  expect(scroll).toHaveBeenCalled()
})

test('before the viewing, Rate is the quiet button', () => {
  mockApi(signedIn())
  renderApp(<CaptureBar houseId="lindevej-14" status="not_visited" />)
  expect(screen.getByRole('button', { name: 'Rate' })).toHaveAttribute('data-variant', 'outline')
  expect(screen.getByText('Add photo')).toBeInTheDocument()
})

test('Note opens a dialog that saves and closes', async () => {
  const calls = mockApi(signedIn({
    'POST /api/houses/lindevej-14/notes': () => ({ id: 1, house_id: 'lindevej-14', person_id: 'alex', body: 'x', created_at: '2026-09-21' }),
  }))
  renderApp(<CaptureBar houseId="lindevej-14" status="visited" />)
  await userEvent.click(screen.getByRole('button', { name: 'Add note' }))
  await userEvent.type(await screen.findByLabelText('Note'), 'Damp in the basement')
  await userEvent.click(screen.getByRole('button', { name: 'Add note' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(calls).toContainEqual({
    method: 'POST', path: '/api/houses/lindevej-14/notes', body: { body: 'Damp in the basement', shared: false } })
})
