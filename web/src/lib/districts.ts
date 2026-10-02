const GEOFA_SQL = 'https://geofa.geodanmark.dk/api/v2/sql/fkg'

/** GeoFA's public SQL API (CORS open): the school districts around a house, as GeoJSON in
 *  WGS84. Only type 5 "Skole" districts that start at 0. klasse / førskole — the layer also
 *  holds 10.-klasse, daycare and SSP districts that blanket whole kommuner, which is what
 *  made GeoFA's own map pile labels on top of each other. `here` = the house's district;
 *  lx/ly = a point inside the district for its label. */
export function districtsUrl(lat: number, lon: number, radiusM = 3000): string {
  const pt = `ST_Transform(ST_SetSRID(ST_MakePoint(${Number(lon)}, ${Number(lat)}), 4326), 25832)`
  const onSurface = 'ST_Transform(ST_PointOnSurface(geometri), 4326)'
  const q = `SELECT udd_distrikt_navn AS name, ST_Contains(geometri, ${pt}) AS here,
    ST_X(${onSurface}) AS lx, ST_Y(${onSurface}) AS ly,
    ST_SimplifyPreserveTopology(geometri, 10) AS geometri
    FROM fkg.t_5710_born_skole_dis
    WHERE udd_distrikt_type_kode = 5 AND starttrin_kode IN (11, 12) AND ST_DWithin(geometri, ${pt}, ${radiusM})
    ORDER BY here`
  return `${GEOFA_SQL}?srs=4326&q=${encodeURIComponent(q)}`
}

export interface DistrictProps { name: string; here: boolean; lx: number; ly: number }
