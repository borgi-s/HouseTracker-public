import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, api } from '@/api/client'
import { keys } from '@/api/queries'
import { type House, type HouseFields, STATUS_LABELS, type Status } from '@/api/types'
import { HouseForm } from '@/components/HouseForm'
import { Button } from '@/components/ui/button'
import { filledFields } from '@/lib/houseForm'

type Tracked = { id: string; address: string; status: Status }

/** The house a 409 says we already track (same link or address), if that is the error. */
const trackedHouse = (e: Error | null): Tracked | undefined =>
  e instanceof ApiError && e.status === 409 ? (e.detail as { house?: Tracked } | undefined)?.house : undefined

/** Spec §4.3: paste the listing URL (the normal path at a viewing) or enter by hand. */
export function AddHouse() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [url, setUrl] = useState('')
  const [manual, setManual] = useState<HouseFields | null>(null)

  const opened = (house: House, mediaPending = 0) => {
    // Best effort (spec §7): if enrich fails the house page offers "Retry location".
    api.enrich(house.id).then(() => qc.invalidateQueries({ queryKey: keys.house(house.id) }), () => {})
    void qc.invalidateQueries({ queryKey: keys.houses })
    navigate(`/house/${encodeURIComponent(house.id)}`, { state: { mediaPending } })
  }
  const scrape = useMutation({
    mutationFn: (useBrowser: boolean) => api.scrape(url.trim(), useBrowser),
    onSuccess: r => opened(r, r.media_pending),
    onError: e => { if (e instanceof ApiError && e.status === 422) setManual({ listing_url: url.trim() }) },
  })
  const create = useMutation({ mutationFn: api.createHouse, onSuccess: h => opened(h) })
  const failed = scrape.error instanceof ApiError ? scrape.error : null
  const tracked = trackedHouse(scrape.error) ?? trackedHouse(create.error)

  return (
    <div className="mx-auto max-w-2xl space-y-8 py-4">
      <h1 className="text-4xl font-bold tracking-tight">Add a house</h1>
      <form className="flex h-16 items-center gap-3 rounded-full border border-input bg-background pr-2 pl-5 shadow-sm"
        onSubmit={e => { e.preventDefault(); if (url.trim()) scrape.mutate(false) }}>
        <Link2 aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        <label htmlFor="listing-link" className="sr-only">Link to the listing</label>
        <input id="listing-link" type="url" required placeholder="Paste a listing link from edc, home, nybolig, danbolig…"
          value={url} onChange={e => setUrl(e.target.value)}
          className="h-12 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground" />
        <Button type="submit" size="lg" disabled={scrape.isPending}>
          {scrape.isPending ? 'Fetching the listing…' : 'Add from link'}
        </Button>
      </form>
      {failed?.status === 502 && (
        <div className="space-y-2 rounded-2xl bg-card p-4 text-sm">
          <p>Couldn't fetch the listing ({failed.message}).</p>
          <Button variant="outline" onClick={() => scrape.mutate(true)} disabled={scrape.isPending}>Try with browser</Button>
        </div>
      )}
      {failed?.status === 422 && <p className="text-sm">Couldn't read an address from that page — enter it by hand below.</p>}
      {tracked && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-card p-4 text-sm">
          <p><span className="font-bold">{tracked.address}</span> is already tracked · {STATUS_LABELS[tracked.status]}</p>
          <Link to={`/house/${encodeURIComponent(tracked.id)}`} className="font-bold underline">Open it</Link>
        </div>
      )}
      {manual
        ? <HouseForm key={JSON.stringify(manual)} initial={manual} submitLabel="Add house"
            pending={create.isPending} onSubmit={p => create.mutate(filledFields(p))} />
        : <Button variant="link" onClick={() => setManual({})}>No link — enter by hand</Button>}
    </div>
  )
}
