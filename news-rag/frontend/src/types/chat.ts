import type { SourceItem } from '../api/chat'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: SourceItem[]
  error?: string
}
