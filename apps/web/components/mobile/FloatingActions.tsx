'use client'

import { useState } from 'react'
import { useWeatherStore } from '../../store/weather'
import { Navigation2, Bot, Layers } from 'lucide-react'

export function FloatingActions() {
  const { setChatOverlayOpen, setActiveBottomNav, setLayerDrawerOpen } = useWeatherStore()
  const [expanded, setExpanded] = useState(false)

  const handleGPS = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        useWeatherStore.getState().setSelectedLocation({
          lat: coords.latitude,
          lon: coords.longitude,
          cityName: 'Vị trí của tôi',
        })
      },
      () => alert('Không thể lấy vị trí GPS.')
    )
  }

  const actions = [
    {
      id: 'gps',
      icon: <Navigation2 className="w-5 h-5" />,
      label: 'GPS',
      color: '#22c55e',
      onClick: handleGPS,
    },
    {
      id: 'ai',
      icon: <Bot className="w-5 h-5" />,
      label: 'AI Chat',
      color: '#38bdf8',
      onClick: () => { setChatOverlayOpen(true); setActiveBottomNav('ai') },
    },
    {
      id: 'layers',
      icon: <Layers className="w-5 h-5" />,
      label: 'Layers',
      color: '#f59e0b',
      onClick: () => setLayerDrawerOpen(true),
    },
  ]

  return (
    <div className="floating-actions-container">
      {/* Sub-actions (shown when expanded) */}
      {actions.map((action, i) => (
        <button
          key={action.id}
          id={`fab-${action.id}`}
          className={`fab-action ${expanded ? 'visible' : ''}`}
          style={{
            transitionDelay: expanded ? `${i * 60}ms` : `${(actions.length - i - 1) * 40}ms`,
            background: action.color,
          }}
          onClick={() => { action.onClick(); setExpanded(false) }}
          aria-label={action.label}
          title={action.label}
        >
          {action.icon}
          <span className="fab-label">{action.label}</span>
        </button>
      ))}

      {/* Main FAB toggle */}
      <button
        id="fab-main"
        className={`fab-main ${expanded ? 'open' : ''}`}
        onClick={() => setExpanded(!expanded)}
        aria-label={expanded ? 'Đóng menu' : 'Mở menu nhanh'}
        aria-expanded={expanded}
      >
        <svg
          className={`fab-plus-icon ${expanded ? 'rotated' : ''}`}
          width="22" height="22" viewBox="0 0 22 22" fill="none"
        >
          <path d="M11 4V18M4 11H18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  )
}
