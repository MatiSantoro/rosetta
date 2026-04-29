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
    const ctx = canvas.getContext('2d')!

    const COL_W = 36
    let columns: Column[] = []
    let rafId:   number

    function rnd(min: number, max: number) { return min + Math.random() * (max - min) }
    function pick() { return GLYPHS[Math.floor(Math.random() * GLYPHS.length)] }

    function init() {
      canvas.width  = window.innerWidth
      canvas.height = window.innerHeight
      const n = Math.ceil(canvas.width / COL_W) + 1

      columns = Array.from({ length: n }, (_, i) => ({
        x:       i * COL_W + 8,
        y:       rnd(-canvas.height, canvas.height),
        speed:   rnd(0.4, 1.0),
        opacity: rnd(0.06, 0.14),
        timer:   0,
        glyph:   pick(),
      }))
    }

    init()
    window.addEventListener('resize', init)

    function draw() {
      // Draw background color on canvas so outer divs can be transparent
      ctx.fillStyle = 'rgb(12, 10, 8)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      ctx.font = '20px serif'

      for (const col of columns) {
        ctx.fillStyle = `rgba(228, 162, 56, ${col.opacity})`
        ctx.fillText(col.glyph, col.x, col.y)

        col.y     += col.speed
        col.timer += 1

        // Change glyph slowly
        if (col.timer > rnd(30, 60)) {
          col.glyph = pick()
          col.timer = 0
        }

        // Reset when off-screen
        if (col.y > canvas.height + 30) {
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
