import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'
import { mockApi, ALEX } from '@/test-utils'

test('the app starts at the person picker when nobody is signed in', async () => {
  mockApi({ 'GET /api/session': () => ({ person: null }), 'GET /api/persons': () => [ALEX] })
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Who are you?' })).toBeInTheDocument()
})
