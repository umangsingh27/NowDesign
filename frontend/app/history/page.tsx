'use client'
import { useState } from 'react'
import useSWR from 'swr'
import { fetchHistory } from '@/lib/api'
import ScoreBadge from '@/components/shared/ScoreBadge'
import ThemeLogoBadge from '@/components/review/ThemeLogoBadge'
import { Theme, LogoType } from '@/lib/types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function HistoryPage() {
  const [themeFilter, setThemeFilter] = useState('')
  const [logoFilter, setLogoFilter]   = useState('')
  const [minScore, setMinScore]       = useState<number | undefined>()

  const { data, isLoading } = useSWR(
    ['history', themeFilter, logoFilter, minScore],
    () => fetchHistory({
      theme: themeFilter || undefined,
      logo_type: logoFilter || undefined,
      min_score: minScore,
    }),
  )

  const selCls = `bg-white/5 border border-white/10 rounded-xl px-3 py-2
    text-sm font-oxanium text-white/70 focus:outline-none focus:border-brand-blue/60`

  return (
    <main className="min-h-screen bg-brand-navy px-6 py-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-urbanist font-extrabold text-2xl text-white">
            Post History
          </h1>
          <a href="/" className="text-sm font-oxanium text-white/50
            hover:text-white transition-colors">← Back</a>
        </div>

        <div className="flex flex-wrap gap-3 mb-6">
          <select value={themeFilter} onChange={e => setThemeFilter(e.target.value)}
            className={selCls}>
            <option value="">All themes</option>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
          <select value={logoFilter} onChange={e => setLogoFilter(e.target.value)}
            className={selCls}>
            <option value="">All logos</option>
            <option value="nowpurchase">NowPurchase</option>
            <option value="metalcloud">MetalCloud</option>
            <option value="combined">Combined</option>
          </select>
          <select value={minScore ?? ''} onChange={e =>
            setMinScore(e.target.value ? Number(e.target.value) : undefined)}
            className={selCls}>
            <option value="">Any score</option>
            <option value="80">80+ (passing)</option>
            <option value="90">90+</option>
          </select>
        </div>

        {isLoading
          ? <p className="text-white/40 font-oxanium">Loading...</p>
          : !data?.length
            ? <p className="text-white/40 font-oxanium">No posts yet.</p>
            : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {data.map((s: {
                  id: string; image_url?: string; compliance_score?: number;
                  theme: Theme; logo_type: LogoType
                }) => (
                  <div key={s.id}
                    className="rounded-xl overflow-hidden border border-white/10
                      bg-brand-navy-dark hover:border-white/20 transition-colors">
                    {s.image_url && (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img src={`${API}${s.image_url}`} alt=""
                           className="w-full aspect-square object-cover" />
                    )}
                    <div className="p-3 flex flex-col gap-2">
                      {s.compliance_score != null && (
                        <ScoreBadge score={s.compliance_score}
                          passed={s.compliance_score >= 80} />
                      )}
                      <ThemeLogoBadge theme={s.theme} logoType={s.logo_type} />
                    </div>
                  </div>
                ))}
              </div>
            )
        }
      </div>
    </main>
  )
}
