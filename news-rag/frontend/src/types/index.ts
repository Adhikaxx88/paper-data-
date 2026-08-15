export interface Source {
  title: string
  source: string
  date: string
  score: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  created_at: string
}

export interface ChatResponse {
  answer: string
  sources: Source[]
}
