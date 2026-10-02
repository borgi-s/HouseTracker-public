import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { PriceDrop } from '@/components/PriceDrop'

test('shows the drop from the original price, spelled out for screen readers', () => {
  render(<PriceDrop original={10_000_000} price={9_500_000} />)
  expect(screen.getByText('↓5%')).toHaveAttribute('aria-hidden', 'true')
  expect(screen.getByText('Price reduced 5% from 10.000.000 kr')).toHaveClass('sr-only')
})

test.each([[null, 9e6], [9e6, null], [9e6, 9e6], [9e6, 9.5e6]])(
  'no bubble for original %s, price %s', (original, price) => {
    const { container } = render(<PriceDrop original={original} price={price} />)
    expect(container).toBeEmptyDOMElement()
  })
