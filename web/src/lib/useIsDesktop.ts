import { useSyncExternalStore } from 'react'

const QUERY = '(min-width: 1024px)'          // Tailwind `lg` — spec §4.4

function subscribe(onChange: () => void) {
  const m = window.matchMedia(QUERY)
  m.addEventListener('change', onChange)
  return () => m.removeEventListener('change', onChange)
}

/** Laptop layout (two panes) vs phone layout (stacked). */
export const useIsDesktop = () => useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches)
