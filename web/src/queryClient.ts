import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { keys } from '@/api/queries'

/** 401 anywhere means "no person picked" (cookie gone, or it names someone deleted):
 *  reset the session so SessionGate shows the picker, and the user lands back where
 *  they were once they pick. Every other failed write toasts its detail (spec §7);
 *  components add onError only for rollback or inline UI. */
export function makeQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // API errors are deterministic; only network blips are worth retrying.
        retry: (count, error) => !(error instanceof ApiError) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
    queryCache: new QueryCache({ onError: e => { signedOut(e) } }),
    mutationCache: new MutationCache({
      onError: e => { if (!signedOut(e)) toast.error(e.message) },
    }),
  })
  function signedOut(e: Error): boolean {
    if (e instanceof ApiError && e.status === 401) {
      client.setQueryData(keys.session, { person: null })
      return true
    }
    return false
  }
  return client
}
