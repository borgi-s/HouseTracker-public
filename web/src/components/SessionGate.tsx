import type { ReactNode } from 'react'
import { usePersons, useSession } from '@/api/queries'
import { WhoAreYou } from '@/routes/WhoAreYou'

export function SessionGate({ children }: { children: ReactNode }) {
  const session = useSession()
  usePersons() // pre-warm: fired in parallel with session so WhoAreYou has data on first render
  if (session.isPending) return null
  if (session.isError) {
    return <p className="p-6 text-destructive">Couldn't reach HouseTracker: {session.error.message}</p>
  }
  return session.data.person ? children : <WhoAreYou />
}
