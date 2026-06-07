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
  setMapViewport: (viewport) => set({ mapViewport: viewport })
}))
