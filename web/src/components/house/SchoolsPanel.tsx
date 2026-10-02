import { useState } from 'react'
import type { School, SchoolDistrict, Schools } from '@/api/types'
import { Button } from '@/components/ui/button'
import { DASH, km, minutes } from '@/lib/format'
import { denmarkText, figureText, figureValue, safeHref } from '@/lib/school'

function Trips({ s }: { s: School }) {
  if (s.walk_min == null && s.bike_min == null) {
    return <p className="text-sm">{s.straight_m == null ? DASH : `${km(s.straight_m)} in a straight line`}</p>
  }
  return (
    <p className="text-sm">
      Walk {minutes(s.walk_min)} · {km(s.walk_m)}<span className="mx-2 text-muted-foreground">|</span>Bike {minutes(s.bike_min)} · {km(s.bike_m)}
    </p>
  )
}

function SchoolCard({ s }: { s: School }) {
  const href = safeHref(s.url)
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="space-y-1">
        <h4 className="font-bold">
          {href ? <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-4">{s.name}</a> : s.name}
        </h4>
        <p className="text-sm text-muted-foreground">
          {[s.address, s.grades && `${s.grades} klasse`].filter(Boolean).join(' · ')}
        </p>
        <Trips s={s} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th scope="col" className="py-1 pr-2 font-medium">Figure</th>
              <th scope="col" className="py-1 pr-2 font-medium">School</th>
              <th scope="col" className="py-1 pr-2 font-medium">Kommune avg</th>
              <th scope="col" className="py-1 font-medium">Denmark</th>
            </tr>
          </thead>
          <tbody>
            {s.figures.map(f => (
              <tr key={f.key} className="border-t">
                <th scope="row" className="py-1 pr-2 text-left font-medium">{f.label}</th>
                <td className="py-1 pr-2">
                  {figureText(f)}{f.note && <span className="text-muted-foreground"> ({f.note})</span>}
                </td>
                <td className="py-1 pr-2">{f.kommune_avg == null ? DASH : figureValue(f, f.kommune_avg)}</td>
                <td className="py-1">{denmarkText(f)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function District({ d }: { d: SchoolDistrict }) {
  const [more, setMore] = useState(false)
  const [first, ...rest] = d.schools
  const link = safeHref(d.link)
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-bold">
        {d.name} <span className="text-sm font-medium text-muted-foreground">{d.grades} klasse</span>
      </h3>
      {d.fallback && (
        <p className="text-sm text-muted-foreground">District school not identified; the nearest folkeskoler are shown.</p>
      )}
      {d.school_count > 1 && (
        <p className="text-sm text-muted-foreground">
          {d.school_count} folkeskoler share this district; the address doesn't pick one school.
          {link && <> <a href={link} target="_blank" rel="noreferrer" className="underline underline-offset-4">The kommune's school page</a></>}
        </p>
      )}
      {first && <SchoolCard s={first} />}
      {more && rest.map(s => <SchoolCard key={s.inst_nr} s={s} />)}
      {rest.length > 0 && (
        <Button variant="outline" size="sm" onClick={() => setMore(m => !m)}>
          {more ? 'Show only the nearest' : `Show ${rest.length === 1 ? '2nd' : '2nd and 3rd'} nearest`}
        </Button>
      )}
    </div>
  )
}

/** The house's district school(s): nearest first, figures against kommune and country. */
export function SchoolsPanel({ schools }: { schools: Schools | null }) {
  if (!schools?.districts.length) return <p className="text-muted-foreground">No school data yet.</p>
  return (
    <div className="space-y-6">
      {schools.districts.map(d => <District key={`${d.name} ${d.grades}`} d={d} />)}
      <p className="text-sm text-muted-foreground">
        Figures from skolegang.dk (Uddannelsesstatistik). Kommune avg = plain mean of the kommune's folkeskoler that year.
      </p>
    </div>
  )
}
