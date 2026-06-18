'use client'

import { useWeatherStore, BottomNavTab } from '../../store/weather'
import { Map, Sparkles, BarChart3, Settings, LucideIcon } from 'lucide-react'

const TABS: { id: BottomNavTab; label: string; icon: LucideIcon }[] = [
  { id: 'map',       label: 'Bản đồ',    icon: Map },
  { id: 'ai',        label: 'AI',        icon: Sparkles },
  { id: 'analytics', label: 'Thống kê',  icon: BarChart3 },
  { id: 'settings',  label: 'Cài đặt',   icon: Settings },
]

export function BottomNavigation() {
  const { activeBottomNav, setActiveBottomNav, setChatOverlayOpen, setSheetState, selectedLocation } = useWeatherStore()

  const handleTab = (id: BottomNavTab) => {
    setActiveBottomNav(id)
    if (id === 'ai') {
      setChatOverlayOpen(true)
    } else {
      setChatOverlayOpen(false)
    }
    if (id === 'analytics') {
      setSheetState('full')
    }
    if (id === 'map') {
      if (!selectedLocation) {
        setSheetState('collapsed')
      }
    }
  }

  return (
    <nav className="mobile-bottom-nav" aria-label="Navigation">
      {TABS.map((tab) => {
        const Icon = tab.icon
        return (
          <button
            key={tab.id}
            id={`nav-tab-${tab.id}`}
            className={`mobile-nav-btn ${activeBottomNav === tab.id ? 'active' : ''}`}
            onClick={() => handleTab(tab.id)}
            aria-current={activeBottomNav === tab.id ? 'page' : undefined}
          >
            <span className="mobile-nav-icon">
              <Icon size={20} strokeWidth={2} />
            </span>
            <span className="mobile-nav-label">{tab.label}</span>
            {activeBottomNav === tab.id && <span className="mobile-nav-indicator" />}
          </button>
        )
      })}
    </nav>
  )
}

