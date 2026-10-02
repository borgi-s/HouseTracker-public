import { expect, test } from 'vitest'
import { combined, floorsText, km, minutes, money, num, pctChange, score5 } from './format'

test('money uses Danish grouping and a dash for missing', () => {
  expect(money(5495000)).toBe('5.495.000 kr')
  expect(money(0)).toBe('0 kr')
  expect(money(null)).toBe('–')
})

test('num keeps one Danish decimal and appends the unit', () => {
  expect(num(142, 'm²')).toBe('142 m²')
  expect(num(4.5)).toBe('4,5')
  expect(num(undefined, 'm²')).toBe('–')
})

test('score5 shows 0..1 overalls on the 1..5 tap scale', () => {
  expect(score5(0.78)).toBe('3.9')
  expect(score5(1)).toBe('5.0')
  expect(score5(null)).toBe('–')
})

test('combined averages only the overalls that exist', () => {
  expect(combined({ alex: 0.8, sam: 0.6 }, ['alex', 'sam'])).toBeCloseTo(0.7)
  expect(combined({ alex: 0.8, sam: null }, ['alex', 'sam'])).toBe(0.8)
  expect(combined({}, ['alex'])).toBeNull()
})

test('minutes, km and pctChange', () => {
  expect(minutes(13.6)).toBe('14 min')
  expect(km(5230)).toBe('5,2 km')
  expect(pctChange(5_000_000, 5_250_000)).toBe('+5.0 %')
  expect(pctChange(5_000_000, 4_750_000)).toBe('-5.0 %')
  expect(pctChange(null, 1)).toBe('–')
})

test('floorsText adds the basement when there is one', () => {
  expect(floorsText(2, 32)).toBe('2 + basement 32 m²')
  expect(floorsText(1, null)).toBe('1')
  expect(floorsText(null, 40)).toBe('–')
})
