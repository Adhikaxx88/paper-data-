import { useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Send } from 'lucide-react'

interface InputBarProps {
  onSend: (text: string) => void
  isLoading: boolean
}

export function InputBar({ onSend, isLoading }: InputBarProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function resize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 4
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }

  function handleSend() {
    const text = value.trim()
    if (!text || isLoading) return
    onSend(text)
    setValue('')
    requestAnimationFrame(resize)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed inset-x-0 bottom-0 border-t border-gray-200 bg-white">
      <div className="mx-auto flex max-w-2xl items-end gap-2 px-4 py-3">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            resize()
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ketik pertanyaan Anda..."
          rows={1}
          className="max-h-24 flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={isLoading || !value.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
