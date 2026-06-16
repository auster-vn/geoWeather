import { create } from 'zustand'

export type ActiveLayerType = 'scatterplot' | 'heatmap' | 'hexagon'
export type BottomNavTab = 'map' | 'ai' | 'analytics' | 'settings'
export type SheetState = 'collapsed' | 'half' | 'full'

export interface RouteSegment {
  lat: number
  lon: number
  rain_risk: 'low' | 'moderate' | 'high'
  wind_risk: 'low' | 'moderate' | 'high'
}

interface WeatherState {
  // Map layer
  activeLayer: ActiveLayerType
  setActiveLayer: (layer: ActiveLayerType) => void

  // Selected location / weather detail
  selectedLocation: {
    lat: number
    lon: number
    cityName: string
    countryCode?: string
  } | null
  setSelectedLocation: (loc: { lat: number; lon: number; cityName: string; countryCode?: string } | null) => void

  // Map viewport
  mapViewport: {
    latitude: number
    longitude: number
    zoom: number
    pitch: number
  }
  setMapViewport: (viewport: { latitude: number; longitude: number; zoom: number; pitch: number }) => void

  // Mobile UI state
  activeBottomNav: BottomNavTab
  setActiveBottomNav: (tab: BottomNavTab) => void

  sheetState: SheetState
  setSheetState: (state: SheetState) => void

  isLayerDrawerOpen: boolean
  setLayerDrawerOpen: (open: boolean) => void

  isChatOverlayOpen: boolean
  setChatOverlayOpen: (open: boolean) => void

  // Route weather
  safeRoute: RouteSegment[] | null
  isFetchingRoute: boolean
  fetchSafeRoute: (originLat: number, originLon: number, destLat: number, destLon: number) => Promise<void>
}

export const useWeatherStore = create<WeatherState>((set) => ({
  // Map layer
  activeLayer: 'scatterplot',
  setActiveLayer: (layer) => set({ activeLayer: layer }),

  // Selected location
  selectedLocation: null,
  setSelectedLocation: (loc) => set({ selectedLocation: loc }),

  // Map viewport
  mapViewport: {
    latitude: 16.0,
    longitude: 106.0,
    zoom: 5.0,
    pitch: 0,
  },
  setMapViewport: (viewport) => set({ mapViewport: viewport }),

  // Mobile UI
  activeBottomNav: 'map',
  setActiveBottomNav: (tab) => set({ activeBottomNav: tab }),

  sheetState: 'collapsed',
  setSheetState: (state) => set({ sheetState: state }),

  isLayerDrawerOpen: false,
  setLayerDrawerOpen: (open) => set({ isLayerDrawerOpen: open }),

  isChatOverlayOpen: false,
  setChatOverlayOpen: (open) => set({ isChatOverlayOpen: open }),

  // Route weather
  safeRoute: null,
  isFetchingRoute: false,
  fetchSafeRoute: async (originLat, originLon, destLat, destLon) => {
    set({ isFetchingRoute: true, safeRoute: null })
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(
        `${apiHost}/api/v1/weather/route?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}&dest_lon=${destLon}`
      )
      if (res.ok) {
        const data = await res.json()
        set({ safeRoute: data.segments ?? data })
      }
    } catch (err) {
      console.error('fetchSafeRoute error:', err)
    } finally {
      set({ isFetchingRoute: false })
    }
  },
}))

