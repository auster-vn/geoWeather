'use client'

import { useState, useEffect } from 'react'

const MOBILE_BREAKPOINT = 768

/**
 * SSR-safe hook that returns true when viewport width < 768px.
 * Updates reactively on window resize.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)

    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    setIsMobile(mql.matches)

    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return isMobile
}
