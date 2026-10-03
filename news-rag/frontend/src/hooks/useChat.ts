import { useCallback, useState } from 'react'
import { createSession, sendChatMessage } from '../api/chat'
import type { ChatMessage } from '../types/chat'

const SESSION_STORAGE_KEY = 'rag_session_id'

function readStoredSessionId(): string {
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function storeSessionId(sessionId: string): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId)
  } catch {
    // localStorage unavailable (private mode, etc.) — session just won't persist
  }
}

function makeId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(readStoredSessionId)

  const sendMessage = useCallback(
    async (query: string) => {
      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: 'user', content: query, timestamp: new Date().toISOString() },
      ])
      setLoading(true)

      try {
        // /api/chat requires a valid session UUID — create one on first send
        // (or if the stored id was never actually issued by the backend).
        let activeSessionId = sessionId
        if (!activeSessionId) {
          activeSessionId = await createSession()
          setSessionId(activeSessionId)
          storeSessionId(activeSessionId)
        }

        const response = await sendChatMessage(activeSessionId, query)

        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'assistant',
            content: response.answer,
            timestamp: new Date().toISOString(),
            sources: response.sources,
          },
        ])
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            error: e instanceof Error ? e.message : 'Terjadi kesalahan saat memproses pertanyaan.',
          },
        ])
      } finally {
        setLoading(false)
      }
    },
    [sessionId],
  )

  return { messages, loading, sessionId, sendMessage }
}
