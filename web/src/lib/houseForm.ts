import { EDITABLE_FIELDS, type EditableField, type HouseFields } from '@/api/types'

export type FieldSpec = {
  key: EditableField
  label: string
  hint?: string
  type: 'text' | 'number' | 'url' | 'textarea'
}

export const FIELD_SPECS: FieldSpec[] = [
  { key: 'address', label: 'Address', type: 'text' },
  { key: 'postal_code', label: 'Postal code', type: 'text' },
  { key: 'city', label: 'City', type: 'text' },
  { key: 'listing_url', label: 'Listing URL', type: 'url' },
  { key: 'maegler_chain', label: 'Mægler', hint: 'estate agent', type: 'text' },
  { key: 'price_dkk', label: 'Price (kr)', type: 'number' },
  { key: 'ejerudgift_dkk', label: 'Ejerudgift (kr/md)', hint: 'monthly owner costs', type: 'number' },
  { key: 'size_m2', label: 'Size (m²)', type: 'number' },
  { key: 'lot_m2', label: 'Lot (m²)', type: 'number' },
  { key: 'rooms', label: 'Rooms', type: 'number' },
  { key: 'floors', label: 'Floors', hint: 'living floors above ground', type: 'number' },
  { key: 'bathrooms', label: 'Bathrooms', type: 'number' },
  { key: 'basement_m2', label: 'Basement (m²)', type: 'number' },
  { key: 'build_year', label: 'Build year', type: 'number' },
  { key: 'energy_label', label: 'Energimærke', hint: 'energy label', type: 'text' },
  { key: 'description', label: 'Description', type: 'textarea' },
]

const NUMERIC = new Set<EditableField>(['price_dkk', 'ejerudgift_dkk', 'size_m2', 'lot_m2', 'rooms', 'build_year', 'floors', 'bathrooms', 'basement_m2'])

export type FormValues = Record<EditableField, string>

export const toFormValues = (fields: HouseFields): FormValues =>
  Object.fromEntries(EDITABLE_FIELDS.map(k => [k, fields[k] == null ? '' : String(fields[k])])) as FormValues

/** Every editable field: '' -> null, numeric fields -> numbers, text trimmed. */
export const parseForm = (values: FormValues): HouseFields =>
  Object.fromEntries(EDITABLE_FIELDS.map(k => {
    const raw = values[k].trim()
    return [k, raw === '' ? null : NUMERIC.has(k) ? Number(raw) : raw]
  })) as HouseFields

/** The PATCH body: only fields that differ from `initial` (null clears one). */
export const changedFields = (initial: HouseFields, parsed: HouseFields): HouseFields =>
  Object.fromEntries(Object.entries(parsed)
    .filter(([k, v]) => (initial[k as EditableField] ?? null) !== v)) as HouseFields

/** The POST body for a new house: only what was filled in. */
export const filledFields = (parsed: HouseFields): HouseFields =>
  Object.fromEntries(Object.entries(parsed).filter(([, v]) => v != null)) as HouseFields
