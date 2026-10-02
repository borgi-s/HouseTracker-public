import { expect, test, vi } from 'vitest'
import { ApiError, api } from './client'

function stub(res: Response) {
  const f = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => res)
  vi.stubGlobal('fetch', f)
  return f
}

test('sends JSON and returns the parsed body', async () => {
  const f = stub(new Response(JSON.stringify({ id: 'alex', name: 'Alex' }), { status: 201 }))
  expect(await api.addPerson('Alex')).toEqual({ id: 'alex', name: 'Alex' })
  const [path, init] = f.mock.calls[0]
  expect(path).toBe('/api/persons')
  expect(init?.method).toBe('POST')
  expect(init?.headers).toEqual({ 'content-type': 'application/json' })
  expect(JSON.parse(String(init?.body))).toEqual({ name: 'Alex' })
})

test('maps an error body to ApiError(status, detail)', async () => {
  stub(new Response(JSON.stringify({ detail: "no house 'nope'" }), { status: 404 }))
  const e = await api.house('nope').catch((err: unknown) => err)
  expect(e).toBeInstanceOf(ApiError)
  expect((e as ApiError).status).toBe(404)
  expect((e as ApiError).message).toBe("no house 'nope'")
})

test('a pydantic 422 list detail still becomes readable text', async () => {
  stub(new Response(JSON.stringify({ detail: [{ loc: ['body', 'url'], msg: 'Field required' }] }), { status: 422 }))
  const e = (await api.scrape('').catch((err: unknown) => err)) as ApiError
  expect(e.status).toBe(422)
  expect(e.message).toContain('Field required')
})

test('an object detail reads as its message and stays on the error', async () => {
  const detail = { message: 'Avej 1 is already tracked', house: { id: 'a', address: 'Avej 1', status: 'rejected' } }
  stub(new Response(JSON.stringify({ detail }), { status: 409 }))
  const e = (await api.createHouse({ address: 'Avej 1' }).catch((err: unknown) => err)) as ApiError
  expect(e.message).toBe('Avej 1 is already tracked')
  expect(e.detail).toEqual(detail)
})

test('a non-JSON error falls back to the status code', async () => {
  stub(new Response('boom', { status: 500 }))
  const e = (await api.houses().catch((err: unknown) => err)) as ApiError
  expect(e.message).toBe('HTTP 500')
})

test('uploads send FormData and no JSON content-type', async () => {
  const f = stub(new Response(JSON.stringify({ id: 'm1' }), { status: 201 }))
  await api.uploadPhoto('lindevej-14', new File(['x'], 'k.jpg', { type: 'image/jpeg' }))
  const [path, init] = f.mock.calls[0]
  expect(path).toBe('/api/houses/lindevej-14/media')
  expect(init?.body).toBeInstanceOf(FormData)
  expect(init?.headers).toBeUndefined()
})

test('ids are URL-encoded', async () => {
  const f = stub(new Response('{}', { status: 200 }))
  await api.house('a b/c')
  expect(f.mock.calls[0][0]).toBe('/api/houses/a%20b%2Fc')
})
