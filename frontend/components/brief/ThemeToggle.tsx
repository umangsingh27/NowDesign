'use client'
import { Moon, Sun } from 'lucide-react'
import { Theme } from '@/lib/types'

interface ThemeToggleProps {
  value: Theme
  onChange: (theme: Theme) => void
}

export default function ThemeToggle({ value, onChange }: ThemeToggleProps) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-widest text-white/50
                         font-oxanium mb-2">
        Post Theme
      </label>
      <div className="flex rounded-pill bg-white/5 border border-white/10 p-1 gap-1">
        {(['dark', 'light'] as Theme[]).map(t => (
          <button
            key={t}
            type="button"
            onClick={() => onChange(t)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4
              rounded-pill text-sm font-oxanium font-medium transition-all duration-200
              ${value === t
                ? 'bg-brand-blue text-white shadow-md'
                : 'text-white/50 hover:text-white/80'
              }`}
          >
            {t === 'dark'
              ? <><Moon size={14} /> Dark Mode</>
              : <><Sun size={14} /> Light Mode</>
            }
          </button>
        ))}
      </div>
    </div>
  )
}
