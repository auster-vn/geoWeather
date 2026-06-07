'use client'

import { useEffect, useState } from 'react'
import { useWeatherStore } from '../../store/weather'
import { useWeatherWS } from '../../hooks/useWeatherWS'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { X, CloudRain, Wind, Thermometer, Droplets, Radio, Calendar, Cloud, Sunrise, Sunset, Sun } from 'lucide-react'

export function WeatherDetail() {
  const { selectedLocation, setSelectedLocation } = useWeatherStore()
  const [weather, setWeather] = useState<any>(null)
  const [forecast, setForecast] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  // Determine H3 index for selected location to stream via WS
  // For demo, let's calculate a dummy or retrieve it from the location if we got it,
  // or calculate the h3 cell. We can just use the resolution 4 string.
  // We can call a helper to get H3, or we can just fetch the detailed weather first
  // which will return the H3 indexes.
  const h3Cell = weather?.h3_r4 || null
  const { data: wsUpdate, status: wsStatus } = useWeatherWS(h3Cell)

  useEffect(() => {
    if (!selectedLocation) {
      setWeather(null)
      return
    }

    const fetchDetails = async () => {
      setLoading(true)
      try {
        const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        
        // Fetch detailed nearest weather
        const res = await fetch(`${apiHost}/api/v1/weather/nearest/${selectedLocation.lat}/${selectedLocation.lon}`)
        if (res.ok) {
          const data = await res.json()
          setWeather(data)
        }
        
        // Fetch Open-Meteo forecast
        const forecastRes = await fetch(`${apiHost}/api/v1/weather/forecast/${selectedLocation.lat}/${selectedLocation.lon}`)
        if (forecastRes.ok) {
          const forecastData = await forecastRes.json()
          setForecast(forecastData)
        }
        
      } catch (err) {
        console.error("Failed to fetch location details:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchDetails()
  }, [selectedLocation])

  if (!selectedLocation) return null

  // Mix standard weather details with live websocket updates if available
  const displayTemp = wsUpdate ? wsUpdate.avg_temperature : (weather?.temperature ?? 25.0)
  const displayWind = wsUpdate ? wsUpdate.max_wind_speed : (weather?.wind_speed ?? 2.0)
  const displayHumidity = wsUpdate ? wsUpdate.avg_humidity : (weather?.humidity ?? 65)

  // Simple WMO weather description mapping
  const getWeatherDesc = (code: number) => {
    if (code === 0) return "Trời quang"
    if ([1, 2, 3].includes(code)) return "Ít mây / Mây rải rác"
    if ([45, 48].includes(code)) return "Có sương mù"
    if ([51, 53, 55, 61, 63, 65].includes(code)) return "Mưa nhỏ / Mưa rào"
    if ([71, 73, 75, 77, 85, 86].includes(code)) return "Có tuyết"
    if ([95, 96, 99].includes(code)) return "Có dông sét"
    return "Thời tiết ổn định"
  }

  return (
    <div className="weather-detail-panel glass-panel">
      {/* Title */}
      <div className="weather-detail-header">
        <div>
          <h3>{selectedLocation.cityName}</h3>
          <p>
            Tọa độ: {selectedLocation.lat.toFixed(4)}, {selectedLocation.lon.toFixed(4)}
          </p>
        </div>
        <button 
          onClick={() => setSelectedLocation(null)}
          className="btn-close"
          title="Đóng chi tiết"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px', color: 'var(--text-secondary)', gap: '8px' }}>
          <LoaderIcon className="w-6 h-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontSize: '12px' }}>Đang tải dữ liệu thực tế...</span>
        </div>
      ) : (
        <div className="weather-detail-body">
          {/* Main Weather Card */}
          <div className="weather-detail-main-card">
            <div className="weather-temp-group">
              <div className="weather-temp-icon">
                <Thermometer className="w-6 h-6" />
              </div>
              <div>
                <span className="weather-temp-val">{displayTemp.toFixed(1)}°C</span>
                <p className="weather-temp-feels">
                  Cảm giác như: {weather?.feels_like?.toFixed(1) ?? (displayTemp + 2).toFixed(1)}°C
                </p>
              </div>
            </div>
            <div className="weather-status-group">
              <span className="weather-status-desc">{getWeatherDesc(weather?.weather_code ?? 0)}</span>
              <span className="weather-status-code">Mã WMO: {weather?.weather_code ?? 0}</span>
            </div>
          </div>

          {/* WebSocket stream status */}
          <div className="weather-ws-status">
            <span className="weather-ws-info">
              <Radio className={`w-3.5 h-3.5 ${wsStatus === 'connected' ? 'pulse-animation' : ''}`} style={{ color: wsStatus === 'connected' ? 'var(--accent-primary-hover)' : 'var(--text-muted)' }} />
              Streaming (H3 cell): {h3Cell?.substring(0, 10) || 'None'}
            </span>
            <span className={`weather-ws-badge ${wsStatus === 'connected' ? 'connected' : 'disconnected'}`}>
              {wsStatus === 'connected' ? 'Live Stream' : 'Disconnected'}
            </span>
          </div>

          {/* Details grid */}
          <div className="weather-grid">
            <div className="weather-grid-item">
              <div className="weather-grid-icon wind">
                <Wind className="w-4 h-4" />
              </div>
              <div>
                <span className="weather-grid-val">{displayWind.toFixed(1)} m/s</span>
                <span className="weather-grid-lbl">Tốc độ gió</span>
              </div>
            </div>
            
            <div className="weather-grid-item">
              <div className="weather-grid-icon humidity">
                <Droplets className="w-4 h-4" />
              </div>
              <div>
                <span className="weather-grid-val">{displayHumidity.toFixed(0)}%</span>
                <span className="weather-grid-lbl">Độ ẩm</span>
              </div>
            </div>

            <div className="weather-grid-item">
              <div className="weather-grid-icon rain">
                <CloudRain className="w-4 h-4" />
              </div>
              <div>
                <span className="weather-grid-val">{weather?.precipitation?.toFixed(1) ?? '0.0'} mm</span>
                <span className="weather-grid-lbl">Lượng mưa</span>
              </div>
            </div>

            <div className="weather-grid-item">
              <div className="weather-grid-icon cloud">
                <Cloud className="w-4 h-4" />
              </div>
              <div>
                <span className="weather-grid-val">{weather?.cloud_cover ?? '0'}%</span>
                <span className="weather-grid-lbl">Lượng mây</span>
              </div>
            </div>

            {forecast?.daily?.sunrise && (
              <div className="weather-grid-item">
                <div className="weather-grid-icon" style={{ color: '#FDB813', background: 'rgba(253, 184, 19, 0.1)' }}>
                  <Sunrise className="w-4 h-4" />
                </div>
                <div>
                  <span className="weather-grid-val">{forecast.daily.sunrise[0].slice(-5)}</span>
                  <span className="weather-grid-lbl">Bình minh</span>
                </div>
              </div>
            )}
            
            {forecast?.daily?.sunset && (
              <div className="weather-grid-item">
                <div className="weather-grid-icon" style={{ color: '#FF7B54', background: 'rgba(255, 123, 84, 0.1)' }}>
                  <Sunset className="w-4 h-4" />
                </div>
                <div>
                  <span className="weather-grid-val">{forecast.daily.sunset[0].slice(-5)}</span>
                  <span className="weather-grid-lbl">Hoàng hôn</span>
                </div>
              </div>
            )}

            {forecast?.daily?.uv_index_max && (
              <div className="weather-grid-item">
                <div className="weather-grid-icon" style={{ color: '#9C27B0', background: 'rgba(156, 39, 176, 0.1)' }}>
                  <Sun className="w-4 h-4" />
                </div>
                <div>
                  <span className="weather-grid-val">{forecast.daily.uv_index_max[0]}</span>
                  <span className="weather-grid-lbl">UV Max</span>
                </div>
              </div>
            )}
          </div>

          {/* History Chart */}
          {/* Chart Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', marginBottom: '12px' }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Calendar className="w-4 h-4" />
              Dự báo 48h tới
            </h4>
          </div>

          <div className="weather-chart-container" style={{ height: '220px' }}>
            {!forecast?.hourly ? (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                Đang tải biểu đồ dự báo...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart 
                  data={
                    forecast.hourly.time.slice(0, 48).map((t: string, i: number) => ({
                      time: t.slice(11, 16),
                      temp: forecast.hourly.temperature_2m[i],
                      humidity: forecast.hourly.precipitation_probability[i]
                    }))
                  } 
                  margin={{ top: 5, right: 0, left: -25, bottom: 0 }}
                >
                  <XAxis 
                    dataKey="time" 
                    stroke="var(--text-muted)" 
                    fontSize={11} 
                    tickLine={false}
                    axisLine={false}
                    dy={5}
                  />
                  <YAxis 
                    yAxisId="left"
                    stroke="var(--text-muted)" 
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    dx={-5}
                  />
                  <YAxis 
                    yAxisId="right" 
                    orientation="right" 
                    stroke="var(--text-muted)" 
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    dx={5}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(15, 23, 42, 0.9)', 
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                      boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                    }}
                    itemStyle={{ color: '#fff' }}
                    labelStyle={{ color: 'var(--text-muted)', marginBottom: '4px' }}
                  />
                  <Line 
                    yAxisId="left"
                    type="monotone" 
                    dataKey="temp" 
                    name="Nhiệt độ (°C)"
                    stroke="var(--accent-primary)" 
                    strokeWidth={3} 
                    dot={false}
                    activeDot={{ r: 5, fill: 'var(--accent-primary)', stroke: '#fff', strokeWidth: 2 }}
                  />
                  <Line 
                    yAxisId="right"
                    type="monotone" 
                    dataKey="humidity" 
                    name="Xác suất mưa (%)"
                    stroke="var(--accent-secondary)" 
                    strokeWidth={2} 
                    dot={false} 
                    strokeDasharray="4 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function LoaderIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}
