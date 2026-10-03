import { useEffect, useRef, useState } from 'react'
import { useChat } from './hooks/useChat'
import { ChatInput } from './components/ChatInput'
import { ChatMessage } from './components/ChatMessage'

const EXAMPLE_QUESTIONS = [
  'Apa dampak bullying pada remaja?',
  'Mental health trends in Indonesian youth',
  'Pengaruh media sosial terhadap kesehatan mental remaja',
]

function App() {
  const [dark, setDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  const { messages, loading, sendMessage } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const isEmpty = messages.length === 0

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = (query: string) => {
    void sendMessage(query)
  }

  return (
    <div className="flex h-screen flex-col bg-[var(--bg-page)] text-neutral-900 dark:text-neutral-100">
      <header
        className="px-6 py-4"
        style={{
          backgroundColor: 'var(--bg-page)',
          backgroundImage: 'linear-gradient(var(--header-overlay), var(--header-overlay))',
          borderBottom: '1px solid var(--header-border)',
        }}
      >
        <div className="mx-auto flex max-w-2xl items-baseline justify-between">
          <div>
            <h1 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              Child Development &amp; Youth Mental Health
            </h1>
            <p className="mt-0.5 text-xs text-neutral-500 dark:text-[#6e7681]">Indonesia · Research Database</p>
          </div>
          <button
            type="button"
            onClick={() => setDark((prev) => !prev)}
            style={{ opacity: 0.5, fontSize: '0.9rem' }}
            className="transition hover:opacity-100"
            aria-label="Toggle dark mode"
          >
            {dark ? '☀' : '🌙'}
          </button>
        </div>
      </header>

      <main
        className={`flex-1 overflow-y-auto px-6 ${isEmpty ? 'flex flex-col items-center justify-center' : 'py-10'}`}
      >
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-8">
          {isEmpty ? (
            <div className="flex w-full flex-col items-center gap-3" style={{ textAlign: 'center' }}>
              <p className="label-tiny text-neutral-500 dark:text-neutral-400">Research Database</p>
              <p className="text-base text-neutral-500 dark:text-[#8b949e]">
                Tanyakan sesuatu tentang kesehatan mental remaja Indonesia
              </p>
              <div
                className="mt-3 flex flex-wrap gap-2"
                style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}
              >
                {EXAMPLE_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => handleSubmit(question)}
                    style={{ borderColor: 'var(--border-strong)' }}
                    className="rounded-sm border px-3 py-1.5 text-xs text-neutral-500 transition hover:bg-[var(--hover-bg)] hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}

              {loading && (
                <div className="flex items-center gap-2 py-2">
                  <span className="loading-dot" style={{ animationDelay: '0s' }} />
                  <span className="loading-dot" style={{ animationDelay: '0.15s' }} />
                  <span className="loading-dot" style={{ animationDelay: '0.3s' }} />
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </main>

      <ChatInput onSubmit={handleSubmit} loading={loading} />
    </div>
  )
}

export default App
