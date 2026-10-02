import { expect, test } from 'vitest'
import { changedFields, filledFields, parseForm, toFormValues } from './houseForm'

test('form values round-trip: blanks become null, numbers become numbers', () => {
  const values = toFormValues({ address: 'Nyvej 2', price_dkk: 4200000, city: null })
  expect(values.address).toBe('Nyvej 2')
  expect(values.price_dkk).toBe('4200000')
  expect(values.city).toBe('')
  const parsed = parseForm({ ...values, size_m2: ' 84 ', energy_label: ' C ' })
  expect(parsed).toMatchObject({ address: 'Nyvej 2', price_dkk: 4200000, size_m2: 84, energy_label: 'C', city: null })
})

test('changedFields is the PATCH body: only differences, null clears', () => {
  const initial = { address: 'Nyvej 2', price_dkk: 4200000, size_m2: 84 }
  const parsed = parseForm({ ...toFormValues(initial), price_dkk: '4000000', size_m2: '' })
  expect(changedFields(initial, parsed)).toEqual({ price_dkk: 4000000, size_m2: null })
})

test('filledFields is the POST body: only what was entered', () => {
  const parsed = parseForm({ ...toFormValues({}), address: 'Kvikvej 1', listing_url: 'https://x.dk/1' })
  expect(filledFields(parsed)).toEqual({ address: 'Kvikvej 1', listing_url: 'https://x.dk/1' })
})
