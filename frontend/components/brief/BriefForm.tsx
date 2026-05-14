'use client'
import { useState } from 'react'
import { Brief, Theme, LogoType, Emotion, PostPurpose } from '@/lib/types'
import ThemeToggle from './ThemeToggle'
import LogoTypeSelector from './LogoTypeSelector'
import GlassCard from '../shared/GlassCard'

const EMOTIONS: Emotion[] = ['inspiring', 'professional', 'urgent', 'celebratory', 'informative']
const PURPOSES: { value: PostPurpose; label: string }[] = [
  { value: 'product_feature',  label: 'Product Feature' },
  { value: 'testimonial',      label: 'Testimonial' },
  { value: 'announcement',     label: 'Announcement' },
  { value: 'insight',          label: 'Insight / Data' },
  { value: 'event',            label: 'Event' },
  { value: 'case_study',       label: 'Case Study' },
  { value: 'team',             label: 'Team / Culture' },
  { value: 'product_launch',   label: 'Product Launch' },
]

interface BriefFormProps {
  onSubmit: (brief: Brief) => void
  isLoading?: boolean
}

export default function BriefForm({ onSubmit, isLoading }: BriefFormProps) {
  const [theme, setTheme]               = useState<Theme>('dark')
  const [logoType, setLogoType]         = useState<LogoType>('nowpurchase')
  const [purpose, setPurpose]           = useState<PostPurpose>('product_feature')
  const [emotion, setEmotion]           = useState<Emotion>('professional')
  const [headline, setHeadline]         = useState('')
  const [stat, setStat]                 = useState('')
  const [bodyCopy, setBodyCopy]         = useState('')
  const [attribution, setAttribution]   = useState('')
  const [cta, setCta]                   = useState('')
  const [requestedBy, setRequestedBy]   = useState('')

  const inputCls = `w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3
    text-white text-sm font-oxanium placeholder:text-white/30
    focus:outline-none focus:border-brand-blue/60 focus:bg-white/8 transition-colors`

  const labelCls = `block text-xs uppercase tracking-widest text-white/50
    font-oxanium mb-1.5`

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!headline.trim()) return
    onSubmit({
      theme, logo_type: logoType, purpose, emotion,
      headline: headline.trim(),
      stat: stat.trim() || undefined,
      body_copy: bodyCopy.trim() || undefined,
      attribution: attribution.trim() || undefined,
      cta: cta.trim() || undefined,
      requested_by: requestedBy.trim() || undefined,
    })
  }

  return (
    <GlassCard className="w-full">
      <h2 className="font-urbanist font-bold text-xl text-white mb-6">
        New Post Brief
      </h2>

      <form onSubmit={handleSubmit} className="space-y-5">
        <ThemeToggle value={theme} onChange={setTheme} />
        <LogoTypeSelector value={logoType} onChange={setLogoType} />

        <div>
          <label className={labelCls}>Post Type</label>
          <select value={purpose}
            onChange={e => setPurpose(e.target.value as PostPurpose)}
            className={inputCls + ' cursor-pointer'}>
            {PURPOSES.map(p => (
              <option key={p.value} value={p.value}
                      className="bg-brand-navy-dark">{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelCls}>Tone / Emotion</label>
          <div className="flex flex-wrap gap-2">
            {EMOTIONS.map(e => (
              <button key={e} type="button" onClick={() => setEmotion(e)}
                className={`px-3 py-1.5 rounded-lg text-xs font-oxanium capitalize
                  border transition-colors
                  ${emotion === e
                    ? 'bg-brand-blue/20 border-brand-blue text-brand-blue-light'
                    : 'border-white/10 text-white/50 hover:border-white/30'
                  }`}>
                {e}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className={labelCls}>Headline <span className="text-brand-blue">*</span></label>
          <input value={headline} onChange={e => setHeadline(e.target.value)}
            placeholder="e.g. MetalCloud reduces charge mix costs by 18%"
            className={inputCls} maxLength={200} required />
        </div>

        <div>
          <label className={labelCls}>Stat / Number <span className="text-white/30">(optional)</span></label>
          <input value={stat} onChange={e => setStat(e.target.value)}
            placeholder="e.g. 23% or ₹80 Cr"
            className={inputCls} maxLength={50} />
        </div>

        <div>
          <label className={labelCls}>Body Copy <span className="text-white/30">(optional)</span></label>
          <textarea value={bodyCopy} onChange={e => setBodyCopy(e.target.value)}
            placeholder="Supporting context, max 2 lines..."
            className={inputCls + ' resize-none'} rows={2} maxLength={200} />
        </div>

        <div>
          <label className={labelCls}>Attribution <span className="text-white/30">(optional)</span></label>
          <input value={attribution} onChange={e => setAttribution(e.target.value)}
            placeholder="e.g. Naman Shah, CEO — NowPurchase"
            className={inputCls} maxLength={100} />
        </div>

        <div>
          <label className={labelCls}>CTA <span className="text-white/30">(optional)</span></label>
          <input value={cta} onChange={e => setCta(e.target.value)}
            placeholder="e.g. Book a Demo"
            className={inputCls} maxLength={80} />
        </div>

        <div>
          <label className={labelCls}>Requested By</label>
          <input value={requestedBy} onChange={e => setRequestedBy(e.target.value)}
            placeholder="Your name"
            className={inputCls} />
        </div>

        <button type="submit" disabled={!headline.trim() || isLoading}
          className={`w-full py-4 rounded-xl font-urbanist font-bold text-base
            transition-all duration-200
            ${headline.trim() && !isLoading
              ? 'bg-brand-blue hover:bg-brand-blue-mid text-white shadow-lg shadow-brand-blue/20 active:scale-[0.98]'
              : 'bg-white/5 text-white/30 cursor-not-allowed'
            }`}>
          {isLoading ? 'Generating...' : 'Generate Post →'}
        </button>
      </form>
    </GlassCard>
  )
}
