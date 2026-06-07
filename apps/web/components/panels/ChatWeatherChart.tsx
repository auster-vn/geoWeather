import React from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export function ChatWeatherChart({ data }: { data: any }) {
  if (!data || !data.hourly_forecast) return null;

  // Take the next 12 hours for a clean chart
  const chartData = data.hourly_forecast.slice(0, 12).map((h: any) => {
    // Format "YYYY-MM-DD HH:MM:SS" -> "HH:00"
    const timeStr = h.time.split(" ")[1] || "";
    const hour = timeStr.split(":")[0];
    
    return {
      time: `${hour}:00`,
      temp: parseFloat(h.temperature),
      rain: parseFloat(h.precipitation_probability),
      rain_mm: parseFloat(h.precipitation_mm)
    }
  })

  return (
    <div className="mt-3 mb-2 p-3 bg-slate-800/50 rounded-xl border border-slate-700/50">
      <div className="text-xs text-slate-400 mb-2 font-medium uppercase tracking-wider">
        Dự báo 12 giờ tới ({data.city})
      </div>
      <div className="h-32 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis dataKey="time" stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
              itemStyle={{ color: '#f8fafc' }}
            />
            <Area type="monotone" dataKey="temp" name="Nhiệt độ (°C)" stroke="#10b981" fillOpacity={1} fill="url(#colorTemp)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
