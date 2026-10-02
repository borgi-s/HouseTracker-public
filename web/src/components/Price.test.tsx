import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Price } from '@/components/Price'

test('sold for a different price: the asking price struck through, the sold price beside it', () => {
  render(<Price price={7_995_000} sold={7_750_000} />)
  expect(screen.getByText('7.995.000 kr').tagName).toBe('S')
  expect(screen.getByText('7.750.000 kr')).toBeInTheDocument()
  expect(screen.getByText('Asking price 7.995.000 kr, sold for 7.750.000 kr')).toHaveClass('sr-only')
})

test.each([[null], [7_995_000]])('sold price %s: just the asking price', sold => {
  const { container } = render(<Price price={7_995_000} sold={sold} />)
  expect(container).toHaveTextContent(/^7\.995\.000 kr$/)
  expect(container.querySelector('s')).toBeNull()
})
