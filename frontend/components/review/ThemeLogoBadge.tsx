import { Theme, LogoType } from '@/lib/types'

const LOGO_LABELS: Record<LogoType, string> = {
  nowpurchase: 'NowPurchase', metalcloud: 'MetalCloud', combined: 'Combined',
}

export default function ThemeLogoBadge({ theme, logoType }: {
  theme: Theme; logoType: LogoType
}) {
  return (
    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-lg
      bg-white/5 border border-white/10 text-xs font-oxanium text-white/60">
      <span className={`w-1.5 h-1.5 rounded-full ${
        theme === 'dark' ? 'bg-brand-blue' : 'bg-amber-400'
      }`} />
      {theme === 'dark' ? 'Dark' : 'Light'} · {LOGO_LABELS[logoType]}
    </span>
  )
}
