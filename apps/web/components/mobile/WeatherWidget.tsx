'use client'

import { useWeatherStore } from '../../store/weather'

interface WeatherWidgetProps {
  temperature?: number
  cityName?: string
  condition?: string
  aqi?: number
  onClick?: () => void
}

const WMO_ICON: Record<number, string> = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌧️', 55: '🌧️',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  71: '❄️', 73: '❄️', 75: '❄️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
}

export function WeatherWidget({ temperature, cityName, condition, aqi, onClick }: WeatherWidgetProps) {
  const { selectedLocation } = useWeatherStore()
  const displayCity = cityName ?? selectedLocation?.cityName ?? 'Chọn vị trí'
  const displayTemp = temperature ?? '--'
  const displayCondition = condition ?? 'Thời tiết ổn định'

  const getAqiColor = (v?: number) => {
    if (!v) return '#22c55e'
    if (v <= 50) return '#22c55e'
    if (v <= 100) return '#f59e0b'
    if (v <= 150) return '#f97316'
    return '#ef4444'
  }

  return (
    <div
      className="weather-widget-collapsed"
      onClick={onClick}
      role="button"
      aria-label="Xem chi tiết thời tiết"
    >
      {/* Drag handle */}
      <div className="sheet-drag-handle" />

      <div className="weather-widget-content">
        {/* Left: temp */}
        <div className="weather-widget-temp-group">
          <span className="weather-widget-temp">{displayTemp !== '--' ? `${Number(displayTemp).toFixed(0)}°` : '--'}</span>
          <div className="weather-widget-info">
            <span className="weather-widget-city">{displayCity}</span>
            <span className="weather-widget-cond">{displayCondition}</span>
          </div>
        </div>

        {/* Right: AQI */}
        {aqi !== undefined && (
          <div className="weather-widget-aqi" style={{ background: `${getAqiColor(aqi)}22`, border: `1px solid ${getAqiColor(aqi)}55` }}>
            <span style={{ color: getAqiColor(aqi), fontSize: '10px', fontWeight: 700 }}>AQI</span>
            <span style={{ color: getAqiColor(aqi), fontSize: '14px', fontWeight: 800 }}>{aqi}</span>
          </div>
        )}

        {/* Chevron */}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          <path d="M4 10L8 6L12 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  )
}
