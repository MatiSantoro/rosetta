import { useEffect, useRef } from 'react'

const GLYPHS = [
  '𓀀','𓀁','𓀂','𓀃','𓀄','𓀅','𓀆','𓀇',
  '𓁀','𓁁','𓁂','𓁃','𓁄','𓁅',
  '𓂀','𓂋','𓂌','𓂍','𓂎',
  '𓃒','𓃓','𓃔','𓃕',
  '𓆑','𓆒','𓆓',
  '𓇯','𓇰','𓇱',
  '𓈖','𓈗','𓈘',
  '𓉐','𓉑','𓉒',
  '𓊪','𓊫','𓊬',
  '𓋴','𓋵',
  '𓌀','𓌁','𓌂',
  '𓍯','𓍰',
  '𓏏','𓏐','𓏑','𓏒',
]

interface Column {
  x:       number
  y:       number
  speed:   number
  opacity: number
  timer:   number
  glyph:   string
}

export default function HieroglyphRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    // 'el' is typed as HTMLCanvasElement (narrowed) — safe to use inside nested functions
    const el  = canvas as HTMLCanvasElement
    const ctx = el.getContext('2d')!

    const COL_W = 36
    let columns: Column[] = []
    let rafId:   number

    function rnd(min: number, max: number) { return min + Math.random() * (max - min) }
    function pick() { return GLYPHS[Math.floor(Math.random() * GLYPHS.length)] }

    function init() {
      el.width  = window.innerWidth
      el.height = window.innerHeight
      const n = Math.ceil(el.width / COL_W) + 1

      columns = Array.from({ length: n }, (_, i) => ({
        x:       i * COL_W + 8,
        y:       rnd(-el.height, el.height),
        speed:   rnd(0.4, 1.0),
        opacity: rnd(0.06, 0.14),
        timer:   0,
        glyph:   pick(),
      }))
    }

    init()
    window.addEventListener('resize', init)

    function draw() {
      // Read current theme from CSS variables so dark/light switch works live
      const style   = getComputedStyle(document.documentElement)
      const bg      = style.getPropertyValue('--bg').trim()      || '#100E0C'
      const isDark  = document.documentElement.classList.contains('dark')

      ctx.fillStyle = bg
      ctx.fillRect(0, 0, el.width, el.height)

      ctx.font = '20px serif'

      for (const col of columns) {
        // Glyphs need higher opacity in light mode to remain visible
        const opacity = isDark ? col.opacity : col.opacity * 2.5
        ctx.fillStyle = `rgba(201, 126, 42, ${opacity})`
        ctx.fillText(col.glyph, col.x, col.y)

        col.y     += col.speed
        col.timer += 1

        if (col.timer > rnd(30, 60)) {
          col.glyph = pick()
          col.timer = 0
        }

        if (col.y > el.height + 30) {
          col.y       = -30
          col.speed   = rnd(0.4, 1.0)
          col.opacity = rnd(0.06, 0.14)
        }
      }

      rafId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', init)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position:      'fixed',
        inset:         0,
        zIndex:        -1,       // behind ALL content — no more covering the logo
        pointerEvents: 'none',
      }}
    />
  )
}
