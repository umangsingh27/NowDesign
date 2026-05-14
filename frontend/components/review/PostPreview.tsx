'use client'
import { Download, RefreshCw } from 'lucide-react'
import ScoreBadge from '../shared/ScoreBadge'
import ThemeLogoBadge from './ThemeLogoBadge'
import { Theme, LogoType } from '@/lib/types'

interface PostPreviewProps {
  imageUrl: string | null
  score: number | null
  theme: Theme
  logoType: LogoType
  onRegenerate?: () => void
}

export default function PostPreview({
  imageUrl, score, theme, logoType, onRegenerate,
}: PostPreviewProps) {
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  function handleDownload() {
    if (!imageUrl) return
    const a = document.createElement('a')
    a.href = `${API}${imageUrl}`
    a.download = `np-post-${Date.now()}.png`
    a.click()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="relative rounded-2xl overflow-hidden
                       ring-1 ring-white/10 bg-brand-navy-mid aspect-square">
        {imageUrl
          /* eslint-disable-next-line @next/next/no-img-element */
          ? <img
              src={`${API}${imageUrl}?t=${Date.now()}`}
              alt="Generated post"
              className="w-full h-full object-cover"
            />
          : <div className="w-full h-full flex items-center justify-center
                             text-white/20 text-sm font-oxanium">
              No image yet
            </div>
        }
      </div>

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {score != null && <ScoreBadge score={score} passed={score >= 80} />}
          <ThemeLogoBadge theme={theme} logoType={logoType} />
        </div>
        <div className="flex gap-2">
          {onRegenerate && (
            <button onClick={onRegenerate}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                text-white/60 hover:text-white border border-white/10
                hover:border-white/30 text-xs font-oxanium transition-colors">
              <RefreshCw size={12} /> Regenerate
            </button>
          )}
          {imageUrl && (
            <button onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                bg-brand-blue/20 hover:bg-brand-blue/30 text-brand-blue-light
                border border-brand-blue/30 text-xs font-oxanium transition-colors">
              <Download size={12} /> Download
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
