import type { HouseDetail, School, SchoolFigure } from '@/api/types'
import { DASH, num } from '@/lib/format'

/** '2024/2025' -> '2024/25' */
export const shortYear = (year: string) => year.replace(/^(\d{4})\/\d\d(\d\d)$/, '$1/$2')

export const figureValue = (f: SchoolFigure, v: number | null = f.value) => num(v, f.unit)

/** A figure the way the house page and Compare show it: the value and its school year. */
export const figureText = (f: SchoolFigure) =>
  f.value == null || f.year == null ? 'not reported' : `${figureValue(f)} · ${shortYear(f.year)}`

/** The Denmark column: national average (wellbeing only) and national rank. */
export function denmarkText(f: SchoolFigure): string {
  const parts = [
    f.national_avg != null && `avg ${figureValue(f, f.national_avg)}`,
    f.national_rank != null && `#${num(f.national_rank)}${f.total_schools ? ` of ${num(f.total_schools)}` : ''}`,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : DASH
}

/** What Compare lines up per house: the nearest school of its first (0.-klasse) district. */
export const nearestSchool = (d: HouseDetail): School | null => d.schools?.districts[0]?.schools[0] ?? null

/** Links from third-party data (GeoFA, skolegang.dk) become hrefs only when http(s). */
export const safeHref = (url: string | null) => (url && /^https?:\/\//i.test(url) ? url : null)
