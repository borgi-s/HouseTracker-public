import { expect, test } from 'vitest'
import { tilesFor, toUtm32 } from './utm'

test('toUtm32 matches an independent transverse Mercator at Lyngby station', () => {
  // Snyder's series (GRS80, CM 9°E, k0 0.9996): (719737.84, 6185820.18)
  const [e, n] = toUtm32(55.76804, 12.50311)
  expect(Math.abs(e - 719737.84)).toBeLessThan(3)
  expect(Math.abs(n - 6185820.18)).toBeLessThan(3)
})

test('tilesFor picks the level nearest the map resolution, capped, and the tiles under the quad', () => {
  const quad: [number, number][] = [[727392, 6188906], [727443, 6188906], [727392, 6188866], [727443, 6188866]]
  const [t] = tilesFor(quad, 0.2, 15)               // 0.2 m/px is L13: 51.2 m tiles
  expect(t).toMatchObject({ level: 13, col: 11863, row: 6076, span: 51.2 })
  expect(tilesFor(quad, 0.2, 11)[0].level).toBe(11)  // flood tiles stop at L11; drawn larger
  expect(tilesFor(quad, 0.2, 15)).toHaveLength(2)    // it straddles the column edge at E 727436.8
})
