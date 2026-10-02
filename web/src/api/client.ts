import type {
  Anchor, Criterion, CriterionIn, CriterionPatch, House, HouseDetail, HouseFields,
  HouseListItem, Media, Note, Person, ScrapeResult, Status, Tag,
} from './types'

/** Any non-2xx response. `message` is FastAPI's `detail` made readable; `detail` is the
 *  raw value (a 409 for a house we already track names that house). */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body instanceof FormData) {
    init.body = body                    // the browser sets the multipart boundary
  } else if (body !== undefined) {
    init.headers = { 'content-type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await fetch(path, init)
  if (!res.ok) {
    const detail: unknown = await res.json().then(b => b?.detail, () => undefined)   // not JSON -> undefined
    throw new ApiError(res.status, readable(detail) ?? `HTTP ${res.status}`, detail)
  }
  return (await res.json()) as T
}

function readable(detail: unknown): string | undefined {
  if (detail === undefined || typeof detail === 'string') return detail
  const message = (detail as { message?: unknown } | null)?.message
  return typeof message === 'string' ? message : JSON.stringify(detail)   // e.g. a pydantic 422 list
}

const enc = encodeURIComponent

export const api = {
  persons: () => request<Person[]>('GET', '/api/persons'),
  addPerson: (name: string) => request<Person>('POST', '/api/persons', { name }),
  session: () => request<{ person: Person | null }>('GET', '/api/session'),
  pickPerson: (personId: string) =>
    request<{ person: Person }>('POST', '/api/session', { person_id: personId }),
  clearSession: () => request<{ person: null }>('DELETE', '/api/session'),

  houses: () => request<HouseListItem[]>('GET', '/api/houses'),
  house: (id: string) => request<HouseDetail>('GET', `/api/houses/${enc(id)}`),
  createHouse: (fields: HouseFields) => request<House>('POST', '/api/houses', fields),
  updateHouse: (id: string, fields: HouseFields) =>
    request<House>('PATCH', `/api/houses/${enc(id)}`, fields),
  deleteHouse: (id: string) => request<{ deleted: string }>('DELETE', `/api/houses/${enc(id)}`),
  scrape: (url: string, useBrowser = false) =>
    request<ScrapeResult>('POST', '/api/houses/scrape', { url, use_browser: useBrowser }),
  rescrape: (id: string) => request<ScrapeResult>('POST', `/api/houses/${enc(id)}/rescrape`),
  enrich: (id: string) => request<unknown>('POST', `/api/houses/${enc(id)}/enrich`),
  setStatus: (id: string, status: Status) =>
    request<House>('PATCH', `/api/houses/${enc(id)}/status`, { status }),

  addNote: (id: string, body: string, shared: boolean) =>
    request<Note>('POST', `/api/houses/${enc(id)}/notes`, { body, shared }),
  deleteNote: (noteId: number) => request<{ deleted: number }>('DELETE', `/api/notes/${noteId}`),
  addTag: (id: string, label: string, shared: boolean) =>
    request<Tag>('POST', `/api/houses/${enc(id)}/tags`, { label, shared }),
  deleteTag: (tagId: number) => request<{ deleted: number }>('DELETE', `/api/tags/${tagId}`),

  criteria: (activeOnly = true) =>
    request<Criterion[]>('GET', `/api/criteria?active_only=${activeOnly}`),
  addCriterion: (c: CriterionIn) => request<Criterion>('POST', '/api/criteria', c),
  updateCriterion: (id: string, patch: CriterionPatch) =>
    request<Criterion>('PATCH', `/api/criteria/${enc(id)}`, patch),
  setScore: (houseId: string, criterionId: string, value: number) =>
    request<unknown>('PUT', `/api/houses/${enc(houseId)}/scores/${enc(criterionId)}`, { value }),
  clearScore: (houseId: string, criterionId: string) =>
    request<unknown>('DELETE', `/api/houses/${enc(houseId)}/scores/${enc(criterionId)}`),

  uploadPhoto: (houseId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Media>('POST', `/api/houses/${enc(houseId)}/media`, form)
  },
  deleteMedia: (mediaId: string) =>
    request<{ deleted: string }>('DELETE', `/api/media/${enc(mediaId)}`),
  anchors: () => request<Anchor[]>('GET', '/api/anchors'),
}
