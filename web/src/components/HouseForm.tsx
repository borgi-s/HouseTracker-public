import { type ChangeEvent, useState } from 'react'
import type { EditableField, HouseFields } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { FIELD_SPECS, parseForm, toFormValues } from '@/lib/houseForm'
import { cn } from '@/lib/utils'

/** Every editable house field. Hands the caller the parsed form; the caller decides
 *  whether that becomes a POST (filledFields) or a PATCH (changedFields). */
export function HouseForm({ initial, submitLabel, pending, onSubmit }: {
  initial: HouseFields; submitLabel: string; pending?: boolean; onSubmit: (parsed: HouseFields) => void
}) {
  const [values, setValues] = useState(() => toFormValues(initial))
  const set = (k: EditableField) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setValues(v => ({ ...v, [k]: e.target.value }))
  return (
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); onSubmit(parseForm(values)) }}>
      {FIELD_SPECS.map(f => (
        <div key={f.key} className={cn('grid gap-1', (f.type === 'textarea' || f.key === 'address') && 'sm:col-span-2')}>
          <Label htmlFor={`f-${f.key}`}>{f.label}</Label>
          {f.type === 'textarea'
            ? <Textarea id={`f-${f.key}`} value={values[f.key]} onChange={set(f.key)} />
            : <Input id={`f-${f.key}`} type={f.type} step={f.type === 'number' ? 'any' : undefined}
                required={f.key === 'address'} value={values[f.key]} onChange={set(f.key)} />}
          {f.hint && <span className="text-xs text-muted-foreground">{f.hint}</span>}
        </div>
      ))}
      <Button type="submit" className="sm:col-span-2" disabled={pending}>{submitLabel}</Button>
    </form>
  )
}
