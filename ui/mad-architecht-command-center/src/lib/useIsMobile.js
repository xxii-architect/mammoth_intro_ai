import { useEffect, useState } from 'react'

export const MOBILE_QUERY = '(max-width: 767px)'

function matches(query) {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches
}

// Tracks a media query live (rotation, window resize, split-screen) instead of reading innerWidth once.
export default function useIsMobile(query = MOBILE_QUERY) {
  const [isMobile, setIsMobile] = useState(() => matches(query))

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined
    const media = window.matchMedia(query)
    const onChange = () => setIsMobile(media.matches)
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [query])

  return isMobile
}
