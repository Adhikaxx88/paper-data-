import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

const MAX_LENGTH = 500
const MAX_ROWS = 5
const LINE_HEIGHT_PX = 20
const VERTICAL_PADDING_PX = 16

interface ChatInputProps {
  onSubmit: (query: string) => void
  loading: boolean
}

export function ChatInput({ onSubmit, loading }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const maxHeight = LINE_HEIGHT_PX * MAX_ROWS + VERTICAL_PADDING_PX
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || loading) return
    onSubmit(trimmed)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div
      className="shrink-0 bg-[var(--bg-page)] px-6 py-4"
      style={{ borderTop: '1px solid var(--border-subtle)' }}
    >
      <div className="mx-auto" style={{ maxWidth: '680px', margin: '0 auto' }}>
        <div
          className="flex items-end gap-3 rounded-md bg-[var(--bg-content)] px-3 py-2"
          style={{ border: '1px solid var(--border)' }}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            maxLength={MAX_LENGTH}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Tanyakan sesuatu..."
            className="max-h-[116px] flex-1 resize-none bg-transparent py-1 text-sm text-neutral-900 outline-none placeholder:text-neutral-400 disabled:opacity-60 dark:text-neutral-100 dark:placeholder:text-neutral-600"
          />
          <button
            type="button"
            onClick={submit}
            disabled={loading || !value.trim()}
            aria-label="Send"
            className="shrink-0 pb-1 text-neutral-500 transition hover:text-neutral-900 disabled:cursor-not-allowed disabled:text-neutral-300 dark:text-neutral-400 dark:hover:text-white dark:disabled:text-neutral-700"
          >
            →
          </button>
        </div>
        <p className="mt-1.5 text-xs text-neutral-400 dark:text-neutral-600">
          Enter untuk kirim · Shift+Enter untuk baris baru
        </p>
      </div>
    </div>
  )
}
