import { Moon, Sun } from 'lucide-react'
import { useState, useEffect } from 'react'

export default function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains('dark')
  )

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [dark])

  return (
    <button
      onClick={() => setDark(d => !d)}
      className="w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150 active:scale-95"
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        border:     '1px solid var(--border)',
        background: 'var(--surface)',
        color:      'var(--text-muted)',
      }}
    >
      {dark
        ? <Sun  size={15} style={{ color: 'var(--accent)' }} />
        : <Moon size={15} style={{ color: 'var(--text-muted)' }} />
      }
    </button>
  )
}
