'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { ComplianceReport, Theme } from '@/lib/types'
import { COMPLIANCE_LABELS } from '@/lib/compliance-labels'

export default function ComplianceBreakdown({
  report, theme,
}: { report: ComplianceReport; theme: Theme }) {
  const [open, setOpen] = useState(false)
  if (!report?.criteria_detail) return null

  return (
    <div className="rounded-xl border border-white/10 overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3
          text-sm font-oxanium text-white/70 hover:text-white
          bg-white/3 hover:bg-white/5 transition-colors">
        <span>Compliance Breakdown</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">
            {Object.values(report.criteria_detail)
              .filter(c => c.score >= c.max * 0.7).length} / 14 passed
          </span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {open && (
        <div className="divide-y divide-white/5">
          {Object.entries(report.criteria_detail).map(([key, criterion]) => {
            const label = COMPLIANCE_LABELS[key]?.[theme] ?? key
            const pct = criterion.max > 0
              ? Math.round((criterion.score / criterion.max) * 100)
              : 0
            const passing = pct >= 70
            return (
              <div key={key} className="px-4 py-2.5 flex items-start gap-3">
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                  passing ? 'bg-success' : 'bg-error'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-oxanium text-white/80 truncate">
                      {label}
                    </p>
                    <span className={`text-xs font-oxanium shrink-0 ${
                      passing ? 'text-success' : 'text-error'
                    }`}>
                      {criterion.score}/{criterion.max}
                    </span>
                  </div>
                  {!passing && criterion.notes && (
                    <p className="text-xs text-white/40 mt-0.5 leading-relaxed">
                      {criterion.notes}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
