'use client'

import { useState, useRef, useEffect } from 'react'
import { useWeatherStore } from '../../store/weather'
import { Search, MapPin, X, Clock, Compass } from 'lucide-react'

const RECENT_KEY = 'geoweather-recent-searches'
const MAX_RECENT = 5

interface SearchResult {
  lat: number
  lon: number
  name: string
  country?: string
}

const POPULAR_LOCATIONS: SearchResult[] = [
  { name: 'Hà Nội', lat: 21.0285, lon: 105.8542, country: 'VN' },
  { name: 'TP. Hồ Chí Minh', lat: 10.823, lon: 106.6297, country: 'VN' },
  { name: 'Đà Nẵng', lat: 16.0544, lon: 108.2022, country: 'VN' },
  { name: 'Nha Trang', lat: 12.2388, lon: 109.1967, country: 'VN' },
  { name: 'Đà Lạt', lat: 11.9404, lon: 108.4583, country: 'VN' }
]

export function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [recents, setRecents] = useState<SearchResult[]>([])
  const [focused, setFocused] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const { setSelectedLocation, setSheetState, setActiveBottomNav, setChatOverlayOpen } = useWeatherStore()

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
        const rawResults = Array.isArray(data) ? data : data.results ?? []
        const mapped = rawResults.map((item: any) => ({
          lat: item.latitude ?? item.lat,
          lon: item.longitude ?? item.lon,
          name: item.city_name ?? item.name,
          country: item.country_code ?? item.country
        }))
        setResults(mapped)
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
    
    // Open the detailed dashboard directly
    setSheetState('full')
    setActiveBottomNav('analytics')
    setChatOverlayOpen(false)
  }

  const handleGPS = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setSelectedLocation({ lat: coords.latitude, lon: coords.longitude, cityName: 'Vị trí của tôi' })
      setSheetState('full')
      setActiveBottomNav('analytics')
      setChatOverlayOpen(false)
    })
  }

  const triggerSearchOrAI = async () => {
    if (!query.trim()) return

    setFocused(false)
    inputRef.current?.blur()

    // 1. If we have results loaded, use the first result
    if (results.length > 0) {
      handleSelect(results[0])
      return
    }

    // 2. Otherwise, fetch immediately via search API prefix match
    setLoading(true)
    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    try {
      const res = await fetch(`${apiHost}/api/v1/location/search?q=${encodeURIComponent(query)}&limit=1`)
      if (res.ok) {
        const data = await res.json()
        const searchResults = Array.isArray(data) ? data : data.results ?? []
        if (searchResults.length > 0) {
          const first = searchResults[0]
          handleSelect({
            lat: first.latitude ?? first.lat,
            lon: first.longitude ?? first.lon,
            name: first.city_name ?? first.name,
            country: first.country_code ?? first.country
          })
          setQuery('')
          setLoading(false)
          return
        }
      }
    } catch (err) {
      console.error(err)
    }

    // 3. NLP extraction API fallback (if direct search fails, e.g. 'Thời tiết Hà Nội')
    try {
      const res = await fetch(`${apiHost}/api/v1/location/nlp?q=${encodeURIComponent(query)}`)
      if (res.ok) {
        const data = await res.json()
        if (data && data.latitude !== undefined && data.longitude !== undefined) {
          handleSelect({
            lat: data.latitude,
            lon: data.longitude,
            name: data.city_name || query
          })
          setQuery('')
          setLoading(false)
          return
        }
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }

    // 4. Fallback: If both fail, send the raw query directly to local AI Chat
    setChatOverlayOpen(true)
    setActiveBottomNav('ai')
    setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent('geoweather:chat-prompt', {
          detail: `Thời tiết tại ${query}`
        })
      )
    }, 300)
    setQuery('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      triggerSearchOrAI()
    }
  }

  const showDropdown = focused && (results.length > 0 || recents.length > 0 || query === '' || loading)

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
          onKeyDown={handleKeyDown}
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

          {!loading && query && results.length > 0 && (
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

          {!loading && query && results.length === 0 && (
            <div style={{ padding: '12px', textAlign: 'center', fontSize: '13px', color: 'var(--text-secondary)' }}>
              Không tìm thấy địa điểm. Nhấn Enter để hỏi AI.
            </div>
          )}

          {!loading && !query && (
            <>
              {recents.length > 0 && (
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

              <p className="mobile-search-group-label" style={{ marginTop: recents.length > 0 ? '12px' : '0' }}>Địa điểm gợi ý</p>
              {POPULAR_LOCATIONS.map((r, i) => (
                <button key={i} className="mobile-search-result" onMouseDown={() => handleSelect(r)}>
                  <Compass className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
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
