'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useWeatherStore } from '../../store/weather'
import { Send, Sparkles, Loader2, Database, MapPin, Mic } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChatWeatherChart } from './ChatWeatherChart'

interface Message {
  role: 'user' | 'assistant'
  content: string
  toolName?: string
  toolData?: any
}

export function ChatPanel() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Xin chào! Tôi là **GeoWeather Assistant**. Bạn có thể hỏi tôi thông tin thời tiết ở các địa điểm bằng ngôn ngữ tự nhiên.\n\nVí dụ: \n- *"Thời tiết Hà Nội hôm nay như thế nào?"*\n- *"Tuần tới Sài Gòn có mưa không?"*\n- *"Chỉ số UV và bụi mịn ở Đà Nẵng?"*'
    }
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [toolStatus, setToolStatus] = useState('')
  const [isListening, setIsListening] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  
  const { setSelectedLocation } = useWeatherStore()

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleLocationClick = () => {
    if (!navigator.geolocation) {
      alert("Trình duyệt của bạn không hỗ trợ định vị.")
      return
    }
    
    setIsLoading(true)
    setToolStatus("Đang lấy vị trí...")
    
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords
        const locMsg = `Thời tiết tại vị trí của tôi (lat: ${latitude.toFixed(4)}, lon: ${longitude.toFixed(4)})`
        setIsLoading(false)
        setToolStatus("")
        
        // Auto send this message
        sendMessage(locMsg)
      },
      (error) => {
        setIsLoading(false)
        setToolStatus("")
        alert("Không thể lấy vị trí: " + error.message)
      }
    )
  }

  const sendMessage = async (userMessage: string) => {
    if (!userMessage.trim() || isLoading) return

    setIsLoading(true)
    setToolStatus('')
    
    // Add user message to state
    const updatedMessages = [...messages, { role: 'user', content: userMessage } as Message]
    setMessages(updatedMessages)

    // Prepare history for API
    const history = updatedMessages.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))

    // Add empty assistant response to stream into
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'
    const eventSourceUrl = `${apiHost}/api/v1/chat/stream?message=${encodeURIComponent(userMessage)}&history_json=${encodeURIComponent(JSON.stringify(history))}`

    try {
      const eventSource = new EventSource(eventSourceUrl)
      
      let fullContent = ''
      
      eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
          eventSource.close()
          setIsLoading(false)
          setToolStatus('')
          return
        }

        try {
          const parsed = JSON.parse(event.data)
          if (parsed.type === 'text') {
            fullContent += parsed.content
            
            // Check if there is a MAP tag in the text stream, e.g. [MAP:21.0285,105.8542,10]
            const mapMatch = fullContent.match(/\[MAP:(-?\d+\.?\d*),(-?\d+\.?\d*),(\d+)\]/)
            if (mapMatch) {
              const lat = parseFloat(mapMatch[1])
              const lon = parseFloat(mapMatch[2])
              setSelectedLocation({
                lat,
                lon,
                cityName: "Tìm kiếm bản đồ"
              })
            }

            // Update the last message content
            setMessages(prev => {
              const next = [...prev]
              if (next.length > 0) {
                next[next.length - 1] = {
                  role: 'assistant',
                  content: fullContent.replace(/\[MAP:.*\]/g, '') // strip map tag from UI
                }
              }
              return next
            })
          } else if (parsed.type === 'tool_call') {
            setToolStatus(`Đang lấy dữ liệu...`)
            setMessages(prev => {
              const next = [...prev]
              if (next.length > 0) {
                next[next.length - 1] = {
                  ...next[next.length - 1],
                  toolName: parsed.tool,
                  toolData: null 
                }
              }
              return next
            })
          } else if (parsed.type === 'tool_result') {
            setToolStatus('')
            setMessages(prev => {
              const next = [...prev]
              if (next.length > 0) {
                next[next.length - 1] = {
                  ...next[next.length - 1],
                  toolData: parsed.data
                }
              }
              return next
            })
          }
        } catch (e) {
          console.error("SSE parse error", e, event.data)
        }
      }

      eventSource.onerror = (err) => {
        console.error('SSE Error:', err)
        eventSource.close()
        setIsLoading(false)
        setToolStatus('')
        setMessages(prev => {
          const next = [...prev]
          if (next.length > 0 && !next[next.length - 1].content) {
             next[next.length - 1].content = "Đã xảy ra lỗi kết nối với máy chủ."
          }
          return next
        })
      }
    } catch (err) {
      console.error(err)
      setIsLoading(false)
    }
  }

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    const userMessage = input.trim()
    setInput('')
    sendMessage(userMessage)
  }

  const toggleListening = () => {
    if (isListening) {
      setIsListening(false)
      return
    }

    const SpeechRecognition = window.SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert("Trình duyệt của bạn không hỗ trợ nhận diện giọng nói.")
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'vi-VN'
    recognition.continuous = false
    recognition.interimResults = false

    recognition.onstart = () => {
      setIsListening(true)
    }

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript
      setInput(prev => prev ? `${prev} ${transcript}` : transcript)
    }

    recognition.onerror = (event: any) => {
      console.error("Speech recognition error", event.error)
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognition.start()
  }

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-icon">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h3 className="chat-header-title">Trợ lý Weather AI</h3>
          <div className="chat-header-status">
            <span className="chat-status-dot pulse-animation" />
            <span>Trực tuyến & Sẵn sàng</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages-container">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`chat-message-row ${m.role === 'user' ? 'user' : ''}`}
          >
            <div className={`chat-bubble ${m.role === 'user' ? 'user' : 'assistant'}`}>
              {m.role === 'user' ? (
                <p>{m.content}</p>
              ) : (
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content}
                  </ReactMarkdown>
                  {m.toolData && m.toolName === 'get_rain_forecast' && (
                    <ChatWeatherChart data={m.toolData} />
                  )}
                </div>
              )}
              
              {m.content === '' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 0', color: 'var(--text-secondary)' }}>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{toolStatus || 'Đang suy nghĩ...'}</span>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Form Input */}
      <form onSubmit={handleSend} className="chat-input-form">
        <div className="chat-input-wrapper">
          <button
            type="button"
            onClick={handleLocationClick}
            disabled={isLoading}
            className="chat-btn-location"
            title="Dùng vị trí hiện tại"
            style={{ 
              background: 'rgba(255,255,255,0.1)', 
              border: '1px solid rgba(255,255,255,0.2)', 
              borderRadius: '8px',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--text-primary)',
              marginRight: '6px'
            }}
          >
            <MapPin className="w-4 h-4" />
          </button>
          
          <button
            type="button"
            onClick={toggleListening}
            disabled={isLoading}
            className={`chat-btn-mic ${isListening ? 'listening' : ''}`}
            title="Hỏi bằng giọng nói"
            style={{ 
              background: isListening ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255,255,255,0.1)', 
              border: `1px solid ${isListening ? 'rgba(239, 68, 68, 0.5)' : 'rgba(255,255,255,0.2)'}`, 
              borderRadius: '8px',
              padding: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: isListening ? '#ef4444' : 'var(--text-primary)',
              marginRight: '6px',
              transition: 'all 0.3s'
            }}
          >
            <Mic className={`w-4 h-4 ${isListening ? 'animate-pulse' : ''}`} />
          </button>

          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Hỏi thời tiết (ví dụ: Hanoi)..."
            disabled={isLoading}
            className="chat-input-field"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="chat-btn-send"
            title="Gửi câu hỏi"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
        <p className="chat-footer-text">
          Hỗ trợ Tiếng Việt & English • Tự động hiển thị trên bản đồ
        </p>
      </form>
    </div>
  )
}
