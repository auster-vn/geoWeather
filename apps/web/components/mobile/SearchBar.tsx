'use client'

import { useState, useRef, useEffect } from 'react'
import { useWeatherStore } from '../../store/weather'
import { Search, MapPin, X, Clock } from 'lucide-react'

const RECENT_KEY = 'geoweather-recent-searches'
const MAX_RECENT = 5

interface SearchResult {
  lat: number
  lon: number
  name: string
  country?: string
}

export function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [recents, setRecents] = useState<SearchResult[]>([])
  const [focused, setFocused] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const { setSelectedLocation } = useWeatherStore()

  // Load recent searches
  useEffect(() => {
    try {
      const stored = localStorage.getItem(RECENT_KEY)
      if (stored) setRecents(JSON.parse(stored))
    } catch {}
  }, [])

  const saveRecent = (result: SearchResult) => {
    setRecents((prev) => {
      const next = [result, ...prev.filter((r) => r.name !== result.name)].slice(0, MAX_RECENT)
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }

  // Debounced search using the backend location API
  const doSearch = async (q: string) => {
    if (!q.trim()) { setResults([]); return }
    setLoading(true)
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiHost}/api/v1/location/search?q=${encodeURIComponent(q)}&limit=6`)
      if (res.ok) {
        const data = await res.json()
        // API may return array of {lat, lon, name, country} or similar
        setResults(Array.isArray(data) ? data : data.results ?? [])
      }
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setQuery(val)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(val), 350)
  }

  const handleSelect = (result: SearchResult) => {
    setSelectedLocation({ lat: result.lat, lon: result.lon, cityName: result.name })
    saveRecent(result)
    setQuery('')
    setResults([])
    setFocused(false)
    inputRef.current?.blur()
  }

  const handleGPS = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setSelectedLocation({ lat: coords.latitude, lon: coords.longitude, cityName: 'Vị trí của tôi' })
    })
  }

  const showDropdown = focused && (results.length > 0 || recents.length > 0 || loading)

  return (
    <div className="mobile-search-container">
      <div className={`mobile-search-bar ${focused ? 'focused' : ''}`}>
        <Search className="w-4 h-4 mobile-search-icon" />
        <input
          ref={inputRef}
          id="mobile-search-input"
          className="mobile-search-input"
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          placeholder="Tìm địa điểm..."
          autoComplete="off"
        />
        {query && (
          <button
            className="mobile-search-clear"
            onMouseDown={(e) => { e.preventDefault(); setQuery(''); setResults([]) }}
            aria-label="Xoá"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          className="mobile-search-gps"
          onMouseDown={(e) => { e.preventDefault(); handleGPS() }}
          aria-label="Dùng GPS"
          title="Vị trí của tôi"
        >
          <MapPin className="w-4 h-4" />
        </button>
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div className="mobile-search-dropdown">
          {loading && (
            <div className="mobile-search-loading">
              <div className="spinner-sm" /> Đang tìm...
            </div>
          )}

          {!loading && results.length > 0 && (
            <>
              <p className="mobile-search-group-label">Kết quả</p>
              {results.map((r, i) => (
                <button key={i} className="mobile-search-result" onMouseDown={() => handleSelect(r)}>
                  <MapPin className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                  <span>{r.name}{r.country ? `, ${r.country}` : ''}</span>
                </button>
              ))}
            </>
          )}

          {!loading && results.length === 0 && recents.length > 0 && (
            <>
              <p className="mobile-search-group-label">Tìm gần đây</p>
              {recents.map((r, i) => (
                <button key={i} className="mobile-search-result" onMouseDown={() => handleSelect(r)}>
                  <Clock className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  <span>{r.name}</span>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
