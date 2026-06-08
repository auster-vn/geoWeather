import { create } from 'zustand'

export type ActiveLayerType = 'scatterplot' | 'heatmap' | 'hexagon'

interface WeatherState {
  activeLayer: ActiveLayerType
  setActiveLayer: (layer: ActiveLayerType) => void
  
  selectedLocation: {
    lat: number
    lon: number
    cityName: string
    countryCode?: string
  } | null
  setSelectedLocation: (loc: { lat: number; lon: number; cityName: string; countryCode?: string } | null) => void
  
  mapViewport: {
    latitude: number
    longitude: number
    zoom: number
    pitch: number
  }
  setMapViewport: (viewport: { latitude: number; longitude: number; zoom: number; pitch: number }) => void

  activeRoute: any | null
  setActiveRoute: (route: any | null) => void
  fetchSafeRoute: (olat: number, olon: number, dlat: number, dlon: number) => Promise<void>
}

export const useWeatherStore = create<WeatherState>((set) => ({
  activeLayer: 'scatterplot',
  setActiveLayer: (layer) => set({ activeLayer: layer }),
  
  selectedLocation: null,
  setSelectedLocation: (loc) => set({ selectedLocation: loc }),
  
  mapViewport: {
    latitude: 20.0,
    longitude: 0.0,
    zoom: 2.0,
    pitch: 0
  },
  setMapViewport: (viewport) => set({ mapViewport: viewport }),

  activeRoute: null,
  setActiveRoute: (route) => set({ activeRoute: route }),
  fetchSafeRoute: async (olat, olon, dlat, dlon) => {
    try {
      const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      const res = await fetch(`${url}/api/v1/routing/safe-route?olat=${olat}&olon=${olon}&dlat=${dlat}&dlon=${dlon}`)
      const data = await res.json()
      if (data.status === "success" && data.best_route) {
        set({ activeRoute: data.best_route })
      }
    } catch (e) {
      console.error("Failed to fetch safe route", e)
    }
  }
}))
