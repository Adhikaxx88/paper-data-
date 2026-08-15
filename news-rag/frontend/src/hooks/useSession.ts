import { useEffect, useState } from 'react'
import { createSession } from '../api/chat'

const STORAGE_KEY = 'rag_session_id'

export function useSession() {
  const [sessionId, setSessionId] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY))
  const [isLoading, setIsLoading] = useState(sessionId === null)

  useEffect(() => {
    if (sessionId !== null) return

    let cancelled = false
    setIsLoading(true)
    createSession()
      .then((id) => {
        if (cancelled) return
        localStorage.setItem(STORAGE_KEY, id)
        setSessionId(id)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [sessionId])

  return { sessionId, isLoading }
}
