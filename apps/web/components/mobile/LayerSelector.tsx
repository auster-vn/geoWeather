'use client'

import { useWeatherStore, ActiveLayerType } from '../../store/weather'
import { X, Thermometer, CloudRain, Droplets, Wind, Flame, Hexagon, Radio } from 'lucide-react'

interface LayerOption {
  id: ActiveLayerType | string
  label: string
  icon: React.ReactNode
  color: string
  desc: string
}

const LAYERS: LayerOption[] = [
  { id: 'scatterplot', label: 'Nhiệt độ', icon: <Thermometer className="w-5 h-5" />, color: '#ef4444', desc: 'Điểm trạm' },
  { id: 'heatmap',     label: 'Heatmap',   icon: <Flame className="w-5 h-5" />,       color: '#f97316', desc: 'Bản đồ nhiệt' },
  { id: 'hexagon',     label: 'H3 Grid',   icon: <Hexagon className="w-5 h-5" />,     color: '#a855f7', desc: '3D Hexagon' },
  { id: 'rain',        label: 'Mưa',       icon: <CloudRain className="w-5 h-5" />,   color: '#3b82f6', desc: 'Lượng mưa' },
  { id: 'humidity',    label: 'Độ ẩm',     icon: <Droplets className="w-5 h-5" />,    color: '#06b6d4', desc: 'Độ ẩm KK' },
  { id: 'wind',        label: 'Gió',        icon: <Wind className="w-5 h-5" />,        color: '#22c55e', desc: 'Tốc độ gió' },
  { id: 'stations',    label: 'Trạm đo',   icon: <Radio className="w-5 h-5" />,       color: '#38bdf8', desc: 'Realtime' },
]

export function LayerSelector() {
  const { isLayerDrawerOpen, setLayerDrawerOpen, activeLayer, setActiveLayer } = useWeatherStore()

  const handleSelect = (id: string) => {
    // Only apply known layer types to the map
    const known: ActiveLayerType[] = ['scatterplot', 'heatmap', 'hexagon']
    if (known.includes(id as ActiveLayerType)) {
      setActiveLayer(id as ActiveLayerType)
    }
    setLayerDrawerOpen(false)
  }

  if (!isLayerDrawerOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="layer-selector-backdrop"
        onClick={() => setLayerDrawerOpen(false)}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div className="layer-selector-drawer" role="dialog" aria-label="Chọn lớp bản đồ">
        {/* Handle */}
        <div className="sheet-drag-handle" style={{ margin: '12px auto 0' }} />

        {/* Header */}
        <div className="layer-selector-header">
          <h3 className="layer-selector-title">Lớp bản đồ</h3>
          <button
            className="btn-close"
            onClick={() => setLayerDrawerOpen(false)}
            aria-label="Đóng"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Grid */}
        <div className="layer-selector-grid">
          {LAYERS.map((layer) => {
            const isActive = activeLayer === layer.id
            return (
              <button
                key={layer.id}
                id={`layer-${layer.id}`}
                className={`layer-selector-item ${isActive ? 'active' : ''}`}
                onClick={() => handleSelect(layer.id)}
                style={isActive ? { borderColor: layer.color, background: `${layer.color}18` } : {}}
              >
                <div
                  className="layer-selector-icon"
                  style={{ color: isActive ? layer.color : undefined, background: isActive ? `${layer.color}22` : undefined }}
                >
                  {layer.icon}
                </div>
                <span className="layer-selector-name">{layer.label}</span>
                <span className="layer-selector-desc">{layer.desc}</span>
              </button>
            )
          })}
        </div>
      </div>
    </>
  )
}
