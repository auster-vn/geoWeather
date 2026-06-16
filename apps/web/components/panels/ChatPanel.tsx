'use client'

import React, { useState, useRef, useEffect } from 'react'
import { useWeatherStore } from '../../store/weather'
import { Send, Sparkles, Loader2, Database, MapPin, Mic, ChevronDown, Check, Volume2, VolumeX } from 'lucide-react'
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
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null)
  const [selectedModel, setSelectedModel] = useState<'local' | 'gemini'>('local')
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null)
  const setSelectedLocation = useWeatherStore((state) => state.setSelectedLocation)
  const fetchSafeRoute = useWeatherStore((state) => state.fetchSafeRoute)
  const [isModelSelectorOpen, setIsModelSelectorOpen] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const modelSelectorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (modelSelectorRef.current && !modelSelectorRef.current.contains(event.target as Node)) {
        setIsModelSelectorOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  // Stop speaking when component unmounts
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const speakText = (text: string, index: number) => {
    if (!window.speechSynthesis) {
      alert("Trình duyệt của bạn không hỗ trợ đọc giọng nói.")
      return
    }

    if (speakingIndex === index) {
      // Toggle stop
      window.speechSynthesis.cancel()
      setSpeakingIndex(null)
      return
    }

    // Stop currently speaking
    window.speechSynthesis.cancel()

    // Strip markdown formatting for cleaner speech
    const cleanText = text
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/\[MAP:.*?\]/g, '')
      .replace(/\[ROUTE:.*?\]/g, '')
      .replace(/#/g, '')
      .replace(/`/g, '')
      .replace(/_FETCHED_ROUTE/g, '')

    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.lang = 'vi-VN'
    utterance.rate = 1.0
    utterance.pitch = 1.0

    utterance.onend = () => {
      setSpeakingIndex(null)
    }
    
    utterance.onerror = () => {
      setSpeakingIndex(null)
    }

    setSpeakingIndex(index)
    window.speechSynthesis.speak(utterance)
  }
  


  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Listen for suggested prompt clicks from ChatOverlay
  useEffect(() => {
    const handler = (e: Event) => {
      const prompt = (e as CustomEvent<string>).detail
      if (prompt && !isLoading) {
        setInput('')
        sendMessage(prompt)
      }
    }
    window.addEventListener('geoweather:chat-prompt', handler)
    return () => window.removeEventListener('geoweather:chat-prompt', handler)
  }, [isLoading]) // eslint-disable-line react-hooks/exhaustive-deps

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
    const eventSourceUrl = `${apiHost}/api/v1/chat/stream?message=${encodeURIComponent(userMessage)}&history_json=${encodeURIComponent(JSON.stringify(history))}&model=${selectedModel}`

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

            // Check if there is a ROUTE tag in the text stream, e.g. [ROUTE:olat,olon,dlat,dlon]
            const routeMatch = fullContent.match(/\[ROUTE:(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*)\]/)
            if (routeMatch && !fullContent.includes('_FETCHED_ROUTE')) {
              const olat = parseFloat(routeMatch[1])
              const olon = parseFloat(routeMatch[2])
              const dlat = parseFloat(routeMatch[3])
              const dlon = parseFloat(routeMatch[4])
              
              // Only call it once per stream
              fullContent += '_FETCHED_ROUTE' 
              
              fetchSafeRoute(olat, olon, dlat, dlon)
            }

            // Update the last message content
            setMessages(prev => {
              const next = [...prev]
              if (next.length > 0) {
                next[next.length - 1] = {
                  role: 'assistant',
                  content: fullContent.replace(/\[MAP:.*\]/g, '').replace(/\[ROUTE:.*\]/g, '').replace(/_FETCHED_ROUTE/g, '') // strip map/route tags from UI
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
            if (parsed.data && parsed.data.lat !== undefined && parsed.data.lon !== undefined) {
              setSelectedLocation({
                lat: parsed.data.lat,
                lon: parsed.data.lon,
                cityName: parsed.data.city_name || parsed.data.place_name || "Địa điểm"
              })
            }
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
          } else if (parsed.type === 'location_resolved') {
            if (parsed.lat !== undefined && parsed.lon !== undefined) {
              setSelectedLocation({
                lat: parsed.lat,
                lon: parsed.lon,
                cityName: parsed.city_name || "Địa điểm"
              })
              
              // Fetch current weather details for this resolved location to render card inside chat
              const weatherApiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
              fetch(`${weatherApiHost}/api/v1/weather/nearest/${parsed.lat}/${parsed.lon}`)
                .then(res => res.json())
                .then(weatherData => {
                  setMessages(prev => {
                    const next = [...prev]
                    if (next.length > 0) {
                      next[next.length - 1] = {
                        ...next[next.length - 1],
                        toolName: 'get_weather_by_coords',
                        toolData: {
                          ...weatherData,
                          city_name: parsed.city_name || weatherData.city_name || "Địa điểm",
                          lat: parsed.lat,
                          lon: parsed.lon
                        }
                      }
                    }
                    return next
                  })
                })
                .catch(err => console.error("Failed to fetch weather for resolved location", err))
            }
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

  const toggleListening = async () => {
    if (isListening && mediaRecorder) {
      mediaRecorder.stop()
      setIsListening(false)
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const audioChunks: Blob[] = []

      recorder.ondataavailable = (event) => {
        audioChunks.push(event.data)
      }

      recorder.onstop = async () => {
        setIsLoading(true)
        setToolStatus('Đang xử lý giọng nói...')
        try {
          const webmBlob = new Blob(audioChunks)
          const arrayBuffer = await webmBlob.arrayBuffer()
          
          const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
          const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)
          
          // Encode to WAV (Python speech_recognition requires WAV/FLAC)
          const numOfChan = audioBuffer.numberOfChannels
          const length = audioBuffer.length * numOfChan * 2 + 44
          const bufferArray = new ArrayBuffer(length)
          const view = new DataView(bufferArray)
          const channels = []
          let sample, offset = 0, pos = 0;
        
          const setUint16 = (data: number) => { view.setUint16(pos, data, true); pos += 2; }
          const setUint32 = (data: number) => { view.setUint32(pos, data, true); pos += 4; }
        
          setUint32(0x46464952); // "RIFF"
          setUint32(length - 8); // file length - 8
          setUint32(0x45564157); // "WAVE"
          setUint32(0x20746d66); // "fmt " chunk
          setUint32(16); // length = 16
          setUint16(1); // PCM
          setUint16(numOfChan);
          setUint32(audioBuffer.sampleRate);
          setUint32(audioBuffer.sampleRate * 2 * numOfChan); // avg. bytes/sec
          setUint16(numOfChan * 2); // block-align
          setUint16(16); // 16-bit
          setUint32(0x61746164); // "data" chunk
          setUint32(length - pos - 4); // chunk length
          
          for (let i = 0; i < audioBuffer.numberOfChannels; i++) {
            channels.push(audioBuffer.getChannelData(i));
          }
          
          while (pos < length) {
            for (let i = 0; i < numOfChan; i++) {
              sample = Math.max(-1, Math.min(1, channels[i][offset]));
              sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
              view.setInt16(pos, sample, true);
              pos += 2;
            }
            offset++;
          }
          
          const wavBlob = new Blob([bufferArray], { type: 'audio/wav' })
          
          const formData = new FormData()
          // chat.py endpoint expects file parameter named "audio"
          formData.append('audio', wavBlob, 'voice.wav')
          
          const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const res = await fetch(`${apiHost}/api/v1/chat/transcribe`, {
            method: 'POST',
            body: formData
          })
          
          if (!res.ok) throw new Error('Voice API failed')
          const data = await res.json()
          
          if (data.text) {
             sendMessage(data.text)
          } else if (data.error) {
             alert(data.error)
          }
        } catch (err: any) {
          console.error(err)
          alert("Lỗi nhận diện giọng nói: " + err.message)
        } finally {
          setIsLoading(false)
          setToolStatus('')
          stream.getTracks().forEach(track => track.stop())
        }
      }

      recorder.start()
      setMediaRecorder(recorder)
      setIsListening(true)
    } catch (err) {
      console.error(err)
      alert("Không thể truy cập microphone.")
    }
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
        {/* Model Selector Dropdown */}
        <div className="model-selector-container" ref={modelSelectorRef}>
          <button 
            onClick={() => setIsModelSelectorOpen(!isModelSelectorOpen)}
            className="model-selector-btn"
          >
            {selectedModel === 'gemini' ? 'Gemini Flash' : 'Local AI'}
            <ChevronDown className="model-selector-chevron" />
          </button>
          
          {isModelSelectorOpen && (
            <div className="model-selector-dropdown">
              <div className="model-selector-dropdown-inner">
                
                {/* Local NLP Option */}
                <button
                  onClick={() => { setSelectedModel('local'); setIsModelSelectorOpen(false); }}
                  className="model-selector-option"
                >
                  <div className="model-selector-check-container">
                    {selectedModel === 'local' && <Check className="model-selector-check" />}
                  </div>
                  <div className="model-selector-option-content">
                    <div className="model-selector-option-header">
                      <span className="model-selector-option-title">Local AI</span>
                      <span className="model-selector-badge local">Nhanh</span>
                    </div>
                    <p className="model-selector-option-desc">Phân tích siêu tốc & Offline</p>
                  </div>
                </button>

                {/* Gemini Option */}
                <button
                  onClick={() => { setSelectedModel('gemini'); setIsModelSelectorOpen(false); }}
                  className="model-selector-option"
                >
                  <div className="model-selector-check-container">
                    {selectedModel === 'gemini' && <Check className="model-selector-check" />}
                  </div>
                  <div className="model-selector-option-content">
                    <div className="model-selector-option-header">
                      <span className="model-selector-option-title">2.5 Flash</span>
                      <span className="model-selector-badge gemini">Mới</span>
                    </div>
                    <p className="model-selector-option-desc">Trợ giúp toàn diện</p>
                  </div>
                </button>

              </div>
            </div>
          )}
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
                  {m.toolData && (m.toolName === 'get_weather_by_city' || m.toolName === 'get_weather_by_coords') && (
                    <div className="chat-weather-dashboard-card" style={{
                      marginTop: '12px',
                      background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(16, 185, 129, 0.1))',
                      border: '1px solid var(--border-color)',
                      borderRadius: '16px',
                      padding: '16px',
                      color: 'var(--text-primary)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>
                          📍 {m.toolData.city_name || m.toolData.place_name || "Địa điểm"}
                        </h4>
                        <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                          {m.toolData.lat?.toFixed(2)}°, {m.toolData.lon?.toFixed(2)}°
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                        <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--accent-primary)' }}>
                          {m.toolData.temperature !== undefined ? `${m.toolData.temperature?.toFixed(1)}°C` : '--'}
                        </div>
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 600 }}>{m.toolData.condition || 'Ổn định'}</div>
                          {m.toolData.feels_like !== undefined && (
                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                              Cảm giác như: {m.toolData.feels_like?.toFixed(1)}°C
                            </div>
                          )}
                        </div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          💨 Gió: <strong style={{ color: 'var(--text-primary)' }}>{m.toolData.wind_speed !== undefined ? `${m.toolData.wind_speed?.toFixed(1)} m/s` : '--'}</strong>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          💧 Độ ẩm: <strong style={{ color: 'var(--text-primary)' }}>{m.toolData.humidity !== undefined ? `${m.toolData.humidity?.toFixed(0)}%` : '--'}</strong>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          🌧️ Mưa: <strong style={{ color: 'var(--text-primary)' }}>{m.toolData.precipitation !== undefined ? `${m.toolData.precipitation?.toFixed(1)} mm` : '--'}</strong>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          ☁️ Mây: <strong style={{ color: 'var(--text-primary)' }}>{m.toolData.cloud_cover !== undefined ? m.toolData.cloud_cover : '--'}</strong>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {m.content === '' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 0', color: 'var(--text-secondary)' }}>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{toolStatus || 'Đang suy nghĩ...'}</span>
                </div>
              )}

              {/* TTS Button */}
              {m.role === 'assistant' && m.content && (
                <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
                  <button 
                    onClick={() => speakText(m.content, idx)}
                    style={{ 
                      background: 'rgba(255,255,255,0.1)', 
                      border: 'none', 
                      borderRadius: '50%', 
                      padding: '6px', 
                      cursor: 'pointer',
                      color: speakingIndex === idx ? '#3b82f6' : 'var(--text-secondary)',
                      transition: 'all 0.2s'
                    }}
                    title={speakingIndex === idx ? "Dừng phát âm" : "Phát âm"}
                  >
                    {speakingIndex === idx ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                  </button>
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
