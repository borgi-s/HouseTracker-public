export type Status = 'not_visited' | 'visited' | 'shortlist' | 'rejected' | 'offer' | 'sold'
export const STATUSES: Status[] = ['not_visited', 'visited', 'shortlist', 'rejected', 'offer', 'sold']
export const STATUS_LABELS: Record<Status, string> = {
  not_visited: 'Not visited',
  visited: 'Visited',
  shortlist: 'Shortlist',
  rejected: 'Rejected',
  offer: 'Offer',
  sold: 'Sold',
}

export interface Person { id: string; name: string }

export interface House {
  id: string
  address: string
  postal_code: string | null
  city: string | null
  kommune: string | null
  lat: number | null
  lon: number | null
  maegler_chain: string | null
  listing_url: string | null
  price_dkk: number | null
  ejerudgift_dkk: number | null
  size_m2: number | null
  lot_m2: number | null
  rooms: number | null
  build_year: number | null
  energy_label: string | null
  description: string | null
  /** living floors above ground: BBR's count raised to what the listing text shows */
  floors: number | null
  bathrooms: number | null
  basement_m2: number | null
  status: Status
  sold_price_dkk: number | null
  sold_date: string | null
  sold_detected_at: string | null
  scrape_completeness: number | null
  source_adapter: string | null
  created_at: string | null
  updated_at: string | null
  price_per_m2: number | null
}

/** person id -> overall on 0..1 (null = nothing to score on yet) */
export type Overall = Record<string, number | null>
/** criterion id -> |A - B| for criteria both of the pair scored */
export type Disagreement = Record<string, number>

/** One open house ("åbent hus"). Times are UTC ISO text, shown in Danish time. */
export interface OpenHouse {
  starts_at: string
  ends_at: string
  /** true = sign-up needed, false = drop-in, null = the source does not say */
  signup: boolean | null
  signup_url: string | null
  /** vanished from the listing before it ended */
  cancelled: boolean
}

export interface HouseListItem extends House {
  cover_url: string | null
  overall: Overall
  disagreement: Disagreement
  /** What the ↓% bubble compares with: the first asking price, else the first price we saw. */
  original_price_dkk: number | null
  /** Upcoming open houses only, soonest first. */
  open_houses: OpenHouse[]
}

export type MediaKind = 'photo' | 'floorplan' | 'pdf' | 'user_photo'

export interface Media {
  id: string
  house_id: string
  kind: MediaKind
  path: string
  source: 'scrape' | 'manual'
  caption: string | null
  sort: number
  added_at: string | null
  url: string
}

export interface Commute {
  house_id: string
  anchor_ref: string
  mode: string
  minutes: number | null
  distance_m: number | null
  computed_at: string | null
}

export interface Anchor {
  id: string
  label: string
  address: string | null
  lat: number | null
  lon: number | null
  kind: string
}

export interface Note { id: number; house_id: string; person_id: string | null; body: string; created_at: string }
export interface Tag { id: number; house_id: string; person_id: string | null; label: string }

export type PriceSource = 'added' | 'boligsiden' | 'agency'
export interface PriceEvent { price_dkk: number; at: string; source: PriceSource }
export interface ListingFacts {
  listed_price_dkk: number | null
  listed_date: string | null
  days_on_market: number | null
  total_days_on_market: number | null
  realtor: string | null
  checked_at: string | null
}
export interface Sale { date: string; price_dkk: number; type: string | null }
export interface PriceHistory {
  /** oldest first */
  events: PriceEvent[]
  listing: ListingFacts | null
  /** tinglyst sales, newest first */
  sales: Sale[]
  original_price_dkk: number | null
}

export interface SchoolFigure {
  key: string
  label: string
  /** which way is better; null = neutral (no best-cell highlight) */
  better: 'high' | 'low' | null
  unit: string
  value: number | null
  /** school year the value is from, e.g. '2024/2025' */
  year: string | null
  kommune_avg: number | null
  national_avg: number | null
  national_rank: number | null
  total_schools: number | null
  note: string | null
}
export interface School {
  inst_nr: string
  name: string
  address: string | null
  url: string
  grades: string | null
  /** 1 = nearest by walking */
  rank: number
  walk_min: number | null
  walk_m: number | null
  bike_min: number | null
  bike_m: number | null
  straight_m: number | null
  figures: SchoolFigure[]
}
export interface SchoolDistrict {
  name: string
  grades: string
  link: string | null
  /** no school found inside the district: the nearest in the kommune are shown */
  fallback: boolean
  /** folkeskoler inside the district */
  school_count: number
  schools: School[]
}
export interface Schools { checked_at: string; districts: SchoolDistrict[] }
export interface HouseDetail {
  house: House
  media: Media[]
  commutes: Commute[]
  status_history: { status: Status; at: string }[]
  notes: Note[]
  tags: Tag[]
  school_map_url: string | null
  /** person id -> criterion id -> 1..5 */
  scores: Record<string, Record<string, number>>
  overall: Overall
  disagreement: Disagreement
  price_history: PriceHistory
  /** null until the district lookup has run */
  schools: Schools | null
  /** every open house seen, soonest first (past and cancelled ones too) */
  open_houses: OpenHouse[]
}

export interface Criterion {
  id: string
  key: string
  label: string
  kind: 'subjective' | 'auto'
  weight: number
  auto_source: string | null
  higher_is_better: boolean
  active: boolean
  sort: number
  created_at: string | null
}

export type CriterionIn = Pick<Criterion, 'key' | 'label' | 'kind'> &
  Partial<Pick<Criterion, 'weight' | 'auto_source' | 'higher_is_better' | 'active' | 'sort'>>
export type CriterionPatch = Partial<Pick<Criterion, 'label' | 'weight' | 'sort' | 'active'>>

/** The fields PATCH /api/houses/{id} accepts (store.EDITABLE_HOUSE_FIELDS). */
export const EDITABLE_FIELDS = [
  'address', 'postal_code', 'city', 'maegler_chain', 'listing_url', 'price_dkk',
  'ejerudgift_dkk', 'size_m2', 'lot_m2', 'rooms', 'build_year', 'energy_label',
  'description', 'floors', 'bathrooms', 'basement_m2',
] as const
export type EditableField = (typeof EDITABLE_FIELDS)[number]
export type HouseFields = Partial<Pick<House, EditableField>>

export interface ScrapeResult extends House { media_pending: number }
