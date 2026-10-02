import L from 'leaflet'
import { tilesFor, toUtm32 } from '@/lib/utm'

type TileUrl = (level: number, row: number, col: number) => string

/** Tiles cut in the Danish UTM grid (EPSG:25832) drawn onto our web-mercator map, the
 *  only grid MiljøGIS serves its noise and flood maps in. Each map tile is a canvas the
 *  UTM tiles under it are painted into with the affine transform taking UTM metres to the
 *  canvas: over one tile the two projections differ by a slight turn and stretch. */
class UtmGrid extends L.GridLayer {
  url: TileUrl
  maxLevel: number
  constructor(url: TileUrl, maxLevel: number, options: L.GridLayerOptions) {
    super(options)
    this.url = url
    this.maxLevel = maxLevel
  }

  protected createTile(coords: L.Coords, done: L.DoneCallback): HTMLElement {
    const size = this.getTileSize()
    const canvas = Object.assign(document.createElement('canvas'), { width: size.x, height: size.y })
    const ctx = canvas.getContext('2d')
    const nw = coords.scaleBy(size)
    const utm = (dx: number, dy: number) => {
      const ll = this._map.unproject(nw.add([dx, dy]), coords.z)
      return toUtm32(ll.lat, ll.lng)
    }
    const [o, right, down, far] = [utm(0, 0), utm(size.x, 0), utm(0, size.y), utm(size.x, size.y)]
    // UTM metres per canvas pixel along x (a) and y (b); inverted, UTM -> canvas.
    const a = [(right[0] - o[0]) / size.x, (right[1] - o[1]) / size.x]
    const b = [(down[0] - o[0]) / size.y, (down[1] - o[1]) / size.y]
    const det = a[0] * b[1] - b[0] * a[1]
    const m = [b[1] / det, -b[0] / det, -a[1] / det, a[0] / det]
    const tiles = tilesFor([o, right, down, far], Math.hypot(a[0], a[1]), this.maxLevel)
    let left = tiles.length
    // Leaflet's TileLayer drops a tile that finishes after the layer left the map; a
    // GridLayer does not, and its _tileReady would read the gone map and throw.
    const ready = () => { if (this._map) done(undefined, canvas) }
    if (!ctx || left === 0 || left > 16) {
      queueMicrotask(ready)
      return canvas
    }
    const finish = () => { if (--left === 0) ready() }
    for (const t of tiles) {
      const img = new Image()
      img.onload = () => {
        const r = t.span / img.width                              // metres per image pixel
        const dE = t.e - o[0]
        const dN = t.n - o[1]
        // image pixel (i, j) is UTM (t.e + i r, t.n - j r); apply m to that minus o
        ctx.setTransform(m[0] * r, m[2] * r, -m[1] * r, -m[3] * r, m[0] * dE + m[1] * dN, m[2] * dE + m[3] * dN)
        ctx.drawImage(img, 0, 0)
        finish()
      }
      img.onerror = finish
      img.src = this.url(t.level, t.row, t.col)
    }
    return canvas
  }
}

export const utmLayer = (url: TileUrl, { maxLevel, opacity, attribution = 'Miljøstyrelsen' }:
  { maxLevel: number; opacity: number; attribution?: string }): L.GridLayer =>
  new UtmGrid(url, maxLevel, { opacity, attribution, zIndex: 2, minZoom: 10 })

const MIM = 'https://tilecache2-miljoegis.mim.dk/gwc/service/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0'
  + '&STYLE=&TILEMATRIXSET=EPSG:25832&FORMAT=image/png'

/** One layer of MiljøGIS's public tile cache (Miljøministeriet). */
export const mimTiles = (layer: string): TileUrl => (level, row, col) =>
  `${MIM}&LAYER=${layer}&TILEMATRIX=L${String(level).padStart(2, '0')}&TILEROW=${row}&TILECOL=${col}`
