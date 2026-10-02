import { expect, test } from 'vitest'
import { distanceKm, mio } from '@/lib/geo'

test('distanceKm is the straight-line distance', () => {
  // Copenhagen City Hall Square to Central Station: 0.359 km by haversine
  expect(distanceKm({ lat: 55.6759, lon: 12.5655 }, { lat: 55.6727, lon: 12.5647 })).toBeCloseTo(0.36, 2)
})

test('mio shortens a price for a map pin', () => {
  expect(mio(8595000)).toBe('8,6 mio')
  expect(mio(9995000)).toBe('10,0 mio')
  expect(mio(null)).toBe('–')
})
