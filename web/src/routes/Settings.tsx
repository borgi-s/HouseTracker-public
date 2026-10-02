import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { keys, useCriteria, usePersons } from '@/api/queries'
import type { Criterion, CriterionPatch } from '@/api/types'
import { AddPersonForm } from '@/components/AddPersonForm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AUTO_SOURCES, DEFAULT_CRITERIA, keyFrom, reorder } from '@/lib/settings'
import { selectClass } from '@/lib/ui'
import { cn } from '@/lib/utils'

export function Settings() {
  const qc = useQueryClient()
  const criteria = useCriteria(true)
  const persons = usePersons()
  // Weights and activity change every overall, so the grid and house pages refetch too.
  const refresh = () => Promise.all(
    [['criteria'], keys.houses, ['house']].map(queryKey => qc.invalidateQueries({ queryKey })))
  const seed = useMutation({
    mutationFn: async () => { for (const c of DEFAULT_CRITERIA) await api.addCriterion(c) },
    onSettled: refresh,
  })
  const patch = useMutation({
    mutationFn: ({ id, p }: { id: string; p: CriterionPatch }) => api.updateCriterion(id, p),
    onSettled: refresh,
  })
  const move = useMutation({
    mutationFn: async (changes: { id: string; sort: number }[]) => {
      for (const ch of changes) await api.updateCriterion(ch.id, { sort: ch.sort })
    },
    onSettled: refresh,
  })
  const list = criteria.data ?? []

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <section className="space-y-3">
        <h1 className="text-xl font-extrabold">Criteria</h1>
        {criteria.isSuccess && list.length === 0 && (
          <div className="rounded-2xl bg-card p-4">
            <p className="mb-3 text-sm text-muted-foreground">
              No criteria yet. Start from a sensible set and adjust it here.
            </p>
            <Button onClick={() => seed.mutate()} disabled={seed.isPending}>Start with defaults</Button>
          </div>
        )}
        <ul className="space-y-2">
          {list.map((c, i) => (
            <CriterionRow key={c.id} c={c} first={i === 0} last={i === list.length - 1}
              onPatch={p => patch.mutate({ id: c.id, p })}
              onMove={d => move.mutate(reorder(list, i, d))} />
          ))}
        </ul>
        <AddCriterionForm nextSort={list.length} onAdded={refresh} />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-extrabold">People</h2>
        <ul className="flex flex-wrap gap-2">
          {persons.data?.map(p => <li key={p.id} className="rounded-full bg-card px-3 py-1 font-bold">{p.name}</li>)}
        </ul>
        <AddPersonForm />
      </section>
    </div>
  )
}

function CriterionRow({ c, first, last, onPatch, onMove }: {
  c: Criterion; first: boolean; last: boolean
  onPatch: (p: CriterionPatch) => void; onMove: (delta: -1 | 1) => void
}) {
  const [label, setLabel] = useState(c.label)
  const [weight, setWeight] = useState(String(c.weight))
  return (
    <li className={cn('flex flex-wrap items-center gap-2 rounded-2xl bg-card p-3', !c.active && 'opacity-60')}>
      <Input aria-label={`${c.label} label`} className="min-w-40 flex-1" value={label}
        onChange={e => setLabel(e.target.value)}
        onBlur={() => { if (label.trim() && label.trim() !== c.label) onPatch({ label: label.trim() }) }} />
      <Input aria-label={`${c.label} weight`} type="number" min={0} step={0.5} className="w-20" value={weight}
        onChange={e => setWeight(e.target.value)}
        onBlur={() => {
          const w = Number(weight)
          if (weight !== '' && w >= 0 && w !== c.weight) onPatch({ weight: w })
        }} />
      <label className="flex items-center gap-1 text-sm">
        <input type="checkbox" checked={c.active} onChange={e => onPatch({ active: e.target.checked })} /> Active
      </label>
      <Button variant="ghost" size="icon" aria-label={`Move ${c.label} up`} disabled={first} onClick={() => onMove(-1)}>↑</Button>
      <Button variant="ghost" size="icon" aria-label={`Move ${c.label} down`} disabled={last} onClick={() => onMove(1)}>↓</Button>
      {c.kind === 'auto' && (
        <p className="w-full text-xs text-muted-foreground">
          Automatic from {c.auto_source} ({c.higher_is_better ? 'higher' : 'lower'} is better)
        </p>
      )}
    </li>
  )
}

function AddCriterionForm({ nextSort, onAdded }: { nextSort: number; onAdded: () => void }) {
  const [label, setLabel] = useState('')
  const [kind, setKind] = useState<'subjective' | 'auto'>('subjective')
  const [source, setSource] = useState(AUTO_SOURCES[0])
  const [higher, setHigher] = useState(false)
  const add = useMutation({
    mutationFn: api.addCriterion,
    onSuccess: () => { setLabel(''); onAdded() },
  })
  return (
    <form className="flex flex-wrap items-center gap-2 rounded-2xl border border-dashed p-3"
      onSubmit={e => {
        e.preventDefault()
        if (!label.trim()) return
        add.mutate({
          key: keyFrom(label), label: label.trim(), kind, sort: nextSort,
          ...(kind === 'auto' ? { auto_source: source, higher_is_better: higher } : {}),
        })
      }}>
      <Input aria-label="New criterion" placeholder="New criterion, e.g. Storage" className="min-w-40 flex-1"
        value={label} onChange={e => setLabel(e.target.value)} />
      <select aria-label="Kind" className={selectClass} value={kind}
        onChange={e => setKind(e.target.value as 'subjective' | 'auto')}>
        <option value="subjective">Scored by us (1–5)</option>
        <option value="auto">Automatic</option>
      </select>
      {kind === 'auto' && (
        <>
          <select aria-label="Source" className={selectClass} value={source} onChange={e => setSource(e.target.value)}>
            {AUTO_SOURCES.map(s => <option key={s}>{s}</option>)}
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={higher} onChange={e => setHigher(e.target.checked)} /> Higher is better
          </label>
        </>
      )}
      <Button type="submit" variant="outline" disabled={add.isPending}>Add criterion</Button>
    </form>
  )
}
