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
      className="btn btn-ghost w-8 h-8 p-0 rounded-lg"
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {dark
        ? <Sun  size={15} style={{ color: 'var(--accent)' }} />
        : <Moon size={15} style={{ color: 'var(--text-muted)' }} />
      }
    </button>
  )
}
