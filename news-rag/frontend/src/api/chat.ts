const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface SourceItem {
  title: string
  source: string
  date: string
  score: number
  url?: string
  article_id: string
}

export interface ChatResponse {
  answer: string
  sources: SourceItem[]
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return body.detail ?? response.statusText
  } catch {
    return response.statusText
  }
}

export async function createSession(): Promise<string> {
  const response = await fetch(`${BASE}/api/session`, { method: 'POST' })
  if (!response.ok) throw new Error(await parseErrorDetail(response))
  const body = (await response.json()) as { session_id: string }
  return body.session_id
}

export async function sendChatMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const response = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  if (!response.ok) throw new Error(await parseErrorDetail(response))
  return response.json() as Promise<ChatResponse>
}
