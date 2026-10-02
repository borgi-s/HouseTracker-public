import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest runs without globals, so Testing Library cannot register this itself.
afterEach(cleanup)

// jsdom has no matchMedia; useIsDesktop needs one. Default: a phone-sized screen.
// A test that needs the laptop layout does
// vi.spyOn(window, 'matchMedia').mockReturnValue({ ...window.matchMedia(''), matches: true }).
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false, media: query, onchange: null,
      addEventListener() {}, removeEventListener() {},
      addListener() {}, removeListener() {}, dispatchEvent: () => false,
    }) as MediaQueryList
}

// jsdom has no pointer capture; the map sheet's drag handle calls it.
Element.prototype.setPointerCapture ??= () => {}
