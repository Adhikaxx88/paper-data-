import type { ChatResponse, Message } from '../types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function createSession(): Promise<string> {
  const response = await fetch(`${BASE}/api/session`, { method: 'POST' })
  const data = await handleResponse<{ session_id: string }>(response)
  return data.session_id
}

export async function sendMessage(session_id: string, message: string): Promise<ChatResponse> {
  const response = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id, message }),
  })
  return handleResponse<ChatResponse>(response)
}

export async function getHistory(session_id: string): Promise<Message[]> {
  const response = await fetch(`${BASE}/api/history/${session_id}`)
  const data = await handleResponse<{ messages: Message[] }>(response)
  return data.messages
}
