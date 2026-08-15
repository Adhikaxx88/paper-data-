import { useEffect, useRef } from 'react'
import type { Message } from '../types'
import { MessageBubble } from './MessageBubble'
import { LoadingDots } from './LoadingDots'

interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full items-center justify-center px-4">
        <p className="text-center text-gray-400">Tanya sesuatu tentang berita terkini 💬</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-4 pb-32 pt-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isLoading && (
        <div className="flex justify-start">
          <div className="rounded-2xl border border-gray-200 bg-white">
            <LoadingDots />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
