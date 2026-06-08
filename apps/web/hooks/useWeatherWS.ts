import { useEffect, useState, useRef } from 'react'

export interface LiveWeatherUpdate {
  h3_index_r4: string
  window_start: string
  window_end: string
  avg_temperature: number
  max_wind_speed: number
  total_precip: number
  avg_humidity: number
  observation_count: number
}

export function useWeatherWS(h3Index: string | null) {
  const [data, setData] = useState<LiveWeatherUpdate | null>(null)
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected')
  const [error, setError] = useState<string | null>(null)
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectDelayRef = useRef(1000) // Initial delay 1s

  useEffect(() => {
    if (!h3Index) {
      setStatus('disconnected')
      return
    }

    const connect = () => {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const wsUrl = `${apiHost.replace('http', 'ws')}/ws/weather/${h3Index}`
      
      setStatus('connecting')
      setError(null)

      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          setStatus('connected')
          reconnectDelayRef.current = 1000 // Reset backoff
          logger("WebSocket connected to H3 cell: " + h3Index)
        }

        ws.onmessage = (event) => {
          try {
            if (event.data === "pong") return
            const update = JSON.parse(event.data)
            setData(update)
          } catch (e) {
            console.warn("Failed to parse websocket update:", e)
          }
        }

        ws.onerror = (e) => {
          setError("WebSocket connection error occurred")
          console.warn("WebSocket error:", e)
        }

        ws.onclose = () => {
          setStatus('disconnected')
          // Trigger reconnect with exponential backoff
          const delay = reconnectDelayRef.current
          reconnectDelayRef.current = Math.min(30000, delay * 2) // max 30s
          
          reconnectTimeoutRef.current = setTimeout(() => {
            logger("Attempting WebSocket reconnect...")
            connect()
          }, delay)
        }
      } catch (err) {
        setError("Failed to create WebSocket instance")
        setStatus('disconnected')
      }
    };

    connect()

    // Ping interval to keep connection alive
    const pingInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping")
      }
    }, 15000)

    return () => {
      clearInterval(pingInterval)
      if (wsRef.current) {
        wsRef.current.onclose = null // Prevents reconnect loop on unmount
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [h3Index])

  const logger = (msg: string) => {
    console.log(`[GeoWeatherWS] ${msg}`)
  }

  return { data, status, error }
}
