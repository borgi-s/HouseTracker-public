import { useMutation, useQueryClient } from '@tanstack/react-query'
import { House, Plus, Settings as SettingsIcon } from 'lucide-react'
import { useLayoutEffect } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigationType } from 'react-router'
import { api } from '@/api/client'
import { keys, usePeople } from '@/api/queries'
import { buttonVariants } from '@/components/ui/button'
import { PERSON } from '@/lib/person'
import { cn } from '@/lib/utils'
import { AddHouse } from '@/routes/AddHouse'
import { Compare } from '@/routes/Compare'
import { HousePage } from '@/routes/HousePage'
import { Houses } from '@/routes/Houses'
import { Settings } from '@/routes/Settings'

const TOP_NAV = [
  { to: '/', label: 'Houses' },
  { to: '/compare', label: 'Compare' },
  { to: '/settings', label: 'Settings' },
]
const PHONE_NAV = [
  { to: '/', label: 'Houses', Icon: House },
  { to: '/add', label: 'Add', Icon: Plus },
  { to: '/settings', label: 'Settings', Icon: SettingsIcon },
]

function PersonChip() {
  const { me, slotOf } = usePeople()
  const qc = useQueryClient()
  const signOut = useMutation({ mutationFn: api.clearSession, onSuccess: s => qc.setQueryData(keys.session, s) })
  if (!me) return null
  const slot = slotOf(me.id)
  return (
    <button type="button" title="Switch person" aria-label={me.name} onClick={() => signOut.mutate()}
      className="flex h-11 items-center gap-2 rounded-full border px-1.5 text-sm font-semibold sm:pr-3.5">
      <span aria-hidden className={cn('grid size-7 place-items-center rounded-full text-xs font-bold',
        slot ? PERSON[slot].solid : 'bg-muted')}>
        {me.name.slice(0, 1).toUpperCase()}
      </span>
      <span aria-hidden className="hidden sm:inline">{me.name}</span>
    </button>
  )
}

/** A link opens its page at the top; Back keeps where you were (the browser restores it). */
function useTopOnNewPage() {
  const { pathname } = useLocation()
  const how = useNavigationType()
  useLayoutEffect(() => { if (how !== 'POP') window.scrollTo(0, 0) }, [pathname, how])
}

export function Shell() {
  useTopOnNewPage()
  return (
    <div className="min-h-dvh pb-24 lg:pb-0">
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center justify-between gap-4 px-4 lg:px-10">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
            <House aria-hidden className="size-6 fill-current" />HouseTracker
          </Link>
          <div className="flex items-center gap-6">
            <nav aria-label="Main" className="hidden items-center gap-6 text-[15px] font-medium lg:flex">
              {TOP_NAV.map(n => (
                <NavLink key={n.to} to={n.to} end className={({ isActive }) => cn(isActive
                  ? 'underline decoration-2 underline-offset-8'
                  : 'text-muted-foreground hover:text-foreground')}>
                  {n.label}
                </NavLink>
              ))}
              <Link to="/add" className={buttonVariants()}><Plus aria-hidden />Add house</Link>
            </nav>
            <PersonChip />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[90rem] px-4 py-6 lg:px-10">
        <Routes>
          <Route path="/" element={<Houses />} />
          <Route path="/add" element={<AddHouse />} />
          <Route path="/house/:id" element={<HousePage />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <nav aria-label="Phone"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t bg-background pb-[env(safe-area-inset-bottom)] lg:hidden">
        {PHONE_NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end className={({ isActive }) => cn(
            'flex h-14 flex-col items-center justify-center gap-0.5 text-xs font-semibold',
            !isActive && 'text-muted-foreground')}>
            <Icon aria-hidden className="size-5" />{label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
