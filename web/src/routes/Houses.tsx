import { SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useHouses, usePeople } from '@/api/queries'
import { HouseCard } from '@/components/HouseCard'
import { HousesMapView } from '@/components/HousesMapView'
import { Button } from '@/components/ui/button'
import { num } from '@/lib/format'
import { areas, filterHouses, type HouseFilter, narrow, priceSteps, SORTS, sortHouses, statusChips } from '@/lib/houses'
import { selectClass } from '@/lib/ui'
import { useIsDesktop } from '@/lib/useIsDesktop'
import { cn } from '@/lib/utils'

const pill = (on: boolean) => cn('h-11 shrink-0 rounded-full border px-4 text-sm font-semibold',
  on ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background')

export function Houses() {
  const houses = useHouses()
  const { me, pair } = usePeople()
  const navigate = useNavigate()
  const desktop = useIsDesktop()
  // Filters and sort live in the URL, so coming back from a house keeps them.
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'map' ? 'map' : 'grid'
  const filter = (params.get('status') ?? 'active') as HouseFilter
  const n = (key: string) => Number(params.get(key)) || null
  const sort = SORTS.find(s => s.key === params.get('sort')) ?? SORTS[0]
  const set = (key: string, value: string | null, replace = true) =>
    setParams(p => { if (value) p.set(key, value); else p.delete(key); return p }, { replace })
  const [picked, setPicked] = useState<string[]>([])
  const [showFilters, setShowFilters] = useState(desktop)     // the phone has no room for them by default

  if (houses.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (houses.isError) return <p className="text-destructive">Couldn't load houses: {houses.error.message}</p>
  if (houses.data.length === 0) {
    return (
      <div className="mx-auto max-w-sm space-y-3 py-16 text-center">
        <p className="text-lg font-bold">No houses yet.</p>
        <Link to="/add" className="font-bold underline">Add the first one</Link>
      </div>
    )
  }

  const narrowed = narrow(houses.data, { area: params.get('area'), maxPrice: n('max'), minSize: n('size'),
    minRooms: n('rooms'), minBaths: n('baths'), openHouse: params.has('open') })
  const pickers: { key: string; label: string; any: string; options: [string, string][] }[] = [
    { key: 'area', label: 'Area', any: 'All areas', options: areas(houses.data).map(a => [a.code, a.label]) },
    { key: 'max', label: 'Max price', any: 'Any price',
      options: priceSteps(houses.data).map(p => [String(p), `Up to ${num(p / 1e6)} mio`]) },
    { key: 'size', label: 'Min size', any: 'Any size', options: [80, 100, 120, 140, 160].map(v => [String(v), `${v}+ m²`]) },
    { key: 'rooms', label: 'Min rooms', any: 'Any rooms', options: [3, 4, 5, 6].map(v => [String(v), `${v}+ rooms`]) },
    { key: 'baths', label: 'Min bathrooms', any: 'Any bathrooms', options: [2, 3].map(v => [String(v), `${v}+ bathrooms`]) },
  ]
  const shown = sortHouses(filterHouses(narrowed, filter), sort.key, me?.id ?? null, pair.map(p => p.id))
  const toggle = (id: string) =>
    setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : p.length < 4 ? [...p, id] : p))
  const filters = <>
    {statusChips(narrowed, filter).map(c => (
      <button key={c.filter} type="button" aria-pressed={filter === c.filter}
        onClick={() => set('status', c.filter === 'active' ? null : c.filter)}
        className={pill(filter === c.filter)}>
        {c.label} · {c.count}
      </button>
    ))}
    {pickers.map(p => (
      <select key={p.key} aria-label={p.label} className={cn(selectClass, 'shrink-0')} value={params.get(p.key) ?? ''}
        onChange={e => set(p.key, e.target.value || null)}>
        <option value="">{p.any}</option>
        {p.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    ))}
    <button type="button" aria-pressed={params.has('open')} onClick={() => set('open', params.has('open') ? null : '1')}
      className={pill(params.has('open'))}>
      Open house
    </button>
  </>

  const active = (filter === 'active' ? 0 : 1) + ['area', 'max', 'size', 'rooms', 'baths', 'open'].filter(k => params.has(k)).length
  const filtersButton = (
    <button type="button" aria-expanded={showFilters} onClick={() => setShowFilters(s => !s)}
      className={cn(pill(false), 'flex items-center gap-2 shadow-sm')}>
      <SlidersHorizontal aria-hidden className="size-4" />Filters{active > 0 && ` · ${active}`}
    </button>
  )

  // On the phone the map covers the page, so it carries the filters itself.
  if (view === 'map' && !desktop) {
    return <HousesMapView houses={shown} pair={pair} toolbar={filtersButton} filters={showFilters ? filters : null}
      onList={() => set('view', null, false)} />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <h1 className="text-4xl font-bold tracking-tight lg:text-[2.75rem]">Houses</h1>
          <p className="text-muted-foreground">{shown.length} {shown.length === 1 ? 'house' : 'houses'} · sorted by {sort.label.toLowerCase()}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <div role="group" aria-label="View" className="flex rounded-full bg-muted p-1">
            {(['grid', 'map'] as const).map(v => (
              <button key={v} type="button" aria-pressed={view === v} onClick={() => set('view', v === 'map' ? 'map' : null, false)}
                className={cn('h-11 rounded-full px-4 text-sm font-semibold', view === v ? 'bg-background shadow-sm' : 'text-muted-foreground')}>
                {v === 'grid' ? 'Grid' : 'Map'}
              </button>
            ))}
          </div>
          {filtersButton}
          <select aria-label="Sort" className={selectClass} value={sort.key} onChange={e => set('sort', e.target.value === 'combined' ? null : e.target.value)}>
            {SORTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>
      </div>
      {(showFilters || picked.length >= 2 || desktop) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-5">
          <div className="flex flex-wrap gap-2">{showFilters && filters}</div>
          {picked.length >= 2
            ? <Button onClick={() => navigate(`/compare?ids=${picked.map(encodeURIComponent).join(',')}`)}>Compare {picked.length}</Button>
            : <span className="hidden text-sm text-muted-foreground lg:inline">Tick 2–4 houses to compare them</span>}
        </div>
      )}
      {view === 'map'
        ? <HousesMapView houses={shown} pair={pair} onList={() => set('view', null, false)} />
        : (
          <div className="grid gap-7 sm:grid-cols-2 lg:grid-cols-3">
            {shown.map(h => (
              <HouseCard key={h.id} house={h} pair={pair} selected={picked.includes(h.id)} onToggle={() => toggle(h.id)} />
            ))}
          </div>
        )}
    </div>
  )
}
