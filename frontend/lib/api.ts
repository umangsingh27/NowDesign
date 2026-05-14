const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function startSession(brief: object) {
  const res = await fetch(`${API}/api/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brief),
  })
  if (!res.ok) throw new Error(`Start session failed: ${res.status}`)
  return res.json()
}

export async function submitFeedback(sessionId: string, message: string) {
  const res = await fetch(`${API}/api/session/${sessionId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error(`Feedback failed: ${res.status}`)
  return res.json()
}

export async function approveSession(sessionId: string, rating: number) {
  const res = await fetch(`${API}/api/session/${sessionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_rating: rating }),
  })
  if (!res.ok) throw new Error(`Approve failed: ${res.status}`)
  return res.json()
}

export function createSSEConnection(
  sessionId: string,
  onEvent: (event: string, data: unknown) => void,
  onDone: () => void
): () => void {
  const url = `${API}/api/session/${sessionId}/stream`
  const source = new EventSource(url)

  const events = ['status_update', 'image_ready', 'state_change', 'error']
  events.forEach(eventType => {
    source.addEventListener(eventType, (e: MessageEvent) => {
      try {
        onEvent(eventType, JSON.parse(e.data))
      } catch {
        onEvent(eventType, e.data)
      }
    })
  })

  source.addEventListener('message', (e: MessageEvent) => {
    if (e.data === '' || e.data === 'done') { source.close(); onDone() }
  })

  source.onerror = () => { source.close(); onDone() }

  return () => source.close()
}

export async function fetchHistory(params?: {
  theme?: string; logo_type?: string; min_score?: number
}) {
  const qs = params ? '?' + new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v != null)
      .map(([k, v]) => [k, String(v)])
  ).toString() : ''
  const res = await fetch(`${API}/api/history${qs}`)
  return res.json()
}

export async function fetchKnowledge() {
  const res = await fetch(`${API}/api/knowledge`)
  return res.json()
}
