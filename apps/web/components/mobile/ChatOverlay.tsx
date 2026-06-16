'use client'

import { useRef, useEffect } from 'react'
import { useWeatherStore } from '../../store/weather'
import { ChatPanel } from '../panels/ChatPanel'
import { X, ChevronDown } from 'lucide-react'

const SUGGESTED_PROMPTS = [
  'Ngày mai có mưa không?',
  'UV hôm nay thế nào?',
  'Tuyến đường nào ít mưa nhất?',
  'Nhiệt độ Hà Nội hôm nay?',
  'Thời tiết Đà Nẵng cuối tuần?',
]

export function ChatOverlay() {
  const { isChatOverlayOpen, setChatOverlayOpen, setActiveBottomNav } = useWeatherStore()
  const overlayRef = useRef<HTMLDivElement>(null)

  // Trap scroll inside overlay
  useEffect(() => {
    if (!isChatOverlayOpen) return
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [isChatOverlayOpen])

  const handleClose = () => {
    setChatOverlayOpen(false)
    setActiveBottomNav('map')
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`chat-overlay-backdrop ${isChatOverlayOpen ? 'visible' : ''}`}
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={overlayRef}
        className={`chat-overlay-panel ${isChatOverlayOpen ? 'open' : ''}`}
        role="dialog"
        aria-label="AI Weather Chat"
        aria-modal="true"
      >
        {/* Handle */}
        <div className="sheet-drag-handle" style={{ margin: '12px auto 4px' }} />

        {/* Header */}
        <div className="chat-overlay-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="chat-header-icon">
              <span style={{ fontSize: 18 }}>🤖</span>
            </div>
            <div>
              <p className="chat-header-title">Trợ lý Weather AI</p>
              <div className="chat-header-status">
                <span className="chat-status-dot pulse-animation" />
                <span>Sẵn sàng hỗ trợ</span>
              </div>
            </div>
          </div>
          <button className="btn-close" onClick={handleClose} aria-label="Đóng chat">
            <ChevronDown className="w-5 h-5" />
          </button>
        </div>

        {/* Suggested prompts — shown as pill chips above the chat */}
        <div className="chat-overlay-prompts">
          {SUGGESTED_PROMPTS.map((p) => (
            <button
              key={p}
              className="chat-prompt-chip"
              onClick={() => {
                // Dispatch to ChatPanel via custom event
                window.dispatchEvent(new CustomEvent('geoweather:chat-prompt', { detail: p }))
              }}
            >
              {p}
            </button>
          ))}
        </div>

        {/* The actual chat panel */}
        <div className="chat-overlay-body">
          <ChatPanel />
        </div>
      </div>
    </>
  )
}
