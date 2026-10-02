import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { SchoolsPanel } from '@/components/house/SchoolsPanel'
import { makeFigure, makeSchool, makeSchools } from '@/test-utils'

const cells = (label: string) =>
  within(screen.getByRole('rowheader', { name: label }).closest('tr')!).getAllByRole('cell').map(c => c.textContent)

test('one district school: link, walk and bike, and each figure against kommune and country', () => {
  render(<SchoolsPanel schools={makeSchools()} />)
  expect(screen.getByRole('link', { name: 'Fuglsanggårdsskolen' }))
    .toHaveAttribute('href', 'https://skolegang.dk/skole/fuglsanggaardsskolen')
  expect(screen.getByText(/^Walk 11 min · 0,9 km/)).toHaveTextContent('Bike 4 min · 1 km')
  expect(cells('Grade average')).toEqual(['8,8 · 2024/25', '8,4', '#71 of 2.870'])
  expect(screen.queryByRole('button', { name: /nearest/ })).not.toBeInTheDocument()
  expect(screen.queryByText(/share this district/)).not.toBeInTheDocument()
})

test('a shared district says so and hides the 2nd and 3rd nearest behind a toggle', async () => {
  render(<SchoolsPanel schools={makeSchools([{
    name: 'Gentofte', school_count: 11, link: 'https://gentofte.dk/folkeskoler',
    schools: [makeSchool({ inst_nr: '1', name: 'Tjørnegårdsskolen' }),
      makeSchool({ inst_nr: '2', name: 'Bakkegårdsskolen' }), makeSchool({ inst_nr: '3', name: 'Gentofte Skole' })],
  }])} />)
  expect(screen.getByText(/^11 folkeskoler share this district/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: "The kommune's school page" })).toHaveAttribute('href', 'https://gentofte.dk/folkeskoler')
  expect(screen.getByRole('link', { name: 'Tjørnegårdsskolen' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Bakkegårdsskolen' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Show 2nd and 3rd nearest' }))
  expect(screen.getByRole('link', { name: 'Bakkegårdsskolen' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Gentofte Skole' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Show only the nearest' }))
  expect(screen.queryByRole('link', { name: 'Bakkegårdsskolen' })).not.toBeInTheDocument()
})

test('missing figures read "not reported"; wellbeing shows the national average; the effect its verdict', () => {
  render(<SchoolsPanel schools={makeSchools([{ schools: [makeSchool({ figures: [
    makeFigure({ value: null, year: null, kommune_avg: null, national_rank: null }),
    makeFigure({ key: 'wellbeing', label: 'Overall wellbeing', value: 3.8, national_avg: 3.6, national_rank: null }),
    makeFigure({ key: 'teaching_effect', label: 'Teaching effect', value: 0.5, note: 'Over niveau' }),
    makeFigure({ key: 'absence', label: 'Absence', unit: '%', value: 6.3, kommune_avg: 6.97 }),
  ] })] }])} />)
  expect(cells('Grade average')).toEqual(['not reported', '–', '–'])
  expect(cells('Overall wellbeing')[2]).toBe('avg 3,6')
  expect(cells('Teaching effect')[0]).toBe('0,5 · 2024/25 (Over niveau)')
  expect(cells('Absence').slice(0, 2)).toEqual(['6,3 % · 2024/25', '7 %'])
})

test('without routes the straight-line distance is shown; a fallback district says so', () => {
  render(<SchoolsPanel schools={makeSchools([{ fallback: true, school_count: 0,
    schools: [makeSchool({ walk_min: null, walk_m: null, bike_min: null, bike_m: null })] }])} />)
  expect(screen.getByText('0,7 km in a straight line')).toBeInTheDocument()
  expect(screen.getByText(/District school not identified/)).toBeInTheDocument()
})

test('no lookup yet', () => {
  render(<SchoolsPanel schools={null} />)
  expect(screen.getByText('No school data yet.')).toBeInTheDocument()
})

test('third-party links that are not http(s) never become hrefs', () => {
  const { container } = render(<SchoolsPanel schools={makeSchools([{
    school_count: 2, link: 'javascript:alert(1)',
    schools: [makeSchool({ url: 'javascript:alert(2)' })],
  }])} />)
  expect(container.querySelector('a[href^="javascript"]')).toBeNull()
  expect(screen.getByRole('heading', { name: 'Fuglsanggårdsskolen' })).toBeInTheDocument()
})
