'use client'
import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { Theme, LogoType } from '@/lib/types'
import GlassCard from '../shared/GlassCard'
import LoadingDots from '../shared/LoadingDots'

const SUGGESTION_CHIPS = [
  'Make headline bigger',
  'Switch to light mode',
  'Switch to dark mode',
  'Use MetalCloud logo',
  'Different background',
  'Increase opacity',
]

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ReviewChatProps {
  sessionId: string
  theme: Theme
  logoType: LogoType
  onFeedback: (message: string) => void
  onApprove: (rating: number) => void
  isGenerating?: boolean
}

export default function ReviewChat({
  onFeedback, onApprove, isGenerating,
}: ReviewChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant',
      content: 'The post is ready for review. Use the chat to request changes, or approve to download.' },
  ])
  const [input, setInput] = useState('')
  const [rating, setRating] = useState(4)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg) return
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    onFeedback(msg)
    setTimeout(() => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Got it — regenerating with your changes...',
      }])
    }, 300)
  }

  return (
    <GlassCard className="flex flex-col h-full w-full" padding="none">
      <div className="px-5 py-4 border-b border-white/8">
        <h3 className="font-urbanist font-bold text-white text-base">
          Review & Revise
        </h3>
        <p className="text-xs text-white/40 font-oxanium mt-0.5">
          Chat to refine · Approve when ready
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm font-oxanium
              ${msg.role === 'user'
                ? 'bg-brand-blue text-white rounded-br-sm'
                : 'bg-white/8 text-white/80 rounded-bl-sm'
              }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isGenerating && (
          <div className="flex justify-start">
            <div className="bg-white/8 px-4 py-3 rounded-2xl rounded-bl-sm">
              <LoadingDots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 pb-2 flex flex-wrap gap-1.5">
        {SUGGESTION_CHIPS.map(chip => (
          <button key={chip} onClick={() => send(chip)}
            disabled={isGenerating}
            className="px-3 py-1 rounded-lg text-xs font-oxanium text-white/50
              hover:text-white border border-white/10 hover:border-white/30
              transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
            {chip}
          </button>
        ))}
      </div>

      <div className="px-4 pb-4 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Request a change..."
          disabled={isGenerating}
          className="flex-1 bg-white/5 border border-white/10 rounded-xl
            px-4 py-2.5 text-sm font-oxanium text-white placeholder:text-white/30
            focus:outline-none focus:border-brand-blue/60 disabled:opacity-50"
        />
        <button onClick={() => send()} disabled={!input.trim() || isGenerating}
          className="p-2.5 rounded-xl bg-brand-blue disabled:opacity-30
            disabled:cursor-not-allowed hover:bg-brand-blue-mid transition-colors">
          <Send size={16} className="text-white" />
        </button>
      </div>

      <div className="px-4 pb-5 border-t border-white/8 pt-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-white/50 font-oxanium">Rating</span>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} onClick={() => setRating(n)}
                className={`text-lg transition-colors ${
                  n <= rating ? 'text-brand-blue' : 'text-white/20'
                }`}>★</button>
            ))}
          </div>
        </div>
        <button onClick={() => onApprove(rating)}
          className="w-full py-3 rounded-xl bg-success/20 hover:bg-success/30
            text-green-400 border border-success/30 font-urbanist font-bold text-sm
            transition-colors">
          Approve & Download ✓
        </button>
      </div>
    </GlassCard>
  )
}
