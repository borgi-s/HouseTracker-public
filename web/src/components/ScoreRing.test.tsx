import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { ScoreRing } from '@/components/ScoreRing'

test('the ring is named by the person and the score on the 1..5 scale', () => {
  render(<ScoreRing name="Alex" value={0.8} tone="a" />)
  expect(screen.getByRole('img', { name: 'Alex 4.0' })).toBeInTheDocument()
})

test('a missing overall shows a dash', () => {
  render(<ScoreRing name="Sam" value={null} tone="b" />)
  expect(screen.getByRole('img', { name: 'Sam –' })).toBeInTheDocument()
})
