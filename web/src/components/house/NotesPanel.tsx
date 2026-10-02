import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { usePeople, usePersons, useRefreshHouse } from '@/api/queries'
import type { HouseDetail } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { PERSON } from '@/lib/person'
import { cn } from '@/lib/utils'

export function NoteForm({ houseId, onDone }: { houseId: string; onDone?: () => void }) {
  const refresh = useRefreshHouse()
  const [body, setBody] = useState('')
  const [shared, setShared] = useState(false)
  const add = useMutation({
    mutationFn: () => api.addNote(houseId, body.trim(), shared),
    onSuccess: () => {
      setBody('')
      setShared(false)
      onDone?.()
      return refresh(houseId)
    },
  })
  return (
    <form className="space-y-2" onSubmit={e => { e.preventDefault(); if (body.trim()) add.mutate() }}>
      <Textarea aria-label="Note" placeholder="What stood out?" value={body} onChange={e => setBody(e.target.value)} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={shared} onChange={e => setShared(e.target.checked)} />
          Shared (ours, not just mine)
        </label>
        <Button type="submit" size="sm" disabled={add.isPending}>Add note</Button>
      </div>
    </form>
  )
}

export function NotesPanel({ detail }: { detail: HouseDetail }) {
  const houseId = detail.house.id
  const [tag, setTag] = useState('')
  const [tagShared, setTagShared] = useState(false)
  const { me, slotOf } = usePeople()
  const persons = usePersons().data ?? []
  const refresh = useRefreshHouse()
  const delNote = useMutation({ mutationFn: api.deleteNote, onSettled: () => refresh(houseId) })
  const delTag = useMutation({ mutationFn: api.deleteTag, onSettled: () => refresh(houseId) })
  const addTag = useMutation({
    mutationFn: ({ label, shared }: { label: string; shared: boolean }) => api.addTag(houseId, label, shared),
    onSuccess: () => { setTag(''); return refresh(houseId) },
  })
  const author = (pid: string | null) => (pid == null ? 'Shared' : persons.find(p => p.id === pid)?.name ?? pid)
  const chip = (pid: string | null) => {
    const s = slotOf(pid)
    return s ? PERSON[s].soft : 'bg-muted text-foreground'
  }
  // Attribution, not ownership — but deleting the other person's words is their call.
  const mayDelete = (pid: string | null) => pid == null || pid === me?.id
  const heading = 'text-xs font-extrabold uppercase tracking-wide text-muted-foreground'

  return (
    <section className="space-y-6">
      <NoteForm houseId={houseId} />
      <ul aria-label="Notes" className="space-y-2">
        {[...detail.notes].reverse().map(n => (
          <li key={n.id} className="rounded-2xl bg-card p-3 text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-extrabold', chip(n.person_id))}>{author(n.person_id)}</span>
              <span className="text-xs text-muted-foreground">{n.created_at}</span>
            </div>
            <p className="whitespace-pre-line">{n.body}</p>
            {mayDelete(n.person_id) && (
              <Button variant="ghost" size="sm" aria-label={`Delete note: ${n.body.slice(0, 40)}`}
                onClick={() => { if (window.confirm('Delete this note?')) delNote.mutate(n.id) }}>Delete</Button>
            )}
          </li>
        ))}
      </ul>

      <div className="space-y-2">
        <h3 className={heading}>Tags</h3>
        <ul aria-label="Tags" className="flex flex-wrap gap-1.5">
          {detail.tags.map(t => (
            <li key={t.id} className={cn('flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold', chip(t.person_id))}>
              {t.label}
              {mayDelete(t.person_id) && (
                <button type="button" aria-label={`Remove tag ${t.label}`} onClick={() => delTag.mutate(t.id)}>×</button>
              )}
            </li>
          ))}
        </ul>
        <form className="flex flex-wrap items-center gap-2"
          onSubmit={e => { e.preventDefault(); if (tag.trim()) addTag.mutate({ label: tag.trim(), shared: tagShared }) }}>
          <Input aria-label="New tag" placeholder="e.g. needs-new-roof" className="w-48" value={tag} onChange={e => setTag(e.target.value)} />
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={tagShared} onChange={e => setTagShared(e.target.checked)} /> Shared
          </label>
          <Button type="submit" variant="outline" size="sm" disabled={addTag.isPending}>Add tag</Button>
        </form>
      </div>
    </section>
  )
}
