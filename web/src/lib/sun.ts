const RAD = Math.PI / 180

export interface SunPosition { azimuth: number; altitude: number }

/** The sun seen from lat/lon: azimuth in degrees clockwise from north, altitude in degrees
 *  above the horizon. The Astronomical Almanac's low-precision formulas (well under 1°). */
export function sunPosition(date: Date, lat: number, lon: number): SunPosition {
  const d = (date.getTime() - Date.UTC(2000, 0, 1, 12)) / 86400000
  const g = (357.529 + 0.98560028 * d) * RAD
  const ecliptic = (280.459 + 0.98564736 * d + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * RAD
  const tilt = (23.439 - 0.00000036 * d) * RAD
  const ra = Math.atan2(Math.cos(tilt) * Math.sin(ecliptic), Math.cos(ecliptic))
  const dec = Math.asin(Math.sin(tilt) * Math.sin(ecliptic))
  const hour = (280.46061837 + 360.98564736629 * d + lon) * RAD - ra
  const phi = lat * RAD
  const altitude = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(hour)) / RAD
  const fromSouth = Math.atan2(Math.sin(hour), Math.cos(hour) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi)) / RAD
  return { azimuth: (fromSouth + 540) % 360, altitude }
}

/** Danish clock time on the 21st of `month` (0-11). The 21st is always inside summer time
 *  (UTC+2) April to October and outside it (UTC+1) November to March. */
export function danishTime(year: number, month: number, minutes: number): Date {
  const offset = month >= 3 && month <= 9 ? 120 : 60
  return new Date(Date.UTC(year, month, 21) + (minutes - offset) * 60000)
}

/** The sun is up once its upper edge clears the horizon, refraction included: the
 *  definition behind published sunrise and sunset times. */
export const UP = -0.833

/** The sun's track while up on the 21st of `month`, every 5 minutes of Danish clock time;
 *  rise/set are the first and last of those minutes. */
export function sunDay(year: number, month: number, lat: number, lon: number) {
  const points: (SunPosition & { minutes: number })[] = []
  for (let m = 0; m <= 1440; m += 5) {
    const p = sunPosition(danishTime(year, month, m), lat, lon)
    if (p.altitude > UP) points.push({ minutes: m, ...p })
  }
  return { points, rise: points[0]?.minutes ?? null, set: points.at(-1)?.minutes ?? null }
}

export const compass = (azimuth: number) => ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(azimuth / 45) % 8]

/** "05:40" */
export const clock = (minutes: number) =>
  `${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`

/** The point `metres` from lat/lon towards `azimuth` (flat-earth; fine for a few hundred m). */
export function towards(lat: number, lon: number, azimuth: number, metres: number): [number, number] {
  return [lat + (metres * Math.cos(azimuth * RAD)) / 111320,
    lon + (metres * Math.sin(azimuth * RAD)) / (111320 * Math.cos(lat * RAD))]
}
