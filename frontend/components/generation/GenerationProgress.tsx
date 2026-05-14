'use client'
import { CheckCircle, Circle, Loader } from 'lucide-react'
import GlassCard from '../shared/GlassCard'
import { Theme, LogoType } from '@/lib/types'

interface Step {
  id: string
  label: string
  sublabel?: string
  status: 'pending' | 'active' | 'done'
}

interface GenerationProgressProps {
  progressMessage: string
  progressPct: number
  theme: Theme
  logoType: LogoType
  attempt?: number
}

export default function GenerationProgress({
  progressMessage, progressPct, theme, logoType, attempt = 1,
}: GenerationProgressProps) {
  const steps: Omit<Step, 'status'>[] = [
    { id: 'kb',        label: `Querying brand knowledge`,
      sublabel: `theme: ${theme}` },
    { id: 'memory',    label: 'Querying past learnings',
      sublabel: `${logoType} · ${theme}` },
    { id: 'plan',      label: 'Planning pixel-perfect layout' },
    { id: 'bg',        label: 'Generating background image',
      sublabel: `${theme === 'dark' ? 'Dark industrial' : 'Clean minimal'} · Gemini Imagen 4` },
    { id: 'glass',     label: 'Rendering glass effect' },
    { id: 'composite', label: 'Compositing elements' },
    { id: 'review',    label: 'Running quality review' },
  ]

  const pctMap: Record<string, number> = {
    kb: 10, memory: 20, plan: 30, bg: 45, glass: 60, composite: 75, review: 85,
  }

  const stepsWithStatus: Step[] = steps.map(s => {
    const threshold = pctMap[s.id] ?? 0
    const status: Step['status'] =
      progressPct >= threshold + 15 ? 'done' :
      progressPct >= threshold     ? 'active' : 'pending'
    return { ...s, status }
  })

  return (
    <GlassCard className="w-full max-w-md mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-urbanist font-bold text-white text-lg">
          {attempt > 1 ? `Regenerating (attempt ${attempt})` : 'Generating Post'}
        </h3>
        <span className="text-brand-blue font-oxanium text-sm font-medium">
          {progressPct}%
        </span>
      </div>

      <div className="h-1 bg-white/10 rounded-full mb-6 overflow-hidden">
        <div className="h-full bg-brand-blue rounded-full transition-all duration-500"
             style={{ width: `${progressPct}%` }} />
      </div>

      <div className="space-y-3">
        {stepsWithStatus.map(step => (
          <div key={step.id} className="flex items-start gap-3">
            <div className="mt-0.5 shrink-0">
              {step.status === 'done'
                ? <CheckCircle size={16} className="text-success" />
                : step.status === 'active'
                  ? <Loader size={16} className="text-brand-blue animate-spin" />
                  : <Circle size={16} className="text-white/20" />
              }
            </div>
            <div>
              <p className={`text-sm font-oxanium ${
                step.status === 'done'   ? 'text-white/60' :
                step.status === 'active' ? 'text-white' : 'text-white/30'
              }`}>
                {step.label}
              </p>
              {step.sublabel && step.status !== 'pending' && (
                <p className="text-xs text-brand-blue-light/60 font-oxanium mt-0.5">
                  {step.sublabel}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {progressMessage && (
        <p className="mt-5 text-xs text-white/40 font-oxanium border-t
                       border-white/5 pt-4 truncate">
          {progressMessage}
        </p>
      )}
    </GlassCard>
  )
}
