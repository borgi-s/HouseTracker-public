import type { Query } from '@tanstack/react-query'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { slotOf } from '@/lib/person'
import { api } from './client'
import type { HouseDetail } from './types'

export const keys = {
  session: ['session'] as const,
  persons: ['persons'] as const,
  houses: ['houses'] as const,
  house: (id: string) => ['house', id] as const,
  criteria: (all: boolean) => ['criteria', all ? 'all' : 'active'] as const,
  anchors: ['anchors'] as const,
  settings: ['settings'] as const,
}

export const useSession = () => useQuery({ queryKey: keys.session, queryFn: api.session })
export const usePersons = () => useQuery({ queryKey: keys.persons, queryFn: api.persons })
export const useHouses = () => useQuery({ queryKey: keys.houses, queryFn: api.houses })
export const useAnchors = () => useQuery({ queryKey: keys.anchors, queryFn: api.anchors })
export const useSettings = () => useQuery({ queryKey: keys.settings, queryFn: api.settings })
/** all=false: active criteria only (what scoring shows); all=true: Settings. */
export const useCriteria = (all = false) =>
  useQuery({ queryKey: keys.criteria(all), queryFn: () => api.criteria(!all) })

export function useHouse(id: string, refetchInterval?: (d: HouseDetail | undefined) => number | false) {
  return useQuery({
    queryKey: keys.house(id),
    queryFn: () => api.house(id),
    refetchInterval: refetchInterval
      ? (q: Query<HouseDetail, Error, HouseDetail>) => refetchInterval(q.state.data)
      : undefined,
  })
}

/** Me, the A/B pair, and the other member of the pair (spec §4). */
export function usePeople() {
  const me = useSession().data?.person ?? null
  const pair = (usePersons().data ?? []).slice(0, 2)
  const other = pair.find(p => p.id !== me?.id) ?? null
  return { me, pair, other, slotOf: (id: string | null | undefined) => slotOf(pair, id) }
}

/** Re-read one house and the grid after a write that changes either. */
export function useRefreshHouse() {
  const qc = useQueryClient()
  return (id: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: keys.house(id) }),
      qc.invalidateQueries({ queryKey: keys.houses }),
    ])
}
