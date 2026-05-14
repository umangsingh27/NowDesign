'use client'
import { useReducer, useRef, useEffect } from 'react'
import { Brief } from '@/lib/types'
import {
  sessionReducer, INITIAL_STATE,
} from '@/lib/session-machine'
import { startSession, submitFeedback, approveSession,
         createSSEConnection } from '@/lib/api'

import BriefForm           from '@/components/brief/BriefForm'
import GenerationProgress  from '@/components/generation/GenerationProgress'
import PostPreview         from '@/components/review/PostPreview'
import ComplianceBreakdown from '@/components/review/ComplianceBreakdown'
import ReviewChat          from '@/components/review/ReviewChat'
import ApprovedPost        from '@/components/approved/ApprovedPost'

export default function HomePage() {
  const [state, dispatch] = useReducer(sessionReducer, INITIAL_STATE)
  const sseCleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => () => { sseCleanupRef.current?.() }, [])

  function connectSSE(sessionId: string) {
    sseCleanupRef.current?.()
    const cleanup = createSSEConnection(
      sessionId,
      (event, data) => {
        const d = data as Record<string, unknown>
        if (event === 'status_update') {
          dispatch({ type: 'PROGRESS',
            message: String(d.message ?? ''),
            pct: Number(d.progress_pct ?? 0) })
        }
        if (event === 'image_ready') {
          dispatch({ type: 'IMAGE_READY',
            imageUrl: String(d.image_url ?? ''),
            score: Number(d.compliance_score ?? 0),
            report: d.report as never })
          dispatch({ type: 'ENTER_REVIEW' })
        }
        if (event === 'error') {
          dispatch({ type: 'ERROR', message: String(d.message ?? 'Unknown error') })
        }
      },
      () => { /* SSE closed */ },
    )
    sseCleanupRef.current = cleanup
  }

  async function handleBriefSubmit(brief: Brief) {
    dispatch({ type: 'START_GENERATING', brief })
    try {
      const res = await startSession(brief)
      dispatch({ type: 'SET_SESSION_ID', sessionId: res.session_id })
      connectSSE(res.session_id)
    } catch (e) {
      dispatch({ type: 'ERROR', message: String(e) })
    }
  }

  async function handleFeedback(message: string) {
    if (!state.sessionId) return
    dispatch({ type: 'SUBMIT_FEEDBACK' })
    try {
      await submitFeedback(state.sessionId, message)
      connectSSE(state.sessionId)
    } catch (e) {
      dispatch({ type: 'ERROR', message: String(e) })
    }
  }

  async function handleApprove(rating: number) {
    if (!state.sessionId) return
    try {
      const res = await approveSession(state.sessionId, rating)
      dispatch({ type: 'APPROVED', imageUrl: res.final_image_url })
    } catch (e) {
      dispatch({ type: 'ERROR', message: String(e) })
    }
  }

  const theme    = state.brief?.theme    ?? 'dark'
  const logoType = state.brief?.logo_type ?? 'nowpurchase'

  return (
    <main className="min-h-screen bg-brand-navy px-6 py-8">
      <header className="max-w-6xl mx-auto flex items-center justify-between mb-8">
        <div className="font-urbanist font-extrabold text-xl text-white">
          <span className="text-brand-blue">Now</span>Purchase
          <span className="text-white/40 font-oxanium font-normal text-sm ml-3">
            Design Studio
          </span>
        </div>
        <nav className="flex gap-4 text-sm font-oxanium text-white/50">
          <a href="/history"   className="hover:text-white transition-colors">History</a>
          <a href="/knowledge" className="hover:text-white transition-colors">Knowledge</a>
        </nav>
      </header>

      {state.error && (
        <div className="max-w-6xl mx-auto mb-6 px-4 py-3 rounded-xl
          bg-error/20 border border-error/30 text-red-400 text-sm font-oxanium
          flex items-center justify-between">
          <span>{state.error}</span>
          <button onClick={() => dispatch({ type: 'RESET' })}
            className="text-red-400/60 hover:text-red-400 ml-4">✕</button>
        </div>
      )}

      {state.appState === 'BRIEF' && (
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="max-w-lg">
            <BriefForm onSubmit={handleBriefSubmit} />
          </div>
          <div className="hidden lg:flex items-center justify-center
            rounded-2xl border border-white/5 bg-brand-navy-dark/50 min-h-[400px]">
            <p className="text-white/20 text-sm font-oxanium">
              Your post will appear here
            </p>
          </div>
        </div>
      )}

      {state.appState === 'GENERATING' && (
        <div className="max-w-6xl mx-auto flex items-start justify-center pt-8">
          <GenerationProgress
            progressMessage={state.progressMessage}
            progressPct={state.progressPct}
            theme={theme}
            logoType={logoType}
          />
        </div>
      )}

      {state.appState === 'REVIEW' && (
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 flex flex-col gap-4">
            <PostPreview
              imageUrl={state.imageUrl}
              score={state.complianceScore}
              theme={theme}
              logoType={logoType}
              onRegenerate={() => handleFeedback('regenerate with a different background')}
            />
            {state.complianceReport && (
              <ComplianceBreakdown
                report={state.complianceReport}
                theme={theme}
              />
            )}
          </div>
          <div className="lg:col-span-2 min-h-[600px] flex">
            <ReviewChat
              sessionId={state.sessionId ?? ''}
              theme={theme}
              logoType={logoType}
              onFeedback={handleFeedback}
              onApprove={handleApprove}
              isGenerating={false}
            />
          </div>
        </div>
      )}

      {state.appState === 'APPROVED' && state.imageUrl && (
        <div className="max-w-6xl mx-auto">
          <ApprovedPost
            imageUrl={state.imageUrl}
            theme={theme}
            logoType={logoType}
            onNewPost={() => dispatch({ type: 'RESET' })}
          />
        </div>
      )}
    </main>
  )
}
