import { useMutation } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { api } from '@/api/client'
import { useAnchors, useRefreshHouse } from '@/api/queries'
import {
  type Anchor, type Commute, EDITABLE_FIELDS, type House, type HouseDetail, type HouseFields,
} from '@/api/types'
import { HouseForm } from '@/components/HouseForm'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DASH, floorsText, km, minutes, MODE_LABEL, money, num, pctChange } from '@/lib/format'
import { changedFields } from '@/lib/houseForm'

const editable = (h: House): HouseFields =>
  Object.fromEntries(EDITABLE_FIELDS.map(k => [k, h[k]])) as HouseFields

/** [label, value, English hint for a Danish term] */
function facts(h: House): [string, string, string?][] {
  const rows: [string, string, string?][] = [
    ['Price', money(h.price_dkk)],
    ['Price per m²', money(h.price_per_m2)],
    ['Ejerudgift', h.ejerudgift_dkk == null ? DASH : `${money(h.ejerudgift_dkk)}/md`, 'monthly owner costs'],
    ['Size', num(h.size_m2, 'm²')],
    ['Lot', num(h.lot_m2, 'm²')],
    ['Rooms', num(h.rooms)],
    ['Floors', floorsText(h.floors, h.basement_m2)],
    ['Bathrooms', num(h.bathrooms)],
    ['Built', h.build_year == null ? DASH : String(h.build_year)],
    ['Energimærke', h.energy_label ?? DASH, 'energy label'],
    ['Kommune', h.kommune ?? DASH, 'municipality'],
    ['Mægler', h.maegler_chain ?? DASH, 'estate agent'],
  ]
  if (h.status === 'sold') {
    rows.push(
      ['Sold for', money(h.sold_price_dkk)],
      ['Sold on', h.sold_date ?? DASH],
      ['vs asking', pctChange(h.price_dkk, h.sold_price_dkk)],
    )
  }
  return rows
}

function CommuteTable({ commutes, anchors }: { commutes: Commute[]; anchors: Anchor[] }) {
  if (commutes.length === 0) {
    return <p className="text-sm text-muted-foreground">No commute times yet (routing needs HT_ORS_KEY on the server).</p>
  }
  const refs = [...new Set(commutes.map(c => c.anchor_ref))]
  const modes = Object.keys(MODE_LABEL)
  const label = (ref: string) =>
    anchors.find(a => a.id === ref)?.label ?? (ref === 'school' ? 'District school' : ref)
  return (
    <table className="w-full text-sm">
      <thead>
        <tr><th />{modes.map(m => <th key={m} className="text-left font-semibold text-muted-foreground">{MODE_LABEL[m]}</th>)}</tr>
      </thead>
      <tbody>
        {refs.map(ref => (
          <tr key={ref}>
            <th scope="row" className="pr-2 text-left font-semibold">{label(ref)}</th>
            {modes.map(m => {
              const c = commutes.find(x => x.anchor_ref === ref && x.mode === m)
              return <td key={m}>{c ? `${minutes(c.minutes)} · ${km(c.distance_m)}` : DASH}</td>
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function DetailsPanel({ detail }: { detail: HouseDetail }) {
  const h = detail.house
  const anchors = useAnchors()
  const refresh = useRefreshHouse()
  const [editing, setEditing] = useState(false)
  const locate = useMutation({ mutationFn: () => api.enrich(h.id), onSettled: () => refresh(h.id) })
  const edit = useMutation({
    mutationFn: (fields: HouseFields) => api.updateHouse(h.id, fields),
    onSuccess: (_house, fields) => {
      setEditing(false)
      // The location comes from the address with its postcode and town.
      if ('address' in fields || 'postal_code' in fields || 'city' in fields) locate.mutate()
      return refresh(h.id)
    },
  })
  const heading = 'text-xs font-extrabold uppercase tracking-wide text-muted-foreground'

  return (
    <section className="space-y-6">
      <div className="space-y-3">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {facts(h).map(([k, v, hint]) => (
            <Fragment key={k}>
              <dt className="text-muted-foreground">{k}{hint && <span className="block text-xs">{hint}</span>}</dt>
              <dd className="font-semibold">{v}</dd>
            </Fragment>
          ))}
        </dl>
        <Dialog open={editing} onOpenChange={setEditing}>
          <DialogTrigger asChild><Button variant="outline" size="sm">Edit details</Button></DialogTrigger>
          <DialogContent aria-describedby={undefined} className="max-h-[90dvh] overflow-y-auto">
            <DialogTitle>Edit details</DialogTitle>
            <HouseForm initial={editable(h)} submitLabel="Save" pending={edit.isPending}
              onSubmit={parsed => {
                const changed = changedFields(editable(h), parsed)
                if (Object.keys(changed).length) edit.mutate(changed)
                else setEditing(false)
              }} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        <h3 className={heading}>Location</h3>
        {h.lat == null ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span>Location not computed.</span>
            <Button variant="outline" size="sm" onClick={() => locate.mutate()} disabled={locate.isPending}>
              Retry location
            </Button>
          </div>
        ) : (
          <>
            <CommuteTable commutes={detail.commutes} anchors={anchors.data ?? []} />
            {detail.school_map_url && (
              <a href={detail.school_map_url} target="_blank" rel="noreferrer"
                className="inline-block text-sm font-semibold underline underline-offset-4">
                School district map (GeoFA) ↗
              </a>
            )}
          </>
        )}
      </div>

      <div className="space-y-1">
        <h3 className={heading}>Status history</h3>
        <ol className="text-sm">
          {detail.status_history.map((e, i) => <li key={i}>{e.at} — {e.status}</li>)}
        </ol>
      </div>
    </section>
  )
}
