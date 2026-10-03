import { useState } from 'react'
import type { ChatMessage as ChatMessageType } from '../types/chat'

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false)

  if (message.role === 'user') {
    return (
      <div
        className="ml-auto max-w-[80%] text-sm text-neutral-900 dark:text-neutral-100"
        style={{ background: 'var(--bubble-bg)', borderRadius: '8px', padding: '12px 16px' }}
      >
        {message.content}
      </div>
    )
  }

  if (message.error) {
    return <p className="text-sm text-red-600 dark:text-red-400">{message.error}</p>
  }

  const rawSources = message.sources ?? []
  // Multiple chunks from the same article can appear in the retrieved
  // top-k — keep only the first (highest-ranked) chunk per article so it
  // doesn't show up more than once as a source card.
  const seenArticleIds = new Set<string>()
  const sources = rawSources.filter((s) => {
    // No article_id to key on — always show it rather than risk dropping
    // distinct sources that all look "the same" to the Set.
    if (!s.article_id) return true
    if (seenArticleIds.has(s.article_id)) return false
    seenArticleIds.add(s.article_id)
    return true
  })

  return (
    <div className="flex flex-col gap-3" style={{ borderLeft: '2px solid var(--accent-bar)', paddingLeft: '12px' }}>
      <p className="text-xs font-medium tracking-wide text-neutral-400 uppercase dark:text-neutral-600">
        Assistant
      </p>

      <p className="text-base leading-[1.7] text-neutral-800 dark:text-neutral-200">{message.content}</p>

      {sources.length > 0 && (
        <div className="mt-1">
          <button
            type="button"
            onClick={() => setSourcesOpen((prev) => !prev)}
            className="text-xs text-neutral-400 transition hover:text-neutral-700 dark:text-neutral-600 dark:hover:text-neutral-300"
          >
            {sourcesOpen ? 'Hide' : 'Show'} sources ({sources.length})
          </button>

          {sourcesOpen && (
            <div className="mt-3">
              <p className="label-tiny mb-2 text-neutral-500 dark:text-neutral-400">Sources</p>
              <ul className="flex flex-col gap-2">
                {sources.map((s, i) => (
                  <li key={i} className="flex flex-col text-sm">
                    {s.url ? (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-inherit text-neutral-700 hover:underline dark:text-neutral-300"
                      >
                        {s.title}
                      </a>
                    ) : (
                      <span className="text-neutral-700 dark:text-neutral-300">{s.title}</span>
                    )}
                    <span className="text-xs text-neutral-400 dark:text-neutral-600">
                      {s.date ? `${s.source} · ${s.date}` : s.source}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
