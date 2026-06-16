'use client'

import React, { useRef, useState, useEffect, useCallback } from 'react'
import { useWeatherStore, SheetState } from '../../store/weather'
import { WeatherWidget } from './WeatherWidget'
import { ForecastCards } from './ForecastCards'
import { useWeatherWS } from '../../hooks/useWeatherWS'
import { X, Wind, Droplets, CloudRain, Cloud, Sunrise, Sunset, Sun, Radio, Thermometer } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const SNAP_COLLAPSED = 80   // px from bottom
const SNAP_HALF_VH  = 50   // % of vh
const SNAP_FULL_VH  = 96   // % of vh

type SheetTab = 'current' | 'forecast' | 'air' | 'sunrise'

const getWeatherDesc = (code: number) => {
  if (code === 0) return 'Trời quang ☀️'
  if ([1, 2, 3].includes(code)) return 'Ít mây ⛅'
  if ([45, 48].includes(code)) return 'Sương mù 🌫️'
  if ([51, 53, 55, 61, 63, 65].includes(code)) return 'Mưa rào 🌧️'
  if ([71, 73, 75, 77].includes(code)) return 'Tuyết ❄️'
  if ([95, 96, 99].includes(code)) return 'Dông sét ⛈️'
  return 'Ổn định 🌤️'
}

export function BottomSheet() {
  const {
    sheetState, setSheetState,
    selectedLocation, setSelectedLocation,
  } = useWeatherStore()

  const [weather, setWeather] = useState<any>(null)
  const [forecast, setForecast] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<SheetTab>('current')

  const h3Cell = weather?.h3_r4 || null
  const { data: wsUpdate, status: wsStatus } = useWeatherWS(h3Cell)

  const sheetRef = useRef<HTMLDivElement>(null)
  const dragStartY = useRef(0)
  const dragStartHeight = useRef(0)
  const isDragging = useRef(false)

  // Fetch weather when location changes
  useEffect(() => {
    if (!selectedLocation) { setWeather(null); setForecast(null); return }
    const go = async () => {
      setLoading(true)
      try {
        const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const [wRes, fRes] = await Promise.all([
          fetch(`${apiHost}/api/v1/weather/nearest/${selectedLocation.lat}/${selectedLocation.lon}`),
          fetch(`${apiHost}/api/v1/weather/forecast/${selectedLocation.lat}/${selectedLocation.lon}`),
        ])
        if (wRes.ok) setWeather(await wRes.json())
        if (fRes.ok) setForecast(await fRes.json())
      } catch (e) { console.error(e) }
      finally { setLoading(false) }
    }
    go()
    // When a location is selected, expand sheet to half
    setSheetState('half')
  }, [selectedLocation])

  const getHeightPx = useCallback((state: SheetState) => {
    const vh = window.innerHeight
    if (state === 'collapsed') return SNAP_COLLAPSED
    if (state === 'half') return Math.round(vh * SNAP_HALF_VH / 100)
    return Math.round(vh * SNAP_FULL_VH / 100)
  }, [])

  const snapToState = useCallback((state: SheetState) => {
    if (!sheetRef.current) return
    sheetRef.current.style.transition = 'height 0.4s cubic-bezier(0.32,0.72,0,1)'
    sheetRef.current.style.height = `${getHeightPx(state)}px`
    setSheetState(state)
  }, [getHeightPx, setSheetState])

  // Sync height when sheetState changes externally
  useEffect(() => {
    snapToState(sheetState)
  }, [sheetState]) // eslint-disable-line react-hooks/exhaustive-deps

  // Touch drag handlers
  const onDragStart = (clientY: number) => {
    isDragging.current = true
    dragStartY.current = clientY
    dragStartHeight.current = sheetRef.current?.offsetHeight ?? getHeightPx(sheetState)
    if (sheetRef.current) sheetRef.current.style.transition = 'none'
  }

  const onDragMove = (clientY: number) => {
    if (!isDragging.current || !sheetRef.current) return
    const delta = dragStartY.current - clientY
    const newH = Math.max(SNAP_COLLAPSED, Math.min(window.innerHeight * 0.97, dragStartHeight.current + delta))
    sheetRef.current.style.height = `${newH}px`
  }

  const onDragEnd = (clientY: number) => {
    if (!isDragging.current) return
    isDragging.current = false
    const delta = dragStartY.current - clientY
    const vh = window.innerHeight
    const halfH = vh * SNAP_HALF_VH / 100

    if (delta > 60) {
      // Dragged up
      snapToState(sheetState === 'collapsed' ? 'half' : 'full')
    } else if (delta < -60) {
      // Dragged down
      snapToState(sheetState === 'full' ? 'half' : 'collapsed')
    } else {
      snapToState(sheetState)
    }
  }

  const displayTemp = wsUpdate ? wsUpdate.avg_temperature : (weather?.temperature ?? null)
  const displayWind = wsUpdate ? wsUpdate.max_wind_speed : (weather?.wind_speed ?? null)
  const displayHumidity = wsUpdate ? wsUpdate.avg_humidity : (weather?.humidity ?? null)

  return (
    <div
      ref={sheetRef}
      className="mobile-bottom-sheet"
      style={{ height: `${SNAP_COLLAPSED}px` }}
      onTouchStart={(e) => onDragStart(e.touches[0].clientY)}
      onTouchMove={(e) => onDragMove(e.touches[0].clientY)}
      onTouchEnd={(e) => onDragEnd(e.changedTouches[0].clientY)}
      onMouseDown={(e) => onDragStart(e.clientY)}
      onMouseMove={(e) => isDragging.current && onDragMove(e.clientY)}
      onMouseUp={(e) => onDragEnd(e.clientY)}
      onMouseLeave={(e) => isDragging.current && onDragEnd(e.clientY)}
    >
      {/* Collapsed state widget */}
      {sheetState === 'collapsed' && (
        <WeatherWidget
          temperature={displayTemp}
          cityName={selectedLocation?.cityName}
          condition={weather ? getWeatherDesc(weather.weather_code ?? 0) : undefined}
          onClick={() => snapToState('half')}
        />
      )}

      {/* Expanded states */}
      {sheetState !== 'collapsed' && (
        <div className="mobile-sheet-inner">
          {/* Handle */}
          <div
            className="sheet-drag-handle"
            style={{ cursor: 'grab', margin: '12px auto 0' }}
          />

          {/* Header */}
          <div className="mobile-sheet-header">
            <div>
              <h2 className="mobile-sheet-title">
                {selectedLocation?.cityName ?? 'Thời tiết'}
              </h2>
              {displayTemp !== null && (
                <p className="mobile-sheet-subtitle">
                  {displayTemp.toFixed(1)}°C · {weather ? getWeatherDesc(weather.weather_code ?? 0) : '—'}
                </p>
              )}
            </div>
            <button
              className="btn-close"
              onClick={() => snapToState('collapsed')}
              aria-label="Thu gọn"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Tabs (only in full state) */}
          {sheetState === 'full' && (
            <div className="mobile-sheet-tabs">
              {(['current', 'forecast', 'air', 'sunrise'] as SheetTab[]).map((tab) => (
                <button
                  key={tab}
                  className={`mobile-tab-btn ${activeTab === tab ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {{ current: 'Hiện tại', forecast: 'Dự báo', air: 'Không khí', sunrise: 'Bình minh' }[tab]}
                </button>
              ))}
            </div>
          )}

          {/* Scrollable content */}
          <div className="mobile-sheet-body">
            {loading && (
              <div className="mobile-sheet-loading">
                <div className="spinner" />
                <span>Đang tải...</span>
              </div>
            )}

            {!loading && (activeTab === 'current' || sheetState === 'half') && (
              <div className="mobile-weather-grid">
                {/* Main temp card */}
                <div className="mobile-weather-main-card">
                  <div className="weather-temp-icon">
                    <Thermometer className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="weather-temp-val">{displayTemp !== null ? `${displayTemp.toFixed(1)}°C` : '--'}</span>
                    <p className="weather-temp-feels">Cảm giác: {weather?.feels_like?.toFixed(1) ?? '--'}°C</p>
                  </div>
                  <div className="mobile-ws-badge">
                    <Radio className={`w-3 h-3 ${wsStatus === 'connected' ? 'pulse-animation' : ''}`} />
                    <span>{wsStatus === 'connected' ? 'Live' : 'Static'}</span>
                  </div>
                </div>

                {/* Grid items */}
                <div className="weather-grid" style={{ marginTop: 0 }}>
                  {[
                    { icon: <Wind className="w-4 h-4" />, cls: 'wind', val: displayWind !== null ? `${displayWind.toFixed(1)} m/s` : '--', lbl: 'Gió' },
                    { icon: <Droplets className="w-4 h-4" />, cls: 'humidity', val: displayHumidity !== null ? `${displayHumidity.toFixed(0)}%` : '--', lbl: 'Độ ẩm' },
                    { icon: <CloudRain className="w-4 h-4" />, cls: 'rain', val: `${weather?.precipitation?.toFixed(1) ?? '0.0'} mm`, lbl: 'Lượng mưa' },
                    { icon: <Cloud className="w-4 h-4" />, cls: 'cloud', val: `${weather?.cloud_cover ?? '0'}%`, lbl: 'Mây' },
                  ].map((item) => (
                    <div key={item.lbl} className="weather-grid-item">
                      <div className={`weather-grid-icon ${item.cls}`}>{item.icon}</div>
                      <div>
                        <span className="weather-grid-val">{item.val}</span>
                        <span className="weather-grid-lbl">{item.lbl}</span>
                      </div>
                    </div>
                  ))}

                  {forecast?.daily?.uv_index_max && (
                    <div className="weather-grid-item">
                      <div className="weather-grid-icon" style={{ color: '#9C27B0', background: 'rgba(156,39,176,0.1)' }}>
                        <Sun className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="weather-grid-val">{forecast.daily.uv_index_max[0]}</span>
                        <span className="weather-grid-lbl">UV Index</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Mini forecast chart in half state */}
                {sheetState === 'half' && forecast?.hourly && (
                  <div style={{ height: 150, marginTop: 8 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={forecast.hourly.time.slice(0, 24).map((t: string, i: number) => ({
                          time: t.slice(11, 16),
                          temp: forecast.hourly.temperature_2m[i],
                        }))}
                        margin={{ top: 4, right: 0, left: -28, bottom: 0 }}
                      >
                        <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                        <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                        <Tooltip
                          contentStyle={{ background: 'rgba(11,18,32,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                          itemStyle={{ color: '#fff' }}
                        />
                        <Line type="monotone" dataKey="temp" name="°C" stroke="#38bdf8" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {/* Forecast tab */}
            {!loading && sheetState === 'full' && activeTab === 'forecast' && (
              <ForecastCards forecast={forecast} />
            )}

            {/* Air quality tab */}
            {!loading && sheetState === 'full' && activeTab === 'air' && (
              <div className="mobile-air-tab">
                <div className="mobile-air-card">
                  <span className="mobile-air-label">Lượng mưa (mm)</span>
                  <span className="mobile-air-value">{weather?.precipitation?.toFixed(1) ?? '0.0'}</span>
                </div>
                <div className="mobile-air-card">
                  <span className="mobile-air-label">Độ phủ mây (%)</span>
                  <span className="mobile-air-value">{weather?.cloud_cover ?? '0'}</span>
                </div>
                {forecast?.daily?.uv_index_max && (
                  <div className="mobile-air-card">
                    <span className="mobile-air-label">UV Index (Max)</span>
                    <span className="mobile-air-value" style={{ color: '#9C27B0' }}>{forecast.daily.uv_index_max[0]}</span>
                  </div>
                )}
              </div>
            )}

            {/* Sunrise tab */}
            {!loading && sheetState === 'full' && activeTab === 'sunrise' && (
              <div className="mobile-air-tab">
                {forecast?.daily?.sunrise && (
                  <div className="mobile-air-card">
                    <Sunrise className="w-6 h-6" style={{ color: '#FDB813' }} />
                    <span className="mobile-air-label">Bình minh</span>
                    <span className="mobile-air-value">{forecast.daily.sunrise[0]?.slice(-5)}</span>
                  </div>
                )}
                {forecast?.daily?.sunset && (
                  <div className="mobile-air-card">
                    <Sunset className="w-6 h-6" style={{ color: '#FF7B54' }} />
                    <span className="mobile-air-label">Hoàng hôn</span>
                    <span className="mobile-air-value">{forecast.daily.sunset[0]?.slice(-5)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
