import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { expect, test, vi } from 'vitest'
import { keys } from '@/api/queries'
import type { HouseDetail } from '@/api/types'
import { districtsUrl } from '@/lib/districts'
import { HousePage } from '@/routes/HousePage'
import {
  fail, makeDetail, makeHouse, makeMedia, makeSchools, mockApi, never, renderApp, signedIn,
} from '@/test-utils'

const MEDIA = [
  makeMedia({ id: 'fp', kind: 'floorplan' }),
  makeMedia({ id: 'pdf', kind: 'pdf' }),
  makeMedia({ id: 'p1', kind: 'photo' }),
  makeMedia({ id: 'u1', kind: 'user_photo', source: 'manual' }),
]
const LISTING = makeDetail({
  media: MEDIA,
  house: makeHouse({ description: 'Lyst rækkehus tæt på skov og S-tog.', rooms: 4, energy_label: 'B' }),
})

function laptop() {
  vi.spyOn(window, 'matchMedia').mockImplementation(query => ({
    matches: true, media: query, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
    dispatchEvent: () => false,
  }) as MediaQueryList)
}

function renderPage(detail: HouseDetail | Response = LISTING, extra = {}, state?: unknown) {
  const calls = mockApi(signedIn({ 'GET /api/houses/lindevej-14': () => detail, ...extra }))
  const { client } = renderApp(<Routes><Route path="/house/:id" element={<HousePage />} /></Routes>,
    { route: '/house/lindevej-14', state })
  return Object.assign(calls, { refetch: () => client.invalidateQueries({ queryKey: keys.house('lindevej-14') }) })
}

const before = (a: Element, b: Element) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

test.each([['laptop', laptop], ['phone', () => {}]])(
  '%s: reads like the listing (photos, address, headline), then where we stand',
  async (_name, layout) => {
    layout()
    renderPage()
    const address = await screen.findByRole('heading', { level: 1, name: 'Lindevej 14' })
    const photo = screen.getByRole('button', { name: 'Open photo 1' })
    const lead = screen.getByText('Lyst rækkehus tæt på skov og S-tog')
    const stand = screen.getByRole('heading', { name: 'Where we stand' })
    expect(before(photo, address) && before(address, lead) && before(lead, stand)).toBe(true)
    expect(screen.getAllByText('Lyst rækkehus tæt på skov og S-tog')).toHaveLength(1)
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
  })

test('the facts strip carries the key numbers', async () => {
  renderPage()
  const summary = within(await screen.findByRole('region', { name: 'Summary' }))   // Details has a Rooms row too
  expect(summary.getByText('Rooms').nextElementSibling).toHaveTextContent('4')
  expect(summary.getByText('Energimærke').nextElementSibling).toHaveTextContent('B')
})

test('Rate this house jumps down to Where we stand', async () => {
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  renderPage()
  await userEvent.click(await screen.findByRole('button', { name: 'Rate this house' }))
  expect(scroll.mock.contexts[0]).toBe(document.getElementById('our-take'))
})

test('the full GeoFA school map is linked from Details', async () => {
  renderPage(makeDetail({ house: makeHouse({ lat: 55.79, lon: 12.47 }), school_map_url: 'https://kort.example/#12.47/55.79' }),
    { [`GET ${districtsUrl(55.79, 12.47)}`]: () => ({ type: 'FeatureCollection', features: [] }) })
  expect(await screen.findByRole('link', { name: /School district map \(GeoFA\)/ }))
    .toHaveAttribute('href', 'https://kort.example/#12.47/55.79')
})

test('a long description starts as a preview; the text or Read more expands it', async () => {
  const text = 'Velkommen til Lindevej 14. '.repeat(30)
  renderPage(makeDetail({ house: makeHouse({ description: text }) }))
  const rest = 'Velkommen til Lindevej 14. '.repeat(29).trim()
  const more = await screen.findByRole('button', { name: 'Read more' })
  expect(more).toHaveAttribute('aria-expanded', 'false')
  await userEvent.click(screen.getByText(rest))
  expect(screen.getByRole('button', { name: 'Show less' })).toHaveAttribute('aria-expanded', 'true')
  await userEvent.click(screen.getByRole('button', { name: 'Show less' }))
  expect(screen.getByRole('button', { name: 'Read more' })).toBeInTheDocument()
})

test('a one-line description is the headline alone, with no Read more', async () => {
  renderPage()
  expect(await screen.findByText('Lyst rækkehus tæt på skov og S-tog')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Read more' })).not.toBeInTheDocument()
})

test('laptop: a photo mosaic whose "all photos" button opens the full-screen viewer', async () => {
  laptop()
  renderPage()
  await userEvent.click(await screen.findByRole('button', { name: 'All 2 photos' }))
  expect(within(await screen.findByRole('dialog')).getByText('1 / 2')).toBeInTheDocument()
})

test('laptop: the salgsopstilling inline', async () => {
  laptop()
  renderPage()
  expect(await screen.findByTitle('Salgsopstilling')).toHaveAttribute('src', '/api/media/pdf/file')
})

test('phone: the PDF as a link', async () => {
  renderPage()
  expect(await screen.findByRole('link', { name: 'Open salgsopstilling (PDF)' })).toHaveAttribute('href', '/api/media/pdf/file')
})

test('where we stand shows both overalls and together; the status still changes', async () => {
  const calls = renderPage(makeDetail({ overall: { alex: 0.8, sam: 0.6 } }),
    { 'PATCH /api/houses/lindevej-14/status': () => ({}) })
  expect(await screen.findByRole('img', { name: 'Alex 4.0' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Sam 3.0' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Together 3.5' })).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Status'), 'shortlist')
  await waitFor(() => expect(calls).toContainEqual(
    { method: 'PATCH', path: '/api/houses/lindevej-14/status', body: { status: 'shortlist' } }))
})

test('the status picker shows the new status while it saves', async () => {
  renderPage(makeDetail(), { 'PATCH /api/houses/lindevej-14/status': never })
  await userEvent.selectOptions(await screen.findByLabelText('Status'), 'shortlist')
  expect(screen.getByLabelText('Status')).toHaveValue('shortlist')
})

test('status selector includes Not visited as the first option', async () => {
  renderPage()
  const select = await screen.findByLabelText('Status')
  const options = Array.from((select as HTMLSelectElement).options).map(o => o.text)
  expect(options[0]).toBe('Not visited')
  expect(options).toContain('Visited')
})

test('Rate button is outline when status is not_visited', async () => {
  renderPage(makeDetail({ house: makeHouse({ status: 'not_visited', description: 'Lyst.' }) }))
  expect(await screen.findByRole('button', { name: 'Rate this house' })).toHaveAttribute('data-variant', 'outline')
})

test('Rate button is default (filled) when status is visited', async () => {
  renderPage(makeDetail({ house: makeHouse({ status: 'visited', description: 'Lyst.' }) }))
  expect(await screen.findByRole('button', { name: 'Rate this house' })).toHaveAttribute('data-variant', 'default')
})

test('our own photo can be deleted from the viewer; a scraped one cannot', async () => {
  laptop()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = renderPage(makeDetail({ media: MEDIA }), { 'DELETE /api/media/u1': () => ({ deleted: 'u1' }) })
  await userEvent.click(await screen.findByRole('button', { name: 'Open photo 1' }))
  expect(screen.queryByRole('button', { name: 'Delete photo' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Next' }))
  await userEvent.click(screen.getByRole('button', { name: 'Delete photo' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/media/u1', body: undefined }))
})

test('right after a scrape it says media are still downloading', async () => {
  renderPage(makeDetail(), {}, { mediaPending: 5 })
  expect(await screen.findByText('Downloading photos and documents…')).toBeInTheDocument()
})

test('the downloading note goes once the wait is over, even if some media never arrive', async () => {
  const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
  const { refetch } = renderPage(makeDetail(), {}, { mediaPending: 5 })
  expect(await screen.findByText('Downloading photos and documents…')).toBeInTheDocument()
  now.mockReturnValue(1_000_000 + 91_000)
  await refetch()                                  // same detail back: nothing new arrived
  await waitFor(() => expect(screen.queryByText('Downloading photos and documents…')).not.toBeInTheDocument())
})

test('an unknown house says so', async () => {
  renderPage(fail(404, "no house 'lindevej-14'"))
  expect(await screen.findByText('No such house.')).toBeInTheDocument()
})

test('phone shows the capture bar', async () => {
  renderPage()
  expect(await screen.findByLabelText('Add photos')).toBeInTheDocument()
})

test('laptop has no capture bar', async () => {
  laptop()
  renderPage()
  await screen.findByRole('heading', { name: 'Where we stand' })
  expect(screen.queryByLabelText('Add photos')).not.toBeInTheDocument()
})

test('laptop: shows listing link even without a description', async () => {
  laptop()
  renderPage(makeDetail({ house: makeHouse({ listing_url: 'https://boligsiden.dk/listing' }) }))
  const link = await screen.findByRole('link', { name: /Listing on boligsiden\.dk/ })
  // The phone-only fallback wraps the link in lg:hidden; on laptop the wrapper must not hide it
  expect(link.closest('div')?.className).not.toContain('lg:hidden')
})

test('the headline price carries the ↓% bubble', async () => {
  renderPage(makeDetail({
    house: makeHouse({ price_dkk: 9_500_000 }),
    price_history: { events: [], listing: null, sales: [], original_price_dkk: 10_000_000 },
  }))
  const summary = await screen.findByRole('region', { name: 'Summary' })
  expect(within(summary).getByText('↓5%')).toBeInTheDocument()
})

test('the page has a Price history section', async () => {
  renderPage(makeDetail())
  expect(await screen.findByRole('heading', { name: 'Price history' })).toBeInTheDocument()
  expect(screen.getByText('Added to our list')).toBeInTheDocument()
})

test('the house can be deleted after a confirm', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const calls = renderPage(LISTING, { 'DELETE /api/houses/lindevej-14': () => ({ deleted: 'lindevej-14' }) })
  await userEvent.click(await screen.findByRole('button', { name: 'Delete house' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'DELETE', path: '/api/houses/lindevej-14', body: undefined }))
})

test('refresh re-reads the listing, re-locates the house and waits for the new photos', async () => {
  const linked = makeDetail({ house: makeHouse({ listing_url: 'https://www.estate.dk/x' }) })
  const calls = renderPage(linked, {
    'POST /api/houses/lindevej-14/rescrape': () => ({ ...linked.house, media_pending: 3 }),
    'POST /api/houses/lindevej-14/enrich': () => ({}),
  })
  await userEvent.click(await screen.findByRole('button', { name: 'Refresh from listing' }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'POST', path: '/api/houses/lindevej-14/rescrape', body: undefined }))
  await waitFor(() => expect(calls).toContainEqual({ method: 'POST', path: '/api/houses/lindevej-14/enrich', body: undefined }))
  expect(await screen.findByText('Downloading photos and documents…')).toBeInTheDocument()
})

test('the School section sits between Price history and Details', async () => {
  renderPage(makeDetail({ schools: makeSchools() }))
  await screen.findByRole('heading', { level: 1, name: 'Lindevej 14' })
  const h2 = screen.getAllByRole('heading', { level: 2 }).map(h => h.textContent ?? '')
  const at = (title: string) => h2.findIndex(t => t.startsWith(title))
  expect([at('Price history'), at('School'), at('Details')]).toEqual([at('Price history'), at('Price history') + 1, at('Price history') + 2])
  expect(screen.getByRole('link', { name: 'Fuglsanggårdsskolen' })).toBeInTheDocument()
})

const OH = (starts_at: string, ends_at: string, over = {}) =>
  ({ starts_at, ends_at, signup: null, signup_url: null, cancelled: false, ...over })

test('open house section: upcoming slots with sign-up links, previous ones folded away', async () => {
  renderPage(makeDetail({
    house: makeHouse({ listing_url: 'https://www.estate.dk/x' }),
    open_houses: [
      OH('2000-10-01T08:00:00Z', '2000-10-01T08:30:00Z'),
      OH('2099-10-04T13:30:00Z', '2099-10-04T13:50:00Z', { signup: true }),
      OH('2099-10-11T08:00:00Z', '2099-10-11T08:30:00Z', { signup: false }),
      OH('2099-10-18T08:00:00Z', '2099-10-18T08:30:00Z', { signup: true, signup_url: 'https://agent.dk/tilmeld', cancelled: true }),
    ],
  }))
  const section = (await screen.findByRole('heading', { name: 'Open house' })).closest('section')!
  expect(section).toHaveTextContent('Sun 4 Oct 15:30–15:50')
  expect(section).toHaveTextContent('Sun 11 Oct 10:00–10:30')
  expect(within(section).getByRole('link', { name: 'Sign up' })).toHaveAttribute('href', 'https://www.estate.dk/x')
  expect(within(section).getByText('Drop-in')).toBeInTheDocument()
  const history = within(section).getByText('Previous open houses (2)')
  expect(history.closest('details')).not.toHaveAttribute('open')          // folded; its rows stay in the DOM
  expect(section).toHaveTextContent('Sun, 1 Oct 2000 10:00–10:30 · held')
  expect(section).toHaveTextContent('Sun, 18 Oct 2099 10:00–10:30 · cancelled')
})

test('open house section: none coming, only history', async () => {
  renderPage(makeDetail({ open_houses: [OH('2000-10-01T08:00:00Z', '2000-10-01T08:30:00Z')] }))
  const section = (await screen.findByRole('heading', { name: 'Open house' })).closest('section')!
  expect(section).toHaveTextContent('No open house planned.')
})

test('no open house section when there has never been one', async () => {
  renderPage()
  await screen.findByRole('heading', { name: 'Price history' })
  expect(screen.queryByRole('heading', { name: 'Open house' })).not.toBeInTheDocument()
})
