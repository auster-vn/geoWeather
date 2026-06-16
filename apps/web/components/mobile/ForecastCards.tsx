'use client'

import { CloudRain, Droplets } from 'lucide-react'

const WMO_ICON: Record<number, string> = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌧️', 55: '🌧️',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  71: '❄️', 73: '❄️', 75: '❄️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
}

const getDayLabel = (dateStr: string, idx: number) => {
  if (idx === 0) return 'Hôm nay'
  if (idx === 1) return 'Ngày mai'
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN', { weekday: 'short', day: 'numeric', month: 'numeric' })
  } catch {
    return dateStr
  }
}

interface ForecastCardsProps {
  forecast: any
}

export function ForecastCards({ forecast }: ForecastCardsProps) {
  if (!forecast) {
    return (
      <div className="forecast-empty">
        <span>Chọn địa điểm để xem dự báo</span>
      </div>
    )
  }

  const { hourly, daily } = forecast

  return (
    <div className="forecast-container">
      {/* Hourly scroll */}
      {hourly && (
        <>
          <h4 className="forecast-section-title">
            🕐 Dự báo 24 giờ
          </h4>
          <div className="hourly-scroll">
            {hourly.time.slice(0, 24).map((time: string, i: number) => {
              const code = hourly.weathercode?.[i] ?? 0
              const temp = hourly.temperature_2m?.[i]
              const rain = hourly.precipitation_probability?.[i] ?? 0
              return (
                <div key={i} className="hourly-card">
                  <span className="hourly-time">{time.slice(11, 16)}</span>
                  <span className="hourly-icon">{WMO_ICON[code] ?? '🌤️'}</span>
                  <span className="hourly-temp">{temp !== undefined ? `${Math.round(temp)}°` : '--'}</span>
                  {rain > 0 && (
                    <div className="hourly-rain">
                      <Droplets className="w-2.5 h-2.5" />
                      <span>{rain}%</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Daily 7-day */}
      {daily && (
        <>
          <h4 className="forecast-section-title" style={{ marginTop: 20 }}>
            📅 Dự báo 7 ngày
          </h4>
          <div className="daily-list">
            {daily.time?.map((dateStr: string, i: number) => {
              const code = daily.weathercode?.[i] ?? 0
              const minT = daily.temperature_2m_min?.[i]
              const maxT = daily.temperature_2m_max?.[i]
              const rain = daily.precipitation_probability_max?.[i] ?? 0
              return (
                <div key={i} className="daily-card">
                  <div className="daily-day">{getDayLabel(dateStr, i)}</div>
                  <span className="daily-icon">{WMO_ICON[code] ?? '🌤️'}</span>
                  <div className="daily-temp-range">
                    <span className="daily-max">{maxT !== undefined ? `${Math.round(maxT)}°` : '--'}</span>
                    <span className="daily-min">{minT !== undefined ? `${Math.round(minT)}°` : '--'}</span>
                  </div>
                  {rain > 0 && (
                    <div className="daily-rain">
                      <CloudRain className="w-3 h-3" />
                      <span>{rain}%</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
