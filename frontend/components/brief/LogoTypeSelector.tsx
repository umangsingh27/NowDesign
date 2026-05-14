'use client'
import { LogoType } from '@/lib/types'

const OPTIONS: { value: LogoType; label: string; tip?: string }[] = [
  { value: 'nowpurchase', label: 'NowPurchase' },
  { value: 'metalcloud',  label: 'MetalCloud' },
  { value: 'combined',    label: 'Combined',
    tip: 'Shows both logos side by side' },
]

interface LogoTypeSelectorProps {
  value: LogoType
  onChange: (type: LogoType) => void
}

export default function LogoTypeSelector({ value, onChange }: LogoTypeSelectorProps) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-widest text-white/50
                         font-oxanium mb-2">
        Logo Type
      </label>
      <div className="flex rounded-2xl bg-white/5 border border-white/10 p-1 gap-1">
        {OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            title={opt.tip}
            className={`flex-1 py-2 px-3 rounded-xl text-sm font-oxanium
              transition-all duration-200 relative
              ${value === opt.value
                ? 'bg-brand-blue text-white'
                : 'text-white/50 hover:text-white/80'
              }`}
          >
            {opt.label}
            {opt.tip && (
              <span className="absolute -top-1 -right-1 w-2 h-2
                               rounded-full bg-brand-blue-light opacity-70" />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
