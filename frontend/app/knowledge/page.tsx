'use client'
import { useState } from 'react'
import useSWR, { mutate } from 'swr'
import { fetchKnowledge } from '@/lib/api'
import GlassCard from '@/components/shared/GlassCard'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function KnowledgePage() {
  const { data, isLoading } = useSWR('knowledge', fetchKnowledge)
  const [content, setContent]       = useState('')
  const [category, setCategory]     = useState('company_info')
  const [topic, setTopic]           = useState('')
  const [collection, setCollection] = useState<'brand_knowledge'|'agent_memory'>('brand_knowledge')
  const [saving, setSaving]         = useState(false)

  const inputCls = `w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5
    text-sm font-oxanium text-white placeholder:text-white/30
    focus:outline-none focus:border-brand-blue/60`

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim() || !topic.trim()) return
    setSaving(true)
    await fetch(`${API}/api/knowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ collection, content, category, topic }),
    })
    setContent('')
    setTopic('')
    mutate('knowledge')
    setSaving(false)
  }

  return (
    <main className="min-h-screen bg-brand-navy px-6 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-urbanist font-extrabold text-2xl text-white">
            Knowledge Base
          </h1>
          <a href="/" className="text-sm font-oxanium text-white/50
            hover:text-white transition-colors">← Back</a>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <GlassCard>
            <h2 className="font-urbanist font-bold text-white mb-4">Add Entry</h2>
            <form onSubmit={handleAdd} className="space-y-3">
              <div className="flex gap-2">
                {(['brand_knowledge', 'agent_memory'] as const).map(c => (
                  <button key={c} type="button" onClick={() => setCollection(c)}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-oxanium
                      border transition-colors
                      ${collection === c
                        ? 'bg-brand-blue/20 border-brand-blue text-brand-blue-light'
                        : 'border-white/10 text-white/50'
                      }`}>
                    {c === 'brand_knowledge' ? 'Brand Knowledge' : 'Agent Memory'}
                  </button>
                ))}
              </div>
              <input value={topic} onChange={e => setTopic(e.target.value)}
                placeholder="Topic" className={inputCls} required />
              <input value={category} onChange={e => setCategory(e.target.value)}
                placeholder="Category (e.g. product_info)" className={inputCls} />
              <textarea value={content} onChange={e => setContent(e.target.value)}
                placeholder="Knowledge content..."
                className={inputCls + ' resize-none'} rows={4} required />
              <button type="submit" disabled={saving}
                className="w-full py-2.5 rounded-xl bg-brand-blue text-white
                  font-oxanium text-sm disabled:opacity-50 hover:bg-brand-blue-mid
                  transition-colors">
                {saving ? 'Saving...' : 'Add to Knowledge Base'}
              </button>
            </form>
          </GlassCard>

          <GlassCard>
            <h2 className="font-urbanist font-bold text-white mb-4">Collections</h2>
            {isLoading
              ? <p className="text-white/40 text-sm font-oxanium">Loading...</p>
              : (
                <div className="space-y-3">
                  <div className="flex justify-between py-3 border-b border-white/8">
                    <span className="text-sm font-oxanium text-white/70">Brand Knowledge</span>
                    <span className="text-sm font-oxanium text-brand-blue-light">
                      {data?.brand_knowledge?.length ?? 0} entries
                    </span>
                  </div>
                  <div className="flex justify-between py-3">
                    <span className="text-sm font-oxanium text-white/70">Agent Memory</span>
                    <span className="text-sm font-oxanium text-brand-blue-light">
                      {data?.agent_memory?.length ?? 0} entries
                    </span>
                  </div>
                </div>
              )
            }
          </GlassCard>
        </div>
      </div>
    </main>
  )
}
