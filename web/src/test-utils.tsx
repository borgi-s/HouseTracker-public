import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router'
import { vi } from 'vitest'
import type {
  Anchor, Criterion, House, HouseDetail, HouseListItem, Media, Person, School, SchoolDistrict,
  SchoolFigure, Schools,
} from '@/api/types'
import { makeQueryClient } from '@/queryClient'

type Handler = (body: unknown) => unknown
export type Call = { method: string; path: string; body: unknown }

export const fail = (status: number, detail: string) =>
  new Response(JSON.stringify({ detail }), { status, headers: { 'content-type': 'application/json' } })

/** A promise that never settles — for asserting optimistic UI mid-flight. */
export const never = () => new Promise<never>(() => {})

/** Stub fetch with a "METHOD /path?query" -> handler table. A handler returns a plain
 *  value (sent as 200 JSON), a Response (sent as-is), or a promise of either. An
 *  unmatched request answers 404 "unmocked …" so a missing handler fails loudly. */
export function mockApi(handlers: Record<string, Handler>): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const path = String(input)
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    calls.push({ method, path, body })
    const handler = handlers[`${method} ${path}`]
    if (!handler) return fail(404, `unmocked ${method} ${path}`)
    const out = await handler(body)
    return out instanceof Response
      ? out
      : new Response(JSON.stringify(out ?? null), { status: 200, headers: { 'content-type': 'application/json' } })
  }))
  return calls
}

export function renderApp(ui: ReactElement, { route = '/', state }: { route?: string; state?: unknown } = {}) {
  const [pathname, query] = route.split('?')
  const client = makeQueryClient()
  // A data router, like the app's, so useBlocker works.
  const router = createMemoryRouter([{ path: '*', element: ui }],
    { initialEntries: [{ pathname, search: query ? `?${query}` : '', state }] })
  const result = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, ...result }
}

/** Renders the current location so a test can assert where navigation went. */
export function LocationProbe() {
  const l = useLocation()
  return <pre data-testid="location">{`${l.pathname}${l.search} ${JSON.stringify(l.state ?? null)}`}</pre>
}

// ---- fixtures -------------------------------------------------------------------

export const ALEX: Person = { id: 'alex', name: 'Alex' }
export const SAM: Person = { id: 'sam', name: 'Sam' }
export const WORK: Anchor = {
  id: 'work', label: 'Work',
  address: 'Arbejdsvej 1, 2800 Kongens Lyngby', lat: 55.7861, lon: 12.5234, kind: 'fixed',
}

export function makeHouse(over: Partial<House> = {}): House {
  return {
    id: 'lindevej-14', address: 'Lindevej 14', postal_code: '2800', city: 'Kongens Lyngby',
    kommune: null, lat: null, lon: null, maegler_chain: null, listing_url: null,
    price_dkk: 5495000, ejerudgift_dkk: 3850, size_m2: 142, lot_m2: null, rooms: 5,
    build_year: 1972, energy_label: 'C', description: null,
    floors: null, bathrooms: null, basement_m2: null, status: 'visited',
    sold_price_dkk: null, sold_date: null, sold_detected_at: null,
    scrape_completeness: null, source_adapter: null,
    created_at: '2026-09-21', updated_at: '2026-09-21', price_per_m2: 5495000 / 142,
    ...over,
  }
}

export function makeListItem(over: Partial<HouseListItem> = {}): HouseListItem {
  return { ...makeHouse(over), cover_url: null, overall: {}, disagreement: {}, original_price_dkk: null, open_houses: [], ...over }
}

export function makeDetail(over: Partial<HouseDetail> = {}): HouseDetail {
  return {
    house: makeHouse(), media: [], commutes: [],
    status_history: [{ status: 'visited', at: '2026-09-21' }],
    notes: [], tags: [], school_map_url: null, scores: {}, overall: {}, disagreement: {},
    price_history: { events: [], listing: null, sales: [], original_price_dkk: null },
    schools: null,
    open_houses: [],
    ...over,
  }
}

export function makeFigure(over: Partial<SchoolFigure> = {}): SchoolFigure {
  return {
    key: 'grade', label: 'Grade average', better: 'high', unit: '', value: 8.8, year: '2024/2025',
    kommune_avg: 8.36, national_avg: null, national_rank: 71, total_schools: 2870, note: null, ...over,
  }
}

export function makeSchool(over: Partial<School> = {}): School {
  return {
    inst_nr: '173003', name: 'Fuglsanggårdsskolen', address: 'Askevænget 10, 2830 Virum',
    url: 'https://skolegang.dk/skole/fuglsanggaardsskolen', grades: '0.–9.', rank: 1,
    walk_min: 11.4, walk_m: 900, bike_min: 4.2, bike_m: 1000, straight_m: 700,
    figures: [makeFigure()], ...over,
  }
}

export function makeSchools(districts: Partial<SchoolDistrict>[] = [{}]): Schools {
  return {
    checked_at: '2026-09-26',
    districts: districts.map(d => ({
      name: 'Fuglsanggårdsskolen', grades: '0.–9.', link: null, fallback: false, school_count: 1,
      schools: [makeSchool()], ...d,
    })),
  }
}

export function makeCriterion(over: Partial<Criterion> = {}): Criterion {
  return {
    id: 'light', key: 'light', label: 'Light', kind: 'subjective', weight: 1,
    auto_source: null, higher_is_better: true, active: true, sort: 0,
    created_at: '2026-09-21', ...over,
  }
}

export function makeMedia(over: Partial<Media> & Pick<Media, 'id' | 'kind'>): Media {
  return {
    house_id: 'lindevej-14', path: `/data/${over.id}`, source: 'scrape', caption: null,
    sort: 0, added_at: '2026-09-21', url: `/api/media/${over.id}/file`, ...over,
  }
}

/** What every signed-in screen asks for: Alex signed in, Alex + Sam as the pair. */
export function signedIn(extra: Record<string, Handler> = {}): Record<string, Handler> {
  return {
    'GET /api/session': () => ({ person: ALEX }),
    'GET /api/persons': () => [ALEX, SAM],
    'GET /api/criteria?active_only=true': () => [],
    'GET /api/anchors': () => [WORK],
    'GET /api/settings': () => ({ notify_price_drops: true, notify_open_houses: true, discord_configured: true }),
    ...extra,
  }
}
