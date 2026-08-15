import { useEffect, useState } from 'react'
import { getHistory, sendMessage as sendMessageApi } from '../api/chat'
import type { Message } from '../types'

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!sessionId) return

    let cancelled = false
    getHistory(sessionId)
      .then((history) => {
        if (!cancelled) setMessages(history)
      })
      .catch((err) => {
        console.error('Failed to load chat history', err)
      })

    return () => {
      cancelled = true
    }
  }, [sessionId])

  async function sendMessage(text: string) {
    if (!sessionId || !text.trim()) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const result = await sendMessageApi(sessionId, text)
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.answer,
        sources: result.sources,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Maaf, terjadi kesalahan saat menghubungi server. Silakan coba lagi.',
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
      console.error('Failed to send message', err)
    } finally {
      setIsLoading(false)
    }
  }

  return { messages, isLoading, sendMessage }
}
