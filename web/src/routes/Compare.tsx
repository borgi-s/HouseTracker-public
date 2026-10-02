import { useQueries } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api } from '@/api/client'
import { keys, useAnchors, useCriteria, usePeople } from '@/api/queries'
import type { HouseDetail } from '@/api/types'
import { type Better, bestIndices, fastestTo, mainAnchor, mean } from '@/lib/compare'
import { combined, DASH, floorsText, minutes, money, num, score5 } from '@/lib/format'
import { photosOf } from '@/lib/house'
import { figureText, nearestSchool } from '@/lib/school'
import { PERSON } from '@/lib/person'
import { cn } from '@/lib/utils'

type Row = { key: string; label: string; cells: ReactNode[]; best: number[] }

export function Compare() {
  const [params] = useSearchParams()
  const ids = (params.get('ids') ?? '').split(',').filter(Boolean).slice(0, 4)
  const results = useQueries({
    queries: ids.map(id => ({ queryKey: keys.house(id), queryFn: () => api.house(id) })),
  })
  const criteria = useCriteria()
  const anchor = mainAnchor(useAnchors().data)
  const { pair } = usePeople()

  if (ids.length < 2) {
    return <p className="text-muted-foreground">Pick 2–4 houses on the <Link to="/" className="underline">Houses</Link> page to compare them.</p>
  }
  const failed = results.find(r => r.isError)
  if (failed) return <p className="text-destructive">Couldn't load a house: {failed.error?.message}</p>
  if (results.some(r => !r.data)) return <p className="text-muted-foreground">Loading…</p>

  const ds = results.map(r => r.data as HouseDetail)
  const pairIds = pair.map(p => p.id)
  const numeric = (label: string, values: (number | null)[], fmt: (v: number | null) => string, better: Better): Row =>
    ({ key: label, label, cells: values.map(fmt), best: bestIndices(values, better) })

  const rows: Row[] = [
    numeric('Price', ds.map(d => d.house.price_dkk), money, 'low'),
    numeric('Size', ds.map(d => d.house.size_m2), v => num(v, 'm²'), 'high'),
    numeric('Price per m²', ds.map(d => d.house.price_per_m2), money, 'low'),
    numeric('Rooms', ds.map(d => d.house.rooms), v => num(v), 'high'),
    numeric('Bathrooms', ds.map(d => d.house.bathrooms), v => num(v), 'high'),
    { key: 'floors', label: 'Floors', cells: ds.map(d => floorsText(d.house.floors, d.house.basement_m2)), best: [] },
    numeric('Ejerudgift', ds.map(d => d.house.ejerudgift_dkk), money, 'low'),
    { key: 'energy', label: 'Energimærke', cells: ds.map(d => d.house.energy_label ?? DASH), best: [] },
    ...(anchor ? [numeric(`${anchor.label} commute`, ds.map(d => fastestTo(d.commutes, anchor.id)), minutes, 'low')] : []),
    ...pair.map(p => numeric(`${p.name} overall`, ds.map(d => d.overall[p.id] ?? null), score5, 'high')),
    numeric('Combined', ds.map(d => combined(d.overall, pairIds)), score5, 'high'),
    ...(criteria.data ?? []).filter(c => c.kind === 'subjective').map(c => ({
      key: `criterion:${c.id}`,
      label: c.label,
      cells: ds.map(d => (
        <span key={d.house.id} className="space-x-2">
          {pair.map((p, i) => (
            <b key={p.id} className={PERSON[i === 0 ? 'a' : 'b'].text}>{d.scores[p.id]?.[c.id] ?? DASH}</b>
          ))}
        </span>
      )),
      best: bestIndices(ds.map(d => mean(pair.map(p => d.scores[p.id]?.[c.id]))), 'high'),
    })),
  ]

  // School rows last (spec D13): each house's nearest school of its 0.-klasse district.
  const schools = ds.map(nearestSchool)
  if (schools.some(Boolean)) {
    const figs = schools.find(s => s)?.figures ?? []
    rows.push(
      { key: 'school', label: 'School', cells: schools.map(s => s?.name ?? DASH), best: [] },
      numeric('Walk to school', schools.map(s => s?.walk_min ?? null), minutes, 'low'),
      numeric('Bike to school', schools.map(s => s?.bike_min ?? null), minutes, 'low'),
      ...figs.map(({ key, label, better }): Row => {
        const fs = schools.map(s => s?.figures.find(f => f.key === key) ?? null)
        return {
          key: `school:${key}`,
          label,
          cells: fs.map(f => (f ? figureText(f) : DASH)),
          best: better ? bestIndices(fs.map(f => f?.value ?? null), better) : [],
        }
      }),
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] border-separate border-spacing-1 text-sm">
        <thead>
          <tr>
            <th />
            {ds.map(d => {
              const cover = photosOf(d.media)[0]
              return (
                <th key={d.house.id} scope="col" className="w-1/4 space-y-1 text-left align-bottom">
                  {cover && <img src={cover.url} alt="" className="aspect-[4/3] w-full rounded-xl object-cover" />}
                  <Link to={`/house/${encodeURIComponent(d.house.id)}`} className="block font-extrabold">{d.house.address}</Link>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.key}>
              <th scope="row" className="pr-2 text-left font-semibold text-muted-foreground">{r.label}</th>
              {r.cells.map((cell, i) => (
                <td key={i} data-best={r.best.includes(i) || undefined}
                  className={cn('rounded-lg px-2 py-1', r.best.includes(i) && 'bg-best font-extrabold')}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
