'use client'
import { Download, Plus, Cpu } from 'lucide-react'
import ThemeLogoBadge from '../review/ThemeLogoBadge'
import { Theme, LogoType } from '@/lib/types'

interface ApprovedPostProps {
  imageUrl: string
  theme: Theme
  logoType: LogoType
  onNewPost: () => void
}

export default function ApprovedPost({
  imageUrl, theme, logoType, onNewPost,
}: ApprovedPostProps) {
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  return (
    <div className="flex flex-col items-center gap-6 max-w-lg mx-auto">
      <div className="text-center">
        <h2 className="font-urbanist font-extrabold text-3xl text-white mb-2">
          Post Approved
        </h2>
        <p className="text-white/50 text-sm font-oxanium">
          Your post has been saved. The system is learning from this session.
        </p>
      </div>

      <div className="w-full rounded-2xl overflow-hidden ring-1 ring-white/10 aspect-square">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`${API}${imageUrl}`} alt="Approved post"
             className="w-full h-full object-cover" />
      </div>

      <div className="flex items-center gap-3">
        <ThemeLogoBadge theme={theme} logoType={logoType} />
        <span className="flex items-center gap-1.5 text-xs text-white/40 font-oxanium">
          <Cpu size={12} /> Learning agent running
        </span>
      </div>

      <div className="flex gap-3 w-full">
        <a href={`${API}${imageUrl}`} download={`np-post-${Date.now()}.png`}
           className="flex-1 flex items-center justify-center gap-2 py-3
             rounded-xl bg-brand-blue hover:bg-brand-blue-mid text-white
             font-urbanist font-bold text-sm transition-colors">
          <Download size={16} /> Download PNG
        </a>
        <button onClick={onNewPost}
          className="flex-1 flex items-center justify-center gap-2 py-3
            rounded-xl bg-white/5 hover:bg-white/10 text-white/80
            border border-white/10 font-urbanist font-bold text-sm transition-colors">
          <Plus size={16} /> New Post
        </button>
      </div>
    </div>
  )
}
