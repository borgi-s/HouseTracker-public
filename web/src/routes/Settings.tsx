import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { keys, useAnchors, useCriteria, usePersons, useSettings } from '@/api/queries'
import type { Anchor, Criterion, CriterionPatch, Person, SettingsPatch } from '@/api/types'
import { AddPersonForm } from '@/components/AddPersonForm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AUTO_SOURCES, DEFAULT_CRITERIA, keyFrom, reorder, sweepSummary, weightShares } from '@/lib/settings'
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
  const remove = useMutation({ mutationFn: api.deleteCriterion, onSettled: refresh })
  const list = criteria.data ?? []
  const shares = weightShares(list)

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
            <CriterionRow key={c.id} c={c} share={shares[c.id]} first={i === 0} last={i === list.length - 1}
              onPatch={p => patch.mutate({ id: c.id, p })}
              onMove={d => move.mutate(reorder(list, i, d))}
              onRemove={() => {
                if (window.confirm(`Remove "${c.label}" and every score given on it? Unticking Active keeps the scores.`))
                  remove.mutate(c.id)
              }} />
          ))}
        </ul>
        <AddCriterionForm nextSort={list.length} onAdded={refresh} />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-extrabold">People</h2>
        <ul className="space-y-2">
          {persons.data?.map(p => <PersonRow key={p.id} p={p} />)}
        </ul>
        <AddPersonForm />
      </section>

      <Places />
      <Notifications />
    </div>
  )
}

function PersonRow({ p }: { p: Person }) {
  const qc = useQueryClient()
  const [name, setName] = useState(p.name)
  // A removed person takes their scores with them, and may be whoever is signed in.
  const refresh = () => Promise.all(
    [keys.persons, keys.session, keys.houses, ['house']].map(queryKey => qc.invalidateQueries({ queryKey })))
  const rename = useMutation({ mutationFn: (n: string) => api.renamePerson(p.id, n), onSettled: refresh })
  const remove = useMutation({ mutationFn: () => api.deletePerson(p.id), onSettled: refresh })
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-2xl bg-card p-3">
      <Input aria-label={`${p.name} name`} className="min-w-40 flex-1" value={name}
        onChange={e => setName(e.target.value)}
        onBlur={() => { if (name.trim() && name.trim() !== p.name) rename.mutate(name.trim()) }} />
      <Button variant="ghost" aria-label={`Remove ${p.name}`} disabled={remove.isPending}
        onClick={() => {
          if (window.confirm(`Remove ${p.name}, with their scores and private notes and tags?`)) remove.mutate()
        }}>Remove</Button>
      {rename.isError && <p className="w-full text-sm text-destructive">{rename.error.message}</p>}
    </li>
  )
}

/** Fixed anchors: where travel times are measured to. */
function Places() {
  const qc = useQueryClient()
  const anchors = useAnchors()
  const [label, setLabel] = useState('')
  const [address, setAddress] = useState('')
  // New travel times are computed in the background, so house pages refetch as they open.
  const refresh = () => Promise.all([keys.anchors, ['house']].map(queryKey => qc.invalidateQueries({ queryKey })))
  const add = useMutation({
    mutationFn: () => api.addAnchor(label.trim(), address.trim()),
    onSuccess: () => { setLabel(''); setAddress(''); return refresh() },
  })
  const remove = useMutation({ mutationFn: api.deleteAnchor, onSettled: refresh })
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-extrabold">Places</h2>
      <p className="text-sm text-muted-foreground">Travel times from every house are measured to these. A new address recomputes them.</p>
      <ul className="space-y-2">
        {anchors.data?.filter(a => a.kind === 'fixed').map(a => (
          <PlaceRow key={a.id} a={a} onSaved={refresh}
            onRemove={() => { if (window.confirm(`Remove ${a.label} and its travel times?`)) remove.mutate(a.id) }} />
        ))}
      </ul>
      <form className="flex flex-wrap items-center gap-2 rounded-2xl border border-dashed p-3"
        onSubmit={e => { e.preventDefault(); if (label.trim() && address.trim()) add.mutate() }}>
        <Input aria-label="Place name" placeholder="Name, e.g. Work" className="w-full sm:w-36"
          value={label} onChange={e => setLabel(e.target.value)} />
        <Input aria-label="Place address" placeholder="Address with postcode" className="min-w-48 flex-1"
          value={address} onChange={e => setAddress(e.target.value)} />
        <Button type="submit" variant="outline" disabled={add.isPending}>Add place</Button>
        {add.isError && <p className="w-full text-sm text-destructive">{add.error.message}</p>}
      </form>
    </section>
  )
}

function PlaceRow({ a, onSaved, onRemove }: { a: Anchor; onSaved: () => unknown; onRemove: () => void }) {
  const [editing, setEditing] = useState(false)
  const [label, setLabel] = useState(a.label)
  const [address, setAddress] = useState(a.address ?? '')
  const save = useMutation({
    mutationFn: () => api.updateAnchor(a.id, { label: label.trim(), address: address.trim() }),
    onSuccess: () => { setEditing(false); return onSaved() },
  })
  if (!editing) {
    return (
      <li className="flex items-center gap-2 rounded-2xl bg-card p-3">
        <div className="flex-1">
          <p className="font-bold">{a.label}</p>
          {a.address && <p className="text-sm text-muted-foreground">{a.address}</p>}
        </div>
        <Button variant="ghost" aria-label={`Edit ${a.label}`} onClick={() => setEditing(true)}>Edit</Button>
        <Button variant="ghost" aria-label={`Remove ${a.label}`} onClick={onRemove}>Remove</Button>
      </li>
    )
  }
  return (
    <li>
      <form className="flex flex-wrap items-center gap-2 rounded-2xl bg-card p-3"
        onSubmit={e => { e.preventDefault(); if (label.trim() && address.trim()) save.mutate() }}>
        <Input aria-label={`${a.label} name`} className="w-full sm:w-36" value={label} onChange={e => setLabel(e.target.value)} />
        <Input aria-label={`${a.label} address`} className="min-w-48 flex-1" value={address}
          onChange={e => setAddress(e.target.value)} />
        <Button type="submit" aria-label={`Save ${a.label}`} disabled={save.isPending}>Save</Button>
        <Button type="button" variant="ghost" onClick={() => {
          setEditing(false); setLabel(a.label); setAddress(a.address ?? ''); save.reset()
        }}>Cancel</Button>
        {save.isError && <p className="w-full text-sm text-destructive">{save.error.message}</p>}
      </form>
    </li>
  )
}

function Notifications() {
  const qc = useQueryClient()
  const settings = useSettings()
  const save = useMutation({
    mutationFn: (p: SettingsPatch) => api.updateSettings(p),
    onSuccess: data => qc.setQueryData(keys.settings, data),
  })
  const sweep = useMutation({ mutationFn: api.lifecycle, onSuccess: () => qc.invalidateQueries({ queryKey: keys.houses }) })
  const s = settings.data
  const off = !s?.discord_configured
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-extrabold">Notifications</h2>
      <div className="space-y-2 rounded-2xl bg-card p-3">
        {s && off && (
          <p className="text-sm text-muted-foreground">
            No Discord webhook is set up, so nothing is sent. Set HT_DISCORD_WEBHOOK on the server to turn it on.
          </p>
        )}
        {([['notify_price_drops', 'Price drops'], ['notify_open_houses', 'Open houses']] as const).map(([k, label]) => (
          <label key={k} className={cn('flex items-center gap-2', off && 'opacity-60')}>
            <input type="checkbox" aria-label={label} disabled={off} checked={s?.[k] ?? false}
              onChange={e => save.mutate({ [k]: e.target.checked })} /> {label}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={sweep.isPending} onClick={() => sweep.mutate()}>
          {sweep.isPending ? 'Checking listings…' : 'Check listings now'}
        </Button>
        {sweep.isSuccess && <span className="text-sm">{sweepSummary(sweep.data)}</span>}
        {sweep.isError && <span className="text-sm text-destructive">Couldn't check: {sweep.error.message}</span>}
      </div>
      <p className="text-xs text-muted-foreground">
        Looks for sold houses, price changes and new open houses. This also runs by itself every day.
      </p>
    </section>
  )
}

function CriterionRow({ c, share, first, last, onPatch, onMove, onRemove }: {
  c: Criterion; share: number | undefined; first: boolean; last: boolean
  onPatch: (p: CriterionPatch) => void; onMove: (delta: -1 | 1) => void; onRemove: () => void
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
      {share !== undefined && (
        <span className="w-10 text-right text-sm tabular-nums text-muted-foreground" title="Share of the overall score">
          {share}%
        </span>
      )}
      <label className="flex items-center gap-1 text-sm">
        <input type="checkbox" checked={c.active} onChange={e => onPatch({ active: e.target.checked })} /> Active
      </label>
      <Button variant="ghost" size="icon" aria-label={`Move ${c.label} up`} disabled={first} onClick={() => onMove(-1)}>↑</Button>
      <Button variant="ghost" size="icon" aria-label={`Move ${c.label} down`} disabled={last} onClick={() => onMove(1)}>↓</Button>
      <Button variant="ghost" size="icon" aria-label={`Remove ${c.label}`} onClick={onRemove}>×</Button>
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
