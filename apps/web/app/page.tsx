'use client'

import { useState, useEffect } from 'react'
import { WeatherMap } from '../components/map/WeatherMap'
import { ChatPanel } from '../components/panels/ChatPanel'
import { WeatherDetail } from '../components/panels/WeatherDetail'
import { useWeatherStore, ActiveLayerType } from '../store/weather'
import { Thermometer, Flame, Hexagon, Globe, RefreshCw, MessageCircle, X } from 'lucide-react'

export default function Home() {
  const { activeLayer, setActiveLayer } = useWeatherStore()
  const [isSyncing, setIsSyncing] = useState(false)
  const [networkError, setNetworkError] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)

  const layerOptions = [
    { id: 'scatterplot' as ActiveLayerType, label: 'Điểm trạm', icon: Thermometer },
    { id: 'heatmap' as ActiveLayerType, label: 'Bản đồ nhiệt', icon: Flame },
    { id: 'hexagon' as ActiveLayerType, label: 'H3 Hexagon 3D', icon: Hexagon },
  ]

  // Poll sync status from backend with exponential backoff on failure
  useEffect(() => {
    let retryMs = 3000
    let timeoutId: ReturnType<typeof setTimeout>

    const checkSyncStatus = async () => {
      try {
        const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiHost}/api/v1/weather/sync/status`)
        if (res.ok) {
          const data = await res.json()
          setIsSyncing(data.is_syncing)
          setNetworkError(false)
          retryMs = 3000 // reset backoff on success
        }
      } catch {
        // API temporarily unavailable — back off quietly
        setNetworkError(true)
        retryMs = Math.min(retryMs * 2, 30000) // max 30s backoff
      } finally {
        timeoutId = setTimeout(checkSyncStatus, retryMs)
      }
    }

    checkSyncStatus()
    return () => clearTimeout(timeoutId)
  }, [])

  const handleSync = async () => {
    setIsSyncing(true)
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiHost}/api/v1/weather/sync`, { method: 'POST' })
      if (res.ok) {
        // Just trigger it, polling will handle visual updates
        console.log("Sync trigger command sent successfully.")
      } else {
        alert("Gửi lệnh đồng bộ thất bại (Có thể do tiến trình đang chạy).")
        // Refetch status immediately
        const statusRes = await fetch(`${apiHost}/api/v1/weather/sync/status`)
        if (statusRes.ok) {
          const data = await statusRes.json()
          setIsSyncing(data.is_syncing)
        }
      }
    } catch (err) {
      console.error(err)
      alert("Lỗi kết nối khi đồng bộ thời tiết.")
      setIsSyncing(false)
    }
  }

  return (
    <div className="app-container">
      {/* Main Map Viewport */}
      <div className="map-viewport">
        <WeatherMap />

        {/* Floating Header */}
        <div className="floating-header glass-panel">
          <div className="header-brand">
            <div className="brand-logo">
              <Globe className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="brand-title">GeoWeather Platform</h1>
              <p className="brand-subtitle">Hệ thống GIS & Phân tích Thời tiết Real-Time</p>
            </div>
          </div>
          <button 
            onClick={handleSync} 
            disabled={isSyncing} 
            className={`btn-sync ${isSyncing ? 'loading' : ''}`}
            title="Đồng bộ lại dữ liệu Open-Meteo"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Đang đồng bộ...' : 'Cập nhật'}</span>
          </button>
          {networkError && (
            <span style={{ fontSize: '10px', color: '#f97316', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f97316', display: 'inline-block', animation: 'pulse 1.5s infinite' }} />
              API đang kết nối lại...
            </span>
          )}
        </div>



        {/* Selected City Details Panel */}
        <WeatherDetail />

        {/* Floating Layer Selection Bar */}
        <div className="layer-selection-bar glass-panel">
          {layerOptions.map((opt) => {
            const Icon = opt.icon
            const isActive = activeLayer === opt.id
            return (
              <button
                key={opt.id}
                onClick={() => setActiveLayer(opt.id)}
                className={`btn-toggle ${isActive ? 'active' : ''}`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{opt.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Mobile Backdrop for Chat */}
      <div 
        className={`mobile-backdrop ${!isChatOpen ? 'hidden' : ''}`} 
        onClick={() => setIsChatOpen(false)}
      />

      {/* Floating Chat Sidebar (Right side) */}
      <div className={`sidebar-right ${!isChatOpen ? 'closed' : ''}`}>
        {/* Grab Handle for bottom sheet */}
        <div className="bottom-sheet-handle md:hidden" />
        
        {/* Mobile close button inside chat */}
        <button 
          className="md:hidden flex items-center justify-center rounded-full" 
          style={{ position: 'absolute', top: '12px', right: '16px', width: '32px', height: '32px', background: 'var(--bg-panel)', color: 'var(--text-primary)', zIndex: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.3)' }}
          onClick={() => setIsChatOpen(false)}
        >
          <X className="w-5 h-5" />
        </button>
        <ChatPanel />
      </div>

      {/* Mobile FAB to open chat */}
      {!isChatOpen && (
        <button className="mobile-chat-fab" onClick={() => setIsChatOpen(true)}>
          <MessageCircle className="w-6 h-6" />
        </button>
      )}
    </div>
  )
}
