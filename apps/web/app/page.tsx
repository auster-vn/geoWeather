'use client'

import { useState, useEffect } from 'react'
import { WeatherMap } from '../components/map/WeatherMap'
import { ChatPanel } from '../components/panels/ChatPanel'
import { WeatherDetail } from '../components/panels/WeatherDetail'
import { ThemeToggle } from '../components/ThemeToggle'
import { useWeatherStore, ActiveLayerType } from '../store/weather'
import { useIsMobile } from '../hooks/useIsMobile'

// Mobile components
import { BottomSheet } from '../components/mobile/BottomSheet'
import { BottomNavigation } from '../components/mobile/BottomNavigation'
import { FloatingActions } from '../components/mobile/FloatingActions'
import { LayerSelector } from '../components/mobile/LayerSelector'
import { SearchBar } from '../components/mobile/SearchBar'
import { ChatOverlay } from '../components/mobile/ChatOverlay'

import {
  Thermometer, Flame, Hexagon, Globe,
  RefreshCw, MessageCircle, ChevronRight,
} from 'lucide-react'

export default function Home() {
  const { activeLayer, setActiveLayer, isChatOverlayOpen, setChatOverlayOpen } = useWeatherStore()
  const isMobile = useIsMobile()

  const [isSyncing, setIsSyncing] = useState(false)
  const [networkError, setNetworkError] = useState(false)
  const [isDark, setIsDark] = useState(false)
  const [themeLoaded, setThemeLoaded] = useState(false)

  // Open chat by default on desktop
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth > 1024) {
      setChatOverlayOpen(true)
    }
  }, [setChatOverlayOpen])

  // Persist and apply theme
  useEffect(() => {
    const saved = localStorage.getItem('geoweather-theme')
    const dark = saved === 'dark'
    setIsDark(dark)
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    setThemeLoaded(true)
  }, [])

  const handleThemeToggle = () => {
    const next = !isDark
    setIsDark(next)
    document.documentElement.setAttribute('data-theme', next ? 'dark' : 'light')
    localStorage.setItem('geoweather-theme', next ? 'dark' : 'light')
  }

  const layerOptions = [
    { id: 'scatterplot' as ActiveLayerType, label: 'Điểm trạm', icon: Thermometer },
    { id: 'heatmap' as ActiveLayerType, label: 'Bản đồ nhiệt', icon: Flame },
    { id: 'hexagon' as ActiveLayerType, label: 'H3 Hexagon 3D', icon: Hexagon },
  ]

  // Poll sync status
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
          retryMs = 3000
        }
      } catch {
        setNetworkError(true)
        retryMs = Math.min(retryMs * 2, 30000)
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
      if (!res.ok) {
        alert('Gửi lệnh đồng bộ thất bại.')
        const statusRes = await fetch(`${apiHost}/api/v1/weather/sync/status`)
        if (statusRes.ok) setIsSyncing((await statusRes.json()).is_syncing)
      }
    } catch (err) {
      console.error(err)
      alert('Lỗi kết nối khi đồng bộ thời tiết.')
      setIsSyncing(false)
    }
  }

  // ─── MOBILE LAYOUT ──────────────────────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="app-container mobile-layout">
        {/* Fullscreen map */}
        <div className="map-viewport">
          {themeLoaded && <WeatherMap isDark={isDark} />}
        </div>

        {/* Mobile Search Bar (top) */}
        <div className="mobile-search-zone">
          <SearchBar />
          <ThemeToggle isDark={isDark} onToggle={handleThemeToggle} />
        </div>

        {/* Floating Action Buttons (right side) */}
        <FloatingActions />

        {/* Layer Selector Drawer */}
        <LayerSelector />

        {/* AI Chat Overlay */}
        <ChatOverlay />

        {/* Bottom Sheet (weather detail) */}
        <BottomSheet />

        {/* Bottom Navigation */}
        <BottomNavigation />
      </div>
    )
  }

  // ─── DESKTOP / LAPTOP LAYOUT ─────────────────────────────────────────────────
  return (
    <div className="app-container">
      {/* Main Map Viewport */}
      <div className="map-viewport">
        {themeLoaded && <WeatherMap isDark={isDark} />}

        {/* Floating Header */}
        <div className="floating-header glass-panel">
          <div className="header-brand">
            <div className="brand-logo">
              <Globe className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="brand-title">GeoWeather Platform</h1>
              <p className="brand-subtitle">Hệ thống GIS &amp; Phân tích Thời tiết Real-Time</p>
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
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f97316', display: 'inline-block' }} />
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
        className={`mobile-backdrop ${!isChatOverlayOpen ? 'hidden' : ''}`}
        onClick={() => setChatOverlayOpen(false)}
      />

      {/* Theme Toggle — fixed, sits right at the left edge of the sidebar */}
      <div className={`theme-toggle-dock ${!isChatOverlayOpen ? 'chat-closed' : ''}`}>
        <ThemeToggle isDark={isDark} onToggle={handleThemeToggle} />
      </div>

      {/* Desktop Chat Toggle Button */}
      <button
        className={`chat-toggle-btn ${!isChatOverlayOpen ? 'chat-closed' : ''}`}
        onClick={() => setChatOverlayOpen(!isChatOverlayOpen)}
        title={isChatOverlayOpen ? 'Đóng khung chat' : 'Mở khung chat'}
      >
        {isChatOverlayOpen ? <ChevronRight className="w-5 h-5" /> : <MessageCircle className="w-5 h-5" />}
      </button>

      {/* Chat Sidebar (Right side) */}
      <div className={`sidebar-right ${!isChatOverlayOpen ? 'closed' : ''}`}>
        <ChatPanel />
      </div>
    </div>
  )
}
