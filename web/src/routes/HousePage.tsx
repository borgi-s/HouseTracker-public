import { useMutation } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { ApiError, api } from '@/api/client'
import { useHouse, useRefreshHouse } from '@/api/queries'
import type { Media } from '@/api/types'
import { CaptureBar } from '@/components/house/CaptureBar'
import { DetailsPanel } from '@/components/house/DetailsPanel'
import { HouseHero } from '@/components/house/HouseHero'
import { HouseSummary } from '@/components/house/HouseSummary'
import { OpenHousePanel } from '@/components/house/OpenHousePanel'
import { PdfView } from '@/components/house/MediaViews'
import { Button } from '@/components/ui/button'
import { PriceHistoryPanel } from '@/components/house/PriceHistoryPanel'
import { SchoolsPanel } from '@/components/house/SchoolsPanel'
import { StatusCard } from '@/components/house/StatusCard'
import { Viewer, type ViewerState } from '@/components/house/Viewer'
import { WhereWeStand } from '@/components/house/WhereWeStand'
import { ofKind, photosOf, POLL_MS, scrapedCount, shouldPoll } from '@/lib/house'
import { useIsDesktop } from '@/lib/useIsDesktop'

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-bold tracking-tight">
        {title}{hint && <span className="ml-2 text-sm font-medium text-muted-foreground">{hint}</span>}
      </h2>
      {children}
    </section>
  )
}

/** Reads like the realtor's page (photos, facts, the listing's text), then where the house
 *  stands for us: its status and our scores. */
export function HousePage() {
  const { id = '' } = useParams()
  const added = (useLocation().state as { mediaPending?: number } | null)?.mediaPending ?? 0
  // What the background download should end with; set on arrival from Add, and again by a refresh.
  const [wait, setWait] = useState(() => ({ pending: added, startedAt: Date.now() }))
  const q = useHouse(id, d => (shouldPoll(scrapedCount(d?.media ?? []), wait.pending, wait.startedAt, Date.now()) ? POLL_MS : false))
  const desktop = useIsDesktop()
  const refresh = useRefreshHouse()
  const [viewer, setViewer] = useState<ViewerState | null>(null)
  const delMedia = useMutation({
    mutationFn: (m: Media) => api.deleteMedia(m.id),
    onSuccess: () => { setViewer(null); return refresh(id) },
  })
  const navigate = useNavigate()
  const rescrape = useMutation({
    mutationFn: () => api.rescrape(id),
    onSuccess: r => {
      setWait({ pending: r.media_pending, startedAt: Date.now() })
      // Best effort, as on Add: the address may have changed, so re-locate the house.
      api.enrich(id).then(() => refresh(id), () => {})
      return refresh(id)
    },
  })
  const delHouse = useMutation({
    mutationFn: () => api.deleteHouse(id),
    onSuccess: async () => { await refresh(id); navigate('/') },
  })

  if (q.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (q.isError) {
    return (
      <p className="text-destructive">
        {q.error instanceof ApiError && q.error.status === 404 ? 'No such house.' : `Couldn't load: ${q.error.message}`}
      </p>
    )
  }

  const d = q.data
  const photos = photosOf(d.media)
  const plans = ofKind(d.media, 'floorplan')
  const pdf = ofKind(d.media, 'pdf')[0]
  const where = d.house.lat != null && d.house.lon != null ? { lat: d.house.lat, lon: d.house.lon } : null
  // dataUpdatedAt, not Date.now(): each poll re-renders, so the last one clears the note
  const downloading = shouldPoll(scrapedCount(d.media), wait.pending, wait.startedAt, q.dataUpdatedAt)

  return (
    <article className="space-y-10 pb-40 lg:pb-12">
      <HouseHero photos={photos} plans={plans} location={where} desktop={desktop}
        onOpen={(tab, index) => setViewer({ tab, index })} />
      {downloading && <p className="text-sm text-muted-foreground">Downloading photos and documents…</p>}
      <HouseSummary detail={d} />
      {d.open_houses.length > 0 && <Section title="Open house"><OpenHousePanel detail={d} /></Section>}
      <StatusCard detail={d} />
      <WhereWeStand detail={d} />
      {pdf && <Section title="Salgsopstilling" hint="sales prospectus"><PdfView pdf={pdf} inline={desktop} /></Section>}
      <Section title="Price history"><PriceHistoryPanel detail={d} /></Section>
      <Section title="School" hint="district folkeskole"><SchoolsPanel schools={d.schools} /></Section>
      <Section title="Details"><DetailsPanel detail={d} /></Section>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={rescrape.isPending || !d.house.listing_url} onClick={() => rescrape.mutate()}>
          {rescrape.isPending ? 'Re-reading the listing…' : 'Refresh from listing'}
        </Button>
        {rescrape.isError && <span className="text-sm text-destructive">Couldn't refresh: {rescrape.error.message}</span>}
        <Button variant="destructive" disabled={delHouse.isPending}
          onClick={() => { if (window.confirm('Delete this house and everything about it?')) delHouse.mutate() }}>
          Delete house
        </Button>
      </div>
      {!desktop && <CaptureBar houseId={d.house.id} status={d.house.status} />}
      <Viewer state={viewer} photos={photos} plans={plans} location={where}
        onChange={setViewer} onClose={() => setViewer(null)}
        onDelete={m => { if (window.confirm('Delete this photo?')) delMedia.mutate(m) }} />
    </article>
  )
}
