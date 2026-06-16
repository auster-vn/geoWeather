'use client'

import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers'
import { HeatmapLayer, HexagonLayer } from '@deck.gl/aggregation-layers'
import { useWeatherStore } from '../../store/weather'
import { Activity, Thermometer, Wind } from 'lucide-react'

// Color scales helper
const TEMPERATURE_COLORS: [number, number, number][] = [
  [0, 0, 255],     // Extreme Cold (Blue)
  [0, 128, 255],   // Cold (Light Blue)
  [0, 255, 128],   // Cool (Teal)
  [255, 255, 0],   // Warm (Yellow)
  [255, 128, 0],   // Hot (Orange)
  [255, 0, 0]      // Extreme Hot (Red)
]

function getTemperatureColor(temp: number): [number, number, number] {
  if (temp < 0) return TEMPERATURE_COLORS[0]
  if (temp < 10) return TEMPERATURE_COLORS[1]
  if (temp < 20) return TEMPERATURE_COLORS[2]
  if (temp < 30) return TEMPERATURE_COLORS[3]
  if (temp < 38) return TEMPERATURE_COLORS[4]
  return TEMPERATURE_COLORS[5]
}

const DARK_STYLE  = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

export function WeatherMap({ isDark = false }: { isDark?: boolean }) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const overlayRef = useRef<MapboxOverlay | null>(null)
  const [weatherPoints, setWeatherPoints] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [errorLog, setErrorLog] = useState<string | null>(null)

  const { activeLayer, selectedLocation, setSelectedLocation, mapViewport, setMapViewport } = useWeatherStore()

  // Fetch weather points from FastAPI
  useEffect(() => {
    const fetchPoints = async () => {
      try {
        const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiHost}/api/v1/weather/all`)
        if (res.ok) {
          const data = await res.json()
          setWeatherPoints(data)
        }
      } catch (err: any) {
        console.error("Failed to load weather points:", err)
        setErrorLog((prev) => (prev ? prev + "\n" : "") + `API point fetch failed: ${err.message || err.toString()}`)
      } finally {
        setLoading(false)
      }
    }
    
    fetchPoints()

    // WebSocket real-time updates
    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl = apiHost.replace(/^http/, 'ws') + '/ws/weather/global'
    
    let ws: WebSocket | null = null;
    const connectWs = () => {
      ws = new WebSocket(wsUrl)
      ws.onmessage = (event) => {
        try {
          const update = JSON.parse(event.data)
          // Stream processor sends hourly aggregates by H3 cell, 
          // but let's update any matching point's temperature/weather
          setWeatherPoints(prev => {
            return prev.map(p => {
              if (p.h3_index_r4 === update.h3_index_r4) {
                return { ...p, temperature: update.avg_temperature, wind_speed: update.max_wind_speed, precipitation: update.total_precip }
              }
              return p
            })
          })
        } catch (e) {
          console.error("WS Parse error", e)
        }
      }
      ws.onclose = () => setTimeout(connectWs, 5000)
    }
    connectWs()

    return () => {
      if (ws) ws.close()
    }
  }, [])

  // Initialize MapLibre GL
  useEffect(() => {
    if (!mapContainerRef.current) return

    const styleUrl = isDark ? DARK_STYLE : LIGHT_STYLE
    
    let map: maplibregl.Map;
    const container = mapContainerRef.current;
    
    try {
      map = new maplibregl.Map({
        container: container,
        style: styleUrl,
        center: [mapViewport.longitude, mapViewport.latitude],
        zoom: mapViewport.zoom,
        pitch: mapViewport.pitch,
        trackResize: true
      })
      mapRef.current = map

      map.on('error', (e: any) => {
        console.error("MapLibre GL error event:", e)
        const msg = e.error?.message || e.message || (e.error ? e.error.toString() : JSON.stringify(e))
        setErrorLog((prev) => (prev ? prev + "\n" : "") + `Map event error: ${msg}`)
      })

      // Add zoom and rotation controls
      map.addControl(new maplibregl.NavigationControl(), 'top-right')

      map.on('load', () => {
        map.resize()
      })

      setTimeout(() => {
        if (mapRef.current) mapRef.current.resize()
      }, 500)
    } catch (err: any) {
      console.error("Failed to initialize MapLibre Map:", err)
      setErrorLog(`Map constructor crash: ${err.message || err.toString()}`)
      return
    }

    // Setup ResizeObserver to dynamically resize map canvas on container dimensions changes
    const resizeObserver = new ResizeObserver(() => {
      map.resize()
    })
    resizeObserver.observe(container)

    // Track map movements and update state
    map.on('moveend', () => {
      const center = map.getCenter()
      setMapViewport({
        longitude: center.lng,
        latitude: center.lat,
        zoom: map.getZoom(),
        pitch: map.getPitch()
      })
    })

    return () => {
      resizeObserver.disconnect()
      map.remove()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Swap map style when theme changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const targetStyle = isDark ? DARK_STYLE : LIGHT_STYLE
    // Only swap if current style differs
    try {
      const current = (map.getStyle() as any)?.name || ''
      if ((isDark && current.toLowerCase().includes('positron')) ||
          (!isDark && current.toLowerCase().includes('dark'))) {
        map.setStyle(targetStyle)
      }
    } catch { map.setStyle(targetStyle) }
  }, [isDark])

  // Fly to selectedLocation when it updates from external components (e.g. ChatPanel)
  useEffect(() => {
    if (selectedLocation && mapRef.current) {
      mapRef.current.flyTo({
        center: [selectedLocation.lon, selectedLocation.lat],
        zoom: 9,
        essential: true,
        duration: 2500
      })
    }
  }, [selectedLocation])

  // Setup Deck.gl Layers overlay
  useEffect(() => {
    const map = mapRef.current
    if (!map || weatherPoints.length === 0) return

    // Create or update Deck.gl overlay
    const layers = []

    if (activeLayer === 'scatterplot') {
      layers.push(
        new ScatterplotLayer({
          id: 'weather-points',
          data: weatherPoints,
          getPosition: (d: any) => [d.longitude, d.latitude],
          getFillColor: (d: any) => getTemperatureColor(d.temperature),
          getRadius: 15000,
          radiusMinPixels: 4,
          radiusMaxPixels: 15,
          pickable: true,
          onClick: ({ object }: any) => {
            if (object) {
              setSelectedLocation({
                lat: object.latitude,
                lon: object.longitude,
                cityName: object.city_name,
                countryCode: object.country_code
              })
            }
          }
        })
      )
    } else if (activeLayer === 'heatmap') {
      layers.push(
        new HeatmapLayer({
          id: 'temperature-heatmap',
          data: weatherPoints,
          getPosition: (d: any) => [d.longitude, d.latitude],
          getWeight: (d: any) => d.temperature + 40, // normalize
          radiusPixels: 50,
          intensity: 1,
          threshold: 0.05
        })
      )
    } else if (activeLayer === 'hexagon') {
      layers.push(
        new HexagonLayer({
          id: 'temperature-hexagon',
          data: weatherPoints,
          getPosition: (d: any) => [d.longitude, d.latitude],
          getElevationWeight: (d: any) => d.wind_speed || 0,
          getColorWeight: (d: any) => d.temperature || 0,
          radius: 60000,
          elevationScale: 800,
          extruded: true,
          pickable: true,
          onClick: ({ object }: any) => {
            if (object && object.points && object.points.length > 0) {
              const item = object.points[0].source
              setSelectedLocation({
                lat: item.latitude,
                lon: item.longitude,
                cityName: item.city_name,
                countryCode: item.country_code
              })
            }
            return true
          }
        })
      )
    }

    if (!overlayRef.current) {
      const overlay = new MapboxOverlay({ layers })
      map.addControl(overlay)
      overlayRef.current = overlay
    } else {
      overlayRef.current.setProps({ layers })
    }
  }, [weatherPoints, activeLayer])

  return (
    <div className="relative" style={{ width: '100%', height: '100%' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', backgroundColor: '#020617' }} />
      
      {errorLog && (
        <div style={{ position: 'absolute', top: '90px', left: '20px', right: '20px', padding: '16px', background: 'rgba(239, 68, 68, 0.95)', border: '1px solid #dc2626', color: 'white', borderRadius: '12px', zIndex: 9999, fontSize: '11px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', pointerEvents: 'auto', maxHeight: '180px', overflowY: 'auto' }}>
          <strong>Map Error Log:</strong>
          <pre style={{ margin: '8px 0 0 0', whiteSpace: 'pre-wrap' }}>{errorLog}</pre>
        </div>
      )}
      
      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: isDark ? 'rgba(2,6,23,0.7)' : 'rgba(232,244,253,0.7)', backdropFilter: 'blur(8px)', zIndex: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: isDark ? '#34d399' : '#0ea5e9', fontWeight: 500 }}>
            <Activity className="animate-spin w-8 h-8" />
            <span>Nạp bản đồ GIS thời tiết...</span>
          </div>
        </div>
      )}

      {/* Legend & Controls overlay */}
      <div className="map-legend">
        <h4 className="map-legend-title">
          <Thermometer className="w-4 h-4" /> GeoWeather Legend
        </h4>
        
        {activeLayer === 'hexagon' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
              <span>Màu: Nhiệt độ (°C)</span>
              <span>Cột: Gió (m/s)</span>
            </div>
            <div style={{ height: '8px', width: '100%', borderRadius: '4px', background: 'linear-gradient(to right, #3b82f6, #facc15, #ef4444)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '9px' }}>
              <span>&lt; 0°C</span>
              <span>20°C</span>
              <span>&gt; 38°C</span>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="map-legend-color-dot" style={{ background: '#2563eb' }} />
              <span>Dưới 10°C (Lạnh)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="map-legend-color-dot" style={{ background: '#34d399' }} />
              <span>10°C - 20°C (Mát mẻ)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="map-legend-color-dot" style={{ background: '#facc15' }} />
              <span>20°C - 30°C (Ấm áp)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="map-legend-color-dot" style={{ background: '#ef4444' }} />
              <span>Trên 30°C (Nóng)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
