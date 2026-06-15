'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  isDark: boolean
  onToggle: () => void
}

export function ThemeToggle({ isDark, onToggle }: Props) {
  const [animating, setAnimating] = useState(false)

  const handleClick = () => {
    if (animating) return
    setAnimating(true)
    onToggle()
    setTimeout(() => setAnimating(false), 900)
  }

  return (
    <>
      {/* Minimal circular button */}
      <button
        id="theme-toggle-btn"
        onClick={handleClick}
        title={isDark ? 'Chuyển sang sáng' : 'Chuyển sang tối'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '44px',
          height: '44px',
          borderRadius: '50%',
          border: `1px solid ${isDark ? 'rgba(255,255,255,0.15)' : 'rgba(14,165,233,0.3)'}`,
          background: isDark
            ? 'rgba(30,41,59,0.7)'
            : 'rgba(255,255,255,0.75)',
          backdropFilter: 'blur(8px)',
          cursor: animating ? 'default' : 'pointer',
          transition: 'all 0.3s ease',
          boxShadow: isDark
            ? '0 2px 12px rgba(0,0,0,0.3)'
            : '0 2px 12px rgba(14,165,233,0.15)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: '18px', lineHeight: 1, transition: 'transform 0.4s ease', transform: animating ? 'scale(1.3) rotate(20deg)' : 'scale(1)' }}>
          {isDark ? '🌙' : '☀️'}
        </span>
      </button>

      {/* Full-screen sweep overlay */}
      {animating && <SweepOverlay toLight={isDark} />}
    </>
  )
}

/** A sun or moon that sweeps diagonally across the whole viewport */
function SweepOverlay({ toLight }: { toLight: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>()
  const startRef = useRef<number | null>(null)
  const DURATION = 850 // ms

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight

    const W = canvas.width
    const H = canvas.height
    // travel from top-left off-screen to bottom-right off-screen
    const DIAG = Math.sqrt(W * W + H * H)

    const draw = (t: number) => {
      // t: 0→1 (eased)
      const ctx = canvas.getContext('2d')!
      ctx.clearRect(0, 0, W, H)

      // Body position: move along diagonal
      const ease = t < 0.5
        ? 4 * t * t * t
        : 1 - Math.pow(-2 * t + 2, 3) / 2
      const x = -150 + (W + 300) * ease
      const y = -100 + (H + 200) * ease

      if (toLight) {
        // ── Sun sweeps in ─────────────────────────────────
        // Wide glow
        const glow = ctx.createRadialGradient(x, y, 0, x, y, 280)
        glow.addColorStop(0, `rgba(255,230,80,${0.35 * Math.sin(Math.PI * t)})`)
        glow.addColorStop(0.5, `rgba(255,200,50,${0.15 * Math.sin(Math.PI * t)})`)
        glow.addColorStop(1, 'rgba(255,200,50,0)')
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(x, y, 280, 0, Math.PI * 2)
        ctx.fill()

        // Sun disk
        const sunR = 48
        const sunGrad = ctx.createRadialGradient(x, y, 0, x, y, sunR)
        sunGrad.addColorStop(0, '#fff7c0')
        sunGrad.addColorStop(0.6, '#FFD700')
        sunGrad.addColorStop(1, '#FF8C00')
        ctx.fillStyle = sunGrad
        ctx.beginPath()
        ctx.arc(x, y, sunR, 0, Math.PI * 2)
        ctx.fill()

        // Rays
        const rayCount = 12
        ctx.save()
        ctx.translate(x, y)
        const rot = t * Math.PI * 0.5
        ctx.rotate(rot)
        ctx.strokeStyle = `rgba(255,220,60,${0.6 * Math.sin(Math.PI * t)})`
        ctx.lineWidth = 2.5
        for (let i = 0; i < rayCount; i++) {
          const angle = (i / rayCount) * Math.PI * 2
          const inner = sunR + 8
          const outer = sunR + 24 + 8 * Math.sin(t * Math.PI * 3 + i)
          ctx.beginPath()
          ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner)
          ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer)
          ctx.stroke()
        }
        ctx.restore()

        // Trailing light sweep
        const sweep = ctx.createLinearGradient(x - 200, y - 200, x + 200, y + 200)
        sweep.addColorStop(0, `rgba(255,245,150,${0.12 * Math.sin(Math.PI * t)})`)
        sweep.addColorStop(1, 'rgba(255,245,150,0)')
        ctx.fillStyle = sweep
        ctx.fillRect(0, 0, W, H)

      } else {
        // ── Moon sweeps in ────────────────────────────────
        const moonOpacity = Math.sin(Math.PI * t)
        const moonR = 40

        // Moonlight glow
        const glow = ctx.createRadialGradient(x, y, 0, x, y, 200)
        glow.addColorStop(0, `rgba(180,200,255,${0.25 * moonOpacity})`)
        glow.addColorStop(1, 'rgba(100,140,255,0)')
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(x, y, 200, 0, Math.PI * 2)
        ctx.fill()

        // Moon disk
        ctx.fillStyle = `rgba(228,232,245,${moonOpacity})`
        ctx.beginPath()
        ctx.arc(x, y, moonR, 0, Math.PI * 2)
        ctx.fill()

        // Crescent shadow
        ctx.fillStyle = `rgba(30,45,100,${moonOpacity * 0.75})`
        ctx.beginPath()
        ctx.arc(x - 14, y - 6, moonR * 0.82, 0, Math.PI * 2)
        ctx.fill()

        // Stars scattered around moon path
        const stars = [
          [-180, -80], [-100, -140], [60, -100], [140, -60],
          [-140, 60], [100, 80], [-60, 120], [200, 40],
          [-220, 20], [180, -120],
        ]
        ctx.fillStyle = '#c8d8ff'
        stars.forEach(([dx, dy], i) => {
          const twinkle = 0.4 + 0.6 * Math.sin(Date.now() / 400 + i * 1.7)
          ctx.globalAlpha = moonOpacity * twinkle * 0.85
          const r = 1.2 + 0.8 * Math.sin(i * 2.3)
          ctx.beginPath()
          ctx.arc(x + dx, y + dy, r, 0, Math.PI * 2)
          ctx.fill()
        })
        ctx.globalAlpha = 1

        // Dark trailing veil
        const veil = ctx.createLinearGradient(x - 250, y - 250, x + 150, y + 150)
        veil.addColorStop(0, `rgba(15,30,60,${0.08 * moonOpacity})`)
        veil.addColorStop(1, 'rgba(15,30,60,0)')
        ctx.fillStyle = veil
        ctx.fillRect(0, 0, W, H)
      }
    }

    const loop = (ts: number) => {
      if (!startRef.current) startRef.current = ts
      const elapsed = ts - startRef.current
      const t = Math.min(elapsed / DURATION, 1)
      draw(t)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(loop)
      }
    }
    rafRef.current = requestAnimationFrame(loop)

    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 99999,
      }}
    />
  )
}
