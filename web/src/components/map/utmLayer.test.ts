import L from 'leaflet'
import { expect, test, vi } from 'vitest'
import { mimTiles, utmLayer } from './utmLayer'

test('a tile finishing after its layer left the map is dropped, not reported to Leaflet', async () => {
  const map = L.map(document.createElement('div')).setView([55.78, 12.52], 14)
  const layer = utmLayer(mimTiles('x'), { maxLevel: 15, opacity: 0.5 }).addTo(map)
  const done = vi.fn()
  const create = (layer as unknown as { createTile: (c: L.Coords, d: L.DoneCallback) => HTMLElement }).createTile
  create.call(layer, Object.assign(L.point(8000, 5000), { z: 14 }) as L.Coords, done)
  map.removeLayer(layer)
  await Promise.resolve()
  expect(done).not.toHaveBeenCalled()
  map.remove()
})
