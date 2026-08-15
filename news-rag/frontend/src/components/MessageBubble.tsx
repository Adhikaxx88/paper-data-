import ReactMarkdown from 'react-markdown'
import type { Message } from '../types'
import { SourceCard } from './SourceCard'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] ${isUser ? '' : 'w-full'}`}>
        <div
          className={
            isUser
              ? 'rounded-2xl bg-blue-600 px-4 py-2.5 text-white'
              : 'rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-gray-900'
          }
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-body text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.sources.map((source, idx) => (
              <SourceCard key={`${message.id}-source-${idx}`} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
