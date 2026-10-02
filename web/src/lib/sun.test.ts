import { expect, test } from 'vitest'
import { compass, danishTime, sunDay, sunPosition } from './sun'

const LYNGBY = [55.77, 12.5] as const
const near = (a: number, b: number, tol: number) => expect(Math.abs(a - b)).toBeLessThan(tol)

test('midsummer noon: the sun stands due south, 90° - latitude + 23.4° up', () => {
  const p = sunPosition(danishTime(2026, 5, 13 * 60 + 10), ...LYNGBY)
  near(p.azimuth, 180, 3)
  near(p.altitude, 90 - 55.77 + 23.44, 0.6)
})

test('sunrise and sunset in Danish clock time, summer and winter', () => {
  const june = sunDay(2026, 5, ...LYNGBY)
  near(june.rise!, 4 * 60 + 25, 12)
  near(june.set!, 21 * 60 + 58, 12)
  const december = sunDay(2026, 11, ...LYNGBY)
  near(december.rise!, 8 * 60 + 37, 12)
  near(december.set!, 15 * 60 + 38, 12)
  near(june.points[0].azimuth, 43, 5)                // midsummer sun rises in the north-east
})

test('compass names the nearest of eight directions', () => {
  expect([0, 44, 135, 200, 340].map(compass)).toEqual(['N', 'NE', 'SE', 'S', 'N'])
})
