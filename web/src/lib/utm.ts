// EPSG:25832 (ETRS89 / UTM zone 32N): the grid Danish agencies cut their map tiles in.
const A = 6378137
const F = 1 / 298.257222101
const K0 = 0.9996
const LON0 = (9 * Math.PI) / 180
const N = F / (2 - F)
const A1 = (A / (1 + N)) * (1 + N ** 2 / 4 + N ** 4 / 64)
const ALPHA = [N / 2 - (2 * N ** 2) / 3 + (5 * N ** 3) / 16, (13 * N ** 2) / 48 - (3 * N ** 3) / 5, (61 * N ** 3) / 240]
const E = Math.sqrt(F * (2 - F))

/** WGS84 lat/lon -> [easting, northing] in metres (Krüger series; mm-accurate in the zone). */
export function toUtm32(lat: number, lon: number): [number, number] {
  const phi = (lat * Math.PI) / 180
  const lam = (lon * Math.PI) / 180 - LON0
  const t = Math.sinh(Math.atanh(Math.sin(phi)) - E * Math.atanh(E * Math.sin(phi)))
  const xi = Math.atan2(t, Math.cos(lam))
  const eta = Math.atanh(Math.sin(lam) / Math.sqrt(1 + t * t))
  let x = eta
  let y = xi
  ALPHA.forEach((a, j) => {
    const k = 2 * (j + 1)
    x += a * Math.cos(k * xi) * Math.sinh(k * eta)
    y += a * Math.sin(k * xi) * Math.cosh(k * eta)
  })
  return [500000 + K0 * A1 * x, K0 * A1 * y]
}

/** MiljøGIS's tile grid: 256 px tiles from (120000, 6500000), 1638.4 m/px at L00, halving
 *  per level (from its WMTS capabilities). */
const GRID = { e0: 120000, n0: 6500000, res0: 1638.4, size: 256 }

export interface UtmTile { level: number; row: number; col: number; e: number; n: number; span: number }

/** The grid tiles under a quad of [E, N] corners, at the level nearest `res` m/px but no
 *  deeper than `maxLevel` (deeper map zooms draw that level's tiles larger). */
export function tilesFor(corners: [number, number][], res: number, maxLevel: number): UtmTile[] {
  const level = Math.max(0, Math.min(maxLevel, Math.round(Math.log2(GRID.res0 / res))))
  const span = (GRID.size * GRID.res0) / 2 ** level
  const es = corners.map(c => c[0])
  const ns = corners.map(c => c[1])
  const tiles: UtmTile[] = []
  for (let row = Math.floor((GRID.n0 - Math.max(...ns)) / span); row <= Math.floor((GRID.n0 - Math.min(...ns)) / span); row++) {
    for (let col = Math.floor((Math.min(...es) - GRID.e0) / span); col <= Math.floor((Math.max(...es) - GRID.e0) / span); col++) {
      tiles.push({ level, row, col, e: GRID.e0 + col * span, n: GRID.n0 - row * span, span })
    }
  }
  return tiles
}
