import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { keys, useCriteria, usePeople } from '@/api/queries'
import type { Criterion, House, HouseDetail } from '@/api/types'
import { Button } from '@/components/ui/button'
import { DASH, money, num } from '@/lib/format'
import { disagrees, PERSON, type Slot } from '@/lib/person'
import { cn } from '@/lib/utils'

/** My taps not yet saved: criterion id -> value (null = clear). */
export type Draft = Record<string, number | null>

/** The draft after picking `value`; picking what is already saved drops the entry. */
export function pickInto(draft: Draft, saved: Record<string, number> | undefined,
                         cid: string, value: number | null): Draft {
  const next = { ...draft }
  if (value === (saved?.[cid] ?? null)) delete next[cid]
  else next[cid] = value
  return next
}

function autoValue(house: House, c: Criterion): string {
  const v = c.auto_source ? (house as unknown as Record<string, unknown>)[c.auto_source] : null
  if (typeof v !== 'number') return DASH
  if (c.auto_source === 'price_per_m2' || c.auto_source?.endsWith('_dkk')) return money(v)
  return c.auto_source?.endsWith('_m2') ? num(v, 'm²') : num(v)
}

export function ScoreRow({ label, mine, other, meSlot, otherSlot, onPick }: {
  label: string; mine?: number; other?: number; meSlot: Slot | null; otherSlot: Slot | null
  onPick: (value: number | null) => void
}) {
  const tint = disagrees(mine, other)
  return (
    <div data-disagree={tint || undefined}
      className={cn('grid grid-cols-1 sm:grid-cols-[7.5rem_1fr] items-center border-b px-1', tint && 'bg-disagree')}>
      <span className="font-semibold">{label}</span>
      <div className="relative grid grid-cols-5">
        <span aria-hidden className="absolute inset-x-[10%] top-1/2 h-px bg-input" />
        {[1, 2, 3, 4, 5].map(n => (
          <button key={n} type="button" aria-label={`${label} ${n}`} aria-pressed={mine === n}
            data-other={other === n || undefined}
            onClick={() => onPick(mine === n ? null : n)}
            className="relative grid size-11 place-items-center justify-self-center">
            <span className={cn('grid place-items-center rounded-full transition-all',
              mine === n
                ? cn('size-8 text-sm font-bold', meSlot ? PERSON[meSlot].solid : 'bg-primary text-primary-foreground')
                : 'size-3.5 border-[1.5px] border-muted-foreground/70 bg-background text-[0px]',
              other === n && cn('ring-2 ring-offset-[3px] ring-offset-muted', otherSlot ? PERSON[otherSlot].ring : 'ring-foreground'))}>
              {n}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

export function ScoresPanel({ detail }: { detail: HouseDetail }) {
  const qc = useQueryClient()
  const criteria = useCriteria()
  const { me, other, slotOf } = usePeople()
  const houseId = detail.house.id
  // Taps are held as a draft until Save. It lives in the query cache, never collected,
  // so it survives moving around the app; a reload or closing the tab asks first.
  const draftKey = ['scoreDraft', me?.id ?? '', houseId]
  const draft = useQuery({ queryKey: draftKey, queryFn: () => ({}) as Draft,
    staleTime: Infinity, gcTime: Infinity }).data ?? {}
  const setDraft = (d: Draft) => qc.setQueryData(draftKey, d)
  const saved = me ? detail.scores[me.id] : undefined
  const pending = Object.entries(draft)
  const save = useMutation({
    mutationFn: async () => {
      for (const [cid, value] of pending)
        await (value == null ? api.clearScore(houseId, cid) : api.setScore(houseId, cid, value))
    },
    onSuccess: () => setDraft({}),
    onSettled: () => Promise.all([
      qc.invalidateQueries({ queryKey: keys.house(houseId) }),
      qc.invalidateQueries({ queryKey: keys.houses }),
    ]),
  })
  useEffect(() => {
    if (!pending.length) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [pending.length])
  const mineOf = (cid: string) => (cid in draft ? draft[cid] ?? undefined : saved?.[cid])
  const list = criteria.data ?? []
  const subjective = list.filter(c => c.kind === 'subjective')
  const auto = list.filter(c => c.kind === 'auto')

  return (
    <section id="scores" className="space-y-1">
      {criteria.isSuccess && subjective.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No criteria yet — <Link to="/settings" className="underline">set them up</Link>.
        </p>
      )}
      {subjective.length > 0 && (
        <p className="flex justify-end gap-4 pb-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className={cn('size-3 rounded-full', PERSON[slotOf(me?.id) ?? 'a'].dot)} />You · tap to score, tap again to clear, then Save</span>
          {other && <span className="flex items-center gap-1.5"><span className={cn('size-2.5 rounded-full ring-2', PERSON[slotOf(other.id) ?? 'b'].ring)} />{other.name}</span>}
        </p>
      )}
      <div className="grid lg:grid-cols-2 lg:gap-x-10">
        {subjective.map(c => (
          <ScoreRow key={c.id} label={c.label}
            mine={me ? mineOf(c.id) : undefined}
            other={other ? detail.scores[other.id]?.[c.id] : undefined}
            meSlot={slotOf(me?.id)} otherSlot={slotOf(other?.id)}
            onPick={value => setDraft(pickInto(draft, saved, c.id, value))} />
        ))}
      </div>
      {pending.length > 0 && (
        // Phone: floats just above the Add photo / Rate / Add note bar. Laptop: bottom right.
        <div role="region" aria-label="Unsaved ratings"
          className="fixed inset-x-3 bottom-[calc(8rem+env(safe-area-inset-bottom))] z-20 flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-2 pl-4 shadow-lg lg:inset-x-auto lg:bottom-6 lg:right-6 lg:max-w-md">
          <span className="flex-1 text-sm font-semibold">
            {pending.length} unsaved rating{pending.length === 1 ? '' : 's'}
          </span>
          <Button variant="ghost" disabled={save.isPending} onClick={() => setDraft({})}>Discard</Button>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save'}</Button>
          {save.isError && <p className="w-full text-sm text-destructive">Couldn't save: {save.error.message}</p>}
        </div>
      )}
      {auto.length > 0 && (
        <div className="space-y-1 pt-3">
          <h3 className="text-xs font-extrabold uppercase tracking-wide text-muted-foreground">Automatic</h3>
          {auto.map(c => (
            <div key={c.id} className="flex justify-between gap-2 px-2 text-sm">
              <span>{c.label}</span>
              <span className="font-semibold">{autoValue(detail.house, c)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
