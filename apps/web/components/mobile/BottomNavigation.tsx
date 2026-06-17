'use client'

import { useWeatherStore, BottomNavTab } from '../../store/weather'

const TABS: { id: BottomNavTab; label: string; icon: string }[] = [
  { id: 'map',       label: 'Bản đồ',    icon: '🗺️' },
  { id: 'ai',        label: 'AI',        icon: '🤖' },
  { id: 'analytics', label: 'Thống kê',  icon: '📊' },
  { id: 'settings',  label: 'Cài đặt',   icon: '⚙️' },
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
      {TABS.map((tab) => (
        <button
          key={tab.id}
          id={`nav-tab-${tab.id}`}
          className={`mobile-nav-btn ${activeBottomNav === tab.id ? 'active' : ''}`}
          onClick={() => handleTab(tab.id)}
          aria-current={activeBottomNav === tab.id ? 'page' : undefined}
        >
          <span className="mobile-nav-icon">{tab.icon}</span>
          <span className="mobile-nav-label">{tab.label}</span>
          {activeBottomNav === tab.id && <span className="mobile-nav-indicator" />}
        </button>
      ))}
    </nav>
  )
}
