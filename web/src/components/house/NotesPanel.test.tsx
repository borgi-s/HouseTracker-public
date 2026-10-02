import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import type { Note } from '@/api/types'
import { NotesPanel } from '@/components/house/NotesPanel'
import { makeDetail, mockApi, renderApp, signedIn } from '@/test-utils'

const note = (id: number, person_id: string | null, body: string): Note =>
  ({ id, house_id: 'lindevej-14', person_id, body, created_at: `2026-09-2${id}` })
const DETAIL = makeDetail({
  notes: [note(1, 'alex', 'Kitchen is dark'), note(2, 'sam', 'Loved the garden'), note(3, null, 'Offer deadline Friday')],
  tags: [{ id: 7, house_id: 'lindevej-14', person_id: 'alex', label: 'needs-new-roof' },
         { id: 8, house_id: 'lindevej-14', person_id: 'sam', label: 'quiet-street' }],
})

test('notes are newest first with their author; only mine and shared ones can be deleted', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = mockApi(signedIn({ 'DELETE /api/notes/1': () => ({ deleted: 1 }) }))
  renderApp(<NotesPanel detail={DETAIL} />)
  const items = within(await screen.findByRole('list', { name: 'Notes' })).getAllByRole('listitem')
  expect(items.map(li => li.textContent)).toEqual([
    expect.stringContaining('Offer deadline Friday'),
    expect.stringContaining('Loved the garden'),
    expect.stringContaining('Kitchen is dark'),
  ])
  expect(await within(items[1]).findByText('Sam')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Delete note: Loved the garden' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Delete note: Offer deadline Friday' })).toBeInTheDocument()
  await userEvent.click(await screen.findByRole('button', { name: 'Delete note: Kitchen is dark' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/notes/1', body: undefined }))
})

test('deleting a note asks first; saying no keeps it', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  const calls = mockApi(signedIn({ 'DELETE /api/notes/1': () => ({ deleted: 1 }) }))
  renderApp(<NotesPanel detail={DETAIL} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Delete note: Kitchen is dark' }))
  expect(confirm).toHaveBeenCalled()
  expect(calls.filter(c => c.method === 'DELETE')).toEqual([])
})

test('a shared note is posted as shared', async () => {
  const calls = mockApi(signedIn({ 'POST /api/houses/lindevej-14/notes': () => note(4, null, 'x') }))
  renderApp(<NotesPanel detail={makeDetail()} />)
  await userEvent.type(screen.getByLabelText('Note'), 'Ask about the roof')
  await userEvent.click(screen.getByLabelText('Shared (ours, not just mine)'))
  await userEvent.click(screen.getByRole('button', { name: 'Add note' }))
  await waitFor(() => expect(calls).toContainEqual({
    method: 'POST', path: '/api/houses/lindevej-14/notes', body: { body: 'Ask about the roof', shared: true } }))
})

test('tags: add one of mine, remove one of mine, never the other person\'s', async () => {
  const calls = mockApi(signedIn({
    'POST /api/houses/lindevej-14/tags': () => ({ id: 9, house_id: 'lindevej-14', person_id: 'alex', label: 'big-garden' }),
    'DELETE /api/tags/7': () => ({ deleted: 7 }),
  }))
  renderApp(<NotesPanel detail={DETAIL} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Remove tag needs-new-roof' }))
  expect(screen.queryByRole('button', { name: 'Remove tag quiet-street' })).not.toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('New tag'), 'big-garden')
  await userEvent.click(screen.getByRole('button', { name: 'Add tag' }))
  await waitFor(() => {
    expect(calls).toContainEqual({ method: 'DELETE', path: '/api/tags/7', body: undefined })
    expect(calls).toContainEqual({
      method: 'POST', path: '/api/houses/lindevej-14/tags', body: { label: 'big-garden', shared: false } })
  })
})
