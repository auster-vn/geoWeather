import { useState, useEffect, useRef } from 'react'
import { MapPin, Navigation, Search } from 'lucide-react'
import { useWeatherStore } from '../../store/weather'

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

interface Suggestion {
  name: string
  address: string
  lat: number
  lon: number
}

function AutocompleteInput({ 
  placeholder, 
  value, 
  onChange, 
  onSelectCoords,
  icon: Icon,
  iconColor,
  onSubmit
}: { 
  placeholder: string, 
  value: string, 
  onChange: (val: string) => void,
  onSelectCoords: (lat: number, lon: number) => void,
  icon: any,
  iconColor: string,
  onSubmit: () => void
}) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  
  const debouncedSearchTerm = useDebounce(value, 400)

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    if (debouncedSearchTerm.length < 2) {
      setSuggestions([])
      setIsOpen(false)
      return
    }

    const fetchSuggestions = async () => {
      setIsSearching(true)
      try {
        const res = await fetch(`https://photon.komoot.io/api/?q=${encodeURIComponent(debouncedSearchTerm)}&limit=5&lang=default`)
        if (res.ok) {
          const data = await res.json()
          const parsed = data.features.map((f: any) => {
            const props = f.properties
            const parts = [props.street, props.district, props.city].filter(Boolean)
            return {
              name: props.name || props.street || props.city || "Địa điểm",
              address: parts.join(', '),
              lat: f.geometry.coordinates[1],
              lon: f.geometry.coordinates[0]
            }
          })
          setSuggestions(parsed)
          setIsOpen(true)
        }
      } catch (err) {
        console.error("Photon API error", err)
      } finally {
        setIsSearching(false)
      }
    }
    
    // Check if the current value matches the exact formatted string we just selected.
    // If it does, we probably don't want to re-search.
    // However, it's safer to just search anyway, it will just show the suggestion again.
    fetchSuggestions()
  }, [debouncedSearchTerm])

  const handleSelect = (sug: Suggestion) => {
    onChange(`${sug.name}${sug.address ? `, ${sug.address}` : ''}`)
    onSelectCoords(sug.lat, sug.lon)
    setIsOpen(false)
  }

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '8px' }}>
        <Icon className={`w-4 h-4 ${iconColor}`} />
        <input 
          type="text" 
          placeholder={placeholder} 
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            setIsOpen(true)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              setIsOpen(false)
              onSubmit()
            }
          }}
          style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', width: '100%', fontSize: '13px' }}
        />
        {isSearching && <Search className="w-3 h-3 text-gray-400" style={{ animation: 'spin 1s linear infinite' }} />}
      </div>

      {isOpen && suggestions.length > 0 && (
        <div style={{ 
          position: 'absolute', 
          top: '100%', 
          left: 0, 
          right: 0, 
          marginTop: '4px',
          background: '#1e293b', 
          border: '1px solid #334155',
          borderRadius: '8px', 
          overflow: 'hidden',
          zIndex: 50,
          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)'
        }}>
          {suggestions.map((sug, i) => (
            <div 
              key={i}
              onClick={() => handleSelect(sug)}
              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: i < suggestions.length - 1 ? '1px solid #334155' : 'none' }}
              onMouseOver={(e) => e.currentTarget.style.background = '#334155'}
              onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>{sug.name}</div>
              {sug.address && <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{sug.address}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function RoutingPanel() {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [originCoords, setOriginCoords] = useState<{lat: number, lon: number} | null>(null)
  const [destCoords, setDestCoords] = useState<{lat: number, lon: number} | null>(null)
  
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const fetchSafeRoute = useWeatherStore(state => state.fetchSafeRoute)

  // Clear coords if user modifies input manually
  const handleOriginChange = (val: string) => {
    setOrigin(val)
    setOriginCoords(null)
  }
  
  const handleDestChange = (val: string) => {
    setDestination(val)
    setDestCoords(null)
  }

  const handleRouteSearch = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Vui lòng nhập đủ Điểm đi và Điểm đến')
      return
    }

    setIsLoading(true)
    setError(null)
    
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      
      let olat = originCoords?.lat
      let olon = originCoords?.lon
      let dlat = destCoords?.lat
      let dlon = destCoords?.lon

      // Fallback: If not selected from autocomplete, geocode via backend
      if (!olat || !olon) {
        const res = await fetch(`${apiHost}/api/v1/routing/geocode?address=${encodeURIComponent(origin)}`)
        if (!res.ok) throw new Error(`Không tìm thấy điểm đi: ${origin}`)
        const data = await res.json()
        olat = data.lat
        olon = data.lon
      }

      if (!dlat || !dlon) {
        const res = await fetch(`${apiHost}/api/v1/routing/geocode?address=${encodeURIComponent(destination)}`)
        if (!res.ok) throw new Error(`Không tìm thấy điểm đến: ${destination}`)
        const data = await res.json()
        dlat = data.lat
        dlon = data.lon
      }

      if (olat && olon && dlat && dlon) {
        await fetchSafeRoute(olat, olon, dlat, dlon)
      }
      
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối khi tìm đường')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="routing-panel glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', width: '320px', pointerEvents: 'auto' }}>
      <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Navigation className="w-4 h-4 text-blue-400" />
        Tìm đường An toàn
      </h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <AutocompleteInput 
          placeholder="Điểm đi (VD: KTX Khu B)"
          value={origin}
          onChange={handleOriginChange}
          onSelectCoords={(lat, lon) => setOriginCoords({lat, lon})}
          icon={MapPin}
          iconColor="text-emerald-400"
          onSubmit={handleRouteSearch}
        />

        <AutocompleteInput 
          placeholder="Điểm đến (VD: Ga Bến Thành)"
          value={destination}
          onChange={handleDestChange}
          onSelectCoords={(lat, lon) => setDestCoords({lat, lon})}
          icon={MapPin}
          iconColor="text-red-400"
          onSubmit={handleRouteSearch}
        />
      </div>

      {error && (
        <div style={{ color: '#ef4444', fontSize: '12px', padding: '4px 8px', background: 'rgba(239,68,68,0.1)', borderRadius: '4px' }}>
          {error}
        </div>
      )}

      <button 
        onClick={handleRouteSearch}
        disabled={isLoading}
        style={{ 
          background: 'linear-gradient(to right, #3b82f6, #2563eb)', 
          color: 'white', 
          border: 'none', 
          padding: '10px', 
          borderRadius: '8px', 
          fontWeight: 600, 
          cursor: isLoading ? 'not-allowed' : 'pointer',
          opacity: isLoading ? 0.7 : 1,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '8px',
          fontSize: '13px',
          transition: 'all 0.2s'
        }}
      >
        {isLoading ? (
          <>
            <span style={{ width: '14px', height: '14px', border: '2px solid white', borderBottomColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 1s linear infinite' }}></span>
            Đang tính toán...
          </>
        ) : (
          'Bắt đầu Chỉ đường'
        )}
      </button>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}} />
    </div>
  )
}
