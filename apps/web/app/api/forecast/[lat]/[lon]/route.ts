/**
 * Vercel API Route: /api/forecast/[lat]/[lon]
 *
 * Proxies the Open-Meteo forecast request from Vercel's Edge network
 * instead of from Render's shared IP (which hits Open-Meteo's daily IP quota).
 *
 * Caching strategy:
 *   - Vercel CDN caches the response for 1 hour (s-maxage=3600)
 *   - Stale-while-revalidate for 2 hours extra (background refresh)
 *   - Forecast data changes slowly — 1h freshness is more than adequate
 */

import { NextRequest, NextResponse } from 'next/server'

const OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'
const USER_AGENT = 'GeoWeather/1.0 (vercel-proxy; contact: phutc04@gmail.com)'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ lat: string; lon: string }> }
) {
  const { lat, lon } = await params
  const latNum = parseFloat(lat)
  const lonNum = parseFloat(lon)

  if (isNaN(latNum) || isNaN(lonNum)) {
    return NextResponse.json({ error: 'Invalid coordinates' }, { status: 400 })
  }

  const searchParams = new URLSearchParams({
    latitude: latNum.toString(),
    longitude: lonNum.toString(),
    hourly: 'precipitation_probability,precipitation,weather_code,temperature_2m',
    daily: 'sunrise,sunset,precipitation_sum,precipitation_hours,weather_code,temperature_2m_max,temperature_2m_min,uv_index_max',
    forecast_days: '7',
    timezone: 'Asia/Bangkok',
  })

  const url = `${OPEN_METEO_URL}?${searchParams.toString()}`

  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT },
      // next.js fetch cache: revalidate every hour
      next: { revalidate: 3600 },
    })

    if (!res.ok) {
      const errorText = await res.text()
      console.error(`[forecast-proxy] Open-Meteo error ${res.status}:`, errorText)
      return NextResponse.json(
        { error: true, reason: errorText, status: res.status },
        { status: res.status }
      )
    }

    const data = await res.json()

    return NextResponse.json(data, {
      headers: {
        // Tell Vercel CDN to cache for 1h, serve stale up to 2h during revalidation
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=7200',
        'X-Forecast-Source': 'open-meteo-via-vercel',
      },
    })
  } catch (err) {
    console.error('[forecast-proxy] fetch failed:', err)
    return NextResponse.json(
      { error: true, reason: String(err) },
      { status: 503 }
    )
  }
}
